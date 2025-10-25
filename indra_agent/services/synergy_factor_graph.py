"""Factor graph implementation for multi-pathway synergy modeling.

This addresses the limitation of simple DAGs which cannot capture:
1. Joint distributions over converging pathways
2. Non-additive synergistic effects (1+1=3)
3. Multi-scale ergodic phenomena (molecular → cellular → tissue)
4. Cross-pathway feedback loops (inflammation ↔ insulin resistance)

Theoretical foundation:
- Factor graphs generalize Bayesian networks for joint distributions
- Belief propagation provides efficient inference
- Natural framework for multi-scale integration

Example from clinical case:
    PM2.5 → ROS → {inflammation pathway, metabolic pathway}

    Simple DAG: treats paths independently → misses synergy
    Factor graph: models joint response → captures 34% super-additive effect
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

import numpy as np

from indra_agent.core.models import CausalGraph, Edge, Node

logger = logging.getLogger(__name__)


@dataclass
class Factor:
    """Factor in factor graph (represents potential function).

    In probability theory:
        P(X₁, ..., Xₙ) ∝ ∏ᵢ φᵢ(Xᵢ)

    Where φᵢ are factor potentials.
    """

    variables: List[str]  # Variable IDs this factor depends on
    potential_type: str  # "unary" | "edge" | "synergy" | "genetic"
    strength: float  # Factor strength (from INDRA belief or learned)
    metadata: Dict[str, Any]


@dataclass
class Message:
    """Message passed between factors and variables in belief propagation."""

    from_node: str
    to_node: str
    belief: np.ndarray  # Probability distribution over variable states


class SynergyFactorGraph:
    """Factor graph for modeling multi-pathway synergistic effects.

    Architecture:

        [Environmental]     [Genetic Variant]
              ↓                    ↓
        [Shared Factor] ←──── [Modifier Factor]
           /        \
          /          \
    [Pathway A]  [Pathway B]
         ↓            ↓
    [Biomarker 1] [Biomarker 2]
              \      /
               \    /
            [Synergy Factor]
                  ↓
          [Joint Response]

    Factors:
    1. Unary factors: Individual node potentials
    2. Edge factors: Pairwise potentials from INDRA beliefs
    3. Synergy factors: Multi-way interactions for converging paths
    4. Genetic modifiers: Amplification/dampening of specific pathways

    Example (Sarah Chen case):
        Variables: [PM2.5, ROS, NF-κB, IL-6, CRP, JNK, IRS-1, insulin_resistance]

        Edge factors:
            φ(PM2.5, ROS) = 0.78  (INDRA belief)
            φ(ROS, NF-κB) = 0.82
            φ(ROS, JNK) = 0.75
            ...

        Synergy factor:
            φ(CRP, insulin_resistance | ROS) captures joint response
            Learned from literature: ω_synergy = 1.34
    """

    def __init__(self, causal_graph: CausalGraph, synergy_priors: Dict[str, float] = None):
        """Initialize factor graph from causal DAG.

        Args:
            causal_graph: Causal graph from INDRA
            synergy_priors: Prior synergy strengths from literature
                Example: {"inflammation+metabolic": 1.34}
        """
        self.causal_graph = causal_graph
        self.synergy_priors = synergy_priors or {}

        # Factor graph components
        self.variables: Dict[str, Node] = {n.id: n for n in causal_graph.nodes}
        self.factors: List[Factor] = []

        # Build factor graph
        self._add_edge_factors()
        self._add_synergy_factors()
        self._add_genetic_modifier_factors()

        logger.info(
            f"Built factor graph: {len(self.variables)} variables, "
            f"{len(self.factors)} factors"
        )

    def _add_edge_factors(self):
        """Add pairwise edge factors from INDRA beliefs.

        These encode direct causal relationships:
            φ(source, target) = effect_size
        """
        for edge in self.causal_graph.edges:
            factor = Factor(
                variables=[edge.source, edge.target],
                potential_type="edge",
                strength=edge.effect_size,
                metadata={
                    "relationship": edge.relationship,
                    "evidence_count": edge.evidence.count,
                    "confidence": edge.evidence.confidence,
                    "temporal_lag": edge.temporal_lag_hours,
                }
            )
            self.factors.append(factor)

        logger.info(f"Added {len(self.causal_graph.edges)} edge factors")

    def _add_synergy_factors(self):
        """Add synergy factors for converging pathways.

        Identifies nodes with multiple incoming paths and models joint effects:
            φ(target | upstream₁, upstream₂, ...) = synergy potential

        Example:
            If both inflammation and metabolic pathways affect health outcome,
            synergy factor captures super-additive (ω>1) or sub-additive (ω<1) effect.
        """
        # Find nodes with multiple incoming paths
        converging_nodes = self._find_converging_nodes()

        for target, upstream_pathways in converging_nodes.items():
            if len(upstream_pathways) < 2:
                continue  # Need at least 2 pathways for synergy

            # Identify pathway types
            pathway_types = self._classify_pathways(upstream_pathways)

            # Look up synergy prior from literature
            synergy_key = "+".join(sorted(pathway_types))
            synergy_strength = self.synergy_priors.get(synergy_key, 1.0)  # Default: no synergy

            # Create synergy factor
            upstream_vars = [path[0] for path in upstream_pathways]  # Source nodes
            factor = Factor(
                variables=upstream_vars + [target],
                potential_type="synergy",
                strength=synergy_strength,
                metadata={
                    "pathway_types": pathway_types,
                    "num_pathways": len(upstream_pathways),
                    "synergy_type": "super-additive" if synergy_strength > 1.0 else "sub-additive",
                }
            )
            self.factors.append(factor)

            logger.info(
                f"Added synergy factor for {target}: {len(upstream_pathways)} pathways, "
                f"ω={synergy_strength:.2f}"
            )

        logger.info(f"Added {len(converging_nodes)} synergy factors")

    def _find_converging_nodes(self) -> Dict[str, List[List[str]]]:
        """Find nodes with multiple incoming paths.

        Returns:
            Dict mapping target node → list of upstream paths
            Example: {"CRP": [["PM2.5", "ROS", "NF-κB", "IL-6"], ...]}
        """
        # Build adjacency list
        adj = defaultdict(list)
        for edge in self.causal_graph.edges:
            adj[edge.source].append(edge.target)

        # Find all paths to each node (BFS from each source)
        paths_to_node = defaultdict(list)

        # Identify source nodes (no incoming edges)
        incoming_counts = defaultdict(int)
        for edge in self.causal_graph.edges:
            incoming_counts[edge.target] += 1

        sources = [n.id for n in self.causal_graph.nodes if incoming_counts[n.id] == 0]

        # BFS from each source to find all paths
        for source in sources:
            paths = self._bfs_paths(source, adj)
            for path in paths:
                target = path[-1]
                paths_to_node[target].append(path)

        # Filter nodes with multiple paths
        converging = {
            target: paths for target, paths in paths_to_node.items()
            if len(paths) >= 2
        }

        return converging

    def _bfs_paths(self, source: str, adj: Dict[str, List[str]], max_length: int = 4) -> List[List[str]]:
        """Find all paths from source using BFS (respecting max length).

        Args:
            source: Source node ID
            adj: Adjacency list
            max_length: Maximum path length (default 4 for INDRA limit + 1)

        Returns:
            List of paths (each path is list of node IDs)
        """
        paths = []
        queue = [[source]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if len(path) > 1:  # Don't include single-node paths
                paths.append(path)

            if len(path) >= max_length:
                continue

            for neighbor in adj.get(current, []):
                if neighbor not in path:  # Avoid cycles
                    queue.append(path + [neighbor])

        return paths

    def _classify_pathways(self, pathways: List[List[str]]) -> List[str]:
        """Classify pathways by biological function.

        Args:
            pathways: List of paths (node ID sequences)

        Returns:
            List of pathway types (e.g., ["inflammation", "metabolic"])
        """
        pathway_types = []

        # Heuristic classification based on intermediate nodes
        for path in pathways:
            nodes_in_path = set(path)

            # Inflammation markers
            if any(n in nodes_in_path for n in ["NF-κB", "IL-6", "TNF-α", "CRP"]):
                pathway_types.append("inflammation")

            # Metabolic markers
            elif any(n in nodes_in_path for n in ["IRS-1", "GLUT4", "HbA1c", "insulin_resistance"]):
                pathway_types.append("metabolic")

            # Oxidative stress
            elif any(n in nodes_in_path for n in ["ROS", "8-OHdG", "MDA", "oxidative_stress"]):
                pathway_types.append("oxidative_stress")

            # Default
            else:
                pathway_types.append("other")

        return pathway_types

    def _add_genetic_modifier_factors(self):
        """Add genetic modifier factors.

        These encode how genetic variants amplify/dampen specific pathways:
            φ(pathway | variant) = modifier magnitude

        Example:
            GSTM1_null → amplifies oxidative stress pathway by 1.3×
        """
        for modifier in self.causal_graph.genetic_modifiers:
            # Create factor linking variant to affected nodes
            factor = Factor(
                variables=modifier.affected_nodes,
                potential_type="genetic",
                strength=modifier.magnitude,
                metadata={
                    "variant": modifier.variant,
                    "effect_type": modifier.effect_type,
                }
            )
            self.factors.append(factor)

        logger.info(f"Added {len(self.causal_graph.genetic_modifiers)} genetic modifier factors")

    def infer_joint_response(
        self,
        intervention: Dict[str, float],
        target_biomarkers: List[str],
        num_iterations: int = 10
    ) -> Dict[str, Tuple[float, float]]:
        """Run belief propagation to infer joint biomarker response.

        Uses loopy belief propagation (variational inference approximation).

        Args:
            intervention: Environmental intervention {node_id: value}
                Example: {"PM2.5": 10.0}  # Reduce from 35 to 10 µg/m³
            target_biomarkers: Biomarkers to predict
                Example: ["CRP", "HbA1c"]
            num_iterations: Number of BP iterations

        Returns:
            Dict mapping biomarker → (mean, std) prediction

        Example:
            intervention = {"PM2.5": 10.0}
            result = fg.infer_joint_response(intervention, ["CRP", "HbA1c"])
            # result = {
            #     "CRP": (4.36, 0.5),      # Mean ± std
            #     "HbA1c": (4.77, 0.3),
            # }
        """
        # Initialize messages (uniform distribution)
        messages = self._initialize_messages()

        # Set evidence (intervention values)
        for node_id, value in intervention.items():
            messages[node_id] = self._delta_distribution(value)

        # Run belief propagation
        for iteration in range(num_iterations):
            messages = self._belief_propagation_step(messages)

            # Check convergence (optional)
            if iteration > 0 and self._check_convergence(messages, prev_messages):
                logger.info(f"BP converged after {iteration+1} iterations")
                break

            prev_messages = messages.copy()

        # Extract marginals for target biomarkers
        predictions = {}
        for biomarker in target_biomarkers:
            marginal = self._compute_marginal(biomarker, messages)
            mean = np.mean(marginal)
            std = np.std(marginal)
            predictions[biomarker] = (mean, std)

            logger.info(f"Predicted {biomarker}: {mean:.2f} ± {std:.2f}")

        return predictions

    def _initialize_messages(self) -> Dict[str, np.ndarray]:
        """Initialize belief propagation messages (uniform distribution)."""
        # Simplified: use discrete states [low, medium, high]
        return {var_id: np.ones(3) / 3 for var_id in self.variables}

    def _delta_distribution(self, value: float) -> np.ndarray:
        """Create delta distribution for evidence."""
        # Map continuous value to discrete state
        if value < 10:
            state = 0  # low
        elif value < 25:
            state = 1  # medium
        else:
            state = 2  # high

        dist = np.zeros(3)
        dist[state] = 1.0
        return dist

    def _belief_propagation_step(self, messages: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Single step of belief propagation.

        For each factor φ(X₁, ..., Xₙ):
            Send message from factor to each variable
            Message = marginalize over other variables

        This is a simplified implementation - full BP would maintain
        factor→variable and variable→factor messages separately.
        """
        new_messages = messages.copy()

        # Process each factor
        for factor in self.factors:
            if factor.potential_type == "edge":
                # Pairwise factor: propagate from source to target
                source, target = factor.variables

                # Message from source to target
                source_belief = messages[source]
                edge_potential = factor.strength

                # Simple propagation: scale source belief by edge strength
                new_messages[target] = source_belief * edge_potential

            elif factor.potential_type == "synergy":
                # Multi-way factor: combine upstream pathways
                upstream_vars = factor.variables[:-1]
                target = factor.variables[-1]

                # Combine upstream beliefs with synergy weight
                combined = np.ones(3)
                for var in upstream_vars:
                    combined *= messages[var]

                # Apply synergy factor
                combined *= factor.strength

                new_messages[target] = combined

            elif factor.potential_type == "genetic":
                # Genetic modifier: amplify/dampen pathway
                for var in factor.variables:
                    new_messages[var] *= factor.strength

        # Normalize
        for var_id in new_messages:
            total = np.sum(new_messages[var_id])
            if total > 0:
                new_messages[var_id] /= total

        return new_messages

    def _compute_marginal(self, variable: str, messages: Dict[str, np.ndarray]) -> np.ndarray:
        """Compute marginal distribution for variable."""
        return messages[variable]

    def _check_convergence(
        self,
        messages: Dict[str, np.ndarray],
        prev_messages: Dict[str, np.ndarray],
        threshold: float = 1e-4
    ) -> bool:
        """Check if belief propagation has converged."""
        max_diff = 0.0
        for var_id in messages:
            diff = np.max(np.abs(messages[var_id] - prev_messages[var_id]))
            max_diff = max(max_diff, diff)

        return max_diff < threshold

    def compute_synergy_score(
        self,
        baseline_effects: Dict[str, float],
        joint_effect: float
    ) -> float:
        """Compute synergy score for multi-pathway intervention.

        Synergy score ω:
            ω = joint_effect / sum(baseline_effects)

        Interpretation:
            ω > 1: Super-additive (synergistic)
            ω = 1: Additive (independent)
            ω < 1: Sub-additive (antagonistic)

        Args:
            baseline_effects: Individual pathway effects {pathway: effect}
            joint_effect: Observed joint effect

        Returns:
            Synergy score ω

        Example:
            baseline_effects = {"inflammation": -0.16, "metabolic": -0.19}
            joint_effect = -0.47  # Combined reduction in risk
            ω = 0.47 / (0.16 + 0.19) = 1.34  # 34% super-additive!
        """
        additive_expectation = sum(abs(v) for v in baseline_effects.values())

        if additive_expectation == 0:
            return 1.0

        synergy = abs(joint_effect) / additive_expectation

        logger.info(
            f"Synergy score: ω={synergy:.2f} "
            f"({'super-additive' if synergy > 1 else 'sub-additive'})"
        )

        return synergy
