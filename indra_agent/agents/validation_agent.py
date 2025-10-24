"""Validation agent for causal graphs.

This agent validates that constructed causal graphs satisfy all mathematical
and structural constraints required for SCM inference:
- DAG constraint (acyclic)
- Stability (spectral radius < 1)
- Parameter ranges (effect_size ∈ [-1,1], temporal_lag ≥ 0)
"""

import logging
from typing import Dict, List

import networkx as nx
import numpy as np

from indra_agent.core.models import CausalGraph, Edge, Node

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Agent responsible for validating causal graph constraints."""

    # Spectral radius threshold (must be < 1 for stability)
    SPECTRAL_RADIUS_THRESHOLD = 0.99

    def validate_graph(self, graph: CausalGraph) -> Dict:
        """Validate causal graph against all constraints.

        Args:
            graph: Causal graph to validate

        Returns:
            Dict with validation results:
                {
                    "is_valid": bool,
                    "checks": {
                        "is_dag": bool,
                        "is_stable": bool,
                        "parameters_valid": bool
                    },
                    "errors": List[str],
                    "warnings": List[str],
                    "metadata": {
                        "spectral_radius": float,
                        "num_nodes": int,
                        "num_edges": int
                    }
                }
        """
        errors = []
        warnings = []
        checks = {}

        # Check 1: DAG constraint
        dag_result = self._validate_dag(graph)
        checks["is_dag"] = dag_result["is_valid"]
        if not dag_result["is_valid"]:
            errors.extend(dag_result["errors"])

        # Check 2: Parameter ranges
        param_result = self._validate_parameters(graph)
        checks["parameters_valid"] = param_result["is_valid"]
        if not param_result["is_valid"]:
            errors.extend(param_result["errors"])
        warnings.extend(param_result["warnings"])

        # Check 3: Stability (spectral radius)
        # Only compute if graph is a DAG (otherwise not meaningful)
        if checks["is_dag"]:
            stability_result = self._validate_stability(graph)
            checks["is_stable"] = stability_result["is_valid"]
            if not stability_result["is_valid"]:
                errors.extend(stability_result["errors"])
            warnings.extend(stability_result["warnings"])
            spectral_radius = stability_result["spectral_radius"]
        else:
            checks["is_stable"] = False
            spectral_radius = None

        # Overall validity
        is_valid = all(checks.values())

        return {
            "is_valid": is_valid,
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "metadata": {
                "spectral_radius": spectral_radius,
                "num_nodes": len(graph.nodes),
                "num_edges": len(graph.edges),
            },
        }

    def _validate_dag(self, graph: CausalGraph) -> Dict:
        """Validate that graph is a Directed Acyclic Graph (DAG).

        Args:
            graph: Causal graph to check

        Returns:
            Dict with validation result
        """
        errors = []

        # Build NetworkX directed graph
        G = nx.DiGraph()

        # Add edges
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)

        # Check for cycles
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                errors.append(
                    f"Graph contains {len(cycles)} cycle(s): {cycles[:3]}"  # Show first 3
                )
                return {"is_valid": False, "errors": errors}
        except Exception as e:
            errors.append(f"Cycle detection failed: {str(e)}")
            return {"is_valid": False, "errors": errors}

        # Verify DAG
        is_dag = nx.is_directed_acyclic_graph(G)
        if not is_dag:
            errors.append("Graph is not a DAG (contains cycles)")

        return {
            "is_valid": is_dag,
            "errors": errors,
        }

    def _validate_parameters(self, graph: CausalGraph) -> Dict:
        """Validate parameter ranges for all edges and nodes.

        Constraints:
            - effect_size ∈ [-1, 1]
            - temporal_lag_hours ≥ 0
            - node types ∈ {environmental, molecular, biomarker, genetic}

        Args:
            graph: Causal graph to check

        Returns:
            Dict with validation result
        """
        errors = []
        warnings = []

        valid_node_types = {"environmental", "molecular", "biomarker", "genetic"}
        valid_relationships = {"activates", "inhibits", "increases", "decreases", "binds"}

        # Check edge parameters
        for edge in graph.edges:
            # Effect size range
            if not -1 <= edge.effect_size <= 1:
                errors.append(
                    f"Edge {edge.source}→{edge.target}: effect_size {edge.effect_size:.3f} "
                    f"not in [-1, 1]"
                )

            # Temporal lag
            if edge.temporal_lag_hours < 0:
                errors.append(
                    f"Edge {edge.source}→{edge.target}: temporal_lag {edge.temporal_lag_hours} "
                    f"must be ≥ 0"
                )

            # Relationship type (warning only)
            if edge.relationship not in valid_relationships:
                warnings.append(
                    f"Edge {edge.source}→{edge.target}: relationship '{edge.relationship}' "
                    f"not in standard set {valid_relationships}"
                )

            # Effect size too small (warning)
            if abs(edge.effect_size) < 0.01:
                warnings.append(
                    f"Edge {edge.source}→{edge.target}: effect_size {edge.effect_size:.3f} "
                    f"very small, may be negligible"
                )

        # Check node types
        for node in graph.nodes:
            if node.type not in valid_node_types:
                errors.append(
                    f"Node {node.id}: type '{node.type}' not in "
                    f"{valid_node_types}"
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_stability(self, graph: CausalGraph) -> Dict:
        """Validate stability via spectral radius check.

        For Linear Gaussian SCM: V = (I - W)^{-1} (μ + ε)
        System is stable iff spectral_radius(W) < 1

        Args:
            graph: Causal graph to check

        Returns:
            Dict with validation result and spectral radius
        """
        errors = []
        warnings = []

        # Build weight matrix W
        n = len(graph.nodes)

        # Handle empty graph
        if n == 0:
            return {
                "is_valid": True,  # Empty graph is trivially stable
                "errors": [],
                "warnings": [],
                "spectral_radius": 0.0,
            }

        node_to_idx = {node.id: i for i, node in enumerate(graph.nodes)}

        W = np.zeros((n, n))

        for edge in graph.edges:
            try:
                i = node_to_idx[edge.target]  # row (child)
                j = node_to_idx[edge.source]  # col (parent)

                # Apply sign based on relationship
                magnitude = edge.effect_size
                if edge.relationship in ["inhibits", "decreases"]:
                    magnitude = -magnitude

                W[i, j] = magnitude
            except KeyError as e:
                errors.append(f"Edge references unknown node: {e}")
                return {
                    "is_valid": False,
                    "errors": errors,
                    "warnings": warnings,
                    "spectral_radius": None,
                }

        # Compute eigenvalues
        try:
            eigenvalues = np.linalg.eigvals(W)
            spectral_radius = float(np.max(np.abs(eigenvalues)))
        except np.linalg.LinAlgError as e:
            errors.append(f"Eigenvalue computation failed: {str(e)}")
            return {
                "is_valid": False,
                "errors": errors,
                "warnings": warnings,
                "spectral_radius": None,
            }

        # Check stability condition
        is_stable = spectral_radius < 1.0

        if not is_stable:
            errors.append(
                f"Unstable graph: spectral_radius(W) = {spectral_radius:.3f} ≥ 1. "
                f"System will diverge under SCM dynamics."
            )
        elif spectral_radius > self.SPECTRAL_RADIUS_THRESHOLD:
            warnings.append(
                f"Spectral radius {spectral_radius:.3f} is close to 1 "
                f"(threshold: {self.SPECTRAL_RADIUS_THRESHOLD}). "
                f"Predictions may be sensitive to parameter uncertainty."
            )

        return {
            "is_valid": is_stable,
            "errors": errors,
            "warnings": warnings,
            "spectral_radius": spectral_radius,
        }

    def fix_violations(self, graph: CausalGraph) -> CausalGraph:
        """Attempt to automatically fix validation violations.

        Strategies:
            - Remove cycles by deleting lowest-evidence edges
            - Cap effect sizes at 0.95 / -0.95
            - Set negative temporal lags to 0
            - Scale down all effect sizes if spectral radius ≥ 1

        Args:
            graph: Causal graph with potential violations

        Returns:
            Fixed causal graph (or original if no fixes possible)
        """
        fixed_graph = graph.model_copy(deep=True)

        # Fix 1: Cap effect sizes
        for edge in fixed_graph.edges:
            if edge.effect_size > 0.95:
                logger.warning(f"Capping effect size {edge.effect_size:.3f} → 0.95 for {edge.source}→{edge.target}")
                edge.effect_size = 0.95
            elif edge.effect_size < -0.95:
                logger.warning(f"Capping effect size {edge.effect_size:.3f} → -0.95 for {edge.source}→{edge.target}")
                edge.effect_size = -0.95

            # Fix negative temporal lags
            if edge.temporal_lag_hours < 0:
                logger.warning(f"Setting negative temporal lag {edge.temporal_lag_hours} → 0 for {edge.source}→{edge.target}")
                edge.temporal_lag_hours = 0

        # Fix 2: Remove cycles (if present)
        validation = self._validate_dag(fixed_graph)
        if not validation["is_valid"]:
            fixed_graph = self._remove_cycles(fixed_graph)

        # Fix 3: Scale down for stability
        stability = self._validate_stability(fixed_graph)
        if not stability["is_valid"] and stability["spectral_radius"] is not None:
            spectral_radius = stability["spectral_radius"]
            scale_factor = 0.95 / spectral_radius  # Scale to 0.95

            logger.warning(
                f"Scaling all effect sizes by {scale_factor:.3f} to ensure stability "
                f"(spectral radius {spectral_radius:.3f} → 0.95)"
            )

            for edge in fixed_graph.edges:
                edge.effect_size *= scale_factor

        return fixed_graph

    def _remove_cycles(self, graph: CausalGraph) -> CausalGraph:
        """Remove cycles by deleting lowest-evidence edges.

        Args:
            graph: Graph with cycles

        Returns:
            Graph with cycles removed (DAG)
        """
        # Build NetworkX graph
        G = nx.DiGraph()
        edge_map = {}  # (source, target) → Edge

        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)
            edge_map[(edge.source, edge.target)] = edge

        # Find all cycles
        cycles = list(nx.simple_cycles(G))

        if not cycles:
            return graph

        # For each cycle, remove the edge with lowest evidence
        edges_to_remove = set()

        for cycle in cycles:
            # Find edge in cycle with lowest evidence
            cycle_edges = []
            for i in range(len(cycle)):
                source = cycle[i]
                target = cycle[(i + 1) % len(cycle)]
                if (source, target) in edge_map:
                    cycle_edges.append((source, target))

            if cycle_edges:
                # Sort by evidence count (ascending)
                cycle_edges_sorted = sorted(
                    cycle_edges,
                    key=lambda e: edge_map[e].evidence.count
                )
                # Remove lowest evidence edge
                edges_to_remove.add(cycle_edges_sorted[0])
                logger.warning(
                    f"Removing edge {cycle_edges_sorted[0][0]}→{cycle_edges_sorted[0][1]} "
                    f"to break cycle {cycle}"
                )

        # Create new graph without removed edges
        filtered_edges = [
            edge for edge in graph.edges
            if (edge.source, edge.target) not in edges_to_remove
        ]

        return CausalGraph(
            nodes=graph.nodes,
            edges=filtered_edges,
            genetic_modifiers=graph.genetic_modifiers,
        )
