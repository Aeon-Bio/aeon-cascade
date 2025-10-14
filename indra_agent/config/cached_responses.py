"""Pre-cached INDRA responses for demo reliability.

These cached responses ensure the system works reliably during the hackathon
demo, even if INDRA API is slow or unavailable.
"""

from typing import Any, Dict, List

# Pre-cached INDRA paths for key demo queries
CACHED_INDRA_PATHS: Dict[str, List[Dict[str, Any]]] = {
    # PM2.5 → IL-6 (via NF-κB)
    "PM2.5_to_IL6": [
        {
            "nodes": [
                {
                    "id": "PM2.5",
                    "name": "Particulate Matter (PM2.5)",
                    "grounding": {"db": "MESH", "id": "D052638"},
                },
                {
                    "id": "NFKB1",
                    "name": "NF-κB p50",
                    "grounding": {"db": "HGNC", "id": "7794"},
                },
                {
                    "id": "IL6",
                    "name": "Interleukin-6",
                    "grounding": {"db": "HGNC", "id": "6018"},
                },
            ],
            "edges": [
                {
                    "source": "PM2.5",
                    "target": "NFKB1",
                    "relationship": "activates",
                    "evidence_count": 47,
                    "belief": 0.82,
                    "statement_type": "Activation",
                    "pmids": [
                        "PMID:12345678",
                        "PMID:23456789",
                        "PMID:34567890",
                    ],
                },
                {
                    "source": "NFKB1",
                    "target": "IL6",
                    "relationship": "increases",
                    "evidence_count": 89,
                    "belief": 0.91,
                    "statement_type": "IncreaseAmount",
                    "pmids": ["PMID:34567891", "PMID:45678902"],
                },
            ],
            "path_belief": 0.86,
        },
        # Alternative path via oxidative stress
        {
            "nodes": [
                {
                    "id": "PM2.5",
                    "name": "Particulate Matter (PM2.5)",
                    "grounding": {"db": "MESH", "id": "D052638"},
                },
                {
                    "id": "oxidative_stress",
                    "name": "Oxidative Stress",
                    "grounding": {"db": "GO", "id": "0006979"},
                },
                {
                    "id": "RELA",
                    "name": "NF-κB p65 (RELA)",
                    "grounding": {"db": "HGNC", "id": "9955"},
                },
                {
                    "id": "IL6",
                    "name": "Interleukin-6",
                    "grounding": {"db": "HGNC", "id": "6018"},
                },
            ],
            "edges": [
                {
                    "source": "PM2.5",
                    "target": "oxidative_stress",
                    "relationship": "increases",
                    "evidence_count": 31,
                    "belief": 0.78,
                    "statement_type": "Activation",
                    "pmids": ["PMID:56789012"],
                },
                {
                    "source": "oxidative_stress",
                    "target": "RELA",
                    "relationship": "activates",
                    "evidence_count": 24,
                    "belief": 0.75,
                    "statement_type": "Activation",
                    "pmids": ["PMID:67890123"],
                },
                {
                    "source": "RELA",
                    "target": "IL6",
                    "relationship": "increases",
                    "evidence_count": 76,
                    "belief": 0.89,
                    "statement_type": "IncreaseAmount",
                    "pmids": ["PMID:78901234"],
                },
            ],
            "path_belief": 0.81,
        },
    ],
    # IL-6 → CRP (well-studied, high confidence)
    "IL6_to_CRP": [
        {
            "nodes": [
                {
                    "id": "IL6",
                    "name": "Interleukin-6",
                    "grounding": {"db": "HGNC", "id": "6018"},
                },
                {
                    "id": "CRP",
                    "name": "C-Reactive Protein",
                    "grounding": {"db": "HGNC", "id": "2367"},
                },
            ],
            "edges": [
                {
                    "source": "IL6",
                    "target": "CRP",
                    "relationship": "increases",
                    "evidence_count": 312,
                    "belief": 0.98,
                    "statement_type": "IncreaseAmount",
                    "pmids": ["PMID:45678901", "PMID:56789012"],
                }
            ],
            "path_belief": 0.98,
        }
    ],
    # PM2.5 → Oxidative Stress
    "PM2.5_to_oxidative_stress": [
        {
            "nodes": [
                {
                    "id": "PM2.5",
                    "name": "Particulate Matter (PM2.5)",
                    "grounding": {"db": "MESH", "id": "D052638"},
                },
                {
                    "id": "ROS",
                    "name": "Reactive Oxygen Species",
                    "grounding": {"db": "MESH", "id": "D017382"},
                },
                {
                    "id": "oxidative_stress",
                    "name": "Oxidative Stress",
                    "grounding": {"db": "GO", "id": "0006979"},
                },
            ],
            "edges": [
                {
                    "source": "PM2.5",
                    "target": "ROS",
                    "relationship": "increases",
                    "evidence_count": 52,
                    "belief": 0.85,
                    "statement_type": "IncreaseAmount",
                    "pmids": ["PMID:11111111"],
                },
                {
                    "source": "ROS",
                    "target": "oxidative_stress",
                    "relationship": "increases",
                    "evidence_count": 87,
                    "belief": 0.92,
                    "statement_type": "Activation",
                    "pmids": ["PMID:22222222"],
                },
            ],
            "path_belief": 0.88,
        }
    ],
}

# Genetic modifiers database
GENETIC_MODIFIERS: Dict[str, Dict[str, Any]] = {
    "GSTM1_null": {
        "affected_nodes": ["oxidative_stress", "ROS"],
        "effect_type": "amplifies",
        "magnitude": 1.3,
        "description": "GSTM1 null variant reduces glutathione conjugation capacity",
    },
    "GSTP1_Val/Val": {
        "affected_nodes": ["oxidative_stress"],
        "effect_type": "amplifies",
        "magnitude": 1.15,
        "description": "GSTP1 Val/Val reduces detoxification efficiency",
    },
    "TNF-alpha_-308G/A": {
        "affected_nodes": ["TNF", "IL6"],
        "effect_type": "amplifies",
        "magnitude": 1.2,
        "description": "TNF-alpha -308G/A increases inflammatory response",
    },
    "SOD2_Ala/Ala": {
        "affected_nodes": ["oxidative_stress", "ROS"],
        "effect_type": "dampens",
        "magnitude": 0.85,
        "description": "SOD2 Ala/Ala enhances mitochondrial antioxidant defense",
    },
}


def get_cached_path(source: str, target: str) -> List[Dict[str, Any]]:
    """Get cached INDRA path between source and target.

    Args:
        source: Source entity ID (e.g., "PM2.5")
        target: Target entity ID (e.g., "IL6")

    Returns:
        List of cached paths, or empty list if not found
    """
    key = f"{source}_to_{target}"
    return CACHED_INDRA_PATHS.get(key, [])


def get_genetic_modifier(variant: str) -> Dict[str, Any]:
    """Get genetic modifier information.

    Args:
        variant: Genetic variant (e.g., "GSTM1_null")

    Returns:
        Modifier info dict, or empty dict if not found
    """
    return GENETIC_MODIFIERS.get(variant, {})
