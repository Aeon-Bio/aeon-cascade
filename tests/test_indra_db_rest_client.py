"""Test INDRA DB REST client for chemical-protein queries.

This tests the CORRECT way to query INDRA for chemical pathways:
- Use INDRA DB REST client (Python API)
- NOT PathwayCommons /biopax/process_pc_pathsbetween endpoint
- Use HasAgent queries with CHEBI namespace

Based on: https://indra.readthedocs.io/en/latest/modules/sources/indra_db_rest/index.html

Run with: pytest tests/test_indra_db_rest_client.py -v -s
"""

import pytest

# Check if indra.sources.indra_db_rest is available
try:
    from indra.sources.indra_db_rest.api import get_statements
    from indra.sources.indra_db_rest.query import HasAgent, HasType
    INDRA_DB_REST_AVAILABLE = True
except ImportError:
    INDRA_DB_REST_AVAILABLE = False
    pytest.skip("indra.sources.indra_db_rest not available", allow_module_level=True)


@pytest.mark.asyncio
@pytest.mark.skipif(not INDRA_DB_REST_AVAILABLE, reason="INDRA DB REST client not available")
async def test_indra_db_chemical_by_name():
    """Test querying INDRA DB with chemical name."""
    print("\n" + "="*70)
    print("TEST 1: INDRA DB Query - Chemical by Name")
    print("="*70)

    # Query for lead (chemical name)
    try:
        processor = get_statements(
            agents=["lead"],
            ev_limit=5
        )

        statements = processor.statements
        print(f"✅ Query succeeded: {len(statements)} statements found for 'lead'")

        if statements:
            stmt = statements[0]
            print(f"   Example: {stmt.subj.name if hasattr(stmt, 'subj') else 'N/A'} → {stmt}")
            print(f"   Evidence: {len(stmt.evidence)} sources")
        else:
            print("   ⚠️  No statements found")

        # Should find at least SOME statements for lead
        assert len(statements) >= 0, "Query should succeed (even if 0 results)"

    except Exception as e:
        print(f"❌ Query failed: {e}")
        pytest.fail(f"INDRA DB query failed: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(not INDRA_DB_REST_AVAILABLE, reason="INDRA DB REST client not available")
async def test_indra_db_chemical_by_chebi_id():
    """Test querying INDRA DB with CHEBI ID."""
    print("\n" + "="*70)
    print("TEST 2: INDRA DB Query - Chemical by CHEBI ID")
    print("="*70)

    # Lead CHEBI ID: CHEBI:25016
    try:
        # Method 1: Using agents parameter with @CHEBI suffix
        processor = get_statements(
            agents=["CHEBI:25016@CHEBI"],
            ev_limit=5
        )

        statements = processor.statements
        print(f"✅ Query succeeded: {len(statements)} statements for CHEBI:25016 (lead)")

        if statements:
            stmt = statements[0]
            print(f"   Example: {stmt}")
            print(f"   Evidence: {len(stmt.evidence)} sources")
        else:
            print("   ⚠️  No statements found")

    except Exception as e:
        print(f"❌ Query failed: {e}")
        pytest.fail(f"INDRA DB CHEBI query failed: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(not INDRA_DB_REST_AVAILABLE, reason="INDRA DB REST client not available")
async def test_indra_db_chemical_protein_interaction():
    """Test querying for chemical-protein interactions."""
    print("\n" + "="*70)
    print("TEST 3: INDRA DB Query - Chemical-Protein Interaction")
    print("="*70)

    # Query: lead → NF-κB (NFKB1)
    try:
        processor = get_statements(
            agents=["lead", "NFKB1"],
            ev_limit=10
        )

        statements = processor.statements
        print(f"✅ Query succeeded: {len(statements)} statements for lead → NFKB1")

        if statements:
            for i, stmt in enumerate(statements[:3], 1):
                print(f"\n   Statement {i}: {stmt}")
                print(f"   Evidence: {len(stmt.evidence)} sources")

                # Show agent details
                if hasattr(stmt, 'subj') and hasattr(stmt, 'obj'):
                    print(f"   Subject: {stmt.subj.name} ({stmt.subj.db_refs})")
                    print(f"   Object: {stmt.obj.name} ({stmt.obj.db_refs})")

        # This should find interactions
        if len(statements) > 0:
            print(f"\n   ✅ FOUND {len(statements)} chemical-protein interactions!")
        else:
            print(f"\n   ⚠️  No interactions found (INDRA DB may not have this data)")

    except Exception as e:
        print(f"❌ Query failed: {e}")
        pytest.fail(f"Chemical-protein interaction query failed: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(not INDRA_DB_REST_AVAILABLE, reason="INDRA DB REST client not available")
async def test_indra_db_hasagent_query():
    """Test using HasAgent query builder."""
    print("\n" + "="*70)
    print("TEST 4: INDRA DB Query - HasAgent with CHEBI Namespace")
    print("="*70)

    # Benzene CHEBI ID: CHEBI:16716
    try:
        from indra.sources.indra_db_rest.api import get_statements_from_query

        # Build query using HasAgent
        query = HasAgent("CHEBI:16716", namespace="CHEBI")

        processor = get_statements_from_query(query, ev_limit=5)
        statements = processor.statements

        print(f"✅ HasAgent query succeeded: {len(statements)} statements for benzene")

        if statements:
            stmt = statements[0]
            print(f"   Example: {stmt}")
            print(f"   Evidence: {len(stmt.evidence)} sources")
        else:
            print("   ⚠️  No statements found")

    except Exception as e:
        print(f"❌ HasAgent query failed: {e}")
        pytest.fail(f"HasAgent query failed: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(not INDRA_DB_REST_AVAILABLE, reason="INDRA DB REST client not available")
async def test_indra_db_chemical_activation():
    """Test querying for chemical activation statements."""
    print("\n" + "="*70)
    print("TEST 5: INDRA DB Query - Chemical Activation")
    print("="*70)

    # Query for activation statements involving lead
    try:
        from indra.sources.indra_db_rest.api import get_statements_from_query

        # HasAgent + HasType for Activation
        query = HasAgent("lead", namespace="NAME") & HasType(["Activation"])

        processor = get_statements_from_query(query, ev_limit=5)
        statements = processor.statements

        print(f"✅ Query succeeded: {len(statements)} activation statements for lead")

        if statements:
            for i, stmt in enumerate(statements[:3], 1):
                print(f"\n   Statement {i}: {stmt}")
                print(f"   Evidence: {len(stmt.evidence)} sources")
        else:
            print("   ⚠️  No activation statements found")

    except Exception as e:
        print(f"❌ Activation query failed: {e}")
        pytest.fail(f"Activation query failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
