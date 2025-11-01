# Causal Intervention API Specification

**Version**: 1.0
**Last Updated**: October 2025
**Status**: Ready for Implementation

---

## Overview

This document specifies the **causal intervention API** that enables counterfactual reasoning via Pearl's do-calculus. The API allows agents to query "What if?" scenarios by performing graph surgery on the causal model and computing interventional distributions.

### Key Capabilities

1. **Interventional Queries**: Answer "What if this person moves to Seattle?" by setting environmental variables and propagating effects
2. **Multiple Interventions**: Support simultaneous interventions on multiple nodes
3. **Backdoor Adjustment**: Automatically identify and adjust for confounders when direct intervention isn't possible
4. **Sensitivity Analysis**: Compute how predictions change with parameter uncertainty
5. **Comparison Mode**: Compare multiple intervention scenarios side-by-side

### Mathematical Foundation

**do-calculus** (Pearl, 2009):
- **do(X = x)**: Intervention operator that sets X to value x
- **Graph Surgery**: Remove all incoming edges to X, set X = x
- **Interventional Distribution**: p(Y | do(X = x)) computed via truncated factorization

**Linear Gaussian SCM**:
```
Observational: V = (I - W)^{-1} (μ + ε)
Interventional: V | do(V_i = v) = (I - W_do)^{-1} (μ + e_i · v + ε)
where W_do = W with row i set to zero (remove parents of V_i)
```

---

## API Endpoints

### 1. Single Intervention

**Endpoint**: `POST /api/v1/intervene`

**Purpose**: Compute counterfactual predictions for a single intervention scenario.

#### Request Schema

```json
{
  "request_id": "string (UUID)",
  "graph_id": "string (UUID from /causal_discovery)",
  "intervention": {
    "node_id": "string",
    "value": "number",
    "unit": "string (optional)"
  },
  "target_biomarkers": ["string"],
  "horizon_days": "integer (default: 90)",
  "confidence_level": "number (default: 0.95)",
  "options": {
    "include_pathway_analysis": "boolean (default: true)",
    "include_sensitivity": "boolean (default: false)"
  }
}
```

**Example Request**:
```json
{
  "request_id": "intervention-001",
  "graph_id": "graph-abc123",
  "intervention": {
    "node_id": "PM2.5",
    "value": 12.5,
    "unit": "µg/m³"
  },
  "target_biomarkers": ["CRP", "IL-6"],
  "horizon_days": 90,
  "confidence_level": 0.95,
  "options": {
    "include_pathway_analysis": true,
    "include_sensitivity": false
  }
}
```

#### Response Schema

```json
{
  "request_id": "string",
  "status": "success | error",
  "intervention_summary": {
    "node_id": "string",
    "value": "number",
    "unit": "string",
    "baseline_value": "number (from original context)"
  },
  "predictions": {
    "<biomarker_id>": {
      "baseline": {
        "mean": "number",
        "ci_lower": "number",
        "ci_upper": "number"
      },
      "post_intervention": {
        "mean": "number",
        "ci_lower": "number",
        "ci_upper": "number"
      },
      "delta": {
        "absolute": "number",
        "percent": "number"
      },
      "timeline": [
        {
          "day": "integer",
          "mean": "number",
          "ci_lower": "number",
          "ci_upper": "number",
          "risk_level": "low | moderate | high"
        }
      ]
    }
  },
  "affected_pathways": [
    {
      "pathway": ["node_id"],
      "relationship_chain": ["increases", "activates"],
      "total_effect_size": "number",
      "explanation": "string (< 200 chars)"
    }
  ],
  "metadata": {
    "computation_time_ms": "integer",
    "graph_nodes": "integer",
    "confidence_level": "number"
  }
}
```

