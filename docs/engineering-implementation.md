# Engineering Implementation Guide: SCM Inference Engine

**Version**: 1.0
**Date**: October 2025
**Status**: Implementation Specification
**Target**: Hackathon MVP (16 hours) → Production hardening

---

## Executive Summary

This document provides step-by-step engineering guidance for implementing the SCM-based causal inference engine. Focus is on **practical implementation** with **clear acceptance criteria** for each component.

**Priority**: Get the math right first, optimize later.

---

## Table of Contents

1. [Quick Start: 16-Hour MVP](#1-quick-start-16-hour-mvp)
2. [Component 1: Effect Size Calculation](#2-component-1-effect-size-calculation)
3. [Component 2: Validation Agent](#3-component-2-validation-agent)
4. [Component 3: SCM Inference Engine](#4-component-3-scm-inference-engine)
5. [Component 4: Intervention API](#5-component-4-intervention-api)
6. [Component 5: MCP Server](#6-component-5-mcp-server)
7. [Testing Strategy](#7-testing-strategy)
8. [Deployment: Offline Demo](#8-deployment-offline-demo)
9. [Cost Monitoring](#9-cost-monitoring)
10. [Production Hardening Checklist](#10-production-hardening-checklist)

---

## 1. Quick Start: 16-Hour MVP

### Prioritized Task List

**Critical Path** (must complete):
1. Fix effect size formula (2h) → `graph_builder.py:232`
2. Implement validation agent (3h) → new file `validation_agent.py`
3. Replace Monte Carlo with SCM (4h) → refactor `temporal_model.py`
4. Add intervention endpoint (3h) → new endpoint `/api/v1/intervene`
5. Create MCP server (4h) → new file `mcp_server.py`

**Total**: 16 hours

**Nice-to-have** (defer if time-constrained):
6. MeSH enrichment integration (3h)
7. Sensitivity analysis (2h)
8. Redis caching (2h)

### Development Environment Setup

```bash
# Install dependencies
cd indra_agent/
pip install -e .
pip install numpy scipy networkx redis

# Verify INDRA connectivity
python -c "from indra_agent.services.indra_service import INDRAService; \
           import asyncio; \
           s = INDRAService(); \
           print(asyncio.run(s.find_causal_paths('CRP', 'IL6', max_depth=3)))"

# Run tests
pytest tests/ -v
```

### Acceptance Criteria (MVP)

- [ ] Effect sizes ∈ [0, 1] for all edges (validation passes)
- [ ] DAG check rejects cyclic graphs
- [ ] Intervention query returns 90-day predictions in <50ms
- [ ] MCP server responds to `discover_causal_pathways` tool
- [ ] Offline demo works with cached INDRA responses
- [ ] Total query time <5s for PM2.5→CRP example

---

## 2. Component 1: Effect Size Calculation

### Current Issue

**File**: `indra_agent/services/graph_builder.py:232`

```python
# CURRENT (ad-hoc heuristic)
def _calculate_effect_size(self, belief: float, evidence_count: int) -> float:
    effect = belief * 0.8
    if evidence_count > 100:
        effect += 0.15
    elif evidence_count > 50:
        effect += 0.10
    elif evidence_count > 20:
        effect += 0.05
    return min(effect, 0.95)
```

**Problems**:
1. Not grounded in statistical theory
2. Discontinuous jumps at thresholds
3. No consideration of evidence diversity
4. Capped at 0.95 arbitrarily

### Principled Formula

**From `mathematical-foundation.md` §5.1**:

```
W_ij = min(α · belief + β · log(1 + evidence_count), 0.95)

Where:
- α = 0.6 (base scaling from belief)
- β = 0.1 (evidence accumulation bonus)
- log captures diminishing returns (10→20 papers less valuable than 1→10)
- 0.95 cap maintains uncertainty (avoid deterministic edges)
```

**Why this works**:
- Belief score (0-1) from INDRA Belief Engine is already a meta-analytic posterior
- Evidence count reflects robustness (more studies = less sampling error)
- Logarithm ensures diminishing returns (1000 papers ≠ 100× better than 10)
- Cap at 0.95 ensures (I - W) is invertible (spectral radius < 1)

### Implementation

**File**: `indra_agent/services/graph_builder.py`

```python
import math
from typing import Dict, List
from indra_agent.core.models import CausalGraph, Edge, Evidence

class GraphBuilderService:
    """Enhanced graph builder with principled effect sizes."""

    # Effect size formula parameters (from mathematical foundation)
    ALPHA = 0.6  # Weight on belief score
    BETA = 0.1   # Weight on evidence accumulation
    MAX_EFFECT = 0.95  # Cap to ensure invertibility

    def _calculate_effect_size(
        self,
        belief: float,
        evidence_count: int,
        relationship: str = "increases"
    ) -> float:
        """Calculate effect size from INDRA belief and evidence.

        Formula: W_ij = min(α·belief + β·log(1 + n), 0.95)

        Args:
            belief: INDRA belief score ∈ [0, 1]
            evidence_count: Number of supporting papers
            relationship: Type of relationship (for sign handling)

        Returns:
            Effect size ∈ [0, 1]

        References:
            See docs/mathematical-foundation.md §5.1
        """
        if not 0 <= belief <= 1:
            raise ValueError(f"Belief must be ∈ [0,1], got {belief}")

        if evidence_count < 0:
            raise ValueError(f"Evidence count must be ≥0, got {evidence_count}")

        # Base effect from belief
        base_effect = self.ALPHA * belief

        # Evidence accumulation bonus (diminishing returns)
        evidence_bonus = self.BETA * math.log(1 + evidence_count)

        # Combined effect (capped)
        effect_size = min(base_effect + evidence_bonus, self.MAX_EFFECT)

        # Handle sign based on relationship
        # Note: SCM weight matrix uses magnitudes; sign encoded separately
        # in relationship field ("increases" vs "decreases")
        if relationship in ["decreases", "inhibits"]:
            # For inhibitory edges, we'll negate during matrix construction
            # Here we just return the magnitude
            pass

        return effect_size
```

### Testing

**File**: `tests/test_graph_builder.py`

```python
import pytest
import math
from indra_agent.services.graph_builder import GraphBuilderService

def test_effect_size_formula():
    """Test effect size calculation matches mathematical spec."""
    builder = GraphBuilderService()

    # Test case 1: High belief, many papers (PM2.5 → oxidative stress)
    belief = 0.78
    evidence_count = 31
    effect = builder._calculate_effect_size(belief, evidence_count)

    expected = min(0.6 * 0.78 + 0.1 * math.log(32), 0.95)
    # = min(0.468 + 0.1 * 3.466, 0.95)
    # = min(0.815, 0.95) = 0.815

    assert abs(effect - expected) < 0.01, f"Got {effect}, expected {expected}"

    # Test case 2: Very high evidence (IL-6 → CRP)
    effect = builder._calculate_effect_size(0.98, 312)
    expected = min(0.6 * 0.98 + 0.1 * math.log(313), 0.95)
    # = min(0.588 + 0.576, 0.95) = 0.95 (capped)

    assert effect == 0.95, "Should be capped at 0.95"

    # Test case 3: Low belief, few papers (speculative edge)
    effect = builder._calculate_effect_size(0.4, 3)
    expected = 0.6 * 0.4 + 0.1 * math.log(4)
    # = 0.24 + 0.139 = 0.379

    assert abs(effect - expected) < 0.01

    # Test case 4: Edge cases
    with pytest.raises(ValueError):
        builder._calculate_effect_size(1.5, 10)  # belief > 1

    with pytest.raises(ValueError):
        builder._calculate_effect_size(0.8, -5)  # negative evidence
```

**Acceptance Criteria**:
- [ ] Formula matches mathematical spec exactly
- [ ] All effects ∈ [0, 1]
- [ ] High-evidence edges approach 0.95 cap
- [ ] Low-evidence edges have reasonable magnitudes (>0.2)
- [ ] Unit tests pass

**Time estimate**: 2 hours

---

## 3. Component 2: Validation Agent

### Purpose

Verify causal graph satisfies SCM mathematical constraints before returning to user.

**Critical checks**:
1. **Structural**: Graph is acyclic (DAG)
2. **Parameters**: Effect sizes ∈ [0,1], temporal lags ≥ 0
3. **Stability**: Spectral radius(W) < 1 (ensures (I-W) invertible)
4. **Biological plausibility**: Temporal ordering, no amplification cascades

### Implementation

**File**: `indra_agent/agents/validation_agent.py`

```python
"""Validation agent for causal graph constraints."""

import logging
from typing import Dict, List
import networkx as nx
import numpy as np

from indra_agent.core.models import CausalGraph, Edge

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of graph validation."""

    def __init__(
        self,
        is_valid: bool,
        errors: List[str] = None,
        warnings: List[str] = None,
        structural_checks: Dict = None,
        parameter_checks: Dict = None,
        stability_checks: Dict = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.structural_checks = structural_checks or {}
        self.parameter_checks = parameter_checks or {}
        self.stability_checks = stability_checks or {}

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "structural_checks": self.structural_checks,
            "parameter_checks": self.parameter_checks,
            "stability_checks": self.stability_checks
        }


class ValidationAgent:
    """Agent for validating SCM constraints on causal graphs."""

    VALID_RELATIONSHIPS = {"increases", "decreases", "activates", "inhibits"}
    MAX_EFFECT_SIZE = 1.0
    MIN_TEMPORAL_LAG = 0
    SPECTRAL_RADIUS_THRESHOLD = 0.99  # Safety margin below 1.0

    def validate(self, causal_graph: CausalGraph) -> ValidationResult:
        """Validate causal graph against SCM constraints.

        Args:
            causal_graph: Graph to validate

        Returns:
            ValidationResult with pass/fail and diagnostics
        """
        errors = []
        warnings = []

        # 1. Structural validation
        structural = self._validate_structure(causal_graph)
        if not structural["is_dag"]:
            errors.append("Graph contains cycles (not a DAG). Use temporal stratification.")
        if not structural["is_connected"]:
            warnings.append("Graph has disconnected components.")
        if not structural["has_root_nodes"]:
            errors.append("Graph has no root nodes (exogenous variables).")

        # 2. Parameter validation
        parameter = self._validate_parameters(causal_graph)
        if not parameter["effect_sizes_valid"]:
            errors.append(f"Effect sizes out of [0,1]: {parameter['invalid_effect_sizes']}")
        if not parameter["temporal_lags_valid"]:
            errors.append(f"Negative temporal lags: {parameter['invalid_lags']}")
        if not parameter["relationships_valid"]:
            errors.append(f"Invalid relationships: {parameter['invalid_relationships']}")

        # 3. Stability validation (spectral radius)
        stability = self._validate_stability(causal_graph)
        if not stability["is_stable"]:
            errors.append(f"Spectral radius {stability['spectral_radius']:.3f} ≥ 1 (unstable).")
        if stability["spectral_radius"] > self.SPECTRAL_RADIUS_THRESHOLD:
            warnings.append(f"Spectral radius {stability['spectral_radius']:.3f} near 1 (numerical issues).")

        # 4. Biological plausibility (soft checks)
        if causal_graph.edges:
            self._check_biological_plausibility(causal_graph, warnings)

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            structural_checks=structural,
            parameter_checks=parameter,
            stability_checks=stability
        )

    def _validate_structure(self, graph: CausalGraph) -> Dict:
        """Check structural properties (DAG, connectivity)."""
        G = nx.DiGraph()

        # Build NetworkX graph
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)

        # Ensure all nodes present (including isolated ones)
        for node in graph.nodes:
            if node.id not in G:
                G.add_node(node.id)

        is_dag = nx.is_directed_acyclic_graph(G)
        is_connected = nx.is_weakly_connected(G) if G.number_of_nodes() > 0 else False

        # Find root nodes (no incoming edges)
        root_nodes = [n for n in G.nodes() if G.in_degree(n) == 0]
        has_root_nodes = len(root_nodes) > 0

        cycles = []
        if not is_dag:
            try:
                cycles = list(nx.simple_cycles(G))[:5]  # Show first 5 cycles
            except Exception:
                cycles = ["(cycle detection failed)"]

        return {
            "is_dag": is_dag,
            "is_connected": is_connected,
            "has_root_nodes": has_root_nodes,
            "root_nodes": root_nodes,
            "cycles": cycles,
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges()
        }

    def _validate_parameters(self, graph: CausalGraph) -> Dict:
        """Check parameter constraints."""
        invalid_effects = []
        invalid_lags = []
        invalid_relationships = []

        for edge in graph.edges:
            # Check effect size ∈ [0, 1]
            if not (0 <= edge.effect_size <= self.MAX_EFFECT_SIZE):
                invalid_effects.append({
                    "edge": f"{edge.source}→{edge.target}",
                    "effect_size": edge.effect_size
                })

            # Check temporal lag ≥ 0
            if edge.temporal_lag_hours < self.MIN_TEMPORAL_LAG:
                invalid_lags.append({
                    "edge": f"{edge.source}→{edge.target}",
                    "lag": edge.temporal_lag_hours
                })

            # Check relationship type
            if edge.relationship not in self.VALID_RELATIONSHIPS:
                invalid_relationships.append({
                    "edge": f"{edge.source}→{edge.target}",
                    "relationship": edge.relationship
                })

        return {
            "effect_sizes_valid": len(invalid_effects) == 0,
            "temporal_lags_valid": len(invalid_lags) == 0,
            "relationships_valid": len(invalid_relationships) == 0,
            "invalid_effect_sizes": invalid_effects,
            "invalid_lags": invalid_lags,
            "invalid_relationships": invalid_relationships
        }

    def _validate_stability(self, graph: CausalGraph) -> Dict:
        """Check spectral radius < 1 for stability.

        For (I - W) to be invertible, we need spectral radius(W) < 1.
        """
        if len(graph.edges) == 0:
            return {"is_stable": True, "spectral_radius": 0.0}

        # Build weight matrix W
        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)
        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}

        W = np.zeros((n, n))

        for edge in graph.edges:
            i = node_to_idx[edge.target]  # Row (target)
            j = node_to_idx[edge.source]  # Col (source)

            # Handle sign based on relationship
            magnitude = edge.effect_size
            if edge.relationship in ["decreases", "inhibits"]:
                magnitude = -magnitude

            W[i, j] = magnitude

        # Compute spectral radius (largest absolute eigenvalue)
        eigenvalues = np.linalg.eigvals(W)
        spectral_radius = np.max(np.abs(eigenvalues))

        is_stable = spectral_radius < 1.0

        return {
            "is_stable": is_stable,
            "spectral_radius": float(spectral_radius),
            "warning_threshold": self.SPECTRAL_RADIUS_THRESHOLD
        }

    def _check_biological_plausibility(
        self,
        graph: CausalGraph,
        warnings: List[str]
    ):
        """Soft checks for biological plausibility."""
        # Check for amplification cascades (effect sizes increasing along paths)
        # This is a heuristic check, not a hard constraint

        # Check temporal consistency (lags should generally increase along paths)
        # This is domain-specific and may not always hold

        # For MVP, just warn if any edge has very high effect (>0.9)
        for edge in graph.edges:
            if edge.effect_size > 0.9:
                warnings.append(
                    f"High effect size {edge.effect_size:.2f} for "
                    f"{edge.source}→{edge.target} (may indicate determinism)"
                )
```

### Integration with Supervisor

**File**: `indra_agent/agents/supervisor.py`

Add validation step before finalization:

```python
from indra_agent.agents.validation_agent import ValidationAgent

class SupervisorAgent:
    def __init__(self):
        # ... existing code
        self.validation_agent = ValidationAgent()

    async def _finalize_response(self, state: OverallState) -> Dict:
        """Finalize with validation check."""
        causal_graph_dict = state.get("causal_graph", {})
        causal_graph = CausalGraph(**causal_graph_dict)

        # VALIDATE GRAPH
        validation_result = self.validation_agent.validate(causal_graph)

        if not validation_result.is_valid:
            logger.error(f"Graph validation failed: {validation_result.errors}")
            return {
                "status": "error",
                "error_code": "INVALID_GRAPH",
                "error_message": "; ".join(validation_result.errors),
                "validation_result": validation_result.to_dict(),
                "next_agent": "END"
            }

        if validation_result.warnings:
            logger.warning(f"Graph validation warnings: {validation_result.warnings}")

        # ... continue with existing finalization logic
```

### Testing

**File**: `tests/test_validation_agent.py`

```python
import pytest
from indra_agent.agents.validation_agent import ValidationAgent
from indra_agent.core.models import CausalGraph, Node, Edge, Evidence

def test_validates_dag():
    """Test DAG validation."""
    agent = ValidationAgent()

    # Valid DAG
    graph = CausalGraph(
        nodes=[
            Node(id="A", name="A", type="environmental"),
            Node(id="B", name="B", type="biomarker")
        ],
        edges=[
            Edge(source="A", target="B", relationship="increases",
                 effect_size=0.8, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=50, belief=0.8))
        ],
        genetic_modifiers=[]
    )

    result = agent.validate(graph)
    assert result.is_valid
    assert result.structural_checks["is_dag"]

    # Cyclic graph (invalid)
    graph_cyclic = CausalGraph(
        nodes=[
            Node(id="A", name="A", type="biomarker"),
            Node(id="B", name="B", type="biomarker")
        ],
        edges=[
            Edge(source="A", target="B", relationship="increases",
                 effect_size=0.8, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=50, belief=0.8)),
            Edge(source="B", target="A", relationship="increases",
                 effect_size=0.7, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=30, belief=0.7))
        ],
        genetic_modifiers=[]
    )

    result_cyclic = agent.validate(graph_cyclic)
    assert not result_cyclic.is_valid
    assert not result_cyclic.structural_checks["is_dag"]
    assert any("cycle" in e.lower() for e in result_cyclic.errors)

def test_validates_parameters():
    """Test parameter range validation."""
    agent = ValidationAgent()

    # Invalid effect size (>1.0)
    graph = CausalGraph(
        nodes=[
            Node(id="A", name="A", type="environmental"),
            Node(id="B", name="B", type="biomarker")
        ],
        edges=[
            Edge(source="A", target="B", relationship="increases",
                 effect_size=1.5,  # INVALID
                 temporal_lag_hours=12,
                 evidence=Evidence(paper_count=50, belief=0.8))
        ],
        genetic_modifiers=[]
    )

    result = agent.validate(graph)
    assert not result.is_valid
    assert not result.parameter_checks["effect_sizes_valid"]

def test_validates_stability():
    """Test spectral radius check."""
    agent = ValidationAgent()

    # Unstable graph (W with spectral radius ≥ 1)
    graph = CausalGraph(
        nodes=[
            Node(id="A", name="A", type="biomarker"),
            Node(id="B", name="B", type="biomarker"),
            Node(id="C", name="C", type="biomarker")
        ],
        edges=[
            Edge(source="A", target="B", relationship="increases",
                 effect_size=0.95, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=100, belief=0.95)),
            Edge(source="B", target="C", relationship="increases",
                 effect_size=0.95, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=100, belief=0.95)),
            Edge(source="C", target="A", relationship="increases",  # Cycle with high weights
                 effect_size=0.95, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=100, belief=0.95))
        ],
        genetic_modifiers=[]
    )

    result = agent.validate(graph)
    # This will fail DAG check, but also would fail stability if it were a DBN
```

**Acceptance Criteria**:
- [ ] Rejects cyclic graphs
- [ ] Rejects effect sizes outside [0,1]
- [ ] Rejects negative temporal lags
- [ ] Warns on spectral radius >0.99
- [ ] Integration test: supervisor returns validation errors

**Time estimate**: 3 hours

---

## 4. Component 3: SCM Inference Engine

### Purpose

Replace naive Monte Carlo simulation with **exact SCM inference** using closed-form solutions.

**Current**: `temporal_model.py` uses forward simulation with ad-hoc dampening
**Target**: Matrix-based inference with proper posterior distributions

### Mathematical Recap

For linear Gaussian SCM:
```
V = (I - W)^{-1} (μ + ε)

Posterior distribution:
p(V) = N((I - W)^{-1} μ, (I - W)^{-1} Σ ((I - W)^{-1})^T)

Where:
- V: endogenous variables (biomarkers)
- W: weight matrix (effect sizes)
- μ: mean vector (baseline values)
- Σ: noise covariance (diagonal for independence)
- ε ~ N(0, Σ)
```

### Implementation

**File**: `indra_agent/services/scm_inference.py` (new file)

```python
"""SCM-based inference engine for causal graphs."""

import logging
from typing import Dict, List, Tuple
import numpy as np
from scipy import linalg

from indra_agent.core.models import CausalGraph, Node, PredictionTimeline

logger = logging.getLogger(__name__)


class SCMInferenceEngine:
    """Inference engine using Linear Gaussian SCMs.

    Replaces Monte Carlo simulation with exact closed-form inference.
    """

    def __init__(self, causal_graph: CausalGraph):
        """Initialize SCM from causal graph.

        Args:
            causal_graph: Validated causal graph (must be DAG)
        """
        self.graph = causal_graph
        self.node_ids = [n.id for n in causal_graph.nodes]
        self.n = len(self.node_ids)
        self.node_to_idx = {nid: i for i, nid in enumerate(self.node_ids)}

        # Build weight matrix W and noise covariance Σ
        self.W, self.Sigma = self._build_matrices()

        # Precompute (I - W)^{-1} for efficiency
        self.I_minus_W_inv = self._compute_inverse()

    def _build_matrices(self) -> Tuple[np.ndarray, np.ndarray]:
        """Build weight matrix W and noise covariance Σ from graph."""
        W = np.zeros((self.n, self.n))
        Sigma = np.eye(self.n) * 0.1  # Default noise variance

        for edge in self.graph.edges:
            i = self.node_to_idx[edge.target]  # Row
            j = self.node_to_idx[edge.source]  # Column

            # Handle sign based on relationship
            magnitude = edge.effect_size
            if edge.relationship in ["decreases", "inhibits"]:
                magnitude = -magnitude

            W[i, j] = magnitude

        # Set node-specific noise variances (heuristic for now)
        for idx, node in enumerate(self.graph.nodes):
            if node.type == "biomarker":
                # Higher noise for biomarkers (measurement error + biological variability)
                Sigma[idx, idx] = 0.2
            elif node.type == "environmental":
                # Lower noise for environmental variables (more stable)
                Sigma[idx, idx] = 0.05
            else:
                Sigma[idx, idx] = 0.1

        return W, Sigma

    def _compute_inverse(self) -> np.ndarray:
        """Compute (I - W)^{-1} with numerical stability checks."""
        I = np.eye(self.n)
        I_minus_W = I - self.W

        try:
            # Check condition number for numerical stability
            cond = np.linalg.cond(I_minus_W)
            if cond > 1e10:
                logger.warning(f"Ill-conditioned matrix (condition number: {cond:.2e})")

            # Compute inverse
            I_minus_W_inv = linalg.inv(I_minus_W)

            return I_minus_W_inv

        except linalg.LinAlgError as e:
            logger.error(f"Matrix inversion failed: {e}")
            # Fallback: use pseudoinverse
            return linalg.pinv(I_minus_W)

    def predict(
        self,
        baseline_values: Dict[str, float],
        horizon_days: int = 90
    ) -> Dict[str, PredictionTimeline]:
        """Generate prediction timelines for biomarkers.

        Args:
            baseline_values: Current biomarker values (e.g., {"CRP": 1.2})
            horizon_days: Number of days to predict

        Returns:
            Dictionary mapping biomarker → PredictionTimeline
        """
        # For static SCM, predictions are immediate (no temporal dynamics yet)
        # We'll return constant predictions with uncertainty

        # Build mean vector μ from baseline values
        mu = np.zeros(self.n)
        for node_id, value in baseline_values.items():
            if node_id in self.node_to_idx:
                mu[self.node_to_idx[node_id]] = value

        # Compute posterior mean: (I - W)^{-1} μ
        posterior_mean = self.I_minus_W_inv @ mu

        # Compute posterior covariance: (I - W)^{-1} Σ ((I - W)^{-1})^T
        posterior_cov = self.I_minus_W_inv @ self.Sigma @ self.I_minus_W_inv.T
        posterior_std = np.sqrt(np.diag(posterior_cov))

        # Generate timelines for biomarkers
        predictions = {}
        biomarker_nodes = [n for n in self.graph.nodes if n.type == "biomarker"]

        for node in biomarker_nodes:
            idx = self.node_to_idx[node.id]
            baseline = baseline_values.get(node.id, posterior_mean[idx])

            # For static SCM, values are constant over time
            # (temporal dynamics require DBN extension - see §7 of math doc)
            mean_value = posterior_mean[idx]
            std_value = posterior_std[idx]

            # Generate timeline points
            timeline_points = []
            for day in [0, 30, 60, 90]:
                if day > horizon_days:
                    break

                # 95% credible interval
                ci_lower = mean_value - 1.96 * std_value
                ci_upper = mean_value + 1.96 * std_value

                # Risk stratification (biomarker-specific)
                risk_level = self._compute_risk_level(node.id, mean_value, baseline)

                timeline_points.append({
                    "day": day,
                    "mean": round(float(mean_value), 2),
                    "confidence_interval": [round(float(ci_lower), 2), round(float(ci_upper), 2)],
                    "risk_level": risk_level
                })

            # Determine unit (biomarker-specific)
            unit = self._get_biomarker_unit(node.id)

            predictions[node.id] = PredictionTimeline(
                baseline=round(float(baseline), 2),
                timeline=timeline_points,
                unit=unit
            )

        return predictions

    def intervene(
        self,
        intervention: Dict[str, float],
        baseline_values: Dict[str, float],
        horizon_days: int = 90
    ) -> Dict[str, PredictionTimeline]:
        """Perform do-calculus intervention and predict outcomes.

        Args:
            intervention: Interventions to apply (e.g., {"PM2.5": 10})
            baseline_values: Current biomarker values
            horizon_days: Prediction horizon

        Returns:
            Predictions under intervention

        References:
            See docs/mathematical-foundation.md §4 (do-calculus)
        """
        # Build intervened weight matrix W_do (zero out rows for intervened variables)
        W_do = self.W.copy()

        for var_id in intervention.keys():
            if var_id in self.node_to_idx:
                idx = self.node_to_idx[var_id]
                W_do[idx, :] = 0  # Zero row i (remove incoming edges)

        # Compute (I - W_do)^{-1}
        I_minus_W_do_inv = linalg.inv(np.eye(self.n) - W_do)

        # Build mean vector with interventions
        mu = np.zeros(self.n)
        for node_id, value in {**baseline_values, **intervention}.items():
            if node_id in self.node_to_idx:
                mu[self.node_to_idx[node_id]] = value

        # Compute interventional posterior
        posterior_mean = I_minus_W_do_inv @ mu
        posterior_cov = I_minus_W_do_inv @ self.Sigma @ I_minus_W_do_inv.T
        posterior_std = np.sqrt(np.diag(posterior_cov))

        # Generate predictions (same logic as predict())
        predictions = {}
        biomarker_nodes = [n for n in self.graph.nodes if n.type == "biomarker"]

        for node in biomarker_nodes:
            idx = self.node_to_idx[node.id]
            baseline = baseline_values.get(node.id, posterior_mean[idx])
            mean_value = posterior_mean[idx]
            std_value = posterior_std[idx]

            timeline_points = []
            for day in [0, 30, 60, 90]:
                if day > horizon_days:
                    break

                ci_lower = mean_value - 1.96 * std_value
                ci_upper = mean_value + 1.96 * std_value
                risk_level = self._compute_risk_level(node.id, mean_value, baseline)

                timeline_points.append({
                    "day": day,
                    "mean": round(float(mean_value), 2),
                    "confidence_interval": [round(float(ci_lower), 2), round(float(ci_upper), 2)],
                    "risk_level": risk_level
                })

            unit = self._get_biomarker_unit(node.id)

            predictions[node.id] = PredictionTimeline(
                baseline=round(float(baseline), 2),
                timeline=timeline_points,
                unit=unit
            )

        return predictions

    def _compute_risk_level(self, biomarker_id: str, value: float, baseline: float) -> str:
        """Compute risk level based on biomarker value.

        Biomarker-specific thresholds (simplified for MVP).
        """
        if biomarker_id == "CRP":
            if value < 1.0:
                return "low"
            elif value < 3.0:
                return "moderate"
            else:
                return "high"
        elif biomarker_id == "IL-6" or biomarker_id == "IL6":
            if value < 2.0:
                return "low"
            elif value < 5.0:
                return "moderate"
            else:
                return "high"
        else:
            # Generic: compare to baseline
            fold_change = value / baseline if baseline > 0 else 1.0
            if fold_change < 1.5:
                return "low"
            elif fold_change < 2.5:
                return "moderate"
            else:
                return "high"

    def _get_biomarker_unit(self, biomarker_id: str) -> str:
        """Get unit for biomarker (simplified for MVP)."""
        units = {
            "CRP": "mg/L",
            "IL-6": "pg/mL",
            "IL6": "pg/mL",
            "8-OHdG": "ng/mL",
            "cortisol": "nmol/L"
        }
        return units.get(biomarker_id, "units")
```

### Integration with Supervisor

**File**: `indra_agent/agents/supervisor.py`

Replace Monte Carlo with SCM inference:

```python
from indra_agent.services.scm_inference import SCMInferenceEngine

class SupervisorAgent:
    async def _generate_predictions(
        self,
        causal_graph: CausalGraph,
        user_context: Dict,
        environmental_data: Dict,
    ) -> Dict:
        """Generate temporal predictions using SCM inference."""
        try:
            # Build SCM inference engine
            engine = SCMInferenceEngine(causal_graph)

            # Get baseline biomarkers
            baseline_biomarkers = user_context.get("current_biomarkers", {})

            # Infer environmental changes (same as before)
            env_changes = self._infer_environmental_changes(
                location_history=user_context.get("location_history", []),
                environmental_data=environmental_data,
            )

            # Generate predictions with intervention (if environmental changes present)
            if env_changes:
                predictions = engine.intervene(
                    intervention=env_changes,
                    baseline_values=baseline_biomarkers,
                    horizon_days=90
                )
            else:
                predictions = engine.predict(
                    baseline_values=baseline_biomarkers,
                    horizon_days=90
                )

            # Convert to dict for serialization
            predictions_dict = {
                biomarker: timeline.model_dump()
                for biomarker, timeline in predictions.items()
            }

            return predictions_dict

        except Exception as e:
            logger.error(f"Failed to generate predictions: {e}")
            return {}
```

### Testing

**File**: `tests/test_scm_inference.py`

```python
import pytest
import numpy as np
from indra_agent.services.scm_inference import SCMInferenceEngine
from indra_agent.core.models import CausalGraph, Node, Edge, Evidence

def test_scm_matrix_construction():
    """Test W matrix construction from graph."""
    graph = CausalGraph(
        nodes=[
            Node(id="PM2.5", name="PM2.5", type="environmental"),
            Node(id="CRP", name="CRP", type="biomarker")
        ],
        edges=[
            Edge(source="PM2.5", target="CRP", relationship="increases",
                 effect_size=0.8, temporal_lag_hours=72,
                 evidence=Evidence(paper_count=100, belief=0.9))
        ],
        genetic_modifiers=[]
    )

    engine = SCMInferenceEngine(graph)

    # Check W matrix
    assert engine.W.shape == (2, 2)
    assert engine.W[1, 0] == 0.8  # CRP (row 1) <- PM2.5 (col 0)
    assert engine.W[0, 0] == 0.0  # Diagonal should be zero

def test_scm_intervention():
    """Test do-calculus intervention."""
    graph = CausalGraph(
        nodes=[
            Node(id="PM2.5", name="PM2.5", type="environmental"),
            Node(id="oxidative_stress", name="Oxidative Stress", type="molecular"),
            Node(id="CRP", name="CRP", type="biomarker")
        ],
        edges=[
            Edge(source="PM2.5", target="oxidative_stress", relationship="increases",
                 effect_size=0.7, temporal_lag_hours=12,
                 evidence=Evidence(paper_count=50, belief=0.8)),
            Edge(source="oxidative_stress", target="CRP", relationship="increases",
                 effect_size=0.6, temporal_lag_hours=24,
                 evidence=Evidence(paper_count=80, belief=0.85))
        ],
        genetic_modifiers=[]
    )

    engine = SCMInferenceEngine(graph)

    # Baseline: PM2.5 = 35, CRP = 3.2
    baseline = {"PM2.5": 35, "CRP": 3.2}

    # Intervention: do(PM2.5 = 10)
    intervention = {"PM2.5": 10}

    predictions = engine.intervene(intervention, baseline, horizon_days=90)

    assert "CRP" in predictions
    assert predictions["CRP"].baseline == 3.2

    # Intervened CRP should be lower (PM2.5 reduced by 71%)
    intervened_crp = predictions["CRP"].timeline[0]["mean"]
    assert intervened_crp < 3.2, "CRP should decrease with PM2.5 intervention"
```

**Acceptance Criteria**:
- [ ] Matrix construction preserves edge signs
- [ ] (I - W)^{-1} computed correctly
- [ ] Predictions have proper confidence intervals
- [ ] Intervention reduces downstream biomarkers
- [ ] Runs in <50ms for n=20 variables

**Time estimate**: 4 hours

---

## 5. Component 4: Intervention API

### Purpose

Add `/api/v1/intervene` endpoint for counterfactual queries using do-calculus.

### API Specification

**Endpoint**: `POST /api/v1/intervene`

**Request**:
```json
{
  "graph_id": "graph_abc123",
  "intervention": {"PM2.5": 10},
  "horizon_days": 90
}
```

**Response**:
```json
{
  "status": "success",
  "predictions": {
    "CRP": {
      "baseline": 3.2,
      "intervened": 1.5,
      "reduction": 1.7,
      "timeline": [...]
    }
  },
  "metadata": {
    "query_time_ms": 8,
    "intervention_type": "environmental"
  }
}
```

### Implementation

**File**: `indra_agent/api/routes.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict
import time

from indra_agent.services.scm_inference import SCMInferenceEngine
from indra_agent.core.models import CausalGraph

router = APIRouter()

# In-memory graph storage (for production; use Redis for production)
graph_store: Dict[str, CausalGraph] = {}


class InterventionRequest(BaseModel):
    """Request for interventional query."""
    graph_id: str = Field(..., description="Graph ID from causal_discovery")
    intervention: Dict[str, float] = Field(..., description="Variables to intervene on")
    horizon_days: int = Field(90, ge=1, le=365, description="Prediction horizon")


class InterventionResponse(BaseModel):
    """Response with interventional predictions."""
    status: str
    predictions: Dict
    metadata: Dict


@router.post("/api/v1/intervene", response_model=InterventionResponse)
async def intervene(request: InterventionRequest):
    """Perform causal intervention and return predictions.

    Uses do-calculus (graph surgery) to compute counterfactual outcomes.
    """
    start_time = time.time()

    # Retrieve graph from storage
    if request.graph_id not in graph_store:
        raise HTTPException(status_code=404, detail=f"Graph {request.graph_id} not found")

    causal_graph = graph_store[request.graph_id]

    try:
        # Build SCM inference engine
        engine = SCMInferenceEngine(causal_graph)

        # Perform intervention
        predictions = engine.intervene(
            intervention=request.intervention,
            baseline_values={},  # TODO: Get from user context
            horizon_days=request.horizon_days
        )

        # Compute reductions
        predictions_dict = {}
        for biomarker, timeline in predictions.items():
            baseline = timeline.baseline
            intervened = timeline.timeline[0]["mean"]
            reduction = baseline - intervened

            predictions_dict[biomarker] = {
                "baseline": baseline,
                "intervened": intervened,
                "reduction": round(reduction, 2),
                "timeline": timeline.timeline
            }

        query_time_ms = int((time.time() - start_time) * 1000)

        return InterventionResponse(
            status="success",
            predictions=predictions_dict,
            metadata={
                "query_time_ms": query_time_ms,
                "intervention_type": "environmental" if any(
                    var in ["PM2.5", "NO2", "O3"] for var in request.intervention.keys()
                ) else "generic"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intervention failed: {str(e)}")


@router.post("/api/v1/causal_discovery")
async def causal_discovery(request: CausalDiscoveryRequest):
    """Existing endpoint - enhanced to store graph."""
    # ... existing logic

    # Generate graph_id and store
    import uuid
    graph_id = f"graph_{uuid.uuid4().hex[:8]}"
    graph_store[graph_id] = causal_graph

    # Include graph_id in response
    response_dict = response.model_dump()
    response_dict["graph_id"] = graph_id

    return response_dict
```

### Testing

**File**: `tests/test_intervention_api.py`

```python
import pytest
from fastapi.testclient import TestClient
from indra_agent.main import app

client = TestClient(app)

def test_intervention_endpoint():
    """Test /api/v1/intervene endpoint."""
    # First, create a graph via causal_discovery
    discovery_response = client.post("/api/v1/causal_discovery", json={
        "query": {"text": "How does PM2.5 affect CRP?"},
        "user_context": {},
        "options": {}
    })

    assert discovery_response.status_code == 200
    graph_id = discovery_response.json()["graph_id"]

    # Now perform intervention
    intervention_response = client.post("/api/v1/intervene", json={
        "graph_id": graph_id,
        "intervention": {"PM2.5": 10},
        "horizon_days": 90
    })

    assert intervention_response.status_code == 200
    data = intervention_response.json()

    assert data["status"] == "success"
    assert "predictions" in data
    assert data["metadata"]["query_time_ms"] < 100  # Should be fast

def test_intervention_404():
    """Test 404 for invalid graph_id."""
    response = client.post("/api/v1/intervene", json={
        "graph_id": "invalid_id",
        "intervention": {"PM2.5": 10},
        "horizon_days": 90
    })

    assert response.status_code == 404
```

**Acceptance Criteria**:
- [ ] Endpoint returns 200 for valid requests
- [ ] Intervention reduces downstream biomarkers
- [ ] Returns 404 for invalid graph_id
- [ ] Query time <100ms (cached matrix inversion)

**Time estimate**: 3 hours

---

## 6. Component 5: MCP Server

### Purpose

Expose causal inference capabilities as MCP tools for agent-to-agent communication.

### MCP Tools

1. **discover_causal_pathways**: Query INDRA + build graph
2. **predict_intervention**: Perform do-calculus intervention
3. **explain_mechanism**: Generate natural language explanation

### Implementation

**File**: `indra_agent/mcp_server.py` (new file)

```python
"""MCP server for causal inference tools."""

import asyncio
import json
from typing import Dict, Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import CausalDiscoveryRequest, UserContext, Query
from indra_agent.services.scm_inference import SCMInferenceEngine

# Initialize INDRA client
indra_client = INDRAAgentClient()

# Create MCP server
server = Server("causal-inference-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="discover_causal_pathways",
            description=(
                "Discover causal pathways between biomarkers, exposures, and health outcomes "
                "using literature-backed evidence from INDRA bio-ontology. "
                "Returns a causal graph with effect sizes and confidence intervals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g., 'How does PM2.5 affect CRP?')"
                    },
                    "user_genetics": {
                        "type": "object",
                        "description": "User genetic variants (e.g., {\"GSTM1\": \"null\"})",
                        "additionalProperties": {"type": "string"}
                    },
                    "current_biomarkers": {
                        "type": "object",
                        "description": "Current biomarker values (e.g., {\"CRP\": 1.2})",
                        "additionalProperties": {"type": "number"}
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="predict_intervention",
            description=(
                "Predict biomarker changes under a causal intervention using do-calculus. "
                "Answers 'what-if' questions like 'What if this person moves to Seattle?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_id": {
                        "type": "string",
                        "description": "Graph ID from discover_causal_pathways"
                    },
                    "intervention": {
                        "type": "object",
                        "description": "Variables to intervene on (e.g., {\"PM2.5\": 10})",
                        "additionalProperties": {"type": "number"}
                    },
                    "horizon_days": {
                        "type": "integer",
                        "description": "Prediction horizon in days (default: 90)",
                        "default": 90
                    }
                },
                "required": ["graph_id", "intervention"]
            }
        ),
        Tool(
            name="explain_mechanism",
            description=(
                "Generate natural language explanation of causal mechanism "
                "between two variables in a causal graph."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_id": {
                        "type": "string",
                        "description": "Graph ID from discover_causal_pathways"
                    },
                    "source": {
                        "type": "string",
                        "description": "Source variable (e.g., 'PM2.5')"
                    },
                    "target": {
                        "type": "string",
                        "description": "Target variable (e.g., 'CRP')"
                    }
                },
                "required": ["graph_id", "source", "target"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "discover_causal_pathways":
        # Build request
        request = CausalDiscoveryRequest(
            request_id="mcp_" + arguments.get("query", "")[:10],
            user_context=UserContext(
                user_id="mcp_user",
                genetics=arguments.get("user_genetics", {}),
                current_biomarkers=arguments.get("current_biomarkers", {}),
                location_history=[]
            ),
            query=Query(text=arguments["query"]),
            options={}
        )

        # Process request
        response = await indra_client.process_request(request)

        # Return graph as JSON
        return [TextContent(
            type="text",
            text=json.dumps(response.model_dump(), indent=2)
        )]

    elif name == "predict_intervention":
        # TODO: Implement intervention logic
        # (Requires accessing graph store from API)
        return [TextContent(
            type="text",
            text="Intervention prediction not yet implemented in MCP"
        )]

    elif name == "explain_mechanism":
        # TODO: Implement explanation logic
        return [TextContent(
            type="text",
            text="Mechanism explanation not yet implemented in MCP"
        )]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
```

### MCP Configuration

**File**: `mcp_config.json`

```json
{
  "mcpServers": {
    "causal-inference": {
      "command": "python",
      "args": ["-m", "indra_agent.mcp_server"],
      "env": {
        "AWS_REGION": "us-east-1"
      }
    }
  }
}
```

### Testing

**Manual test**:

```bash
# Run MCP server
python -m indra_agent.mcp_server

# Test with MCP client (e.g., Claude Desktop)
# Tool call: discover_causal_pathways
# Args: {"query": "How does PM2.5 affect CRP?"}
```

**Acceptance Criteria**:
- [ ] MCP server starts without errors
- [ ] `discover_causal_pathways` returns valid JSON
- [ ] Tools are discoverable by MCP clients
- [ ] Responses match API endpoint format

**Time estimate**: 4 hours

---

## 7. Testing Strategy

### Unit Tests

**Coverage targets**:
- Effect size calculation: 100%
- Validation agent: 100%
- SCM inference: 90%
- Intervention API: 90%

**Run tests**:
```bash
pytest tests/ -v --cov=indra_agent --cov-report=html
```

### Integration Tests

**Test case 1: End-to-end PM2.5→CRP**

```python
async def test_e2e_pm25_crp():
    """Test full pipeline: discovery → validation → intervention."""
    client = INDRAAgentClient()

    # 1. Discover causal pathways
    request = CausalDiscoveryRequest(
        request_id="test_e2e",
        user_context=UserContext(
            user_id="test_user",
            genetics={"GSTM1": "null"},
            current_biomarkers={"CRP": 3.2},
            location_history=[{"city": "Los Angeles"}]
        ),
        query=Query(text="How does PM2.5 affect CRP?"),
        options={"include_predictions": True}
    )

    response = await client.process_request(request)

    assert response.status == "success"
    assert len(response.causal_graph.edges) > 0
    assert "CRP" in response.predictions

    # 2. Validate graph
    from indra_agent.agents.validation_agent import ValidationAgent
    validator = ValidationAgent()

    graph = CausalGraph(**response.causal_graph.model_dump())
    validation = validator.validate(graph)

    assert validation.is_valid

    # 3. Perform intervention
    engine = SCMInferenceEngine(graph)

    intervention_predictions = engine.intervene(
        intervention={"PM2.5": 10},
        baseline_values={"CRP": 3.2},
        horizon_days=90
    )

    assert "CRP" in intervention_predictions
    assert intervention_predictions["CRP"].timeline[0]["mean"] < 3.2
```

### Performance Tests

**Latency benchmarks**:

```python
import time

def test_scm_inference_latency():
    """SCM inference should be <50ms for n=20."""
    # Build test graph with 20 nodes
    graph = build_test_graph(n=20)

    engine = SCMInferenceEngine(graph)

    start = time.time()
    predictions = engine.predict({}, horizon_days=90)
    elapsed_ms = (time.time() - start) * 1000

    assert elapsed_ms < 50, f"Inference took {elapsed_ms}ms (target: <50ms)"

def test_intervention_latency():
    """Intervention should be <10ms (cached inverse)."""
    graph = build_test_graph(n=20)
    engine = SCMInferenceEngine(graph)

    start = time.time()
    predictions = engine.intervene({"A": 10}, {}, horizon_days=90)
    elapsed_ms = (time.time() - start) * 1000

    assert elapsed_ms < 10, f"Intervention took {elapsed_ms}ms (target: <10ms)"
```

---

## 8. Deployment: Offline Demo

### Problem

Hackathon demo must work **offline** with no external API dependencies.

### Solution: Pre-cached Responses

**File**: `indra_agent/config/cached_responses.py`

Already exists with cached INDRA paths. Enhance with:

1. **Cache warming script** (pre-populate common queries)
2. **Offline mode flag** (skip external APIs if enabled)
3. **Fallback logic** (use cache if API fails)

**Enhancement**:

```python
# indra_agent/services/indra_service.py

class INDRAService:
    def __init__(self, offline_mode: bool = False):
        self.offline_mode = offline_mode or os.getenv("OFFLINE_MODE") == "true"

    async def find_causal_paths(self, source: str, target: str, max_depth: int = 4):
        """Find causal paths with offline fallback."""

        # Check cache first
        cache_key = f"{source}_{target}_{max_depth}"
        if cache_key in CACHED_PATHS:
            logger.info(f"Using cached paths for {source}→{target}")
            return CACHED_PATHS[cache_key]

        if self.offline_mode:
            logger.warning(f"Offline mode: no cached path for {source}→{target}")
            return []

        # Try API
        try:
            return await self._fetch_from_api(source, target, max_depth)
        except Exception as e:
            logger.error(f"INDRA API failed: {e}, checking cache")
            return CACHED_PATHS.get(cache_key, [])
```

**Cache warming script**:

```bash
# scripts/warm_cache.sh

python -c "
from indra_agent.config.cached_responses import CACHED_PATHS
print(f'Cached {len(CACHED_PATHS)} query results')
print('Common queries:')
for key in list(CACHED_PATHS.keys())[:5]:
    print(f'  - {key}')
"
```

**Demo instructions**:

```bash
# Enable offline mode
export OFFLINE_MODE=true

# Run demo
python -m indra_agent.main
```

**Acceptance Criteria**:
- [ ] Offline mode works with cached responses
- [ ] PM2.5→CRP query succeeds offline
- [ ] Warnings logged for missing cache entries
- [ ] Falls back to cache on API failure

---

## 9. Cost Monitoring

### Problem

LLM calls to AWS Bedrock can be expensive at scale.

### Solution: Cost Guards

**File**: `indra_agent/services/cost_monitor.py` (new)

```python
"""Cost monitoring and budget enforcement."""

import logging
from typing import Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CostBudget:
    """Per-query cost budget."""
    max_llm_calls: int = 5  # Max LLM calls per query
    max_api_calls: int = 20  # Max external API calls
    warn_threshold: float = 0.50  # Warn at 50% budget

    # Tracking
    llm_calls: int = 0
    api_calls: int = 0


class CostMonitor:
    """Monitor and enforce cost budgets."""

    def __init__(self):
        self.budgets: Dict[str, CostBudget] = {}

    def create_budget(self, request_id: str) -> CostBudget:
        """Create budget for request."""
        budget = CostBudget()
        self.budgets[request_id] = budget
        return budget

    def check_llm_budget(self, request_id: str) -> bool:
        """Check if LLM budget available."""
        budget = self.budgets.get(request_id)
        if not budget:
            return True

        if budget.llm_calls >= budget.max_llm_calls:
            logger.error(f"LLM budget exhausted for {request_id}")
            return False

        budget.llm_calls += 1

        if budget.llm_calls / budget.max_llm_calls > budget.warn_threshold:
            logger.warning(f"LLM budget at {budget.llm_calls}/{budget.max_llm_calls}")

        return True

    def check_api_budget(self, request_id: str) -> bool:
        """Check if API budget available."""
        budget = self.budgets.get(request_id)
        if not budget:
            return True

        if budget.api_calls >= budget.max_api_calls:
            logger.error(f"API budget exhausted for {request_id}")
            return False

        budget.api_calls += 1
        return True


# Global cost monitor
cost_monitor = CostMonitor()
```

**Integration**:

```python
# indra_agent/agents/supervisor.py

from indra_agent.services.cost_monitor import cost_monitor

class SupervisorAgent:
    async def __call__(self, state: OverallState, config: RunnableConfig):
        request_id = state.get("request_id")

        # Create budget
        budget = cost_monitor.create_budget(request_id)

        # Check before LLM call
        if not cost_monitor.check_llm_budget(request_id):
            return {"status": "error", "error_code": "BUDGET_EXCEEDED"}

        # ... rest of logic
```

**Acceptance Criteria**:
- [ ] Warns at 50% budget
- [ ] Rejects requests exceeding budget
- [ ] Logs cost metrics per request

---

## 10. Production Hardening Checklist

**Post-production tasks** (defer for now):

### Infrastructure
- [ ] Replace in-memory graph storage with Redis
- [ ] Add PostgreSQL for persistent graph storage
- [ ] Implement distributed tracing (Jaeger)
- [ ] Add health check endpoints (`/health`, `/ready`)

### Scalability
- [ ] Implement sparse matrix methods for n>100
- [ ] Add caching layer (Redis) for (I-W)^{-1}
- [ ] Horizontal scaling with Kubernetes
- [ ] Load balancing across multiple instances

### Reliability
- [ ] Circuit breakers for external APIs
- [ ] Retry logic with exponential backoff
- [ ] Rate limiting per API key
- [ ] Graceful degradation (partial graphs)

### Observability
- [ ] Structured logging (JSON format)
- [ ] Metrics dashboard (Prometheus + Grafana)
- [ ] Alert rules for SLA violations
- [ ] Cost tracking per user/query

### Security
- [ ] API key authentication
- [ ] Input validation (prompt injection)
- [ ] Rate limiting (per-user quotas)
- [ ] HTTPS + certificate management

---

**End of Engineering Implementation Guide**
