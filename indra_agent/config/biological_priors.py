"""Biological prior knowledge for SCM construction.

This module encodes well-established mechanistic relationships from biomedical literature
that can be used to guide causal discovery when INDRA paths are incomplete.

Design Principles:
- Only include relationships with strong literature support (>50 papers or established textbook knowledge)
- Belief scores reflect consensus strength, not individual study effect sizes
- Priors serve as "bridges" when INDRA's direct path search fails
- All priors should be verifiable against INDRA's literature when possible
"""

from typing import Dict, List, Tuple

# Type aliases for clarity
EntityPair = Tuple[str, str]  # (source, target)
PriorMetadata = Dict[str, any]  # {belief, mechanism, pmid_count}


# Environmental exposures → Molecular initiators
# These are the "entry points" where external factors affect biology
ENVIRONMENTAL_TO_MOLECULAR = {
    # PM2.5 particulate matter effects
    ("Particulate Matter", "reactive oxygen species"): {
        "belief": 0.92,
        "mechanism": "mitochondrial_dysfunction",
        "evidence_count": 150,
        "rationale": "PM2.5 causes ROS generation via mitochondrial damage and NADPH oxidase activation"
    },
    ("Particulate Matter", "oxidative stress"): {
        "belief": 0.90,
        "mechanism": "redox_imbalance",
        "evidence_count": 200,
        "rationale": "Direct measurement of oxidative stress biomarkers (8-OHdG, MDA) in PM2.5 exposure studies"
    },
    ("Particulate Matter", "TNF"): {
        "belief": 0.85,
        "mechanism": "innate_immune_activation",
        "evidence_count": 120,
        "rationale": "PM2.5 activates macrophages and dendritic cells, releasing TNF-α"
    },

    # Ozone effects
    ("Ozone", "IL8"): {
        "belief": 0.88,
        "mechanism": "airway_inflammation",
        "evidence_count": 80,
        "rationale": "O3 directly damages airway epithelium, triggering IL-8 release"
    },
    ("Ozone", "oxidative stress"): {
        "belief": 0.85,
        "mechanism": "lipid_peroxidation",
        "evidence_count": 90,
        "rationale": "Ozone reacts with membrane lipids causing oxidative damage"
    },
}


# Canonical molecular cascades
# Well-established signaling pathways that appear in textbooks
MOLECULAR_CASCADES = {
    # Oxidative stress → inflammation pathway
    ("reactive oxygen species", "NFKB1"): {
        "belief": 0.95,
        "mechanism": "redox_signaling",
        "evidence_count": 300,
        "rationale": "ROS activates IKK complex, leading to NF-κB nuclear translocation"
    },
    ("oxidative stress", "NFKB1"): {
        "belief": 0.93,
        "mechanism": "redox_sensitive_transcription",
        "evidence_count": 250,
        "rationale": "Oxidative stress is canonical NF-κB activator via IκB degradation"
    },

    # NF-κB → cytokine transcription
    ("NFKB1", "IL6"): {
        "belief": 0.96,
        "mechanism": "transcription_factor",
        "evidence_count": 500,
        "rationale": "NF-κB binding sites in IL-6 promoter region, direct transcriptional activation"
    },
    ("NFKB1", "TNF"): {
        "belief": 0.95,
        "mechanism": "transcription_factor",
        "evidence_count": 450,
        "rationale": "TNF-α gene has NF-κB response elements in promoter"
    },
    ("NFKB1", "IL1B"): {
        "belief": 0.94,
        "mechanism": "transcription_factor",
        "evidence_count": 400,
        "rationale": "IL-1β is direct NF-κB transcriptional target"
    },

    # Cytokine network
    ("TNF", "IL6"): {
        "belief": 0.90,
        "mechanism": "cytokine_cascade",
        "evidence_count": 200,
        "rationale": "TNF-α induces IL-6 expression via TNFR signaling"
    },
    ("IL1B", "IL6"): {
        "belief": 0.88,
        "mechanism": "cytokine_cascade",
        "evidence_count": 180,
        "rationale": "IL-1β activates IL-6 transcription via MyD88/NF-κB pathway"
    },

    # IL-6 → Acute phase response
    ("IL6", "CRP"): {
        "belief": 0.98,
        "mechanism": "hepatic_acute_phase_response",
        "evidence_count": 600,
        "rationale": "IL-6 is THE primary regulator of CRP synthesis in hepatocytes via STAT3"
    },
}


