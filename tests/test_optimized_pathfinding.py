"""Test optimized INDRA pathfinding (single query + Dijkstra).

Tests the Phase 2.1-2.3 optimizations:
- Single efficient query with persist=False
- Dijkstra with path_limit=10 (not shortest_simple_paths with 500)
- Skip preassembly (belief filtering only)

Expected: <10s latency, <100 MB memory for IL6 → CRP (direct path exists)
"""

import asyncio
import logging
import time
import tracemalloc

from indra_agent.services.indranet_service import IndraNetService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_optimized_il6_to_crp():
    """Test IL6 → CRP pathfinding with optimized queries.

    IL6 → CRP has direct statements in INDRA, so this tests:
    1. Single query efficiency (not triple query)
    2. Dijkstra pathfinding (not k-shortest)
    3. Belief filtering (not preassembly)
    """

    tracemalloc.start()
    start_time = time.time()

    service = IndraNetService()

    logger.info("=" * 80)
    logger.info("TESTING OPTIMIZED PATHFINDING: IL6 → CRP")
    logger.info("=" * 80)
    logger.info("Expected: <10s latency, direct paths found")
    logger.info("")

    try:
        # Test find_causal_paths (exercises all optimizations)
        paths = await service.find_causal_paths(
            source="IL6",
            target="CRP",
            max_depth=4,
            use_cache=False  # Force fresh query
        )

        elapsed = time.time() - start_time
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        logger.info("=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)
        logger.info(f"⏱️  Latency: {elapsed:.2f}s (target: <10s)")
        logger.info(f"💾 Peak memory: {peak_mem / 1024 / 1024:.1f} MB (target: <100 MB)")
        logger.info(f"🔗 Paths found: {len(paths)}")
        logger.info("")

        if paths:
            logger.info("Top 3 paths:")
            for i, path in enumerate(paths[:3], 1):
                nodes = " → ".join(path.get("nodes", []))
                mdl_score = path.get("mdl_score", 0.0)
                belief = path.get("avg_belief", 0.0)
                evidence = path.get("total_evidence", 0)

                logger.info(f"  {i}. {nodes}")
                logger.info(f"     MDL: {mdl_score:.3f}, Belief: {belief:.3f}, Evidence: {evidence} papers")

        logger.info("")
        logger.info("=" * 80)
        logger.info("VALIDATION")
        logger.info("=" * 80)

        checks = {
            "Latency <10s": elapsed < 10.0,
            "Memory <100 MB": peak_mem / 1024 / 1024 < 100,
            "Found paths": len(paths) > 0,
            "Direct path (length ≤3)": any(len(p.get("nodes", [])) <= 3 for p in paths) if paths else False
        }

        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            logger.info(f"{status} {check}")

        all_passed = all(checks.values())

        logger.info("")
        if all_passed:
            logger.info("🎉 ALL CHECKS PASSED - Optimizations working!")
        else:
            logger.warning("⚠️  Some checks failed - review results")

        logger.info("=" * 80)

        return paths, all_passed, elapsed, peak_mem

    except Exception as e:
        elapsed = time.time() - start_time
        tracemalloc.stop()

        logger.error("=" * 80)
        logger.error(f"❌ EXCEPTION: {str(e)}")
        logger.error("=" * 80)
        import traceback
        logger.error(traceback.format_exc())
        logger.error(f"Failed after {elapsed:.2f}s")

        return [], False, elapsed, 0


async def test_optimized_tnf_to_il6():
    """Test TNF → IL6 pathfinding (another direct path)."""

    tracemalloc.start()
    start_time = time.time()

    service = IndraNetService()

    logger.info("")
    logger.info("=" * 80)
    logger.info("TESTING OPTIMIZED PATHFINDING: TNF → IL6")
    logger.info("=" * 80)

    paths = await service.find_causal_paths(
        source="TNF",
        target="IL6",
        max_depth=3,
        use_cache=False
    )

    elapsed = time.time() - start_time
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    logger.info(f"⏱️  Latency: {elapsed:.2f}s")
    logger.info(f"🔗 Paths found: {len(paths)}")

    passed = elapsed < 10.0 and len(paths) > 0
    status = "✅" if passed else "❌"
    logger.info(f"{status} TNF → IL6 pathfinding")
    logger.info("=" * 80)

    return paths, passed


async def main():
    """Run all optimization tests."""

    logger.info("\n🚀 TESTING PHASE 2.1-2.3 OPTIMIZATIONS")
    logger.info("Expected improvements:")
    logger.info("  - Single query: 60s → ~6s (10× faster)")
    logger.info("  - Dijkstra: 500 paths → 10 paths (milliseconds)")
    logger.info("  - No preassembly: 53s saved, 4GB → 100MB")
    logger.info("")

    # Test 1: IL6 → CRP
    paths1, passed1, latency1, memory1 = await test_optimized_il6_to_crp()

    # Test 2: TNF → IL6
    paths2, passed2 = await test_optimized_tnf_to_il6()

    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("OPTIMIZATION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"IL6 → CRP: {latency1:.2f}s, {memory1/1024/1024:.1f} MB, {len(paths1)} paths")
    logger.info(f"TNF → IL6: {len(paths2)} paths")
    logger.info("")

    all_passed = passed1 and passed2

    if all_passed:
        logger.info("✅ OPTIMIZATIONS VALIDATED")
        logger.info("   - Single query working (<10s)")
        logger.info("   - Dijkstra finding paths")
        logger.info("   - Memory efficient (<100 MB)")
        return 0
    else:
        logger.error("❌ OPTIMIZATION VALIDATION FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
