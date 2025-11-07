"""
Test INDRA DB REST API for environmental exposure pathways.

This tests the INDRA statement database (indra.sources.indra_db_rest) directly,
as used by our current IndraNetService implementation.

Previous tests used PathwayCommons endpoint (/biopax/process_pc_pathsbetween).
This tests a DIFFERENT data source - INDRA's pre-assembled statement database.

Critical question: Does INDRA DB contain literature-extracted environmental
pathways that PathwayCommons lacks?
"""

import os
import asyncio
from typing import List, Dict, Any

# Configure INDRA DB URL (same as indranet_service.py does)
if not os.environ.get('INDRA_DB_REST_URL'):
    default_url = os.getenv('INDRA_DB_REST_URL', 'https://db.indra.bio')
    os.environ['INDRA_DB_REST_URL'] = default_url
    print(f"✓ Set INDRA_DB_REST_URL to: {default_url}\n")

try:
    import indra.sources.indra_db_rest as idr
    from indra.statements import Statement
    INDRA_AVAILABLE = True
except ImportError:
    print("❌ INDRA Python library not installed")
    print("   Install with: pip install indra")
    INDRA_AVAILABLE = False
    exit(1)


def test_environmental_query(
    subject: str,
    object_name: str,
    description: str
) -> Dict[str, Any]:
    """
    Query INDRA DB for statements between subject and object.

    This matches how IndraNetService.build_biomarker_network() queries INDRA.
    """
    print(f"\n{'='*80}")
    print(f"TEST: {description}")
    print(f"Query: {subject} → {object_name}")
    print(f"{'='*80}")

    try:
        # Query INDRA DB REST API (same as IndraNetService does)
        processor = idr.get_statements(
            subject=subject,
            object=object_name,
            limit=200,
            persist=False,
            ev_limit=5,
            sort_by='ev_count',
            timeout=30,
            tries=2
        )

        statements = processor.statements

        if not statements:
            print(f"❌ NO STATEMENTS: {subject} → {object_name}")
            return {
                "subject": subject,
                "object": object_name,
                "statement_count": 0,
                "statements": []
            }

        print(f"✅ FOUND {len(statements)} statements!")

        # Analyze statements
        statement_types = {}
        total_evidence = 0

        for stmt in statements[:10]:  # Show first 10
            stmt_type = type(stmt).__name__
            statement_types[stmt_type] = statement_types.get(stmt_type, 0) + 1

            evidence_count = len(stmt.evidence)
            total_evidence += evidence_count

            print(f"\n  Statement: {stmt}")
            print(f"    Type: {stmt_type}")
            print(f"    Evidence: {evidence_count} papers")
            if hasattr(stmt, 'belief'):
                print(f"    Belief: {stmt.belief:.3f}")

            # Show first piece of evidence
            if stmt.evidence:
                ev = stmt.evidence[0]
                print(f"    Source: {ev.source_api}")
                if hasattr(ev, 'pmid') and ev.pmid:
                    print(f"    PMID: {ev.pmid}")

        print(f"\n  Statement type distribution:")
        for stmt_type, count in statement_types.items():
            print(f"    {stmt_type}: {count}")

        print(f"\n  Total evidence across statements: {total_evidence}")

        return {
            "subject": subject,
            "object": object_name,
            "statement_count": len(statements),
            "statement_types": statement_types,
            "total_evidence": total_evidence,
            "statements": statements[:10]
        }

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {
            "subject": subject,
            "object": object_name,
            "error": str(e)
        }


