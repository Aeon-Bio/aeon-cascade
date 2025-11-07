"""Test INDRA queries using CHEBI IDs vs chemical names.

This investigates the user's question: "are we querying using the labels?"

We'll test whether INDRA responds better to:
- Chemical names (labels): "lead", "benzene"
- CHEBI IDs: "CHEBI:25016", "CHEBI:16716"
- Formatted names: "Lead(2+)", "Pb"

Run with: pytest tests/test_indra_chebi_id_queries.py -v -s
"""

import pytest
from indra_agent.services.indra_production_client import INDRAProductionClient


@pytest.mark.asyncio
async def test_indra_query_with_chemical_names():
    """Test INDRA queries using plain chemical names (current approach)."""
    indra_client = INDRAProductionClient()

    test_cases = [
        ("lead", "oxidative stress"),
        ("benzene", "oxidative stress"),
        ("cadmium", "inflammation"),
    ]

    print("\n" + "="*70)
    print("TEST 1: INDRA Queries with Chemical Names (Labels)")
    print("="*70)

    async with indra_client:
        for chemical, target in test_cases:
            try:
                statements = await indra_client.get_paths_between(
                    [chemical, target],
                    preassemble=True
                )

                count = len(statements) if statements else 0
                status = "✅" if count > 0 else "❌"

                print(f"{status} '{chemical}' → {target}: {count} statements")

            except Exception as e:
                print(f"⚠️  '{chemical}' → {target}: ERROR - {e}")


@pytest.mark.asyncio
async def test_indra_query_with_chebi_ids():
    """Test INDRA queries using CHEBI identifiers."""
    indra_client = INDRAProductionClient()

    test_cases = [
        ("CHEBI:25016", "lead", "oxidative stress"),      # Lead
        ("CHEBI:16716", "benzene", "oxidative stress"),    # Benzene
        ("CHEBI:22977", "cadmium", "inflammation"),        # Cadmium
    ]

    print("\n" + "="*70)
    print("TEST 2: INDRA Queries with CHEBI IDs")
    print("="*70)

    async with indra_client:
        for chebi_id, name, target in test_cases:
            try:
                statements = await indra_client.get_paths_between(
                    [chebi_id, target],
                    preassemble=True
                )

                count = len(statements) if statements else 0
                status = "✅" if count > 0 else "❌"

                print(f"{status} '{chebi_id}' ({name}) → {target}: {count} statements")

            except Exception as e:
                print(f"⚠️  '{chebi_id}' ({name}) → {target}: ERROR - {e}")


@pytest.mark.asyncio
async def test_indra_query_with_formatted_names():
    """Test INDRA queries using chemical formulas and formatted names."""
    indra_client = INDRAProductionClient()

    test_cases = [
        ("Pb", "lead", "oxidative stress"),           # Element symbol
        ("Lead(2+)", "lead", "oxidative stress"),     # Ionic form
        ("C6H6", "benzene", "oxidative stress"),      # Chemical formula
        ("benzene", "benzene", "oxidative stress"),   # Standard name (lowercase)
        ("Benzene", "benzene", "oxidative stress"),   # Standard name (capitalized)
    ]

    print("\n" + "="*70)
    print("TEST 3: INDRA Queries with Formatted Names")
    print("="*70)

    async with indra_client:
        for query_term, canonical_name, target in test_cases:
            try:
                statements = await indra_client.get_paths_between(
                    [query_term, target],
                    preassemble=True
                )

                count = len(statements) if statements else 0
                status = "✅" if count > 0 else "❌"

                print(f"{status} '{query_term}' ({canonical_name}) → {target}: {count} statements")

            except Exception as e:
                print(f"⚠️  '{query_term}' ({canonical_name}) → {target}: ERROR - {e}")


@pytest.mark.asyncio
async def test_indra_query_with_mesh_ids():
    """Test INDRA queries using MeSH identifiers (alternative to CHEBI)."""
    indra_client = INDRAProductionClient()

    test_cases = [
        ("MESH:D007854", "lead", "oxidative stress"),         # Lead MeSH ID
        ("MESH:D001554", "benzene", "oxidative stress"),      # Benzene MeSH ID
        ("MESH:D002104", "cadmium", "inflammation"),          # Cadmium MeSH ID
    ]

    print("\n" + "="*70)
    print("TEST 4: INDRA Queries with MeSH IDs")
    print("="*70)

    async with indra_client:
        for mesh_id, name, target in test_cases:
            try:
                statements = await indra_client.get_paths_between(
                    [mesh_id, target],
                    preassemble=True
                )

                count = len(statements) if statements else 0
                status = "✅" if count > 0 else "❌"

                print(f"{status} '{mesh_id}' ({name}) → {target}: {count} statements")

            except Exception as e:
                print(f"⚠️  '{mesh_id}' ({name}) → {target}: ERROR - {e}")


@pytest.mark.asyncio
async def test_indra_query_double_prefix_check():
    """Test if double-prefix bug affects queries (user's observation)."""
    indra_client = INDRAProductionClient()

    test_cases = [
        ("CHEBI:16716", "single prefix", "oxidative stress"),
        ("CHEBI:CHEBI:16716", "double prefix", "oxidative stress"),
    ]

    print("\n" + "="*70)
    print("TEST 5: Double-Prefix Bug Check")
    print("="*70)
    print("User observed: network.indra.bio shows 'CHEBI:CHEBI:[id]'")
    print("Testing if this affects query behavior...")
    print("="*70)

    async with indra_client:
        for query_term, description, target in test_cases:
            try:
                statements = await indra_client.get_paths_between(
                    [query_term, target],
                    preassemble=True
                )

                count = len(statements) if statements else 0
                status = "✅" if count > 0 else "❌"

                print(f"{status} '{query_term}' ({description}) → {target}: {count} statements")

            except Exception as e:
                print(f"⚠️  '{query_term}' ({description}) → {target}: ERROR - {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