**Example Response**:
```json
{
  "request_id": "intervention-001",
  "status": "success",
  "intervention_summary": {
    "node_id": "PM2.5",
    "value": 12.5,
    "unit": "µg/m³",
    "baseline_value": 34.5
  },
  "predictions": {
    "CRP": {
      "baseline": {
        "mean": 5.2,
        "ci_lower": 4.1,
        "ci_upper": 6.3
      },
      "post_intervention": {
        "mean": 2.8,
        "ci_lower": 2.1,
        "ci_upper": 3.5
      },
      "delta": {
        "absolute": -2.4,
        "percent": -46.2
      },
      "timeline": [
        {"day": 0, "mean": 5.2, "ci_lower": 4.1, "ci_upper": 6.3, "risk_level": "moderate"},
        {"day": 30, "mean": 3.8, "ci_lower": 3.0, "ci_upper": 4.6, "risk_level": "moderate"},
        {"day": 60, "mean": 3.1, "ci_lower": 2.4, "ci_upper": 3.8, "risk_level": "low"},
        {"day": 90, "mean": 2.8, "ci_lower": 2.1, "ci_upper": 3.5, "risk_level": "low"}
      ]
    },
    "IL-6": {
      "baseline": {"mean": 3.8, "ci_lower": 2.9, "ci_upper": 4.7},
      "post_intervention": {"mean": 1.9, "ci_lower": 1.4, "ci_upper": 2.4},
      "delta": {"absolute": -1.9, "percent": -50.0},
      "timeline": [
        {"day": 0, "mean": 3.8, "ci_lower": 2.9, "ci_upper": 4.7, "risk_level": "moderate"},
        {"day": 30, "mean": 2.7, "ci_lower": 2.1, "ci_upper": 3.3, "risk_level": "moderate"},
        {"day": 60, "mean": 2.2, "ci_lower": 1.6, "ci_upper": 2.8, "risk_level": "low"},
        {"day": 90, "mean": 1.9, "ci_lower": 1.4, "ci_upper": 2.4, "risk_level": "low"}
      ]
    }
  },
  "affected_pathways": [
    {
      "pathway": ["PM2.5", "NFKB1", "IL6", "CRP"],
      "relationship_chain": ["activates", "increases", "increases"],
      "total_effect_size": 0.71,
      "explanation": "Reducing PM2.5 by 64% decreases NF-κB activation, lowering IL-6 and CRP"
    }
  ],
  "metadata": {
    "computation_time_ms": 87,
    "graph_nodes": 8,
    "confidence_level": 0.95
  }
}
```

---

### 2. Multi-Intervention Comparison

**Endpoint**: `POST /api/v1/intervene/compare`

**Purpose**: Compare multiple intervention scenarios side-by-side.

#### Request Schema

```json
{
  "request_id": "string (UUID)",
  "graph_id": "string (UUID from /causal_discovery)",
  "scenarios": [
    {
      "scenario_id": "string",
      "label": "string (human-readable)",
      "interventions": [
        {
          "node_id": "string",
          "value": "number",
          "unit": "string (optional)"
        }
      ]
    }
  ],
  "target_biomarkers": ["string"],
  "horizon_days": "integer (default: 90)",
  "confidence_level": "number (default: 0.95)"
}
```

**Example Request**:
```json
{
  "request_id": "compare-001",
  "graph_id": "graph-abc123",
  "scenarios": [
    {
      "scenario_id": "baseline",
      "label": "Current (Los Angeles)",
      "interventions": []
    },
    {
      "scenario_id": "seattle",
      "label": "Move to Seattle",
      "interventions": [
        {"node_id": "PM2.5", "value": 7.8, "unit": "µg/m³"}
      ]
    },
    {
      "scenario_id": "portland",
      "label": "Move to Portland",
      "interventions": [
        {"node_id": "PM2.5", "value": 10.2, "unit": "µg/m³"}
      ]
    }
  ],
  "target_biomarkers": ["CRP", "IL-6"],
  "horizon_days": 90,
  "confidence_level": 0.95
}
```

#### Response Schema

```json
{
  "request_id": "string",
  "status": "success | error",
  "comparison": {
    "<scenario_id>": {
      "label": "string",
      "predictions": {
        "<biomarker_id>": {
          "mean": "number",
          "ci_lower": "number",
          "ci_upper": "number"
        }
      }
    }
  },
  "ranking": [
    {
      "scenario_id": "string",
      "label": "string",
      "total_health_score": "number (higher = better)",
      "explanation": "string (< 200 chars)"
    }
  ],
  "metadata": {
    "computation_time_ms": "integer",
    "scenarios_compared": "integer"
  }
}
```

