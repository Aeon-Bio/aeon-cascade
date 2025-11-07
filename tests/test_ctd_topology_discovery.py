"""Test CTD topology discovery: Find causal structure spanning observations.

This test demonstrates the core insight:
- CTD provides environmental → molecular edges (174K relationships)
- We find CONVERGENT nodes where multiple exposures meet
- These convergent nodes are the SHARED MECHANISMS
- Query INDRA to validate and extend with molecular detail

The network IS the prior. INDRA IS the validation.
"""

import pytest
from pathlib import Path

from indra_agent.services.ctd_network_builder import CTDNetworkBuilder


@pytest.fixture
def ctd_builder():
    """Load CTD network from extracted relationships."""
    ctd_path = Path("/Users/noot/Documents/digitalme/scripts/ontology_ingestion/output/ctd_environmental_exposures_relationships.csv")

    if not ctd_path.exists():
        pytest.skip(f"CTD relationships not found: {ctd_path}")

    builder = CTDNetworkBuilder(ctd_path)

    # Load network (no filters - get everything)
    builder.load_network(min_evidence=1)

    return builder


def test_pm25_glucose_convergence(ctd_builder):
    """Find genes affected by BOTH PM2.5 and Glucose.

    This is the Sarah Chen scenario:
    - PM2.5 exposure (environmental)
    - High glucose (metabolic/dietary)
    - Both drive inflammation via SHARED molecular targets

    The convergent nodes are where synergy emerges.
    """
    # Chemical IDs from CTD
    pm25_id = "D052638"  # Particulate Matter
    glucose_id = "D005947"  # Glucose

    # Find genes affected by BOTH exposures
    convergent = ctd_builder.find_convergent_targets(
        exposure_nodes=[pm25_id, glucose_id],
        min_convergence=2  # Must be affected by at least 2 exposures
    )

    print(f"\n{'='*70}")
    print(f"CONVERGENT NODES: PM2.5 + Glucose → Shared Targets")
    print(f"{'='*70}")
    print(f"Found {len(convergent)} genes affected by BOTH exposures\n")

    # Show top 20 by evidence
    for i, node in enumerate(convergent[:20], 1):
        print(f"{i:2d}. {node['gene_symbol']:12s} - {node['total_evidence']:3d} papers - {node['explanation']}")

    # Extract inflammatory markers
    inflammatory_markers = ["IL6", "TNF", "NFKB1", "CRP", "MAPK1", "MAPK3", "AKT1", "JNK"]

    convergent_inflammatory = [
        c for c in convergent
        if any(marker in c['gene_symbol'] for marker in inflammatory_markers)
    ]

    print(f"\n{'='*70}")
    print(f"CONVERGENT INFLAMMATORY NODES")
    print(f"{'='*70}")

    for node in convergent_inflammatory:
        print(f"  {node['gene_symbol']:12s} - Affected by: {node['affected_by']}")
        print(f"  {'':12s}   Evidence: {node['total_evidence']} papers")

    # These are the PATHWAY HINTS for INDRA
    pathway_hints = [c['gene_symbol'] for c in convergent_inflammatory]

    print(f"\n{'='*70}")
    print(f"PATHWAY HINTS FOR INDRA VALIDATION")
    print(f"{'='*70}")
    print(f"Instead of exhaustive search, query INDRA for:")

    for hint in pathway_hints:
        print(f"  {hint} → [CRP, IL6, inflammation markers]")

    print(f"\nQuery reduction: ~100 exhaustive → {len(pathway_hints)} targeted")

    # Validate we found key nodes
    assert len(convergent) > 0, "Should find convergent nodes"
    assert any("IL6" in c['gene_symbol'] or "TNF" in c['gene_symbol'] for c in convergent), \
        "Should find IL6 or TNF (known inflammatory convergence)"


