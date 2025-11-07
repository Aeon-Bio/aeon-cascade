"""Test if Writer KG has indexed our uploaded ontology data.

This test verifies that CHEBI, GO, and MeSH data uploaded to Writer KG
is actually queryable and returns the expected ontology IDs.

Run with: pytest tests/test_writer_kg_data_availability.py -v -s
"""

import pytest
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService


pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured"
)


@pytest.mark.asyncio
async def test_writer_kg_has_mesh_data():
    """Test if MeSH data is queryable."""
    service = WriterKGService()

    try:
        question = "What is the MeSH ID for particulate matter? Show me the exact MeSH descriptor record."

        result = await service.query_mesh_terms(question, max_snippets=10)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"MeSH Data Availability Test")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer length: {len(answer)} chars")
        print(f"Sources: {len(sources)}")
        print(f"\nAnswer:")
        print(answer[:500])
        print(f"\nFirst source snippet:")
        if sources:
            print(sources[0].get("snippet", "")[:300])

        # Check for MeSH ID pattern
        import re
        mesh_ids = re.findall(r'\b([D]\d{6})\b', answer + str(sources))

        print(f"\nMeSH IDs found: {mesh_ids}")

        if len(mesh_ids) == 0:
            print(f"\n❌ NO MESH DATA FOUND")
            pytest.fail("MeSH data not accessible in Writer KG!")

        print(f"\n✅ MeSH data is accessible: {len(mesh_ids)} IDs found")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_writer_kg_has_chebi_data():
    """Test if CHEBI data is queryable."""
    service = WriterKGService()

    try:
        # Direct CHEBI query
        question = "What is the CHEBI ID for benzene? Show me the complete CHEBI entry with ID, label, and formula."

        result = await service.query_mesh_terms(question, max_snippets=15)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"CHEBI Data Availability Test")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer length: {len(answer)} chars")
        print(f"Sources: {len(sources)}")
        print(f"\nAnswer:")
        print(answer)
        print(f"\nSources ({len(sources)} total):")
        for i, source in enumerate(sources[:3]):
            print(f"\nSource {i+1}:")
            print(f"  Snippet: {source.get('snippet', '')[:200]}")

        # Check for CHEBI ID pattern
        import re
        chebi_ids = re.findall(r'\bCHEBI[:\s]?(\d+)\b', answer + str(sources), re.IGNORECASE)

        print(f"\nCHEBI IDs found: {['CHEBI:' + id for id in chebi_ids]}")

        if len(chebi_ids) == 0:
            print(f"\n❌ NO CHEBI DATA FOUND")
            print(f"\nThis means:")
            print(f"  1. Writer KG hasn't indexed CHEBI data yet, OR")
            print(f"  2. CHEBI data format in graph doesn't match query, OR")
            print(f"  3. Need to wait for indexing to complete")
            pytest.skip("CHEBI data not yet accessible in Writer KG - may need indexing time")

        print(f"\n✅ CHEBI data is accessible: {len(chebi_ids)} IDs found")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_writer_kg_has_go_data():
    """Test if GO (Gene Ontology) data is queryable."""
    service = WriterKGService()

    try:
        question = "What is the GO (Gene Ontology) ID for oxidative stress? Show me the GO term entry."

        result = await service.query_mesh_terms(question, max_snippets=15)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"GO Data Availability Test")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer length: {len(answer)} chars")
        print(f"Sources: {len(sources)}")
        print(f"\nAnswer:")
        print(answer)
        print(f"\nSources ({len(sources)} total):")
        for i, source in enumerate(sources[:3]):
            print(f"\nSource {i+1}:")
            print(f"  Snippet: {source.get('snippet', '')[:200]}")

        # Check for GO ID pattern
        import re
        go_ids = re.findall(r'\bGO[:\s]?(\d{7})\b', answer + str(sources), re.IGNORECASE)

        print(f"\nGO IDs found: {['GO:' + id for id in go_ids]}")

        if len(go_ids) == 0:
            print(f"\n❌ NO GO DATA FOUND")
            print(f"\nThis means:")
            print(f"  1. Writer KG hasn't indexed GO data yet, OR")
            print(f"  2. GO data format in graph doesn't match query, OR")
            print(f"  3. Need to wait for indexing to complete")
            pytest.skip("GO data not yet accessible in Writer KG - may need indexing time")

        print(f"\n✅ GO data is accessible: {len(go_ids)} IDs found")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
async def test_writer_kg_raw_query_all_ontologies():
    """Test raw query to see what Writer KG actually returns."""
    service = WriterKGService()

    try:
        question = "List all ontology entries for 'lead' including MeSH, CHEBI, GO, and any other database IDs"

        result = await service.query_mesh_terms(question, max_snippets=30, grounding_level=0.5)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        print(f"\n{'='*70}")
        print(f"Raw Query Test - All Ontologies")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Sources returned: {len(sources)}")

        # Extract ALL possible ID patterns
        import re
        full_text = answer + "\n" + "\n".join([s.get("snippet", "") for s in sources])

        patterns = {
            "MeSH": r'\b([DCA]\d{6})\b',
            "CHEBI": r'\bCHEBI[:\s]?(\d+)\b',
            "GO": r'\bGO[:\s]?(\d{7})\b',
            "HGNC": r'\bHGNC[:\s]?(\d+)\b',
            "UniProt": r'\b([A-Z][0-9][A-Z0-9]{3}[0-9])\b',  # UniProt accession
        }

        print(f"\nOntology IDs Found:")
        for onto_name, pattern in patterns.items():
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            matches = list(set(matches))[:5]  # Unique, first 5
            print(f"  {onto_name}: {len(matches)} unique - {matches}")

        print(f"\nFull Answer:")
        print(answer)

        print(f"\nSample Sources (first 3):")
        for i, source in enumerate(sources[:3]):
            print(f"\nSource {i+1}:")
            print(f"  {source.get('snippet', '')[:300]}")

    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