**Example Response**:
```json
{
  "request_id": "compare-001",
  "status": "success",
  "comparison": {
    "baseline": {
      "label": "Current (Los Angeles)",
      "predictions": {
        "CRP": {"mean": 5.2, "ci_lower": 4.1, "ci_upper": 6.3},
        "IL-6": {"mean": 3.8, "ci_lower": 2.9, "ci_upper": 4.7}
      }
    },
    "seattle": {
      "label": "Move to Seattle",
      "predictions": {
        "CRP": {"mean": 2.1, "ci_lower": 1.6, "ci_upper": 2.6},
        "IL-6": {"mean": 1.5, "ci_lower": 1.1, "ci_upper": 1.9}
      }
    },
    "portland": {
      "label": "Move to Portland",
      "predictions": {
        "CRP": {"mean": 2.6, "ci_lower": 2.0, "ci_upper": 3.2},
        "IL-6": {"mean": 1.8, "ci_lower": 1.3, "ci_upper": 2.3}
      }
    }
  },
  "ranking": [
    {
      "scenario_id": "seattle",
      "label": "Move to Seattle",
      "total_health_score": 92.5,
      "explanation": "Lowest PM2.5 (7.8 µg/m³) results in 60% lower CRP and 61% lower IL-6"
    },
    {
      "scenario_id": "portland",
      "label": "Move to Portland",
      "total_health_score": 87.3,
      "explanation": "Moderate PM2.5 (10.2 µg/m³) reduces CRP by 50% and IL-6 by 53%"
    },
    {
      "scenario_id": "baseline",
      "label": "Current (Los Angeles)",
      "total_health_score": 45.0,
      "explanation": "High PM2.5 (34.5 µg/m³) maintains elevated inflammatory biomarkers"
    }
  ],
  "metadata": {
    "computation_time_ms": 134,
    "scenarios_compared": 3
  }
}
```

---

### 3. Sensitivity Analysis

**Endpoint**: `POST /api/v1/intervene/sensitivity`

**Purpose**: Analyze how predictions change under parameter uncertainty.

#### Request Schema

```json
{
  "request_id": "string (UUID)",
  "graph_id": "string (UUID from /causal_discovery)",
  "intervention": {
    "node_id": "string",
    "value": "number",
    "unit": "string (optional)"
  },
  "target_biomarker": "string",
  "sensitivity_parameters": {
    "effect_size_variance": "number (default: 0.1)",
    "noise_variance_factor": "number (default: 1.5)",
    "num_samples": "integer (default: 1000)"
  }
}
```

**Example Request**:
```json
{
  "request_id": "sensitivity-001",
  "graph_id": "graph-abc123",
  "intervention": {
    "node_id": "PM2.5",
    "value": 12.5,
    "unit": "µg/m³"
  },
  "target_biomarker": "CRP",
  "sensitivity_parameters": {
    "effect_size_variance": 0.1,
    "noise_variance_factor": 1.5,
    "num_samples": 1000
  }
}
```

#### Response Schema

```json
{
  "request_id": "string",
  "status": "success | error",
  "nominal_prediction": {
    "mean": "number",
    "ci_lower": "number",
    "ci_upper": "number"
  },
  "sensitivity_analysis": {
    "mean_range": ["number", "number"],
    "ci_range": [["number", "number"], ["number", "number"]],
    "robustness_score": "number (0-1, higher = more robust)",
    "critical_edges": [
      {
        "edge": {"source": "string", "target": "string"},
        "sensitivity_coefficient": "number",
        "explanation": "string (< 150 chars)"
      }
    ]
  },
  "metadata": {
    "computation_time_ms": "integer",
    "num_samples": "integer"
  }
}
```

**Example Response**:
```json
{
  "request_id": "sensitivity-001",
  "status": "success",
  "nominal_prediction": {
    "mean": 2.8,
    "ci_lower": 2.1,
    "ci_upper": 3.5
  },
  "sensitivity_analysis": {
    "mean_range": [2.4, 3.3],
    "ci_range": [[1.8, 2.5], [2.9, 4.1]],
    "robustness_score": 0.82,
    "critical_edges": [
      {
        "edge": {"source": "IL6", "target": "CRP"},
        "sensitivity_coefficient": 0.45,
        "explanation": "IL-6 → CRP is the strongest driver; ±10% effect size changes CRP by ±18%"
      },
      {
        "edge": {"source": "NFKB1", "target": "IL6"},
        "sensitivity_coefficient": 0.31,
        "explanation": "NF-κB → IL-6 is moderately sensitive; ±10% effect size changes CRP by ±12%"
      }
    ]
  },
  "metadata": {
    "computation_time_ms": 342,
    "num_samples": 1000
  }
}
```

---

## Implementation Architecture

### Graph Storage