def test_multi_exposure_synergy(ctd_builder):
    """Find genes affected by ALL environmental exposures.

    This discovers CORE HUBS in the causal network - genes that integrate
    signals from air pollution, heavy metals, oxidative stress, etc.

    These are the highest-value intervention targets.
    """
    # All environmental exposures from CTD
    exposures = [
        "D052638",  # PM2.5
        "D005947",  # Glucose
        "D010126",  # Ozone
        "D007854",  # Lead
        "D001151",  # Arsenic
        "D006861",  # Hydrogen Peroxide (oxidative stress)
    ]

    # Find genes affected by at least 3 exposures
    convergent = ctd_builder.find_convergent_targets(
        exposure_nodes=exposures,
        min_convergence=3
    )

    print(f"\n{'='*70}")
    print(f"CORE HUBS: Genes Affected by ≥3 Exposures")
    print(f"{'='*70}")
    print(f"Found {len(convergent)} core hub genes\n")

    for i, node in enumerate(convergent[:30], 1):
        affected_count = node['convergence_degree']
        print(f"{i:2d}. {node['gene_symbol']:12s} - {affected_count}/6 exposures, {node['total_evidence']:4d} papers")

    # These hubs are where SYSTEMS-LEVEL intervention matters most
    assert len(convergent) > 0, "Should find core hubs"


def test_pathway_discovery_pm25_to_crp(ctd_builder):
    """Find ALL paths from PM2.5 to CRP (inflammation biomarker).

    This discovers:
    - Direct edges: PM2.5 → CRP (if exists)
    - 2-hop paths: PM2.5 → IL6 → CRP
    - 3-hop paths: PM2.5 → NFKB1 → IL6 → CRP

    The intermediates (IL6, NFKB1) are the MECHANISTIC HINTS for INDRA.
    """
    pm25_id = "D052638"

    # Try to find paths to CRP
    paths = ctd_builder.find_multi_hop_paths(
        source_ids=[pm25_id],
        target_gene="CRP",
        max_hops=3
    )

    print(f"\n{'='*70}")
    print(f"PATHWAYS: PM2.5 → CRP")
    print(f"{'='*70}")

    if paths:
        print(f"Found {len(paths)} paths\n")

        for i, path in enumerate(paths[:10], 1):
            path_str = " → ".join(path['path_nodes'])
            print(f"{i:2d}. {path_str}")
            print(f"    Length: {path['length']} hops, Evidence: {path['total_evidence']} papers")
            print(f"    Intermediates: {path['intermediates']}")
    else:
        print("No direct paths found (expected - CRP is downstream)")
        print("\nBut CTD gives us the FIRST HOP: PM2.5 → IL6, TNF, NFKB1")
        print("Then INDRA validates: IL6 → CRP, TNF → CRP")

    # Find what PM2.5 directly affects
    if ctd_builder.graph.has_node(pm25_id):
        direct_targets = list(ctd_builder.graph.successors(pm25_id))

        print(f"\n{'='*70}")
        print(f"PM2.5 DIRECT TARGETS (First Hop)")
        print(f"{'='*70}")
        print(f"PM2.5 directly affects {len(direct_targets)} genes")

        # Show inflammatory markers
        inflammatory_targets = [
            t for t in direct_targets
            if any(marker in t for marker in ["IL6", "TNF", "NFKB", "CRP", "MAPK", "JNK"])
        ]

        print(f"\nInflammatory pathway targets:")
        for target in inflammatory_targets[:20]:
            edge_data = ctd_builder.graph[pm25_id][target]
            print(f"  PM2.5 → {target:12s} ({edge_data['evidence_count']} papers)")


def test_extract_indra_query_hints(ctd_builder):
    """Extract pathway hints to seed INDRA queries (the actual integration).

    This is the KEY FUNCTION that bridges CTD → INDRA:
    1. CTD: environmental → molecular (PM2.5 → IL6)
    2. Extract intermediates (IL6, TNF, NFKB1)
    3. INDRA: molecular → biomarker (IL6 → CRP)

    Result: Complete causal chain with evidence.
    """
    exposures = ["D052638", "D005947"]  # PM2.5, Glucose
    biomarkers = ["CRP", "IL6"]  # Inflammation markers

    hints = ctd_builder.get_pathway_hints_for_indra(
        exposure_nodes=exposures,
        target_biomarkers=biomarkers
    )

    print(f"\n{'='*70}")
    print(f"INDRA QUERY HINTS")
    print(f"{'='*70}")

    for biomarker, intermediates in hints.items():
        print(f"\nBiomarker: {biomarker}")
        print(f"  Query INDRA for these intermediates:")

        for intermediate in intermediates:
            print(f"    {intermediate} → {biomarker}")

    total_queries = sum(len(v) for v in hints.values())
    print(f"\nTotal targeted queries: {total_queries}")
    print(f"vs Exhaustive: ~100+ (2 exposures × ~50 inflammation genes)")
    print(f"Reduction: {100 - (total_queries / 100 * 100):.0f}%")

    assert len(hints) > 0, "Should generate pathway hints"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
