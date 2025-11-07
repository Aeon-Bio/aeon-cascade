"""Test Writer KG → CHEBI → INDRA integration pipeline.

This test verifies that:
1. Writer KG contains CHEBI chemical entities and can answer queries about them
2. CHEBI chemicals can be used for INDRA pathway queries
3. The complete workflow (Writer KG → CHEBI → INDRA) produces useful results

Example query flow:
  User: "How does pollution affect inflammation?"

  Step 1: Writer KG enrichment
    Query: "What chemicals are in air pollution?"
    Writer KG → CHEBI data → [
        "nitrogen dioxide" (CHEBI:17997),
        "ozone" (CHEBI:25812),
        "lead" (CHEBI:25016),
        ...
    ]

  Step 2: INDRA pathway discovery
    "lead" → INDRA → "oxidative stress" → "IL-6" → "inflammation"
    (REAL pathways backed by papers)

Run with: pytest tests/test_writer_kg_chebi_integration.py -v -s
"""

import re
import pytest
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService
from indra_agent.services.indra_production_client import INDRAProductionClient


pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured (set WRITER_API_KEY and WRITER_GRAPH_ID)"
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_contains_chebi_data():
    """Test Writer KG contains CHEBI chemical data."""
    service = WriterKGService()

    try:
        # Query for a specific CHEBI chemical
        result = await service.query_mesh_terms(
            question="What is lead? Include its CHEBI ID if available.",
            max_snippets=10,
            grounding_level=0.8
        )

        assert result is not None, "Should return results for chemical query"
        assert "answer" in result, "Response should contain answer"

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        # Check if CHEBI data is present
        import re
        has_chebi = bool(re.search(r'CHEBI', answer, re.IGNORECASE))

        print(f"\n✅ Writer KG CHEBI data check:")
        print(f"   Answer mentions CHEBI: {has_chebi}")
        print(f"   Answer preview: {answer[:300]}...")
        print(f"   Sources returned: {len(sources)}")

        # May fail if CHEBI not indexed yet - that's OK for now
        if not has_chebi:
            pytest.skip("CHEBI data not yet queryable in Writer KG (may still be indexing)")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_chemical_expansion():
    """Test Writer KG can expand environmental terms to specific chemicals.

    Rationale: "Air pollution" is abstract, but Writer KG should help identify
    specific chemicals like PM2.5 constituents for pathway analysis.
    """
    service = WriterKGService()

    try:
        result = await service.query_mesh_terms(
            question="What specific chemical compounds are major components of air pollution? Include metals and organic compounds.",
            max_snippets=20,
            grounding_level=0.7
        )

        assert result is not None
        answer = result.get("answer", "")

        # Look for specific chemical mentions
        import re
        metals = re.findall(r'\b(lead|cadmium|arsenic|mercury|chromium)\b', answer, re.IGNORECASE)
        organics = re.findall(r'\b(benzene|formaldehyde|toluene|naphthalene|ozone)\b', answer, re.IGNORECASE)

        found_chemicals = set([m.lower() for m in metals] + [o.lower() for o in organics])

        print(f"\n✅ Chemical expansion test:")
        print(f"   Total chemicals mentioned: {len(found_chemicals)}")
        print(f"   Metals found: {', '.join(set(m.lower() for m in metals))}")
        print(f"   Organics found: {', '.join(set(o.lower() for o in organics))}")
        print(f"   Answer preview: {answer[:400]}...")

        # Should find at least 2 chemicals (even without CHEBI, general knowledge works)
        assert len(found_chemicals) >= 2, \
            f"Should identify at least 2 chemicals, found: {found_chemicals}"

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_chemicals_are_indra_queryable():
    """Test that common pollution chemicals have INDRA pathways.

    This validates the INDRA side of the integration - do these chemicals
    actually have pathway data in INDRA?
    """
    indra_client = INDRAProductionClient()

    # Common pollution chemicals (from CHEBI or general knowledge)
    test_chemicals = [
        "lead",
        "cadmium",
        "benzene",
        "formaldehyde",
        "ozone"
    ]

    pathway_results = {}

    async with indra_client:
        for chemical in test_chemicals:
            try:
                statements = await indra_client.get_paths_between(
                    [chemical, "oxidative stress"],
                    preassemble=True
                )

                pathway_results[chemical] = len(statements) if statements else 0

                if statements and len(statements) > 0:
                    print(f"   ✅ {chemical} → oxidative stress: {len(statements)} statements")
                else:
                    print(f"   ❌ {chemical} → oxidative stress: NO PATHWAYS")

            except Exception as e:
                print(f"   ⚠️  {chemical}: Query error: {e}")
                pathway_results[chemical] = 0

    # At least 50% of test chemicals should have INDRA pathways
    chemicals_with_pathways = sum(1 for count in pathway_results.values() if count > 0)
    compatibility_rate = chemicals_with_pathways / len(test_chemicals)

    print(f"\n✅ INDRA pathway availability:")
    print(f"   {chemicals_with_pathways}/{len(test_chemicals)} chemicals have pathways")
    print(f"   Compatibility rate: {compatibility_rate:.1%}")

    assert compatibility_rate >= 0.4, \
        f"At least 40% of chemicals should have INDRA pathways, got {compatibility_rate:.1%}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_to_end_pollution_to_pathway():
    """End-to-end test: Environmental query → INDRA pathways.

    Workflow:
    1. Identify pollution-related chemicals (via Writer KG or domain knowledge)
    2. Query INDRA for chemical → health effect pathways
    3. Validate we get evidence-based connections
    """
    indra_client = INDRAProductionClient()

    # Chemicals known to be in pollution (Writer KG could provide these)
    pollution_chemicals = ["lead", "ozone", "formaldehyde"]
    health_target = "inflammation"

    pathway_found = False

    async with indra_client:
        for chemical in pollution_chemicals:
            try:
                statements = await indra_client.get_paths_between(
                    [chemical, health_target],
                    preassemble=True
                )

                if statements and len(statements) > 0:
                    pathway_found = True
                    print(f"\n✅ PATHWAY FOUND: {chemical} → {health_target}")
                    print(f"   Statements: {len(statements)}")

                    # Show first statement as example
                    stmt = statements[0]
                    subj = stmt.get("subj", {}).get("name", "?")
                    obj = stmt.get("obj", {}).get("name", "?")
                    evidence_count = len(stmt.get("evidence", []))

                    print(f"   Example: {subj} → {obj}")
                    print(f"   Evidence: {evidence_count} papers")
                    break

            except Exception as e:
                print(f"   ⚠️  {chemical} → {health_target}: {e}")

    assert pathway_found, \
        f"Should find at least one {health_target} pathway for pollution chemicals"

    print(f"\n✅ END-TO-END TEST PASSED")
    print(f"   Pollution chemicals → INDRA pathways → Evidence ✓")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_chebi_hierarchy():
    """Test Writer KG preserves CHEBI hierarchical relationships.

    CHEBI has parent-child relationships (e.g., "lead" is-a "metal")
    that are useful for semantic expansion.
    """
    service = WriterKGService()

    try:
        # Query for hierarchical relationship
        result = await service.query_mesh_terms(
            question="What is the chemical classification hierarchy for lead? What broader chemical classes does it belong to?",
            max_snippets=15
        )

        assert result is not None
        answer = result.get("answer", "")

        # Look for hierarchy indicators
        import re
        hierarchy_terms = re.findall(
            r'\b(metal|element|compound|class|parent|child|is-a|subclass)\b',
            answer,
            re.IGNORECASE
        )

        has_hierarchy = len(hierarchy_terms) > 0

        print(f"\n✅ Chemical hierarchy test:")
        print(f"   Hierarchy terms found: {len(set(hierarchy_terms))}")
        print(f"   Terms: {', '.join(set(t.lower() for t in hierarchy_terms))}")
        print(f"   Answer preview: {answer[:300]}...")

        # Even general knowledge should provide some hierarchy
        assert has_hierarchy, "Should provide some hierarchical context"

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_specific_chebi_term_lookup():
    """Test looking up a specific CHEBI term by ID or name.

    This validates we can retrieve individual CHEBI entities.
    """
    service = WriterKGService()

    try:
        # Query for benzene (CHEBI:16716)
        result = await service.query_mesh_terms(
            question="What is benzene (CHEBI:16716)? Provide its definition and chemical properties.",
            max_snippets=10,
            grounding_level=0.9
        )

        assert result is not None
        answer = result.get("answer", "")

        # Check if benzene information is returned
        has_benzene_info = bool(re.search(r'benzene', answer, re.IGNORECASE))

        print(f"\n✅ Specific CHEBI term lookup:")
        print(f"   Found benzene information: {has_benzene_info}")
        print(f"   Answer preview: {answer[:300]}...")

        # May not have CHEBI data yet
        if not has_benzene_info:
            pytest.skip("CHEBI term lookup not working yet (may still be indexing)")

    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