**Option 1: In-Memory (MVP)**
```python
# Store graphs in memory with TTL
from collections import OrderedDict
from datetime import datetime, timedelta

class GraphStore:
    def __init__(self, max_size=100, ttl_hours=24):
        self.graphs = OrderedDict()
        self.ttl_hours = ttl_hours
        self.max_size = max_size

    def store(self, graph_id: str, graph_data: dict) -> None:
        """Store graph with timestamp."""
        if len(self.graphs) >= self.max_size:
            self.graphs.popitem(last=False)  # Remove oldest

        self.graphs[graph_id] = {
            "data": graph_data,
            "timestamp": datetime.utcnow()
        }

    def retrieve(self, graph_id: str) -> dict:
        """Retrieve graph if not expired."""
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        entry = self.graphs[graph_id]
        age = datetime.utcnow() - entry["timestamp"]

        if age > timedelta(hours=self.ttl_hours):
            del self.graphs[graph_id]
            raise ValueError(f"Graph {graph_id} expired")

        return entry["data"]
```

**Option 2: Redis (Production)**
```python
import redis
import json

class RedisGraphStore:
    def __init__(self, redis_url="redis://localhost:6379", ttl_hours=24):
        self.redis = redis.from_url(redis_url)
        self.ttl_seconds = ttl_hours * 3600

    def store(self, graph_id: str, graph_data: dict) -> None:
        """Store graph with TTL."""
        key = f"graph:{graph_id}"
        value = json.dumps(graph_data)
        self.redis.setex(key, self.ttl_seconds, value)

    def retrieve(self, graph_id: str) -> dict:
        """Retrieve graph."""
        key = f"graph:{graph_id}"
        value = self.redis.get(key)

        if value is None:
            raise ValueError(f"Graph {graph_id} not found or expired")

        return json.loads(value)
```

### Intervention Engine

