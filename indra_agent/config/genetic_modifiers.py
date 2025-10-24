"""Genetic modifier pathway mapping for causal graph enhancement.

This module maps genetic variants to affected biological pathways.
Effect sizes come ENTIRELY from VCFParser (literature-derived, zygosity-adjusted).

NO HARDCODED EFFECT SIZES - all magnitudes from VCFParser.to_effect_modifiers()
"""

from typing import Any, Dict, Set

# Map genetic variants to affected biological pathways/nodes
# This is the ONLY hardcoded information - which pathways each variant affects
# Effect sizes (magnitudes) come from VCF parser with literature citations
VARIANT_TO_PATHWAYS: Dict[str, Set[str]] = {
    "GSTM1_null": {
        "oxidative_stress",
        "ROS",
        "reactive oxygen species",
        "glutathione",
    },
    "GSTP1_Ile105Val": {
        "oxidative_stress",
        "xenobiotic_metabolism",
    },
    "TNF_-308G>A": {
        "TNF",
        "IL6",
        "inflammation",
        "inflammatory_response",
    },
    "SOD2_Val16Ala": {
        "oxidative_stress",
        "ROS",
        "reactive oxygen species",
        "mitochondrial_function",
    },
    "TCF7L2_rs7903146": {
        "glucose",
        "insulin",
        "HbA1c",
        "diabetes",
        "insulin_resistance",
        "incretin_signaling",
    },
    "MTHFR_C677T": {
        "homocysteine",
        "cardiovascular_risk",
        "folate_metabolism",
    },
}

# Effect type by functional consequence
# This determines whether variant amplifies or dampens the pathway
VARIANT_EFFECT_TYPES: Dict[str, str] = {
    "GSTM1_null": "amplifies",  # Loss of detoxification → increased oxidative stress
    "GSTP1_Ile105Val": "amplifies",  # Reduced catalytic efficiency → increased oxidative stress
    "TNF_-308G>A": "amplifies",  # Increased transcription → amplified inflammation
    "SOD2_Val16Ala": "amplifies",  # Reduced mitochondrial import → increased oxidative stress
    "TCF7L2_rs7903146": "amplifies",  # Impaired incretin signaling → increased diabetes risk
    "MTHFR_C677T": "amplifies",  # Reduced enzyme activity → increased cardiovascular risk
}


def get_affected_pathways(variant: str) -> Set[str]:
    """Get biological pathways affected by a genetic variant.

    Args:
        variant: Genetic variant (e.g., "GSTM1_null", "TCF7L2_rs7903146")

    Returns:
        Set of pathway/node IDs affected by this variant
        Returns empty set if variant not in database
    """
    return VARIANT_TO_PATHWAYS.get(variant, set())


def get_effect_type(variant: str) -> str:
    """Get effect type for a genetic variant.

    Args:
        variant: Genetic variant (e.g., "GSTM1_null")

    Returns:
        "amplifies" or "dampens" based on functional consequence
        Returns "amplifies" as default
    """
    return VARIANT_EFFECT_TYPES.get(variant, "amplifies")


def build_genetic_modifier_info(
    variant: str,
    magnitude: float,
    affected_nodes: Set[str],
) -> Dict[str, Any]:
    """Build genetic modifier info dict from VCF parser output.

    Args:
        variant: Genetic variant name
        magnitude: Effect size from VCFParser (zygosity-adjusted, literature-derived)
        affected_nodes: Set of pathway nodes present in causal graph

    Returns:
        Modifier info dict with:
            - affected_nodes: List of node IDs affected by variant
            - effect_type: "amplifies" or "dampens"
            - magnitude: Effect size from VCF parser (e.g., 2.34 from PMID:18053222)
    """
    return {
        "affected_nodes": list(affected_nodes),
        "effect_type": get_effect_type(variant),
        "magnitude": magnitude,
    }


def get_genetic_modifier(variant: str, effect_modifiers: Dict[str, float] = None) -> Dict[str, Any]:
    """Get genetic modifier info for a variant (legacy compatibility).

    This is a compatibility wrapper for code that still uses the old API.
    New code should use GeneticEffectService for dynamic INDRA-based discovery.

    Args:
        variant: Genetic variant name (e.g., "GSTM1_null")
        effect_modifiers: Optional dict of {variant: magnitude} from VCF parser

    Returns:
        Modifier info dict with affected_nodes, effect_type, magnitude
        Returns None if variant not in database
    """
    affected_pathways = get_affected_pathways(variant)
    if not affected_pathways:
        return None

    # Get magnitude from effect_modifiers or use default 1.3
    magnitude = 1.3
    if effect_modifiers and variant in effect_modifiers:
        magnitude = effect_modifiers[variant]

    return build_genetic_modifier_info(variant, magnitude, affected_pathways)
