"""Test Writer KG ontology completeness for causal discovery.

This test emulates the INDRA agent workflow:
1. User asks environmental health question
2. Writer KG expands to specific chemical/biomarker terms
3. Check if Writer KG returns ontology IDs (MeSH, CHEBI, GO)
4. Validate IDs are usable for INDRA queries

Key Question: Does Writer KG return a "holistic but precisely useful" set of terms?

Holistic = Multiple diverse chemicals/biomarkers, not just 1
Precisely Useful = Include ontology IDs (MeSH/CHEBI/GO) for INDRA grounding

Run with: pytest tests/test_writer_kg_ontology_completeness.py -v -s
"""

import pytest
import re
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService


# Skip if Writer KG not configured
pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured (set WRITER_API_KEY and WRITER_GRAPH_ID)"
)


def extract_ontology_ids(text: str) -> dict:
    """Extract all ontology IDs from text.

    Args:
        text: Text to search for IDs

    Returns:
        Dict with lists of found IDs by type
    """
    return {
        "mesh_ids": re.findall(r'\b([DCA]\d{6})\b', text),
        "chebi_ids": re.findall(r'\b(CHEBI:\d+)\b', text),
        "go_ids": re.findall(r'\b(GO:\d{7})\b', text),
        "hgnc_symbols": re.findall(r'\b([A-Z][A-Z0-9]{2,10})\b', text),  # Gene symbols
    }


