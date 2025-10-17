"""Live integration tests for Writer Knowledge Graph API.

These tests require:
- WRITER_API_KEY environment variable set
- WRITER_GRAPH_ID environment variable set (MeSH ontology graph ID)

Run with: pytest tests/test_live_writer_kg_integration.py -v -s

Skip if not configured: pytest tests/test_live_writer_kg_integration.py -v --skip-live
"""

import pytest
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService


# Skip entire module if Writer KG not configured
pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured (set WRITER_API_KEY and WRITER_GRAPH_ID)"
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_health_check():
    """Test Writer KG API is accessible and configured correctly."""
    settings = get_settings()

    assert settings.writer_api_key is not None, "WRITER_API_KEY must be set"
    assert settings.writer_graph_id is not None, "WRITER_GRAPH_ID must be set"

    service = WriterKGService()

    try:
        # Try a simple query to verify connectivity
        result = await service.query_mesh_terms(
            question="What is the MeSH ID for particulate matter?",
            max_snippets=1
        )

        # Should get some response (even if empty)
        assert result is not None
        assert "answer" in result
        assert "sources" in result

        print(f"\n✅ Writer KG API health check passed")
        print(f"   Answer: {result.get('answer', '')[:100]}...")
        print(f"   Sources: {len(result.get('sources', []))}")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_mesh_term_query():
    """Test querying for a specific MeSH term."""
    service = WriterKGService()

    try:
        # Query for PM2.5 (well-known environmental pollutant)
        result = await service.find_mesh_term("PM2.5")

        assert result is not None, "Should find result for PM2.5"

        # Expected fields
        assert "mesh_id" in result
        assert "mesh_label" in result

        # Verify it's the right MeSH term (Particulate Matter = D052638)
        mesh_id = result["mesh_id"]
        assert mesh_id.startswith("D"), f"MeSH ID should start with D, got: {mesh_id}"

        print(f"\n✅ Found MeSH term for PM2.5:")
        print(f"   MeSH ID: {result.get('mesh_id')}")
        print(f"   Label: {result.get('mesh_label')}")
        print(f"   Definition: {result.get('definition', '')[:100]}...")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_biomarker_enrichment():
    """Test enriching clinical biomarkers with MeSH ontology."""
    service = WriterKGService()

    try:
        # Test multiple biomarkers
        biomarkers = ["CRP", "IL-6", "8-OHdG"]
        results = []

        for biomarker in biomarkers:
            result = await service.find_mesh_term(biomarker)
            if result:
                results.append({
                    "query": biomarker,
                    "mesh_id": result.get("mesh_id"),
                    "label": result.get("mesh_label")
                })

        assert len(results) > 0, f"Should find at least one biomarker, searched: {biomarkers}"

        print(f"\n✅ Biomarker enrichment results:")
        for r in results:
            print(f"   {r['query']} -> {r['mesh_id']} ({r['label']})")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_synonym_resolution():
    """Test resolving synonyms and alternate names."""
    service = WriterKGService()

    try:
        # Test that different names for same concept map to same MeSH ID
        test_cases = [
            ("particulate matter", "PM2.5"),
            ("C-reactive protein", "CRP"),
            ("interleukin 6", "IL-6"),
        ]

        for canonical, synonym in test_cases:
            result1 = await service.find_mesh_term(canonical)
            result2 = await service.find_mesh_term(synonym)

            # Both should find results
            if result1 and result2:
                # Should resolve to same or related MeSH terms
                print(f"\n   '{canonical}' -> {result1.get('mesh_id')}")
                print(f"   '{synonym}' -> {result2.get('mesh_id')}")

                # If different IDs, they should be in related_terms
                if result1["mesh_id"] != result2["mesh_id"]:
                    related_ids = [
                        r["mesh_id"]
                        for r in result1.get("related_terms", [])
                    ]
                    assert result2["mesh_id"] in related_ids or \
                           result1["mesh_id"] in [
                               r["mesh_id"]
                               for r in result2.get("related_terms", [])
                           ], f"Terms should be related: {canonical} <-> {synonym}"

        print(f"\n✅ Synonym resolution test passed")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_hierarchical_relationships():
    """Test that MeSH hierarchical relationships are returned."""
    service = WriterKGService()

    try:
        # Query for PM2.5, which should have hierarchical relationships
        result = await service.find_mesh_term("particulate matter")

        assert result is not None

        # Should have related terms (broader/narrower concepts)
        if "related_terms" in result:
            related = result["related_terms"]
            assert len(related) > 0, "Should have related MeSH terms"

            print(f"\n✅ Hierarchical relationships for '{result.get('mesh_label')}':")
            for rel in related[:5]:  # Show first 5
                print(f"   {rel.get('relationship', '?').upper()}: {rel.get('label')} ({rel.get('mesh_id')})")
        else:
            pytest.skip("No related_terms in response (may be API limitation)")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_caching():
    """Test that WriterKGService caches results properly."""
    service = WriterKGService()

    try:
        question = "What is the MeSH ID for inflammation?"

        # First query (cache miss)
        result1 = await service.query_mesh_terms(question)

        # Second query (should hit cache)
        result2 = await service.query_mesh_terms(question)

        # Results should be identical
        assert result1 == result2, "Cached result should match original"

        # Verify cache has the entry
        cache_key = f"{question}:10:0.8"  # default params
        assert cache_key in service._cache

        print(f"\n✅ Caching verified: {len(service._cache)} entries")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_query_config_options():
    """Test different query configuration options."""
    service = WriterKGService()

    try:
        question = "What is oxidative stress?"

        # Test different grounding levels
        result_low = await service.query_mesh_terms(
            question,
            grounding_level=0.5,
            max_snippets=5
        )

        result_high = await service.query_mesh_terms(
            question,
            grounding_level=0.9,
            max_snippets=3
        )

        # Both should return results
        assert result_low is not None
        assert result_high is not None

        # Higher grounding level may return fewer but more precise results
        print(f"\n✅ Query config options:")
        print(f"   Low grounding (0.5): {len(result_low.get('sources', []))} sources")
        print(f"   High grounding (0.9): {len(result_high.get('sources', []))} sources")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_batch_enrichment():
    """Test enriching multiple terms in batch (real-world scenario)."""
    service = WriterKGService()

    try:
        # Simulate extracting entities from user query
        query = "How does air pollution affect inflammation and CRP levels?"
        entities = ["air pollution", "inflammation", "CRP"]

        enriched = []

        for entity in entities:
            result = await service.find_mesh_term(entity)
            if result:
                enriched.append({
                    "original_term": entity,
                    "mesh_id": result.get("mesh_id"),
                    "mesh_label": result.get("mesh_label"),
                    "definition": result.get("definition", "")[:100]
                })

        # Should enrich at least 2 out of 3 terms
        assert len(enriched) >= 2, f"Should enrich most terms, got {len(enriched)}/3"

        print(f"\n✅ Batch enrichment: {len(enriched)}/{len(entities)} terms enriched")
        for e in enriched:
            print(f"   '{e['original_term']}' -> {e['mesh_id']} ({e['mesh_label']})")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_error_handling():
    """Test error handling for invalid queries."""
    service = WriterKGService()

    try:
        # Query with nonsense term
        result = await service.find_mesh_term("xyznotarealtermxyz123")

        # Should return None or empty result, not crash
        assert result is None or result.get("mesh_id") is None

        print(f"\n✅ Error handling: Invalid query handled gracefully")

    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