```python
import numpy as np
from typing import Dict, List, Optional
from indra_agent.core.models import CausalGraph, InterventionRequest

class InterventionEngine:
    """Implements do-calculus for causal interventions."""

    def __init__(self, graph: CausalGraph):
        self.graph = graph
        self.n = len(graph.nodes)
        self.node_to_idx = {node.id: i for i, node in enumerate(graph.nodes)}

        # Build weight matrix W
        self.W = self._build_weight_matrix()

        # Build baseline mean vector μ
        self.mu = self._build_mean_vector()

        # Build noise covariance Σ
        self.Sigma = self._build_noise_covariance()

    def _build_weight_matrix(self) -> np.ndarray:
        """Build weight matrix W from causal graph."""
        W = np.zeros((self.n, self.n))

        for edge in self.graph.edges:
            i = self.node_to_idx[edge.target]
            j = self.node_to_idx[edge.source]

            magnitude = edge.effect_size
            if edge.relationship in ["decreases", "inhibits"]:
                magnitude = -magnitude

            W[i, j] = magnitude

        return W

    def _build_mean_vector(self) -> np.ndarray:
        """Build baseline mean vector μ from node properties."""
        mu = np.zeros(self.n)

        for node in self.graph.nodes:
            if hasattr(node, 'baseline_value') and node.baseline_value is not None:
                mu[self.node_to_idx[node.id]] = node.baseline_value

        return mu

    def _build_noise_covariance(self) -> np.ndarray:
        """Build noise covariance matrix Σ."""
        # Start with identity (unit variance)
        Sigma = np.eye(self.n)

        # Scale by node-specific variance if available
        for node in self.graph.nodes:
            if hasattr(node, 'noise_variance') and node.noise_variance is not None:
                idx = self.node_to_idx[node.id]
                Sigma[idx, idx] = node.noise_variance

        return Sigma

    def intervene(
        self,
        interventions: Dict[str, float],
        target_nodes: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """Perform intervention and compute predictions.

        Args:
            interventions: Dict mapping node_id to intervention value
            target_nodes: Nodes to compute predictions for (default: all biomarkers)

        Returns:
            Dict mapping node_id to prediction statistics
        """
        # Build intervention vector and mask
        intervention_mask = np.zeros(self.n, dtype=bool)
        intervention_values = np.zeros(self.n)

        for node_id, value in interventions.items():
            if node_id not in self.node_to_idx:
                raise ValueError(f"Node {node_id} not in graph")

            idx = self.node_to_idx[node_id]
            intervention_mask[idx] = True
            intervention_values[idx] = value

        # Graph surgery: W_do = W with intervened rows zeroed
        W_do = self.W.copy()
        W_do[intervention_mask, :] = 0

        # Modified mean: μ_do = μ + Σ_i e_i · v_i for intervened nodes
        mu_do = self.mu.copy()
        mu_do[intervention_mask] = intervention_values[intervention_mask]

        # Compute interventional distribution
        I_minus_W_do = np.eye(self.n) - W_do

        # Check invertibility
        if np.linalg.cond(I_minus_W_do) > 1e10:
            raise ValueError("Intervention leads to unstable system (I - W_do nearly singular)")

        I_minus_W_do_inv = np.linalg.inv(I_minus_W_do)

        # Posterior mean: E[V | do(...)] = (I - W_do)^{-1} μ_do
        posterior_mean = I_minus_W_do_inv @ mu_do

        # Posterior covariance: Var[V | do(...)] = (I - W_do)^{-1} Σ ((I - W_do)^{-1})^T
        posterior_cov = I_minus_W_do_inv @ self.Sigma @ I_minus_W_do_inv.T
        posterior_std = np.sqrt(np.diag(posterior_cov))

        # Compute baseline (observational) for comparison
        I_minus_W_inv = np.linalg.inv(np.eye(self.n) - self.W)
        baseline_mean = I_minus_W_inv @ self.mu
        baseline_cov = I_minus_W_inv @ self.Sigma @ I_minus_W_inv.T
        baseline_std = np.sqrt(np.diag(baseline_cov))

        # Build predictions
        predictions = {}

        target_indices = range(self.n)
        if target_nodes:
            target_indices = [self.node_to_idx[n] for n in target_nodes if n in self.node_to_idx]

        for idx in target_indices:
            node_id = self.graph.nodes[idx].id

            # Skip intervened nodes (they're fixed)
            if intervention_mask[idx]:
                continue

            predictions[node_id] = {
                "baseline": {
                    "mean": float(baseline_mean[idx]),
                    "ci_lower": float(baseline_mean[idx] - 1.96 * baseline_std[idx]),
                    "ci_upper": float(baseline_mean[idx] + 1.96 * baseline_std[idx])
                },
                "post_intervention": {
                    "mean": float(posterior_mean[idx]),
                    "ci_lower": float(posterior_mean[idx] - 1.96 * posterior_std[idx]),
                    "ci_upper": float(posterior_mean[idx] + 1.96 * posterior_std[idx])
                },
                "delta": {
                    "absolute": float(posterior_mean[idx] - baseline_mean[idx]),
                    "percent": float(100 * (posterior_mean[idx] - baseline_mean[idx]) / baseline_mean[idx]) if baseline_mean[idx] != 0 else 0
                }
            }

        return predictions

    def compute_timeline(
        self,
        interventions: Dict[str, float],
        target_node: str,
        horizon_days: int = 90,
        resolution_days: int = 30
    ) -> List[Dict]:
        """Compute prediction timeline with temporal dynamics.

        For production MVP, use linear interpolation from baseline to steady-state.
        Post-production: Replace with discrete-time dynamic Bayesian network.
        """
        # Get steady-state prediction
        predictions = self.intervene(interventions, target_nodes=[target_node])

        if target_node not in predictions:
            raise ValueError(f"No prediction for {target_node}")

        baseline = predictions[target_node]["baseline"]["mean"]
        steady_state = predictions[target_node]["post_intervention"]["mean"]
        ci_width = predictions[target_node]["post_intervention"]["ci_upper"] - predictions[target_node]["post_intervention"]["ci_lower"]

        # Linear interpolation timeline (MVP simplification)
        timeline = []
        for day in range(0, horizon_days + 1, resolution_days):
            progress = min(day / horizon_days, 1.0)
            current_mean = baseline + progress * (steady_state - baseline)

            # Confidence interval widens slightly over time (uncertainty accumulates)
            time_factor = 1.0 + 0.2 * progress  # +20% width at t=horizon
            ci_half_width = (ci_width / 2) * time_factor

            current_ci_lower = current_mean - ci_half_width
            current_ci_upper = current_mean + ci_half_width

            # Risk level heuristic (biomarker-specific thresholds needed for production)
            if current_mean < 3.0:
                risk_level = "low"
            elif current_mean < 5.0:
                risk_level = "moderate"
            else:
                risk_level = "high"

            timeline.append({
                "day": day,
                "mean": round(current_mean, 2),
                "ci_lower": round(current_ci_lower, 2),
                "ci_upper": round(current_ci_upper, 2),
                "risk_level": risk_level
            })

        return timeline
```

---

## FastAPI Route Implementation

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import uuid

router = APIRouter(prefix="/api/v1", tags=["intervention"])