# Known biological mediators that often appear in causal chains
# These are high-priority targets for neighborhood expansion
KNOWN_MEDIATORS = [
    # Oxidative stress
    "reactive oxygen species",
    "oxidative stress",
    "superoxide",

    # Transcription factors
    "NFKB1",  # NF-κB p50
    "RELA",   # NF-κB p65
    "STAT3",
    "AP1",

    # Pro-inflammatory cytokines
    "TNF",    # TNF-α
    "IL1B",   # IL-1β
    "IL6",    # IL-6
    "IL8",    # IL-8 (CXCL8)

    # Anti-inflammatory
    "IL10",

    # Acute phase proteins
    "CRP",
    "SAA1",   # Serum amyloid A
]


# Entity name normalization for INDRA queries
# Maps common synonyms to INDRA-preferred names
ENTITY_NAME_MAPPING = {
    # Environmental
    "PM2.5": "Particulate Matter",
    "PM10": "Particulate Matter",
    "O3": "Ozone",
    "NO2": "Nitrogen Dioxide",

    # ROS/oxidative stress
    "ROS": "reactive oxygen species",
    "superoxide": "reactive oxygen species",

    # NF-κB complex (multiple subunits)
    "NF-κB": "NFKB1",
    "NFκB": "NFKB1",
    "NF-kappaB": "NFKB1",

    # Cytokines
    "TNF-α": "TNF",
    "TNF-alpha": "TNF",
    "IL-1β": "IL1B",
    "IL-1beta": "IL1B",
    "IL-6": "IL6",
    "IL-8": "IL8",
    "IL-10": "IL10",

    # Acute phase
    "C-reactive protein": "CRP",
    "C-Reactive Protein": "CRP",
}


def normalize_entity_name(entity: str) -> str:
    """Normalize entity name to INDRA-preferred form.

    Args:
        entity: Entity name (user input or from MeSH)

    Returns:
        Normalized entity name for INDRA queries
    """
    return ENTITY_NAME_MAPPING.get(entity, entity)


def get_prior_edge(source: str, target: str) -> PriorMetadata:
    """Get prior knowledge edge between two entities.

    Args:
        source: Source entity name
        target: Target entity name

    Returns:
        Prior metadata if edge exists, None otherwise
    """
    # Normalize names
    source_norm = normalize_entity_name(source)
    target_norm = normalize_entity_name(target)

    # Check both cascade dictionaries
    pair = (source_norm, target_norm)

    if pair in ENVIRONMENTAL_TO_MOLECULAR:
        return ENVIRONMENTAL_TO_MOLECULAR[pair]

    if pair in MOLECULAR_CASCADES:
        return MOLECULAR_CASCADES[pair]

    return None


def get_all_prior_edges() -> List[Tuple[str, str, PriorMetadata]]:
    """Get all prior knowledge edges.

    Returns:
        List of (source, target, metadata) tuples
    """
    edges = []

    for (source, target), metadata in ENVIRONMENTAL_TO_MOLECULAR.items():
        edges.append((source, target, metadata))

    for (source, target), metadata in MOLECULAR_CASCADES.items():
        edges.append((source, target, metadata))

    return edges


def is_known_mediator(entity: str) -> bool:
    """Check if entity is a known biological mediator.

    Args:
        entity: Entity name

    Returns:
        True if entity is in KNOWN_MEDIATORS
    """
    entity_norm = normalize_entity_name(entity)
    return entity_norm in KNOWN_MEDIATORS


def get_mediators_between(source: str, target: str) -> List[str]:
    """Get known mediators that could connect source to target.

    Strategy: Return mediators that have prior edges from source OR to target.

    Args:
        source: Source entity
        target: Target entity

    Returns:
        List of potential mediator names
    """
    source_norm = normalize_entity_name(source)
    target_norm = normalize_entity_name(target)

    mediators = set()

    # Find mediators downstream of source
    for (s, t), _ in {**ENVIRONMENTAL_TO_MOLECULAR, **MOLECULAR_CASCADES}.items():
        if s == source_norm and t in KNOWN_MEDIATORS:
            mediators.add(t)

    # Find mediators upstream of target
    for (s, t), _ in {**ENVIRONMENTAL_TO_MOLECULAR, **MOLECULAR_CASCADES}.items():
        if t == target_norm and s in KNOWN_MEDIATORS:
            mediators.add(s)

    return list(mediators)
