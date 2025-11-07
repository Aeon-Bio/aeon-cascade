"""Quick test of INDRA DB for environmental pathways - minimal test."""

import os

# Configure INDRA DB URL
os.environ['INDRA_DB_REST_URL'] = 'https://db.indra.bio'

import indra.sources.indra_db_rest as idr

print("="*80)
print("QUICK INDRA DB TEST: Environmental Pathways")
print("="*80)

# Test 1: PM2.5 → IL-6 (environmental)
print("\n[TEST 1] PM2.5 → IL-6")
try:
    processor = idr.get_statements(
        subject="Particulate Matter",
        object="Interleukin-6",
        limit=10,
        timeout=20
    )
    stmts = processor.statements
    print(f"Result: {len(stmts)} statements")
    if stmts:
        print("✅ FOUND ENVIRONMENTAL PATHWAY!")
        for i, stmt in enumerate(stmts[:3]):
            print(f"\n  Statement {i+1}: {stmt}")
            print(f"    Evidence: {len(stmt.evidence)} papers")
    else:
        print("❌ NO STATEMENTS")
except Exception as e:
    print(f"❌ ERROR: {e}")

# Test 2: IL-6 → CRP (control - should work)
print("\n[TEST 2] IL-6 → CRP (CONTROL)")
try:
    processor = idr.get_statements(
        subject="IL6",
        object="CRP",
        limit=10,
        timeout=20
    )
    stmts = processor.statements
    print(f"Result: {len(stmts)} statements")
    if stmts:
        print("✅ CONTROL WORKS")
    else:
        print("❌ CONTROL FAILED (API issue)")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
if len(processor.statements) > 0:
    print("✅ INDRA DB contains environmental data!")
    print("   CTD integration may be REDUNDANT")
else:
    print("❌ INDRA DB does NOT contain environmental data")
    print("   CTD integration is CRITICAL")