class Intervention(BaseModel):
    node_id: str = Field(..., description="Node to intervene on")
    value: float = Field(..., description="Intervention value")
    unit: Optional[str] = Field(None, description="Unit of measurement")

class InterventionRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    graph_id: str = Field(..., description="Graph ID from /causal_discovery")
    intervention: Intervention
    target_biomarkers: List[str] = Field(..., description="Biomarkers to predict")
    horizon_days: int = Field(90, ge=1, le=365)
    confidence_level: float = Field(0.95, ge=0.5, le=0.99)
    options: Optional[Dict] = Field(default_factory=dict)

@router.post("/intervene")
async def perform_intervention(request: InterventionRequest):
    """Perform causal intervention and compute predictions."""
    try:
        # Retrieve graph from storage
        graph_data = graph_store.retrieve(request.graph_id)
        graph = CausalGraph(**graph_data)

        # Initialize intervention engine
        engine = InterventionEngine(graph)

        # Perform intervention
        interventions = {request.intervention.node_id: request.intervention.value}
        predictions = engine.intervene(interventions, target_nodes=request.target_biomarkers)

        # Compute timelines
        timeline_predictions = {}
        for biomarker_id in request.target_biomarkers:
            if biomarker_id in predictions:
                timeline = engine.compute_timeline(
                    interventions,
                    biomarker_id,
                    horizon_days=request.horizon_days
                )
                timeline_predictions[biomarker_id] = {
                    **predictions[biomarker_id],
                    "timeline": timeline
                }

        # Identify affected pathways
        affected_pathways = _identify_affected_pathways(
            graph,
            request.intervention.node_id,
            request.target_biomarkers
        )

        return {
            "request_id": request.request_id,
            "status": "success",
            "intervention_summary": {
                "node_id": request.intervention.node_id,
                "value": request.intervention.value,
                "unit": request.intervention.unit,
                "baseline_value": _get_baseline_value(graph, request.intervention.node_id)
            },
            "predictions": timeline_predictions,
            "affected_pathways": affected_pathways,
            "metadata": {
                "computation_time_ms": 0,  # TODO: measure
                "graph_nodes": len(graph.nodes),
                "confidence_level": request.confidence_level
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

def _identify_affected_pathways(
    graph: CausalGraph,
    source_node: str,
    target_nodes: List[str]
) -> List[Dict]:
    """Find all paths from source to targets."""
    import networkx as nx

    # Build NetworkX graph
    G = nx.DiGraph()
    for edge in graph.edges:
        G.add_edge(edge.source, edge.target, **edge.dict())

    affected_pathways = []

    for target in target_nodes:
        if target not in G:
            continue

        try:
            # Find all simple paths
            paths = list(nx.all_simple_paths(G, source_node, target, cutoff=5))

            for path in paths[:3]:  # Limit to top 3 paths
                # Compute total effect size (product of edge effects)
                total_effect = 1.0
                relationships = []

                for i in range(len(path) - 1):
                    edge_data = G[path[i]][path[i+1]]
                    total_effect *= edge_data['effect_size']
                    relationships.append(edge_data['relationship'])

                # Generate explanation
                delta_pct = abs((graph.nodes[0].baseline_value - 12.5) / graph.nodes[0].baseline_value * 100) if len(graph.nodes) > 0 else 0
                explanation = f"Reducing {path[0]} by {delta_pct:.0f}% affects {' → '.join(path)}"

                affected_pathways.append({
                    "pathway": path,
                    "relationship_chain": relationships,
                    "total_effect_size": round(total_effect, 2),
                    "explanation": explanation[:200]
                })

        except nx.NetworkXNoPath:
            continue

    return affected_pathways

def _get_baseline_value(graph: CausalGraph, node_id: str) -> Optional[float]:
    """Get baseline value for node from graph."""
    for node in graph.nodes:
        if node.id == node_id:
            return getattr(node, 'baseline_value', None)
    return None
```

---

## Validation Rules

### Request Validation

1. **Graph ID Must Exist**:
   - Check graph_store for valid graph_id
   - Return 404 if not found or expired

2. **Intervention Node Must Exist**:
   - Verify intervention.node_id is in graph
   - Return 400 with error message if not

3. **Intervention Value Must Be Valid**:
   - For environmental nodes: value >= 0
   - For biomarkers: value > 0
   - For molecular nodes: value >= 0

4. **Target Biomarkers Must Exist**:
   - Verify all target_biomarkers are in graph
   - Warn if target is not a biomarker type
   - Return partial results if some targets missing

5. **Horizon Must Be Reasonable**:
   - horizon_days ∈ [1, 365]
   - Warn if >180 days (predictions less reliable)

### Response Validation

1. **Predictions Must Have Finite Values**:
   - Check for NaN, Inf in mean/ci_lower/ci_upper
   - Return error if computation failed

2. **Confidence Intervals Must Be Valid**:
   - ci_lower < mean < ci_upper
   - Width proportional to uncertainty

3. **Delta Must Be Consistent**:
   - delta.absolute = post_intervention.mean - baseline.mean
   - delta.percent = 100 * delta.absolute / baseline.mean

4. **Timeline Must Be Ordered**:
   - timeline[i].day < timeline[i+1].day
   - timeline[0].day = 0, timeline[-1].day = horizon_days

---

## Error Handling

### Error Response Schema

```json
{
  "request_id": "string",
  "status": "error",
  "error": {
    "code": "string (enum)",
    "message": "string",
    "details": "object (optional)"
  }
}
```

### Error Codes

| Code | HTTP Status | Description | Example |
|------|-------------|-------------|---------|
| `GRAPH_NOT_FOUND` | 404 | Graph ID not in storage or expired | "Graph graph-xyz not found" |
| `INVALID_NODE` | 400 | Intervention node not in graph | "Node 'PM10' not in graph" |
| `INVALID_VALUE` | 400 | Intervention value out of range | "Value -5.2 invalid for environmental node" |
| `UNSTABLE_SYSTEM` | 400 | Intervention leads to unstable SCM | "Intervention causes spectral radius > 1" |
| `COMPUTATION_ERROR` | 500 | Matrix inversion failed | "Singular matrix in (I - W_do)^{-1}" |
| `TIMEOUT` | 504 | Computation exceeded time limit | "Intervention computation timed out after 5s" |

---

## Performance Requirements

### Latency Targets (n=20 nodes)

- Single intervention: **< 100ms** (p95)
- Multi-intervention comparison (3 scenarios): **< 300ms** (p95)
- Sensitivity analysis (1000 samples): **< 500ms** (p95)

### Scalability

- **Computation Complexity**: O(n³) for matrix inversion
- **Memory**: O(n²) for weight matrix and covariance
- **Expected Load**: 20-30 nodes per graph, 10 graphs/minute

### Optimization Strategies

1. **Cache Matrix Inversions**:
   ```python
   @lru_cache(maxsize=128)
   def _cached_inverse(W_bytes: bytes) -> np.ndarray:
       W = np.frombuffer(W_bytes).reshape((n, n))
       return np.linalg.inv(np.eye(n) - W)
   ```

2. **Lazy Timeline Computation**:
   - Only compute timeline if `include_timeline=true`
   - Use coarser resolution for long horizons

3. **Parallel Scenario Comparison**:
   ```python
   from concurrent.futures import ThreadPoolExecutor

   with ThreadPoolExecutor(max_workers=4) as executor:
       futures = [executor.submit(engine.intervene, scenario) for scenario in scenarios]
       results = [f.result() for f in futures]
   ```

---

## Testing Strategy

### Unit Tests

**Test 1: Single Intervention**
```python
def test_single_intervention():
    # Setup graph with PM2.5 → IL6 → CRP
    graph = build_test_graph()
    engine = InterventionEngine(graph)

    # Intervene: reduce PM2.5 from 34.5 to 12.5
    predictions = engine.intervene({"PM2.5": 12.5}, target_nodes=["CRP", "IL6"])

    # Assertions
    assert "CRP" in predictions
    assert predictions["CRP"]["delta"]["absolute"] < 0  # Should decrease
    assert predictions["CRP"]["post_intervention"]["mean"] < predictions["CRP"]["baseline"]["mean"]
    assert predictions["CRP"]["post_intervention"]["ci_lower"] < predictions["CRP"]["post_intervention"]["ci_upper"]
```

**Test 2: Multi-Intervention**
```python
def test_multi_intervention():
    graph = build_test_graph()
    engine = InterventionEngine(graph)

    # Intervene on multiple nodes
    predictions = engine.intervene({"PM2.5": 10.0, "ozone": 0.03}, target_nodes=["CRP"])

    assert "CRP" in predictions
    # Combined effect should be stronger than single intervention
```

**Test 3: Invalid Intervention**
```python
def test_invalid_intervention_node():
    graph = build_test_graph()
    engine = InterventionEngine(graph)

    with pytest.raises(ValueError, match="Node 'INVALID' not in graph"):
        engine.intervene({"INVALID": 10.0})
```

**Test 4: Unstable Intervention**
```python
def test_unstable_intervention():
    # Create graph with strong feedback (would violate spectral radius if modified)
    graph = build_feedback_graph()
    engine = InterventionEngine(graph)

    # This intervention should fail stability check
    with pytest.raises(ValueError, match="unstable system"):
        engine.intervene({"feedback_node": 100.0})
```

### Integration Tests

**Test 5: Full API Call**
```python
@pytest.mark.asyncio
async def test_intervention_endpoint():
    # First create a graph
    discovery_response = await client.post("/api/v1/causal_discovery", json=discovery_request)
    graph_id = discovery_response.json()["graph_id"]

    # Now intervene
    intervention_request = {
        "graph_id": graph_id,
        "intervention": {"node_id": "PM2.5", "value": 12.5},
        "target_biomarkers": ["CRP", "IL-6"],
        "horizon_days": 90
    }

    response = await client.post("/api/v1/intervene", json=intervention_request)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "predictions" in data
    assert "CRP" in data["predictions"]
    assert "timeline" in data["predictions"]["CRP"]
```

### Contract Tests

**Test 6: Response Schema Compliance**
```python
def test_intervention_response_schema():
    response = perform_intervention_api_call()
    data = response.json()

    # Validate against Pydantic model
    InterventionResponse(**data)  # Should not raise

    # Check required fields
    assert "request_id" in data
    assert "status" in data
    assert data["status"] in ["success", "error"]
    assert "predictions" in data

    # Validate prediction structure
    for biomarker_id, prediction in data["predictions"].items():
        assert "baseline" in prediction
        assert "post_intervention" in prediction
        assert "delta" in prediction
        assert "timeline" in prediction

        # Validate credible intervals
        assert prediction["baseline"]["ci_lower"] < prediction["baseline"]["mean"]
        assert prediction["baseline"]["mean"] < prediction["baseline"]["ci_upper"]
```

---

## MCP Integration

The intervention API should be exposed via MCP (Model Context Protocol) for agent-to-agent communication.

### MCP Tool: `causal_intervene`

```json
{
  "name": "causal_intervene",
  "description": "Perform causal intervention to answer 'What if?' questions using do-calculus",
  "inputSchema": {
    "type": "object",
    "properties": {
      "graph_id": {
        "type": "string",
        "description": "Graph ID from previous causal_discover call"
      },
      "intervention": {
        "type": "object",
        "properties": {
          "node_id": {"type": "string"},
          "value": {"type": "number"}
        }
      },
      "target_biomarkers": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["graph_id", "intervention", "target_biomarkers"]
  }
}
```

**Example MCP Call**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "causal_intervene",
    "arguments": {
      "graph_id": "graph-abc123",
      "intervention": {
        "node_id": "PM2.5",
        "value": 12.5
      },
      "target_biomarkers": ["CRP", "IL-6"]
    }
  }
}
```

---

## Deployment Checklist

### MVP (Hackathon)

- [x] Mathematical foundation documented
- [ ] `InterventionEngine` class implemented
- [ ] `/api/v1/intervene` endpoint
- [ ] In-memory graph storage
- [ ] Unit tests for intervention logic
- [ ] Integration test with full workflow
- [ ] Error handling for invalid interventions
- [ ] OpenAPI docs auto-generated

### Production (Post-Hackathon)

- [ ] Redis-based graph storage
- [ ] Rate limiting (10 requests/minute per user)
- [ ] Caching of common interventions
- [ ] Parallel scenario comparison
- [ ] Sensitivity analysis endpoint
- [ ] Logging and monitoring
- [ ] Cost tracking (AWS Bedrock calls)
- [ ] Multi-timescale DBN for temporal dynamics

---

## References

**Pearl (2009)**: *Causality: Models, Reasoning, and Inference* - do-calculus foundation

**Peters et al. (2017)**: *Elements of Causal Inference* - Identifiability theory

**Bareinboim & Pearl (2016)**: "Causal Inference and the Data-Fusion Problem" - External validity

**Shpitser & Pearl (2006)**: "Identification of Conditional Interventional Distributions" - General do-calculus

**API Design**:
- `/api/v1/causal_discovery` creates graph (prerequisite)
- `/api/v1/intervene` performs do-calculus on stored graph
- MCP server exposes both for agent-to-agent communication

---

**End of Intervention API Specification**
