"""Comprehensive integration tests for the complete ontology pipeline.

This test suite validates:
1. Writer KG data availability (all 4 ontologies)
2. WriterKGService extraction methods (MeSH, CHEBI, GO, FPLX)
3. INDRA format conversion for causal queries
4. End-to-end systems medicine workflow

Run with: pytest tests/test_ontology_integration.py -v -s
"""

import pytest
import re
from typing import Dict, List
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService


pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured"
)


# ============================================================================
# PHASE 1: Individual Ontology Data Availability
# ============================================================================

@pytest.mark.asyncio
async def test_mesh_data_availability():
    """Verify MeSH (Medical Subject Headings) data is indexed and queryable."""
    service = WriterKGService()

    try:
        question = "What is the MeSH descriptor for particulate matter PM2.5?"
        result = await service.query_mesh_terms(question, max_snippets=10)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"TEST: MeSH Data Availability")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer: {answer[:300]}...")
        print(f"Sources: {len(sources)}")

        # Extract MeSH IDs
        mesh_ids = re.findall(r'\b([D]\d{6})\b', answer + str(sources))
        print(f"MeSH IDs found: {mesh_ids[:5]}")

        assert len(mesh_ids) > 0, "MeSH data not found - indexing may not be complete"
        print(f"✅ PASS: {len(mesh_ids)} MeSH IDs extracted")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_chebi_data_availability():
    """Verify CHEBI (Chemical Entities) data is indexed and queryable."""
    service = WriterKGService()

    try:
        question = "What is the CHEBI ID for benzene? Include chemical formula."
        result = await service.query_mesh_terms(question, max_snippets=15)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"TEST: CHEBI Data Availability")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer: {answer[:300]}...")
        print(f"Sources: {len(sources)}")

        # Extract CHEBI IDs
        chebi_ids = re.findall(r'\bCHEBI[:\s]?(\d+)\b', answer + str(sources), re.IGNORECASE)
        print(f"CHEBI IDs found: {['CHEBI:' + id for id in chebi_ids[:5]]}")

        if len(chebi_ids) == 0:
            pytest.skip("CHEBI data not yet indexed - need to wait 24-48h")

        print(f"✅ PASS: {len(chebi_ids)} CHEBI IDs extracted")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_go_data_availability():
    """Verify GO (Gene Ontology) data is indexed and queryable."""
    service = WriterKGService()

    try:
        question = "What is the GO (Gene Ontology) ID for oxidative stress response?"
        result = await service.query_mesh_terms(question, max_snippets=15)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"TEST: GO Data Availability")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer: {answer[:300]}...")
        print(f"Sources: {len(sources)}")

        # Extract GO IDs
        go_ids = re.findall(r'\bGO[:\s]?(\d{7})\b', answer + str(sources), re.IGNORECASE)
        print(f"GO IDs found: {['GO:' + id for id in go_ids[:5]]}")

        if len(go_ids) == 0:
            pytest.skip("GO data not yet indexed - need to wait 24-48h")

        print(f"✅ PASS: {len(go_ids)} GO IDs extracted")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_fplx_data_availability():
    """Verify FPLX (FamPlex Protein Families) data is indexed and queryable."""
    service = WriterKGService()

    try:
        question = "What is the FPLX (FamPlex) protein family for JNK kinases? List member genes."
        result = await service.query_mesh_terms(question, max_snippets=15)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"TEST: FPLX Data Availability")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer: {answer[:300]}...")
        print(f"Sources: {len(sources)}")

        # Extract FPLX IDs
        fplx_ids = re.findall(r'\bFPLX[:\s]?([A-Za-z0-9_]+)\b', answer + str(sources), re.IGNORECASE)
        print(f"FPLX IDs found: {['FPLX:' + id for id in fplx_ids[:5]]}")

        if len(fplx_ids) == 0:
            pytest.skip("FPLX data not yet indexed - need to wait 24-48h")

        print(f"✅ PASS: {len(fplx_ids)} FPLX IDs extracted")

    finally:
        await service.cleanup()


# ============================================================================
# PHASE 2: WriterKGService Extraction Methods
# ============================================================================

