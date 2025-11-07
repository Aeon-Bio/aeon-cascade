#!/usr/bin/env python3
"""Test INDRA DB with real queries to answer architectural questions.

Questions to answer:
1. Does INDRA accept @AUTO namespace (Gilda internally)?
2. Does INDRA accept database IDs in ID@NAMESPACE format?
3. Do plain name queries work exhaustively?
4. What's the actual query format that returns results?

DO NOT cruft the codebase - this is a throwaway test script.
"""

import os
import sys
import asyncio
from pathlib import Path

# Set INDRA environment
os.environ['INDRA_DB_REST_URL'] = 'https://db.indra.bio'
os.environ['INDRA_DB_REST_API_KEY'] = ''

import indra.sources.indra_db_rest as idr


def test_query_formats():
    """Test different query formats to see what actually works."""

    print("=" * 80)
    print("INDRA DB Query Format Tests")
    print("=" * 80)
    print()

    test_cases = [
        # Format 1: Plain names (current approach)
        ("Plain names", {"subject": "PM2.5", "object": "IL6"}),
        ("Plain names alt", {"subject": "Particulate Matter", "object": "IL6"}),

        # Format 2: Database IDs with @NAMESPACE (from docs)
        ("MESH @ format", {"subject": "D052638@MESH", "object": "5973@HGNC"}),
        ("ID only", {"subject": "D052638", "object": "5973"}),

        # Format 3: @AUTO (Gilda internally)
        ("AUTO namespace", {"subject": "PM2.5@AUTO", "object": "IL6@AUTO"}),

        # Format 4: Known working query (IL6 → CRP)
        ("Known working", {"subject": "IL6", "object": "CRP"}),
        ("Known working HGNC", {"subject": "5973@HGNC", "object": "2367@HGNC"}),
    ]

    results = {}

    for name, params in test_cases:
        print(f"Testing: {name}")
        print(f"  Query: {params}")

        try:
            processor = idr.get_statements(
                subject=params.get("subject"),
                object=params.get("object"),
                limit=10,
                persist=False,
                ev_limit=3,
                timeout=15,
                tries=1
            )

            stmt_count = len(processor.statements)
            results[name] = stmt_count

            if stmt_count > 0:
                print(f"  ✓ Found {stmt_count} statements")
                # Show first statement
                stmt = processor.statements[0]
                print(f"    Example: {stmt.subj.name} → {stmt.obj.name}")
                print(f"    Type: {stmt.__class__.__name__}, Belief: {stmt.belief:.3f}")
            else:
                print(f"  ✗ No statements found")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            results[name] = f"ERROR: {e}"

        print()

    # Summary
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    for name, count in results.items():
        status = "✓" if isinstance(count, int) and count > 0 else "✗"
        print(f"{status} {name:30} {count}")
    print()

    return results


def test_exhaustive_synonym_search():
    """Test if exhaustive synonym search actually works."""

    print("=" * 80)
    print("Exhaustive Synonym Search Test")
    print("=" * 80)
    print()

    # Test: Do different synonyms return different statements?
    pm25_variants = ["PM2.5", "Particulate Matter", "particulates", "PM 2.5"]
    il6_variants = ["IL6", "IL-6", "Interleukin-6", "interleukin 6"]

    all_statements = {}
    statement_hashes = set()

    for src in pm25_variants:
        for tgt in il6_variants:
            query = f"{src} → {tgt}"
            print(f"Query: {query}")

            try:
                processor = idr.get_statements(
                    subject=src,
                    object=tgt,
                    limit=50,
                    persist=False,
                    ev_limit=3,
                    timeout=10
                )

                count = len(processor.statements)
                print(f"  Statements: {count}")

                if count > 0:
                    all_statements[query] = processor.statements
                    for stmt in processor.statements:
                        statement_hashes.add(stmt.get_hash())

            except Exception as e:
                print(f"  Error: {e}")

        print()

    # Summary
    print("=" * 80)
    print(f"Total unique statements: {len(statement_hashes)}")
    print(f"Total queries: {len(pm25_variants) * len(il6_variants)}")
    print(f"Queries with results: {len(all_statements)}")

    if statement_hashes:
        print(f"\n✓ Exhaustive search WORKS - found {len(statement_hashes)} unique statements")
    else:
        print(f"\n✗ Exhaustive search FAILED - no statements found")
    print()


def test_known_working_pathway():
    """Test a known working pathway to verify INDRA is accessible."""

    print("=" * 80)
    print("Known Working Pathway Test (NF-κB → IL6 → CRP)")
    print("=" * 80)
    print()

    pathways = [
        ("NFKB1", "IL6"),
        ("IL6", "CRP"),
        ("NF-κB", "IL6"),  # Alternative name
        ("NF-kappa B", "IL6"),  # Full name
    ]

    for source, target in pathways:
        print(f"Testing: {source} → {target}")

        try:
            processor = idr.get_statements(
                subject=source,
                object=target,
                limit=10,
                persist=False,
                ev_limit=3
            )

            count = len(processor.statements)
            print(f"  Statements: {count}")

            if count > 0:
                stmt = processor.statements[0]
                print(f"  Example: {stmt.subj.name} ({stmt.subj.db_refs})")
                print(f"           → {stmt.obj.name} ({stmt.obj.db_refs})")
                print(f"  Type: {stmt.__class__.__name__}, Belief: {stmt.belief:.3f}")

        except Exception as e:
            print(f"  Error: {e}")

        print()


if __name__ == "__main__":
    print("\n")
    print("🧬 Testing INDRA DB Query Formats")
    print("Purpose: Determine optimal query strategy for exhaustive synonym search")
    print("\n")

    # Run tests
    test_known_working_pathway()
    test_query_formats()
    test_exhaustive_synonym_search()

    print("\n")
    print("✓ Test complete - check results above")
    print("This script can be deleted after reviewing results")
    print("\n")