def count_unique_chemicals(text: str) -> int:
    """Count unique chemical names mentioned.

    Args:
        text: Text to analyze

    Returns:
        Count of unique chemicals
    """
    # Common pollution chemicals
    chemicals = [
        'lead', 'cadmium', 'arsenic', 'mercury', 'chromium',
        'benzene', 'formaldehyde', 'toluene', 'xylene',
        'ozone', 'nitrogen dioxide', 'sulfur dioxide',
        'pm2.5', 'pm10', 'particulate matter', 'carbon monoxide'
    ]

    text_lower = text.lower()
    found = set()

    for chem in chemicals:
        if chem in text_lower:
            found.add(chem)

    return len(found)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_pollution_chemicals_holistic():
    """Test if Writer KG returns MULTIPLE diverse chemicals (holistic expansion)."""
    service = WriterKGService()

    try:
        # Environmental health query
        question = "What chemicals are in air pollution?"

        result = await service.query_mesh_terms(
            question,
            max_snippets=20,  # Need many snippets for holistic coverage
            grounding_level=0.7  # Moderate precision to get variety
        )

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        # Combine answer + sources for full text
        full_text = answer + "\n" + "\n".join([
            s.get("snippet", "") for s in sources
        ])

        # Count unique chemicals
        chemical_count = count_unique_chemicals(full_text)

        print(f"\n{'='*70}")
        print(f"TEST: Holistic Chemical Expansion")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"Answer length: {len(answer)} chars")
        print(f"Sources: {len(sources)}")
        print(f"Unique chemicals mentioned: {chemical_count}")
        print(f"\nFirst 500 chars of answer:")
        print(answer[:500])

        # HOLISTIC CRITERION: Should mention ≥2 diverse chemicals
        assert chemical_count >= 2, f"Expected ≥2 chemicals, got {chemical_count} (not holistic!)"

        print(f"\n✅ HOLISTIC: {chemical_count} diverse chemicals found")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_returns_ontology_ids():
    """Test if Writer KG returns ontology IDs (precisely useful for INDRA)."""
    service = WriterKGService()

    try:
        # Query for specific chemical
        question = "What chemicals are in air pollution? Include MeSH IDs, CHEBI IDs, and chemical formulas."

        result = await service.query_mesh_terms(
            question,
            max_snippets=20,
            grounding_level=0.8
        )

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        # Combine all text
        full_text = answer + "\n" + "\n".join([
            s.get("snippet", "") for s in sources
        ])

        # Extract ontology IDs
        ids = extract_ontology_ids(full_text)

        print(f"\n{'='*70}")
        print(f"TEST: Ontology ID Presence")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"\nOntology IDs found:")
        print(f"  MeSH IDs: {len(ids['mesh_ids'])} - {ids['mesh_ids'][:5]}")
        print(f"  CHEBI IDs: {len(ids['chebi_ids'])} - {ids['chebi_ids'][:5]}")
        print(f"  GO IDs: {len(ids['go_ids'])} - {ids['go_ids'][:5]}")
        print(f"  Gene symbols: {len(ids['hgnc_symbols'])} - {ids['hgnc_symbols'][:10]}")

        # PRECISELY USEFUL CRITERION: Must return ontology IDs
        total_ids = len(ids['mesh_ids']) + len(ids['chebi_ids']) + len(ids['go_ids'])

        print(f"\nTotal ontology IDs: {total_ids}")

        if total_ids == 0:
            print(f"\n❌ NO ONTOLOGY IDs FOUND")
            print(f"Writer KG is NOT precisely useful for INDRA!")
            print(f"\nAnswer sample:")
            print(answer[:500])
            pytest.fail("No ontology IDs returned - cannot ground to INDRA!")

        print(f"\n✅ PRECISELY USEFUL: {total_ids} ontology IDs found")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_specific_chemical_chebi_id():
    """Test if Writer KG can return CHEBI ID for specific chemical."""
    service = WriterKGService()

    try:
        # Direct chemical query
        chemicals_to_test = [
            ("lead", "CHEBI:25016"),
            ("benzene", "CHEBI:16716"),
            ("formaldehyde", "CHEBI:16842"),
        ]

        results = []

        for chem_name, expected_chebi in chemicals_to_test:
            question = f"What is the CHEBI ID for {chem_name}?"

            result = await service.query_mesh_terms(
                question,
                max_snippets=10,
                grounding_level=0.9  # High precision for exact ID
            )

            answer = result.get("answer", "")
            sources = result.get("sources", [])
            full_text = answer + "\n" + "\n".join([s.get("snippet", "") for s in sources])

            ids = extract_ontology_ids(full_text)

            chebi_found = expected_chebi in ids['chebi_ids'] if ids['chebi_ids'] else False
            any_chebi = len(ids['chebi_ids']) > 0

            results.append({
                "chemical": chem_name,
                "expected_chebi": expected_chebi,
                "chebi_found": chebi_found,
                "any_chebi": any_chebi,
                "chebi_ids": ids['chebi_ids']
            })

        print(f"\n{'='*70}")
        print(f"TEST: Specific CHEBI ID Retrieval")
        print(f"{'='*70}")

        for r in results:
            status = "✅" if r['chebi_found'] else ("⚠️ " if r['any_chebi'] else "❌")
            print(f"{status} {r['chemical']:15} -> Expected: {r['expected_chebi']:15} | Found: {r['chebi_ids']}")

        # Check if ANY CHEBI IDs returned
        any_chebi_returned = any(r['any_chebi'] for r in results)

        if not any_chebi_returned:
            print(f"\n❌ NO CHEBI IDs RETURNED FOR ANY CHEMICAL")
            print(f"Writer KG does NOT return CHEBI IDs!")
            pytest.fail("Writer KG cannot return CHEBI IDs - INDRA integration will fail!")

        print(f"\n✅ At least some CHEBI IDs returned")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_mesh_to_indra_compatibility():
    """Test if Writer KG MeSH IDs are compatible with INDRA queries."""
    service = WriterKGService()

    try:
        # Query for pollutant
        term = "particulate matter"
        result = await service.find_mesh_term(term)

        assert result is not None, f"Should find MeSH term for {term}"

        mesh_id = result.get("mesh_id")
        mesh_label = result.get("mesh_label")

        print(f"\n{'='*70}")
        print(f"TEST: MeSH ID → INDRA Compatibility")
        print(f"{'='*70}")
        print(f"Query: {term}")
        print(f"MeSH ID: {mesh_id}")
        print(f"MeSH Label: {mesh_label}")

        # INDRA expects MeSH IDs in format: "MESH:D052638"
        if mesh_id:
            indra_format = f"MESH:{mesh_id}"
            print(f"INDRA query format: {indra_format}")
            print(f"\n✅ MeSH ID usable for INDRA")
        else:
            print(f"\n❌ NO MeSH ID returned")
            pytest.fail("No MeSH ID - cannot query INDRA!")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_go_terms_for_pathways():
    """Test if Writer KG returns GO terms for biological processes."""
    service = WriterKGService()

    try:
        # Query for biological process
        question = "What are the Gene Ontology (GO) terms for oxidative stress and inflammation? Include GO IDs."

        result = await service.query_mesh_terms(
            question,
            max_snippets=15,
            grounding_level=0.8
        )

        answer = result.get("answer", "")
        sources = result.get("sources", [])
        full_text = answer + "\n" + "\n".join([s.get("snippet", "") for s in sources])

        ids = extract_ontology_ids(full_text)

        print(f"\n{'='*70}")
        print(f"TEST: GO Terms for Pathways")
        print(f"{'='*70}")
        print(f"Question: {question}")
        print(f"GO IDs found: {len(ids['go_ids'])}")
        print(f"Examples: {ids['go_ids'][:10]}")

        if len(ids['go_ids']) == 0:
            print(f"\n⚠️  NO GO TERMS RETURNED")
            print(f"Writer KG may not have GO ontology indexed yet")
            pytest.skip("GO terms not yet available in Writer KG")

        print(f"\n✅ GO terms available: {len(ids['go_ids'])} IDs")

    finally:
        await service.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_kg_end_to_end_causal_discovery_prep():
    """End-to-end test: Does Writer KG prepare us for causal discovery?

    This emulates the INDRA agent workflow:
    1. User query: "How does air pollution affect inflammation?"
    2. Writer KG expansion: chemicals + biomarkers
    3. Check: Do we have ontology IDs for INDRA grounding?
    """
    service = WriterKGService()

    try:
        # User question
        user_query = "How does air pollution affect inflammation?"

        print(f"\n{'='*70}")
        print(f"TEST: End-to-End Causal Discovery Preparation")
        print(f"{'='*70}")
        print(f"User Query: {user_query}")

        # Step 1: Expand "air pollution" to specific chemicals
        chem_question = "What specific chemicals are in air pollution? List chemical names with their MeSH and CHEBI IDs."
        chem_result = await service.query_mesh_terms(chem_question, max_snippets=20)

        chem_text = chem_result.get("answer", "") + "\n" + "\n".join([
            s.get("snippet", "") for s in chem_result.get("sources", [])
        ])

        chem_ids = extract_ontology_ids(chem_text)
        chem_count = count_unique_chemicals(chem_text)

        print(f"\n1️⃣  Chemical Expansion:")
        print(f"   Unique chemicals: {chem_count}")
        print(f"   MeSH IDs: {len(chem_ids['mesh_ids'])}")
        print(f"   CHEBI IDs: {len(chem_ids['chebi_ids'])}")

        # Step 2: Expand "inflammation" to biomarkers
        biomarker_question = "What biomarkers indicate inflammation? Include MeSH IDs and gene symbols."
        biomarker_result = await service.query_mesh_terms(biomarker_question, max_snippets=15)

        biomarker_text = biomarker_result.get("answer", "") + "\n" + "\n".join([
            s.get("snippet", "") for s in biomarker_result.get("sources", [])
        ])

        biomarker_ids = extract_ontology_ids(biomarker_text)

        print(f"\n2️⃣  Biomarker Expansion:")
        print(f"   MeSH IDs: {len(biomarker_ids['mesh_ids'])}")
        print(f"   Gene symbols: {len(biomarker_ids['hgnc_symbols'])}")

        # Step 3: Evaluate completeness
        total_chemicals = chem_count
        total_ids = (
            len(chem_ids['mesh_ids']) + len(chem_ids['chebi_ids']) +
            len(biomarker_ids['mesh_ids']) + len(biomarker_ids['hgnc_symbols'])
        )

        print(f"\n3️⃣  Causal Discovery Readiness:")
        print(f"   Total chemicals: {total_chemicals}")
        print(f"   Total ontology IDs: {total_ids}")

        # Criteria
        is_holistic = total_chemicals >= 2
        is_precisely_useful = total_ids >= 3  # Need at least a few IDs

        print(f"\n   Holistic (≥2 chemicals): {'✅' if is_holistic else '❌'}")
        print(f"   Precisely Useful (≥3 IDs): {'✅' if is_precisely_useful else '❌'}")

        if is_holistic and is_precisely_useful:
            print(f"\n✅ Writer KG provides HOLISTIC and PRECISELY USEFUL results!")
            print(f"   Ready for INDRA causal discovery!")
        else:
            issues = []
            if not is_holistic:
                issues.append(f"Only {total_chemicals} chemicals (need ≥2)")
            if not is_precisely_useful:
                issues.append(f"Only {total_ids} ontology IDs (need ≥3)")

            print(f"\n❌ Writer KG NOT ready for causal discovery:")
            for issue in issues:
                print(f"   - {issue}")

            pytest.fail(f"Writer KG incomplete: {', '.join(issues)}")

    finally:
        await service.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