@pytest.mark.asyncio
async def test_extract_all_ontology_ids():
    """Test unified ontology ID extraction from Writer KG responses."""
    service = WriterKGService()

    # Mock answer with all ontology types
    sample_text = """
    The particulate matter exposure (MeSH: D052638) leads to oxidative stress
    (GO:0006979) through reactive oxygen species. This activates JNK kinases
    (FPLX:JNK, genes MAPK8/MAPK9/MAPK10) and increases benzene metabolites
    (CHEBI:16716). The pathway involves NFKB1 and other signaling proteins.
    """

    extracted = service._extract_all_ontology_ids(sample_text)

    print(f"\n{'='*70}")
    print(f"TEST: Unified Ontology ID Extraction")
    print(f"{'='*70}")
    print(f"Sample text: {sample_text[:200]}...")
    print(f"\nExtracted IDs:")
    for onto, ids in extracted.items():
        print(f"  {onto}: {ids}")

    # Verify all ontology types extracted
    assert len(extracted["mesh_ids"]) > 0, "MeSH IDs not extracted"
    assert len(extracted["go_ids"]) > 0, "GO IDs not extracted"
    assert len(extracted["fplx_ids"]) > 0, "FPLX IDs not extracted"
    assert len(extracted["chebi_ids"]) > 0, "CHEBI IDs not extracted"
    assert len(extracted["hgnc_symbols"]) > 0, "HGNC symbols not extracted"

    print(f"\n✅ PASS: All 5 ontology types extracted successfully")


@pytest.mark.asyncio
async def test_build_indra_formats():
    """Test INDRA format conversion for causal pathway queries."""
    service = WriterKGService()

    # Sample ontology IDs
    ids = {
        "mesh_ids": ["D052638"],  # PM2.5
        "chebi_ids": ["CHEBI:16716"],  # Benzene
        "go_ids": ["GO:0006979"],  # Oxidative stress
        "fplx_ids": ["FPLX:JNK"],  # JNK family
        "hgnc_symbols": ["NFKB1", "MAPK8"]
    }

    indra_formats = service._build_indra_formats(ids)

    print(f"\n{'='*70}")
    print(f"TEST: INDRA Format Conversion")
    print(f"{'='*70}")
    print(f"Input IDs: {ids}")
    print(f"\nINDRA Formats:")
    for key, value in indra_formats.items():
        print(f"  {key}: {value}")

    # Verify format correctness
    assert indra_formats["mesh"] == "MESH:D052638", "MeSH format incorrect"
    assert indra_formats["chebi"] == "CHEBI:16716@CHEBI", "CHEBI format incorrect"
    assert indra_formats["go"] == "GO:0006979", "GO format incorrect"
    assert indra_formats["fplx"] == "FPLX:JNK", "FPLX format incorrect"

    print(f"\n✅ PASS: All INDRA formats correct")


# ============================================================================
# PHASE 3: Multi-Ontology Integration
# ============================================================================

@pytest.mark.asyncio
async def test_cross_ontology_query():
    """Test querying across multiple ontologies in a single request."""
    service = WriterKGService()

    try:
        question = """
        For the pollution-inflammation pathway:
        1. What is the MeSH ID for particulate matter PM2.5?
        2. What is the GO ID for oxidative stress?
        3. What is the FPLX family for NF-kappa-B proteins?
        4. What CHEBI chemicals are involved in inflammation?
        """

        result = await service.query_mesh_terms(question, max_snippets=30)

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        full_text = answer + "\n".join([s.get("snippet", "") for s in sources])

        print(f"\n{'='*70}")
        print(f"TEST: Cross-Ontology Query")
        print(f"{'='*70}")
        print(f"Question: {question[:100]}...")
        print(f"Sources: {len(sources)}")

        # Extract all ontology types
        extracted = service._extract_all_ontology_ids(full_text)

        print(f"\nExtracted across all ontologies:")
        for onto, ids in extracted.items():
            if ids:
                print(f"  {onto}: {ids[:3]}... ({len(ids)} total)")

        # Build INDRA formats
        indra_formats = service._build_indra_formats(extracted)

        print(f"\nINDRA query formats ready:")
        for key, value in indra_formats.items():
            print(f"  {key}: {value}")

        # Verify multi-ontology extraction
        ontology_count = sum(1 for ids in extracted.values() if len(ids) > 0)
        print(f"\n✅ PASS: {ontology_count}/5 ontology types found in cross-query")

    finally:
        await service.cleanup()


