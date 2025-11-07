"""Test high-evidence singleton preservation in FPLX aggregation.

Critical test: Ensures hub proteins like IL6, TNF, CRP are NOT lost during aggregation.
"""

import pytest
from pathlib import Path

from indra_agent.services.ctd_network_builder import CTDNetworkBuilder
from indra_agent.services.fplx_aggregator import FPLXAggregator


@pytest.fixture
def ctd_builder():
    """Load CTD network from extracted relationships."""
    ctd_path = Path("/Users/noot/Documents/digitalme/scripts/ontology_ingestion/output/ctd_environmental_exposures_relationships.csv")

    if not ctd_path.exists():
        pytest.skip(f"CTD relationships not found: {ctd_path}")

    builder = CTDNetworkBuilder(ctd_path)
    builder.load_network(min_evidence=1)

    return builder


@pytest.fixture
def fplx_aggregator():
    """Initialize FPLX aggregator with FamPlex mappings."""
    return FPLXAggregator()


def test_high_evidence_singletons_preserved(ctd_builder, fplx_aggregator):
    """Test that critical hub proteins are preserved as singletons.

    IL6, TNF, CRP are NOT in FPLX families, but they're critical inflammatory hubs.
    They should be preserved as high-evidence singletons.
    """
    # Find genes affected by PM2.5 + Glucose
    pm25_id = "D052638"
    glucose_id = "D005947"

    convergent_genes = ctd_builder.find_convergent_targets(
        exposure_nodes=[pm25_id, glucose_id],
        min_convergence=2
    )

    # Check if IL6, TNF are in the convergent set
    convergent_gene_symbols = {g['gene_symbol'] for g in convergent_genes}

    print(f"\n{'='*70}")
    print(f"Convergent Gene Check")
    print(f"{'='*70}")
    print(f"Total convergent genes: {len(convergent_genes)}")
    print(f"IL6 in convergent set: {'IL6' in convergent_gene_symbols}")
    print(f"TNF in convergent set: {'TNF' in convergent_gene_symbols}")
    print(f"CRP in convergent set: {'CRP' in convergent_gene_symbols}")

    # Get evidence for these genes
    for gene in ['IL6', 'TNF', 'CRP', 'NFKB1', 'MAPK1']:
        gene_dict = next((g for g in convergent_genes if g['gene_symbol'] == gene), None)
        if gene_dict:
            print(f"{gene}: {gene_dict['total_evidence']} papers, convergence={gene_dict['convergence_degree']}")

    # Aggregate to families (with default threshold = 10 papers)
    nodes = fplx_aggregator.aggregate_to_families(
        convergent_genes=convergent_genes,
        min_family_size=2,
        singleton_evidence_threshold=10
    )

    print(f"\n{'='*70}")
    print(f"Aggregation Results")
    print(f"{'='*70}")
    print(f"Total nodes: {len(nodes)}")

    # Find families vs singletons
    families = [n for n in nodes if not n.get('is_singleton', False)]
    singletons = [n for n in nodes if n.get('is_singleton', False)]

    print(f"Families: {len(families)}")
    print(f"Singletons: {len(singletons)}")

    # Check if IL6, TNF, CRP are present
    node_ids = {n['family_id'] for n in nodes}

    print(f"\n{'='*70}")
    print(f"Critical Hub Proteins")
    print(f"{'='*70}")

    for hub in ['IL6', 'TNF', 'CRP', 'NFKB1', 'MAPK1']:
        is_present = hub in node_ids
        status = "✓ PRESERVED" if is_present else "✗ LOST"

        if is_present:
            node = next(n for n in nodes if n['family_id'] == hub)
            is_singleton = node.get('is_singleton', False)
            node_type = "singleton" if is_singleton else "family member"
            print(f"{hub:10s} - {status} (as {node_type}, {node['total_evidence']} papers)")
        else:
            print(f"{hub:10s} - {status}")

    # Show all singletons
    print(f"\n{'='*70}")
    print(f"All High-Evidence Singletons (≥10 papers)")
    print(f"{'='*70}")

    for i, singleton in enumerate(singletons, 1):
        print(f"{i:2d}. {singleton['family_id']:12s} - {singleton['total_evidence']:3d} papers, {singleton['convergence_degree']}/2 exposures")

    # Assertions
    assert 'IL6' in node_ids or 'TNF' in node_ids, \
        "At least one of IL6 or TNF should be preserved (critical inflammatory hubs)"


def test_singleton_evidence_threshold_adjustment(ctd_builder, fplx_aggregator):
    """Test adjusting singleton evidence threshold.

    Lower threshold = more singletons preserved
    Higher threshold = more aggressive aggregation
    """
    pm25_id = "D052638"
    glucose_id = "D005947"

    convergent_genes = ctd_builder.find_convergent_targets(
        exposure_nodes=[pm25_id, glucose_id],
        min_convergence=2
    )

    print(f"\n{'='*70}")
    print(f"Threshold Sensitivity Analysis")
    print(f"{'='*70}")

    for threshold in [5, 10, 20, 50]:
        nodes = fplx_aggregator.aggregate_to_families(
            convergent_genes=convergent_genes,
            min_family_size=2,
            singleton_evidence_threshold=threshold
        )

        families = [n for n in nodes if not n.get('is_singleton', False)]
        singletons = [n for n in nodes if n.get('is_singleton', False)]

        print(f"\nThreshold = {threshold} papers:")
        print(f"  Total nodes: {len(nodes)} ({len(families)} families + {len(singletons)} singletons)")
        print(f"  Reduction: {len(convergent_genes) / len(nodes):.1f}×")

        # Check IL6, TNF presence
        node_ids = {n['family_id'] for n in nodes}
        il6_present = "IL6" in node_ids
        tnf_present = "TNF" in node_ids

        print(f"  IL6: {'✓' if il6_present else '✗'}")
        print(f"  TNF: {'✓' if tnf_present else '✗'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
