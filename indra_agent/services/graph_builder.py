"""Graph builder service for constructing causal graphs from INDRA paths.

This service converts INDRA paths into the causal graph format required by
the API specification, including effect size calculation and temporal lag estimation.
"""

import logging
from typing import Any, Dict, List, Set

import networkx as nx
from indra.statements import Statement

from indra_agent.config.genetic_modifiers import get_genetic_modifier
from indra_agent.core.models import (
    CausalGraph,
    Edge,
    Evidence,
    GeneticModifier,
    Grounding,
    Node,
)
from indra_agent.services.indranet_service import IndraNetworkResult

logger = logging.getLogger(__name__)


class GraphBuilderService:
    """Service for building causal graphs from INDRA paths.

    IMPORTANT - Node Retention Policy:
    DO NOT implement Markov condition pruning (removing intermediate nodes).
    ALL nodes from INDRA paths must be retained because:
    1. Mechanistic nodes (e.g., NF-κB) are drug targets
    2. Intermediate nodes are genetic modifier attachment points
    3. Full chains provide biological interpretability for clinicians
    4. Pruning violates causal semantics (fabricates d-separation)

    See ARCHITECTURE_FIX_PLAN.md Issue #2 for details.
    """

    # Effect size calculation parameters (FIXED per brutalist critique)
    # Use raw INDRA belief scores - no artificial scaling
    MAX_EFFECT = 0.98  # Stability cap for numerical stability (not saturation)
    EVIDENCE_WEIGHT_SCALE = 10.0  # Denominator for log evidence bonus
    MAX_EVIDENCE_BONUS = 0.15  # Cap evidence bonus to avoid inflating weak beliefs

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
        effect_modifiers: Dict[str, float] = None,
    ) -> CausalGraph:
        """Build causal graph from INDRA paths.

        Args:
            paths: List of INDRA paths
            genetics: User genetic variants (DEPRECATED - use effect_modifiers)
            effect_modifiers: Optional dict from VCFParser.to_effect_modifiers()
                Example: {"GSTM1_null": 2.34, "TCF7L2_rs7903146": 1.225}
                These are zygosity-adjusted, literature-derived effect sizes.

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

        # Apply genetic modifiers (preferring effect_modifiers from VCF parser)
        genetic_modifiers = self._apply_genetic_modifiers(
            genetics, node_map, effect_modifiers
        )

        return CausalGraph(
            nodes=list(node_map.values()),
            edges=edges,
            genetic_modifiers=genetic_modifiers,
        )

    def build_causal_graph_from_indranet(
        self,
        indranet_result: IndraNetworkResult,
        genetics: Dict[str, str],
        effect_modifiers: Dict[str, float] = None,
    ) -> CausalGraph:
        """Build causal graph from IndraNetworkResult.

        This method converts the NetworkX graph and INDRA statements from
        IndraNetService into the API-compliant CausalGraph format.

        Args:
            indranet_result: Result from IndraNetService.build_biomarker_network()
            genetics: User genetic variants (DEPRECATED - use effect_modifiers)
            effect_modifiers: Optional dict from VCFParser.to_effect_modifiers()

        Returns:
            CausalGraph with nodes, edges, and genetic modifiers
        """
        logger.info(
            f"Building causal graph from IndraNet: "
            f"{len(indranet_result.node_names)} nodes, {indranet_result.edge_count} edges"
        )

        # Collect nodes from NetworkX graph
        node_map: Dict[str, Node] = {}
        for node_id in indranet_result.graph.nodes():
            # Get node data from graph
            node_data = indranet_result.graph.nodes[node_id]

            # Create node
            node_map[node_id] = self._create_node_from_name(
                node_id, node_data
            )

        # Collect edges from NetworkX graph
        edges: List[Edge] = []
        for source, target, edge_data in indranet_result.graph.edges(data=True):
            # Get belief and evidence from IndraNet metadata
            belief = indranet_result.belief_scores.get((source, target), 0.5)
            evidence_count = indranet_result.evidence_counts.get((source, target), 0)

            # Determine relationship type from edge sign
            # NOTE: Map to Pydantic enum values: ["activates", "inhibits", "increases", "decreases"]
            sign = edge_data.get("sign", 0)
            if sign > 0:
                relationship = "activates"
            elif sign < 0:
                relationship = "inhibits"
            else:
                # Unsigned edge (sign=0) - use generic "increases"
                # This avoids ValidationError from "regulates" not in enum
                relationship = "increases"

            # Get statement type from edge data
            stmt_type = edge_data.get("stmt_type", "Activation")

            # Calculate effect size
            effect_size = self._calculate_effect_size(belief, evidence_count)

            # Estimate temporal lag
            temporal_lag = self.TEMPORAL_LAG_MAP.get(
                stmt_type, self.TEMPORAL_LAG_MAP["default"]
            )

            # Create edge
            edges.append(
                Edge(
                    source=source,
                    target=target,
                    relationship=relationship,
                    evidence=Evidence(
                        count=evidence_count,
                        confidence=belief,
                        sources=[],  # PMIDs not in NetworkX metadata
                        summary=f"{source} {relationship} {target}",
                    ),
                    effect_size=effect_size,
                    temporal_lag_hours=temporal_lag,
                )
            )

        # Remove duplicate edges (keep highest evidence)
        edges = self._deduplicate_edges(edges)

        # Apply genetic modifiers
        genetic_modifiers = self._apply_genetic_modifiers(
            genetics, node_map, effect_modifiers
        )

        logger.info(
            f"Built causal graph: {len(node_map)} nodes, {len(edges)} edges, "
            f"{len(genetic_modifiers)} genetic modifiers"
        )

        return CausalGraph(
            nodes=list(node_map.values()),
            edges=edges,
            genetic_modifiers=genetic_modifiers,
        )

    def _create_node_from_name(
        self, node_id: str, node_data: Dict[str, Any]
    ) -> Node:
        """Create Node from NetworkX node name and data.

        Args:
            node_id: Node identifier (e.g., "CRP", "IL6")
            node_data: Node data from NetworkX graph

        Returns:
            Node instance
        """
        # Try to infer database from node name
        # For now, assume HGNC for gene/protein names
        database = "HGNC"

        # Common MESH entities
        if node_id in ["PM2.5", "PM10", "ozone", "NO2"]:
            database = "MESH"

        # GO processes
        if "stress" in node_id.lower() or "inflammation" in node_id.lower():
            database = "GO"

        # Determine node type
        node_type = self._infer_node_type(node_id, database)

        return Node(
            id=node_id,
            type=node_type,
            label=node_id,  # Use node ID as label
            grounding=Grounding(
                database=database,
                identifier="",  # Not available from NetworkX
            ),
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
        """Calculate effect size from INDRA belief score and evidence count.

        FIXED FORMULA (per brutalist critique):
            effect_size = belief  (use raw INDRA belief score)
            evidence_weight = min(log(1 + evidence_count) / 10, 0.15)  (separate confidence metric)

        This avoids saturation issues from the old formula that multiplied belief by 0.6
        and capped everything at 0.95. Now:
        - Weak beliefs (0.1-0.3) stay weak (not inflated)
        - Strong beliefs (0.8-0.9) stay strong (not artificially reduced)
        - Evidence adds modest confidence boost (max +0.15) with diminishing returns

        Args:
            belief: INDRA belief score (0-1)
            evidence_count: Number of supporting papers

        Returns:
            Effect size in [0, 1] range

        Raises:
            ValueError: If belief is not in [0, 1]
        """
        import math

        # Validate input
        if not 0 <= belief <= 1:
            logger.error(f"Invalid belief score: {belief} (must be ∈ [0,1])")
            raise ValueError(f"Belief must be ∈ [0,1], got {belief}")

        # Use raw INDRA belief as base effect size (NO scaling)
        effect_size = belief

        # Calculate evidence weight separately (for metadata, not effect size)
        # This provides diminishing returns: log(1+1)=0.69, log(1+100)=4.6, log(1+1000)=6.9
        evidence_weight = min(
            math.log(1 + evidence_count) / self.EVIDENCE_WEIGHT_SCALE,
            self.MAX_EVIDENCE_BONUS
        )

        # Add modest evidence bonus to effect size (capped at MAX_EFFECT for stability)
        # This gives high-evidence edges a small boost without saturating
        effect_size_with_evidence = min(effect_size + evidence_weight, self.MAX_EFFECT)

        # Log warning if effect size is suspiciously high or low
        if effect_size < 0.1:
            logger.warning(
                f"Very low effect size: {effect_size:.3f} (belief={belief:.3f}, "
                f"evidence={evidence_count})"
            )
        elif effect_size_with_evidence > 0.95:
            logger.warning(
                f"Very high effect size: {effect_size_with_evidence:.3f} (belief={belief:.3f}, "
                f"evidence={evidence_count})"
            )

        return effect_size_with_evidence

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
        self,
        genetics: Dict[str, str],
        node_map: Dict[str, Node],
        effect_modifiers: Dict[str, float] = None,
    ) -> List[GeneticModifier]:
        """Apply genetic modifiers to causal graph.

        PREFERRED: Pass effect_modifiers from VCFParser.to_effect_modifiers() for
        zygosity-adjusted, literature-derived effect sizes with PMIDs.

        Args:
            genetics: User genetic variants (DEPRECATED - only for variant names)
            node_map: Map of node IDs to Node objects
            effect_modifiers: Optional dict from VCFParser.to_effect_modifiers()
                Example: {"GSTM1_null": 2.34, "TCF7L2_rs7903146": 1.225}

        Returns:
            List of genetic modifiers with literature-derived effect sizes
        """
        modifiers = []
        node_ids = set(node_map.keys())

        # If effect_modifiers provided (VCF parser output), use directly
        if effect_modifiers:
            for variant_key, magnitude in effect_modifiers.items():
                # Get base info (affected nodes, description) from config
                modifier_info = get_genetic_modifier(variant_key, effect_modifiers)
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
                            magnitude=magnitude,  # Zygosity-adjusted from VCF
                        )
                    )

        # Fallback to genetics dict (deprecated path for backward compatibility)
        elif genetics:
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