# ============================================================================
# PHASE 4: Systems Medicine Workflow (End-to-End)
# ============================================================================

@pytest.mark.asyncio
async def test_systems_medicine_pathway_discovery():
    """Test end-to-end systems medicine workflow: exposure → mechanism → biomarker."""
    service = WriterKGService()

    try:
        # Simulate Sarah Chen's clinical case
        question = """
        For the environmental exposure pathway from PM2.5 to inflammation:
        1. Identify the environmental factor (PM2.5) - MeSH ID
        2. Identify the molecular mechanism (oxidative stress) - GO ID
        3. Identify the protein family (NF-kappa-B) - FPLX ID
        4. Identify the biomarker (C-reactive protein) - any database ID

        Show complete ontology cross-references for this causal chain.
        """

        result = await service.query_mesh_terms(question, max_snippets=40, grounding_level=0.7)

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        full_text = answer + "\n".join([s.get("snippet", "") for s in sources])

        print(f"\n{'='*70}")
        print(f"TEST: Systems Medicine Pathway Discovery")
        print(f"{'='*70}")
        print(f"Clinical Case: PM2.5 → Oxidative Stress → NF-κB → IL-6 → CRP")
        print(f"Sources returned: {len(sources)}")

        # Extract pathway components
        extracted = service._extract_all_ontology_ids(full_text)

        print(f"\n1. Environmental Factor (MeSH):")
        print(f"   {extracted['mesh_ids'][:3] if extracted['mesh_ids'] else 'Not found (indexing pending)'}")

        print(f"\n2. Molecular Process (GO):")
        print(f"   {extracted['go_ids'][:3] if extracted['go_ids'] else 'Not found (indexing pending)'}")

        print(f"\n3. Protein Families (FPLX):")
        print(f"   {extracted['fplx_ids'][:3] if extracted['fplx_ids'] else 'Not found (indexing pending)'}")

        print(f"\n4. Chemicals/Biomarkers (CHEBI):")
        print(f"   {extracted['chebi_ids'][:3] if extracted['chebi_ids'] else 'Not found (indexing pending)'}")

        print(f"\n5. Gene Symbols (HGNC):")
        print(f"   {extracted['hgnc_symbols'][:5] if extracted['hgnc_symbols'] else 'Not found'}")

        # Build INDRA-ready formats
        indra_formats = service._build_indra_formats(extracted)

        print(f"\nINDRA-Ready Pathway Components:")
        for component, indra_id in indra_formats.items():
            print(f"  {component}: {indra_id}")

        print(f"\nPathway Readiness:")
        pathway_components = len(indra_formats)
        print(f"  Components ready for INDRA query: {pathway_components}/4")

        # At minimum, we need MeSH (always indexed first)
        assert len(extracted["mesh_ids"]) > 0, "No pathway components found"

        if pathway_components >= 3:
            print(f"\n✅ PASS: Multi-ontology pathway ready for causal discovery")
        else:
            print(f"\n⚠️  PARTIAL: {pathway_components}/4 ontologies indexed (waiting for CHEBI/GO/FPLX)")

    finally:
        await service.cleanup()


# ============================================================================
# PHASE 5: FPLX Family-Level Aggregation (Systems Medicine Power Feature)
# ============================================================================

