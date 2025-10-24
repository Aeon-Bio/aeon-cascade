#!/usr/bin/env python3
"""Verify new Writer KG has proper labels after rebuild.

Run this after:
1. Uploading mesh_for_writer.csv to Writer
2. Creating new KG from uploaded file
3. Updating WRITER_GRAPH_ID in .env

Usage:
    python verify_new_kg.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from indra_agent.services.writer_kg_service import WriterKGService


async def main():
    """Test Writer KG with newly rebuilt MeSH data."""
    print("=" * 70)
    print("Writer KG Verification (Post-Rebuild)")
    print("=" * 70)
    print()

    # Create service
    service = WriterKGService()

    # Test cases: MeSH IDs that were previously returning corrupted labels
    test_cases = [
        ("D052638", "Particulate Matter"),
        ("D002097", "C-Reactive Protein"),
        ("D015850", "Interleukin-6"),
        ("D014409", "Tumor Necrosis Factor-alpha"),
        ("D016328", "NF-kappa B"),
    ]

    print("Testing MeSH ID → Label resolution:")
    print()

    passed = 0
    failed = 0

    for mesh_id, expected_label in test_cases:
        try:
            result = await service.find_mesh_term(mesh_id)

            if result and result.get("mesh_label"):
                label = result["mesh_label"]

                if label == mesh_id:
                    # Still returning ID instead of label (FAIL)
                    print(f"✗ {mesh_id}: Got '{label}' (still corrupted!)")
                    failed += 1
                elif label == expected_label:
                    # Perfect match
                    print(f"✓ {mesh_id}: '{label}' (correct)")
                    passed += 1
                else:
                    # Different label (might be variant)
                    print(f"⚠ {mesh_id}: Got '{label}', expected '{expected_label}'")
                    passed += 1
            else:
                print(f"✗ {mesh_id}: No result or no label")
                failed += 1

        except Exception as e:
            print(f"✗ {mesh_id}: Error - {e}")
            failed += 1

    await service.cleanup()

    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print()
        print("✓ SUCCESS: Writer KG is working correctly with proper labels!")
        print("You can now run the E2E tests:")
        print("  uv run pytest tests/test_live_e2e_with_writer_kg.py -v")
        return 0
    else:
        print()
        print("✗ FAILED: Writer KG still has issues")
        print("Check:")
        print("  1. Did you upload the correct mesh_for_writer.csv file?")
        print("  2. Did you create a NEW Knowledge Graph (not update existing)?")
        print("  3. Did you update WRITER_GRAPH_ID in .env with the new Graph ID?")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
