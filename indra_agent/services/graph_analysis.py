"""Graph analysis service for identifying synergies and structural patterns.

This service provides algorithms for analyzing causal graph structure to detect:
- Convergent nodes (multiple incoming edges)
- Feedback loops (cycles)
- Multi-target synergies (single intervention affecting multiple biomarkers)
"""

import logging
from typing import Dict, List, Set, Tuple

from indra_agent.core.models import CausalGraph, Edge, Node

logger = logging.getLogger(__name__)


class GraphAnalysisService:
    """Service for analyzing causal graph structure and identifying synergies."""

    def find_convergent_nodes(
        self, graph: CausalGraph, min_in_degree: int = 2
    ) -> List[Dict]:
        """Find convergent nodes where multiple causal paths meet.

        Convergent nodes are high-value intervention targets because they integrate
        signals from multiple upstream pathways. For example, IRS-1 receives inputs
        from both IL-6 (inflammatory) and JNK (metabolic stress).

        Args:
            graph: CausalGraph with nodes and edges
            min_in_degree: Minimum number of incoming edges to be considered convergent

        Returns:
            List of convergent nodes with metadata: [{node_id, label, type, in_degree, incoming_sources}]
        """
        # Build incoming edge map
        incoming_edges: Dict[str, List[Edge]] = {node.id: [] for node in graph.nodes}

        for edge in graph.edges:
            incoming_edges[edge.target].append(edge)

        # Filter convergent nodes
        convergent = []
        for node in graph.nodes:
            in_degree = len(incoming_edges[node.id])
            if in_degree >= min_in_degree:
                convergent.append({
                    "node_id": node.id,
                    "label": node.label,
                    "type": node.type,
                    "in_degree": in_degree,
                    "incoming_sources": [
                        {
                            "source_id": edge.source,
                            "relationship": edge.relationship,
                            "effect_size": edge.effect_size
                        }
                        for edge in incoming_edges[node.id]
                    ]
                })

        # Sort by in_degree descending
        convergent.sort(key=lambda x: x["in_degree"], reverse=True)

        logger.info(f"Found {len(convergent)} convergent nodes (min_in_degree={min_in_degree})")
        return convergent

    def detect_feedback_loops(self, graph: CausalGraph) -> List[Dict]:
        """Detect feedback loops (cycles) in the causal graph.

        Feedback loops are critical for understanding disease dynamics. For example,
        the inflammation-insulin resistance loop: IL-6 → IRS-1 inhibition → hyperglycemia
        → AGEs → more inflammation (back to IL-6).

        Args:
            graph: CausalGraph with nodes and edges

        Returns:
            List of cycles: [{nodes: List[str], edges: List[Dict], length: int}]
        """
        # Build adjacency list
        adjacency: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}
        edge_map: Dict[Tuple[str, str], Edge] = {}

        for edge in graph.edges:
            adjacency[edge.source].append(edge.target)
            edge_map[(edge.source, edge.target)] = edge

        # DFS-based cycle detection
        all_cycles = []
        visited_global: Set[str] = set()

        def dfs_cycle(start: str, current: str, path: List[str], visited_in_path: Set[str]):
            """DFS to find cycles from a starting node."""
            if current in visited_in_path:
                # Found a cycle
                cycle_start_idx = path.index(current)
                cycle_nodes = path[cycle_start_idx:] + [current]

                # Build cycle with edge details
                cycle_edges = []
                for i in range(len(cycle_nodes) - 1):
                    edge = edge_map.get((cycle_nodes[i], cycle_nodes[i + 1]))
                    if edge:
                        cycle_edges.append({
                            "source": edge.source,
                            "target": edge.target,
                            "relationship": edge.relationship,
                            "effect_size": edge.effect_size
                        })

                all_cycles.append({
                    "nodes": cycle_nodes,
                    "edges": cycle_edges,
                    "length": len(cycle_nodes) - 1
                })
                return

            if current in visited_global:
                return

            visited_in_path.add(current)
            path.append(current)

            for neighbor in adjacency.get(current, []):
                dfs_cycle(start, neighbor, path, visited_in_path)

            path.pop()
            visited_in_path.remove(current)

        # Find all cycles
        for node_id in adjacency.keys():
            if node_id not in visited_global:
                dfs_cycle(node_id, node_id, [], set())
                visited_global.add(node_id)

        # Remove duplicate cycles (same nodes, different starting points)
        unique_cycles = []
        seen_sets = []
        for cycle in all_cycles:
            cycle_set = frozenset(cycle["nodes"][:-1])  # Exclude duplicate last node
            if cycle_set not in seen_sets:
                seen_sets.append(cycle_set)
                unique_cycles.append(cycle)

        logger.info(f"Found {len(unique_cycles)} feedback loops in graph")
        return unique_cycles

    def find_pathways(
        self, graph: CausalGraph, source_id: str, target_id: str, max_depth: int = 5
    ) -> List[Dict]:
        """Find all pathways from source to target within max_depth.

        Args:
            graph: CausalGraph with nodes and edges
            source_id: Source node ID
            target_id: Target node ID
            max_depth: Maximum path length

        Returns:
            List of pathways: [{nodes: List[str], edges: List[Dict], length: int, total_effect: float}]
        """
        # Build adjacency list
        adjacency: Dict[str, List[str]] = {node.id: [] for node in graph.nodes}
        edge_map: Dict[Tuple[str, str], Edge] = {}

        for edge in graph.edges:
            adjacency[edge.source].append(edge.target)
            edge_map[(edge.source, edge.target)] = edge

        # BFS to find all paths
        pathways = []
        queue = [(source_id, [source_id], 0)]

        while queue:
            current, path, depth = queue.pop(0)

            if current == target_id:
                # Found a pathway
                pathway_edges = []
                total_effect = 1.0

                for i in range(len(path) - 1):
                    edge = edge_map.get((path[i], path[i + 1]))
                    if edge:
                        pathway_edges.append({
                            "source": edge.source,
                            "target": edge.target,
                            "relationship": edge.relationship,
                            "effect_size": edge.effect_size
                        })
                        # Multiply effect sizes along path
                        total_effect *= edge.effect_size

                pathways.append({
                    "nodes": path,
                    "edges": pathway_edges,
                    "length": len(path) - 1,
                    "total_effect": total_effect
                })
                continue

            if depth >= max_depth:
                continue

            for neighbor in adjacency.get(current, []):
                if neighbor not in path:  # Avoid cycles in path search
                    queue.append((neighbor, path + [neighbor], depth + 1))

        logger.info(f"Found {len(pathways)} pathways from {source_id} to {target_id}")
        return pathways

    def compute_multi_target_synergy(
        self,
        graph: CausalGraph,
        intervention_node_id: str,
        target_biomarkers: List[str]
    ) -> Dict:
        """Compute synergy score for a single intervention affecting multiple targets.

        Synergy occurs when a single intervention affects multiple disease pathways
        simultaneously. For example, reducing PM2.5 exposure decreases both inflammation
        (CRP) and insulin resistance (HbA1c) via shared oxidative stress pathway.

        Synergy score formula:
            S = (N_affected / N_total) * (1 + convergence_bonus)

        Where:
        - N_affected: Number of target biomarkers affected by intervention
        - N_total: Total number of target biomarkers
        - convergence_bonus: +0.5 if intervention affects a convergent node

        Score interpretation:
        - S < 1.0: Sub-additive (independent pathways, no synergy)
        - S = 1.0: Additive (linear effects)
        - S > 1.0: Super-additive (true synergy from convergence)

        Args:
            graph: CausalGraph with nodes and edges
            intervention_node_id: Node ID to intervene on
            target_biomarkers: List of biomarker node IDs to optimize

        Returns:
            Synergy analysis: {
                synergy_score: float,
                affected_targets: List[str],
                pathways_per_target: Dict[str, List],
                convergent_nodes_affected: List[str],
                explanation: str
            }
        """
        # Find pathways from intervention to each target
        pathways_per_target: Dict[str, List] = {}
        affected_targets = []

        for target_id in target_biomarkers:
            pathways = self.find_pathways(
                graph=graph,
                source_id=intervention_node_id,
                target_id=target_id,
                max_depth=5
            )

            if pathways:
                pathways_per_target[target_id] = pathways
                affected_targets.append(target_id)

        # Calculate base synergy score
        n_affected = len(affected_targets)
        n_total = len(target_biomarkers)
        base_score = n_affected / n_total if n_total > 0 else 0.0

        # Detect convergent nodes in affected pathways
        convergent_nodes_in_pathways = self._find_convergent_nodes_in_pathways(
            graph=graph,
            pathways_per_target=pathways_per_target
        )

        # Apply convergence bonus
        convergence_bonus = 0.5 if len(convergent_nodes_in_pathways) > 0 else 0.0
        synergy_score = base_score * (1.0 + convergence_bonus)

        # Generate explanation
        if synergy_score > 1.0:
            explanation = (
                f"Super-additive synergy (score={synergy_score:.2f}): "
                f"Single intervention affects {n_affected}/{n_total} targets via "
                f"{len(convergent_nodes_in_pathways)} convergent nodes"
            )
        elif synergy_score == 1.0:
            explanation = f"Additive effects (score=1.0): Affects {n_affected}/{n_total} targets independently"
        else:
            explanation = f"Limited synergy (score={synergy_score:.2f}): Only {n_affected}/{n_total} targets affected"

        logger.info(f"Synergy score: {synergy_score:.2f} for intervention on {intervention_node_id}")

        return {
            "synergy_score": synergy_score,
            "affected_targets": affected_targets,
            "pathways_per_target": pathways_per_target,
            "convergent_nodes_affected": convergent_nodes_in_pathways,
            "explanation": explanation
        }

    def _find_convergent_nodes_in_pathways(
        self,
        graph: CausalGraph,
        pathways_per_target: Dict[str, List]
    ) -> List[str]:
        """Find convergent nodes that appear in multiple target pathways.

        These are the key integration points where cross-pathway synergy occurs.

        Args:
            graph: CausalGraph
            pathways_per_target: Dict mapping target_id → List of pathways

        Returns:
            List of convergent node IDs that appear in multiple pathways
        """
        # Count how many different targets each node appears in
        node_target_count: Dict[str, Set[str]] = {}

        for target_id, pathways in pathways_per_target.items():
            for pathway in pathways:
                for node_id in pathway["nodes"]:
                    if node_id not in node_target_count:
                        node_target_count[node_id] = set()
                    node_target_count[node_id].add(target_id)

        # Find nodes that affect multiple targets
        convergent_nodes = [
            node_id for node_id, targets in node_target_count.items()
            if len(targets) > 1
        ]

        logger.debug(f"Found {len(convergent_nodes)} convergent nodes in pathways")
        return convergent_nodes