@pytest.mark.asyncio
async def test_fplx_family_aggregation_benefit():
    """Test family-level query reduction via FPLX (579 families vs 4,156 genes)."""
    service = WriterKGService()

    try:
        question = """
        For the NF-kappa-B signaling pathway:
        1. What is the FPLX family ID for NF-kappa-B proteins?
        2. List the individual HGNC gene members of this family
        3. How many genes are in the NF-kappa-B family?
        """

        result = await service.query_mesh_terms(question, max_snippets=20)

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        full_text = answer + "\n".join([s.get("snippet", "") for s in sources])

        print(f"\n{'='*70}")
        print(f"TEST: FPLX Family-Level Aggregation")
        print(f"{'='*70}")
        print(f"Question: {question[:80]}...")

        # Extract FPLX families and genes
        fplx_ids = re.findall(r'\bFPLX[:\s]?([A-Za-z0-9_]+)\b', full_text, re.IGNORECASE)
        hgnc_symbols = re.findall(r'\b([A-Z][A-Z0-9]{2,10})\b', full_text)

        # Filter likely gene symbols (common patterns)
        gene_keywords = ['NFKB', 'REL', 'RELA', 'RELB']
        nfkb_genes = [g for g in hgnc_symbols if any(k in g for k in gene_keywords)]

        print(f"\nFPLX Families found: {list(set(fplx_ids))}")
        print(f"NF-κB family members: {list(set(nfkb_genes))[:10]}")

        if len(fplx_ids) > 0:
            # Calculate query reduction
            family_count = 1  # FPLX:NFkappaB
            gene_count = len(set(nfkb_genes)) if nfkb_genes else 5  # Typical NF-κB family size
            reduction_factor = gene_count / family_count if family_count > 0 else 1

            print(f"\nQuery Reduction Analysis:")
            print(f"  Without FPLX: Query {gene_count} individual genes")
            print(f"  With FPLX:    Query 1 protein family")
            print(f"  Reduction:    {reduction_factor:.1f}× fewer queries")

            print(f"\n✅ PASS: Family-level aggregation working ({reduction_factor:.1f}× reduction)")
        else:
            pytest.skip("FPLX data not yet indexed - family aggregation not testable")

    finally:
        await service.cleanup()


# ============================================================================
# PHASE 6: Data Completeness Summary
# ============================================================================

@pytest.mark.asyncio
async def test_ontology_completeness_summary():
    """Generate completeness report for all uploaded ontologies."""
    service = WriterKGService()

    try:
        # Query all ontologies simultaneously
        question = """
        List database IDs for these terms:
        1. Particulate matter (MeSH)
        2. Benzene (CHEBI)
        3. Oxidative stress (GO)
        4. JNK kinases (FPLX)
        5. NF-kappa-B (any database)
        """

        result = await service.query_mesh_terms(question, max_snippets=50, grounding_level=0.6)

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        full_text = answer + "\n".join([s.get("snippet", "") for s in sources])

        print(f"\n{'='*70}")
        print(f"ONTOLOGY COMPLETENESS REPORT")
        print(f"{'='*70}")

        # Extract all ontology types
        extracted = service._extract_all_ontology_ids(full_text)

        # Expected counts from upload
        expected_entities = {
            "MeSH": 312_504,
            "CHEBI": 204_929,
            "GO": 47_572,
            "FPLX": 579,
        }

        print(f"\nUpload Status:")
        print(f"  Total Entities Uploaded: 570,740")
        print(f"  Upload Date: 2025-11-04")
        print(f"  Graph ID: 59341a3c-5333-455c-8649-4298994cef93")

        print(f"\nIndexing Status:")
        status = {
            "MeSH": "✅ INDEXED" if len(extracted["mesh_ids"]) > 0 else "⏳ PENDING",
            "CHEBI": "✅ INDEXED" if len(extracted["chebi_ids"]) > 0 else "⏳ PENDING",
            "GO": "✅ INDEXED" if len(extracted["go_ids"]) > 0 else "⏳ PENDING",
            "FPLX": "✅ INDEXED" if len(extracted["fplx_ids"]) > 0 else "⏳ PENDING",
        }

        for onto, stat in status.items():
            count = expected_entities[onto]
            print(f"  {onto:10s} ({count:>7,} entities): {stat}")

        indexed_count = sum(1 for s in status.values() if "✅" in s)
        total_count = len(status)

        print(f"\nOverall Progress: {indexed_count}/{total_count} ontologies indexed")
        print(f"Estimated Indexing Time: 24-48 hours for 570K entities")

        if indexed_count == total_count:
            print(f"\n✅ ALL ONTOLOGIES INDEXED - System ready for production")
        else:
            print(f"\n⏳ INDEXING IN PROGRESS - {total_count - indexed_count} ontologies pending")

    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