def main():
    """
    Test environmental exposure queries using INDRA DB REST API.

    This replicates how our current IndraNetService queries INDRA,
    not the PathwayCommons endpoint tested previously.
    """

    print("="*80)
    print("INDRA DB REST API Environmental Pathway Testing")
    print("="*80)
    print("\nThis tests the INDRA statement database directly")
    print("(indra.sources.indra_db_rest - as used by IndraNetService)")
    print("\nPrevious tests used PathwayCommons endpoint")
    print("This is a DIFFERENT data source with literature-extracted statements")
    print("="*80)

    # Test 1: Environmental exposures
    environmental_tests = [
        ("Particulate Matter", "Interleukin-6", "PM2.5 → IL-6"),
        ("Particulate Matter", "oxidative stress", "PM2.5 → oxidative stress"),
        ("Ozone", "inflammation", "Ozone → inflammation"),
        ("Air Pollutants", "C-Reactive Protein", "Air Pollutants → CRP"),
        ("Cigarette smoke", "reactive oxygen species", "Cigarette smoke → ROS"),
    ]

    print("\n" + "="*80)
    print("CATEGORY 1: Environmental Exposures")
    print("="*80)

    env_results = []
    for subject, obj, desc in environmental_tests:
        result = test_environmental_query(subject, obj, desc)
        env_results.append(result)

    # Test 2: Heavy metals (specific chemicals)
    metal_tests = [
        ("Lead", "oxidative stress", "Lead → oxidative stress"),
        ("Cadmium", "inflammation", "Cadmium → inflammation"),
        ("Arsenic", "NF-kappa-B", "Arsenic → NF-κB"),
        ("Mercury", "Interleukin-6", "Mercury → IL-6"),
    ]

    print("\n" + "="*80)
    print("CATEGORY 2: Heavy Metals")
    print("="*80)

    metal_results = []
    for subject, obj, desc in metal_tests:
        result = test_environmental_query(subject, obj, desc)
        metal_results.append(result)

    # Test 3: Organic pollutants
    organic_tests = [
        ("Benzene", "DNA damage", "Benzene → DNA damage"),
        ("Formaldehyde", "oxidative stress", "Formaldehyde → oxidative stress"),
        ("Benzo[a]pyrene", "p53", "Benzo[a]pyrene → p53"),
    ]

    print("\n" + "="*80)
    print("CATEGORY 3: Organic Pollutants")
    print("="*80)

    organic_results = []
    for subject, obj, desc in organic_tests:
        result = test_environmental_query(subject, obj, desc)
        organic_results.append(result)

    # Test 4: Known working molecular pathways (control)
    control_tests = [
        ("IL6", "CRP", "IL-6 → CRP (CONTROL - should work)"),
        ("TNF", "IL6", "TNF → IL-6 (CONTROL - should work)"),
    ]

    print("\n" + "="*80)
    print("CATEGORY 4: Control Tests (Known Molecular Pathways)")
    print("="*80)

    control_results = []
    for subject, obj, desc in control_tests:
        result = test_environmental_query(subject, obj, desc)
        control_results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    def count_successes(results):
        return sum(1 for r in results if r.get("statement_count", 0) > 0)

    env_success = count_successes(env_results)
    metal_success = count_successes(metal_results)
    organic_success = count_successes(organic_results)
    control_success = count_successes(control_results)

    print(f"\nEnvironmental exposures: {env_success}/{len(env_results)} found pathways")
    print(f"Heavy metals: {metal_success}/{len(metal_results)} found pathways")
    print(f"Organic pollutants: {organic_success}/{len(organic_tests)} found pathways")
    print(f"Control (molecular): {control_success}/{len(control_tests)} found pathways")

    total_env = env_success + metal_success + organic_success
    total_tested = len(env_results) + len(metal_results) + len(organic_results)

    print(f"\n{'='*80}")
    print(f"CRITICAL FINDING:")
    print(f"{'='*80}")

    if total_env > 0:
        print(f"✅ INDRA DB CONTAINS ENVIRONMENTAL PATHWAYS!")
        print(f"   Found {total_env}/{total_tested} environmental exposure pathways")
        print(f"\n   IMPLICATION: Our CTD integration may be REDUNDANT")
        print(f"   INDRA DB has literature-extracted environmental data")
        print(f"   that PathwayCommons endpoint doesn't expose!")
    else:
        print(f"❌ INDRA DB DOES NOT CONTAIN ENVIRONMENTAL PATHWAYS")
        print(f"   Found 0/{total_tested} environmental exposure pathways")
        print(f"\n   IMPLICATION: CTD integration is CRITICAL")
        print(f"   INDRA DB lacks environmental data (same as PathwayCommons)")

    if control_success == len(control_tests):
        print(f"\n✅ Control tests passed ({control_success}/{len(control_tests)})")
        print(f"   INDRA DB molecular pathways work as expected")
    else:
        print(f"\n⚠️  Control tests failed ({control_success}/{len(control_tests)})")
        print(f"   INDRA DB connection or API issue")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
