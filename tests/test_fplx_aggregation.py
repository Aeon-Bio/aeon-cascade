"""Test FPLX aggregation: Dimensional reduction from genes to protein families.

This test demonstrates the critical Markov boundary discovery step:
- CTD convergence: 1,937 genes affected by PM2.5 + Glucose
- FPLX aggregation: 1,937 genes → ~100 protein families
- Dimensional reduction: ~20× parameter space reduction

The families become the Markov boundary candidates for parsimonious causal structure.
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


def test_fplx_loading(fplx_aggregator):
    """Test FPLX mappings load correctly."""
    fplx_aggregator.load_mappings()

    stats = fplx_aggregator.compute_family_statistics()

    print(f"\n{'='*70}")
    print(f"FPLX Ontology Statistics")
    print(f"{'='*70}")
    print(f"Total genes with family mappings: {stats['total_genes']}")
    print(f"Total protein families: {stats['total_families']}")
    print(f"Average family size: {stats['avg_family_size']:.1f} genes")
    print(f"\nTop 10 largest families:")

    for i, family in enumerate(stats['largest_families'], 1):
        print(f"  {i:2d}. {family['family_id']:30s} - {family['gene_count']:3d} genes")

    assert stats['total_genes'] > 0, "Should load gene mappings"
    assert stats['total_families'] > 0, "Should load families"


def test_gene_to_family_lookup(fplx_aggregator):
    """Test individual gene → family lookups."""
    fplx_aggregator.load_mappings()

    # Test MAPK family
    mapk1_families = fplx_aggregator.get_gene_families("MAPK1")
    mapk3_families = fplx_aggregator.get_gene_families("MAPK3")

    print(f"\n{'='*70}")
    print(f"Gene → Family Lookups")
    print(f"{'='*70}")
    print(f"MAPK1 families: {mapk1_families}")
    print(f"MAPK3 families: {mapk3_families}")

    assert "ERK" in mapk1_families, "MAPK1 should be in ERK family"
    assert "ERK" in mapk3_families, "MAPK3 should be in ERK family"

    # Test JNK family
    mapk8_families = fplx_aggregator.get_gene_families("MAPK8")
    print(f"MAPK8 families: {mapk8_families}")
    assert "JNK" in mapk8_families, "MAPK8 should be in JNK family"

    # Test IL6 family
    il6_families = fplx_aggregator.get_gene_families("IL6")
    print(f"IL6 families: {il6_families}")


def test_family_to_genes_expansion(fplx_aggregator):
    """Test family → genes expansion."""
    fplx_aggregator.load_mappings()

    # ERK family
    erk_members = fplx_aggregator.get_family_members("ERK")
    print(f"\n{'='*70}")
    print(f"Family → Genes Expansion")
    print(f"{'='*70}")
    print(f"ERK family members: {erk_members}")

    assert "MAPK1" in erk_members, "ERK should contain MAPK1"
    assert "MAPK3" in erk_members, "ERK should contain MAPK3"

    # JNK family
    jnk_members = fplx_aggregator.get_family_members("JNK")
    print(f"JNK family members: {jnk_members}")

    assert "MAPK8" in jnk_members, "JNK should contain MAPK8"
    assert "MAPK9" in jnk_members, "JNK should contain MAPK9"
    assert "MAPK10" in jnk_members, "JNK should contain MAPK10"


def test_aggregate_ctd_convergent_genes(ctd_builder, fplx_aggregator):
    """Test aggregating CTD convergent genes to FPLX families.

    This is the KEY FUNCTION that achieves dimensional reduction:
    1,937 convergent genes → ~100 protein families
    """
    # Find genes affected by BOTH PM2.5 and Glucose
    pm25_id = "D052638"
    glucose_id = "D005947"

    convergent_genes = ctd_builder.find_convergent_targets(
        exposure_nodes=[pm25_id, glucose_id],
        min_convergence=2
    )

    print(f"\n{'='*70}")
    print(f"CTD Convergent Genes → FPLX Families")
    print(f"{'='*70}")
    print(f"Input: {len(convergent_genes)} convergent genes (PM2.5 + Glucose)")

    # Aggregate to families
    families = fplx_aggregator.aggregate_to_families(
        convergent_genes=convergent_genes,
        min_family_size=2  # At least 2 genes per family
    )

    print(f"Output: {len(families)} protein families")
    print(f"Dimensional reduction: {len(convergent_genes) / max(len(families), 1):.1f}×")
    print(f"\nTop 20 families by total evidence:")

    for i, family in enumerate(families[:20], 1):
        print(f"{i:2d}. {family['family_id']:20s} - {family['gene_count']:2d} genes, {family['total_evidence']:4d} papers")
        print(f"    Members: {', '.join(family['member_genes'][:5])}")
        if len(family['member_genes']) > 5:
            print(f"             ...and {len(family['member_genes']) - 5} more")

    # Validate key families are present
    family_ids = {f['family_id'] for f in families}

    # Check for known inflammatory families
    inflammatory_families = ["ERK", "JNK", "NFkappaB", "STAT"]
    found_inflammatory = [fam for fam in inflammatory_families if fam in family_ids]

    print(f"\n{'='*70}")
    print(f"Inflammatory Pathway Families Detected")
    print(f"{'='*70}")

    for fam_id in found_inflammatory:
        family = next(f for f in families if f['family_id'] == fam_id)
        print(f"\n{family['family_id']}:")
        print(f"  Members: {', '.join(family['member_genes'])}")
        print(f"  Evidence: {family['total_evidence']} papers")
        print(f"  Convergence: {family['convergence_degree']} exposures")

    assert len(families) > 0, "Should aggregate to families"
    assert len(families) < len(convergent_genes), "Should reduce dimensionality"


def test_markov_boundary_candidate_selection(ctd_builder, fplx_aggregator):
    """Test selecting top Markov boundary candidates from aggregated families.

    This demonstrates the final parsimony step:
    ~100 families → ~12 Markov boundary hubs (highest evidence)
    """
    # Find multi-exposure convergent genes
    exposures = [
        "D052638",  # PM2.5
        "D005947",  # Glucose
        "D010126",  # Ozone
        "D007854",  # Lead
    ]

    convergent_genes = ctd_builder.find_convergent_targets(
        exposure_nodes=exposures,
        min_convergence=2
    )

    # Aggregate to families
    families = fplx_aggregator.aggregate_to_families(
        convergent_genes=convergent_genes,
        min_family_size=2
    )

    # Select top 12 candidates (Markov boundary size)
    top_candidates = families[:12]

    print(f"\n{'='*70}")
    print(f"MARKOV BOUNDARY CANDIDATES (Top 12 Families)")
    print(f"{'='*70}")
    print(f"Dimensional reduction path:")
    print(f"  {len(convergent_genes)} convergent genes")
    print(f"  → {len(families)} protein families")
    print(f"  → {len(top_candidates)} Markov boundary candidates")
    print(f"\nCandidates:")

    for i, candidate in enumerate(top_candidates, 1):
        print(f"\n{i:2d}. {candidate['family_id']}")
        print(f"    Genes: {candidate['gene_count']}")
        print(f"    Evidence: {candidate['total_evidence']} papers")
        print(f"    Convergence: {candidate['convergence_degree']}/{len(exposures)} exposures")
        print(f"    Members: {', '.join(candidate['member_genes'][:3])}")
        if len(candidate['member_genes']) > 3:
            print(f"             ...and {len(candidate['member_genes']) - 3} more")

    # These are the nodes that will be validated with INDRA
    print(f"\n{'='*70}")
    print(f"Next Step: INDRA Validation")
    print(f"{'='*70}")
    print(f"Query INDRA for paths from these {len(top_candidates)} families to:")
    print(f"  - CRP (inflammation biomarker)")
    print(f"  - IL6 (inflammatory cytokine)")
    print(f"  - HbA1c (metabolic biomarker)")

    family_ids = [c['family_id'] for c in top_candidates]
    print(f"\nFamilies to validate: {', '.join(family_ids)}")

    assert len(top_candidates) == 12, "Should select exactly 12 candidates"
    assert all(c['total_evidence'] > 0 for c in top_candidates), "All candidates should have evidence"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
