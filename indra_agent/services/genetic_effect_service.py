"""Genetic effect service for discovering variant-to-pathway relationships via INDRA.

NO HARDCODED PATHWAYS - all relationships discovered dynamically from INDRA.
Effect sizes come from VCFParser (literature-derived with PMIDs).
"""

import logging
from typing import Dict, List, Set, Any, Optional

logger = logging.getLogger(__name__)


class GeneticEffectService:
    """Service for discovering genetic variant effects on biological pathways via INDRA."""

    def __init__(self, indra_service):
        """Initialize service with INDRA client.

        Args:
            indra_service: INDRAService instance for querying relationships
        """
        self.indra_service = indra_service

    async def get_affected_pathways(
        self, gene_symbol: str, graph_nodes: Set[str]
    ) -> Set[str]:
        """Discover which graph nodes are affected by a genetic variant using INDRA.

        Strategy:
        1. Query INDRA for all proteins/processes that this gene affects
        2. Find intersection with nodes present in causal graph
        3. Return dynamically discovered affected nodes

        Args:
            gene_symbol: Gene symbol (e.g., "GSTM1", "TCF7L2")
            graph_nodes: Set of node IDs present in causal graph

        Returns:
            Set of graph node IDs affected by this gene variant
        """
        affected = set()

        # Query INDRA for downstream targets of this gene
        # This uses INDRA's gene-to-pathway knowledge base
        try:
            # Search for statements where this gene is the subject
            # Example: GSTM1 affects oxidative stress, glutathione metabolism
            paths = await self.indra_service.find_causal_paths(
                source=gene_symbol,
                target=None,  # Find all downstream effects
                max_depth=2,  # Direct and 1-hop effects
                use_cache=True,
            )

            # Extract target nodes from paths
            for path in paths:
                for node in path.get("nodes", []):
                    node_id = node.get("id", "")
                    node_name = node.get("name", "")

                    # Check if this node is in our causal graph
                    if node_id in graph_nodes or node_name in graph_nodes:
                        affected.add(node_id if node_id in graph_nodes else node_name)

        except Exception as e:
            logger.warning(f"Failed to query INDRA for {gene_symbol} effects: {e}")
            # Return empty set - no affected pathways discovered

        return affected

    def infer_effect_type(
        self, variant_name: str, functional_effect: Optional[str]
    ) -> str:
        """Infer whether variant amplifies or dampens pathway activity.

        Uses functional_effect from VCF parser to determine direction.

        Args:
            variant_name: Variant display name (e.g., "GSTM1_null")
            functional_effect: Functional effect from VCF parser
                (e.g., "loss_of_function", "gain_of_function", "risk_factor")

        Returns:
            "amplifies" or "dampens"
        """
        if not functional_effect:
            return "amplifies"  # Default conservative assumption

        effect_lower = functional_effect.lower()

        # Loss of function variants typically amplify disease pathways
        # (loss of protective function → increased risk)
        if "loss" in effect_lower or "null" in variant_name.lower():
            return "amplifies"

        # Gain of function can go either way
        if "gain" in effect_lower:
            # Gain of pro-inflammatory gene → amplifies inflammation
            # Gain of antioxidant gene → dampens oxidative stress
            # Default to amplifies (conservative for risk assessment)
            return "amplifies"

        # Risk factors amplify disease pathways
        if "risk" in effect_lower or "pathogenic" in effect_lower:
            return "amplifies"

        # Protective variants dampen disease pathways
        if "protective" in effect_lower or "benign" in effect_lower:
            return "dampens"

        # Default: amplifies (conservative for risk assessment)
        return "amplifies"

    async def build_genetic_modifiers_from_vcf(
        self,
        vcf_report,
        graph_nodes: Set[str],
    ) -> List[Dict[str, Any]]:
        """Build genetic modifiers entirely from VCF parser + INDRA discovery.

        NO HARDCODED PATHWAYS OR EFFECT SIZES.
        All data comes from:
        1. VCF parser: variant, effect_size (literature + PMID), functional_effect
        2. INDRA: which pathways this gene affects (dynamic discovery)

        Args:
            vcf_report: VCFReport from VCFParser.parse_vcf()
            graph_nodes: Set of node IDs present in causal graph

        Returns:
            List of genetic modifier dicts with:
                - variant: Variant name
                - affected_nodes: Dynamically discovered from INDRA
                - effect_type: Inferred from functional effect
                - magnitude: From VCF parser (zygosity-adjusted, literature-derived)
        """
        modifiers = []

        for variant in vcf_report.variants:
            # Only include variants with effect sizes > 1.0 (risk factors)
            if not variant.effect_size or variant.effect_size <= 1.0:
                continue

            # Get variant display name (e.g., "GSTM1_null", "TCF7L2_rs7903146")
            from indra_agent.services.vcf_parser import VCFParser

            parser = VCFParser()
            display_name = parser.VARIANT_DISPLAY_NAMES.get(
                variant.variant_id, variant.variant_id
            )

            # Discover affected pathways dynamically via INDRA
            affected_nodes = await self.get_affected_pathways(
                variant.gene_symbol, graph_nodes
            )

            if not affected_nodes:
                logger.info(
                    f"Variant {display_name} ({variant.gene_symbol}) "
                    f"does not affect any nodes in causal graph - skipping"
                )
                continue

            # Infer effect type from functional annotation
            effect_type = self.infer_effect_type(
                display_name, variant.functional_effect
            )

            modifiers.append(
                {
                    "variant": display_name,
                    "affected_nodes": list(affected_nodes),
                    "effect_type": effect_type,
                    "magnitude": variant.effect_size,  # Literature-derived from VCF
                }
            )

            logger.info(
                f"Genetic modifier: {display_name} {effect_type} "
                f"{affected_nodes} by {variant.effect_size:.2f}× (PMID:{variant.pmid})"
            )

        return modifiers
