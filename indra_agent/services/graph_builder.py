"""Graph builder service for constructing causal graphs from INDRA paths.

This service converts INDRA paths into the causal graph format required by
the API specification, including effect size calculation and temporal lag estimation.
"""

import logging
from typing import Any, Dict, List, Set

from indra_agent.config.cached_responses import get_genetic_modifier
from indra_agent.core.models import (
    CausalGraph,
    Edge,
    Evidence,
    GeneticModifier,
    Grounding,
    Node,
)

logger = logging.getLogger(__name__)


class GraphBuilderService:
    """Service for building causal graphs from INDRA paths."""

    # Temporal lag estimates based on mechanism type
    TEMPORAL_LAG_MAP = {
        "Phosphorylation": 1,  # Fast signaling
        "Complex": 2,  # Protein binding
        "Activation": 6,  # Transcription factor
        "IncreaseAmount": 12,  # Gene expression
        "DecreaseAmount": 12,  # Gene repression
        "Inhibition": 6,  # Inhibition
        "default": 6,
    }

    def build_causal_graph(
        self,
        paths: List[Dict[str, Any]],
        genetics: Dict[str, str],
    ) -> CausalGraph:
        """Build causal graph from INDRA paths.

        Args:
            paths: List of INDRA paths
            genetics: User genetic variants

        Returns:
            CausalGraph with nodes, edges, and genetic modifiers
        """
        # Collect all unique nodes
        node_map: Dict[str, Node] = {}
        edges: List[Edge] = []

        # Process each path
        for path in paths:
            # Add nodes
            for node_data in path.get("nodes", []):
                node_id = node_data["id"]
                if node_id not in node_map:
                    node_map[node_id] = self._create_node(node_data)

            # Add edges
            for edge_data in path.get("edges", []):
                edge = self._create_edge(edge_data)
                edges.append(edge)

        # Remove duplicate edges (keep highest evidence)
        edges = self._deduplicate_edges(edges)

        # Apply genetic modifiers
        genetic_modifiers = self._apply_genetic_modifiers(genetics, node_map)

        return CausalGraph(
            nodes=list(node_map.values()),
            edges=edges,
            genetic_modifiers=genetic_modifiers,
        )

    def _create_node(self, node_data: Dict[str, Any]) -> Node:
        """Create Node from INDRA node data.

        Args:
            node_data: Node data from INDRA

        Returns:
            Node instance
        """
        node_id = node_data["id"]
        grounding_data = node_data.get("grounding", {})

        # Determine node type
        node_type = self._infer_node_type(node_id, grounding_data.get("db", ""))

        return Node(
            id=node_id,
            type=node_type,
            label=node_data.get("name", node_id),
            grounding=Grounding(
                database=grounding_data.get("db", "UNKNOWN"),
                identifier=grounding_data.get("id", ""),
            ),
        )

    def _infer_node_type(self, node_id: str, database: str) -> str:
        """Infer node type from ID and database.

        Args:
            node_id: Node identifier
            database: Database (MESH, HGNC, GO, CHEBI)

        Returns:
            Node type (environmental, molecular, biomarker, genetic)
        """
        # Environmental exposures
        if node_id in ["PM2.5", "PM10", "ozone", "NO2"] or database == "MESH":
            return "environmental"

        # Biological processes
        if database == "GO" or node_id in ["oxidative_stress", "inflammation"]:
            return "molecular"

        # Biomarkers (typical clinical markers)
        if node_id in ["CRP", "IL6", "8-OHdG"]:
            return "biomarker"

        # Default to molecular
        return "molecular"

    def _create_edge(self, edge_data: Dict[str, Any]) -> Edge:
        """Create Edge from INDRA edge data.

        Args:
            edge_data: Edge data from INDRA

        Returns:
            Edge instance
        """
        evidence_count = edge_data.get("evidence_count", 0)
        belief = edge_data.get("belief", 0.5)
        pmids = edge_data.get("pmids", [])[:3]  # Limit to 3 PMIDs

        # Calculate effect size from INDRA belief
        effect_size = self._calculate_effect_size(belief, evidence_count)

        # Estimate temporal lag
        stmt_type = edge_data.get("statement_type", "Activation")
        temporal_lag = self.TEMPORAL_LAG_MAP.get(stmt_type, self.TEMPORAL_LAG_MAP["default"])

        # Create evidence summary
        relationship = edge_data.get("relationship", "activates")
        source = edge_data.get("source", "")
        target = edge_data.get("target", "")
        summary = f"{source} {relationship} {target}"

        return Edge(
            source=source,
            target=target,
            relationship=relationship,
            evidence=Evidence(
                count=evidence_count,
                confidence=belief,
                sources=pmids,
                summary=summary,
            ),
            effect_size=effect_size,
            temporal_lag_hours=temporal_lag,
        )

    def _calculate_effect_size(self, belief: float, evidence_count: int) -> float:
        """Calculate effect size from INDRA belief score.

        Args:
            belief: INDRA belief score (0-1)
            evidence_count: Number of supporting papers

        Returns:
            Effect size in [0, 1] range
        """
        # Base effect from belief
        effect = belief * 0.8

        # Boost for high evidence
        if evidence_count > 100:
            effect += 0.15
        elif evidence_count > 50:
            effect += 0.10
        elif evidence_count > 20:
            effect += 0.05

        # Cap at 0.95 (avoid determinism)
        return min(effect, 0.95)

    def _deduplicate_edges(self, edges: List[Edge]) -> List[Edge]:
        """Remove duplicate edges, keeping highest evidence.

        Args:
            edges: List of edges (may contain duplicates)

        Returns:
            Deduplicated list of edges
        """
        edge_map: Dict[tuple, Edge] = {}

        for edge in edges:
            key = (edge.source, edge.target, edge.relationship)

            # Keep edge with highest evidence count
            if key not in edge_map or edge.evidence.count > edge_map[key].evidence.count:
                edge_map[key] = edge

        return list(edge_map.values())

    def _apply_genetic_modifiers(
        self, genetics: Dict[str, str], node_map: Dict[str, Node]
    ) -> List[GeneticModifier]:
        """Apply genetic modifiers to causal graph.

        Args:
            genetics: User genetic variants
            node_map: Map of node IDs to Node objects

        Returns:
            List of genetic modifiers
        """
        modifiers = []
        node_ids = set(node_map.keys())

        for gene, variant in genetics.items():
            # Format as variant key
            variant_key = f"{gene}_{variant.replace('/', '')}"

            # Get modifier info
            modifier_info = get_genetic_modifier(variant_key)
            if not modifier_info:
                continue

            # Check if any affected nodes are in graph
            affected_nodes = modifier_info.get("affected_nodes", [])
            present_nodes = [n for n in affected_nodes if n in node_ids]

            if present_nodes:
                modifiers.append(
                    GeneticModifier(
                        variant=variant_key,
                        affected_nodes=present_nodes,
                        effect_type=modifier_info["effect_type"],
                        magnitude=modifier_info["magnitude"],
                    )
                )

        return modifiers

    def generate_explanations(
        self,
        causal_graph: CausalGraph,
        environmental_data: Dict[str, Any],
        genetics: Dict[str, str],
    ) -> List[str]:
        """Generate human-readable explanations from causal graph.

        Args:
            causal_graph: Constructed causal graph
            environmental_data: Environmental context data
            genetics: User genetic variants

        Returns:
            List of 3-5 explanation strings (< 200 chars each)
        """
        explanations = []

        # Environmental delta
        if "delta" in environmental_data:
            delta = environmental_data["delta"]
            explanations.append(
                f"PM2.5 exposure {delta['description']} ({delta['old_value']} to {delta['new_value']} µg/m³)"
            )

        # Genetic context
        if genetics and causal_graph.genetic_modifiers:
            modifier = causal_graph.genetic_modifiers[0]
            explanations.append(
                f"Your {modifier.variant} variant {modifier.effect_type} the response by {int((modifier.magnitude - 1) * 100)}%"
            )

        # Causal mechanism
        if causal_graph.edges:
            # Find highest evidence edge
            top_edge = max(causal_graph.edges, key=lambda e: e.evidence.count)
            explanations.append(
                f"{top_edge.source} {top_edge.relationship} {top_edge.target} "
                f"({top_edge.evidence.count} papers, confidence: {top_edge.evidence.confidence:.2f})"
            )

        # Path summary
        if len(causal_graph.nodes) >= 3:
            node_names = [n.label for n in causal_graph.nodes[:3]]
            explanations.append(f"Causal chain: {' → '.join(node_names)}")

        # Expected outcome (if we have target biomarker)
        biomarker_nodes = [n for n in causal_graph.nodes if n.type == "biomarker"]
        if biomarker_nodes:
            biomarker = biomarker_nodes[0]
            explanations.append(
                f"Expected impact on {biomarker.label} based on mechanistic evidence"
            )

        # Ensure we have 3-5 explanations
        while len(explanations) < 3:
            explanations.append(f"Analysis based on {len(causal_graph.edges)} causal relationships")

        return explanations[:5]  # Max 5
