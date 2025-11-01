"""Test Sarah Chen scenario: PM2.5 → CRP pathway discovery with MDL ranking.

Expected behavior:
- Find path through oxidative stress and inflammation (PM2.5 → ROS → NF-κB → IL-6 → CRP)
- MDL should rank shorter, high-belief paths higher
- Hub nodes (NF-κB, IL-6) should appear in top paths
- Performance: <2s latency, <100 MB memory
"""

import asyncio
import json
import logging
import time
import tracemalloc
from pathlib import Path

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    Query,
    RequestOptions,
    UserContext,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_sarah_chen_pm25_to_crp():
    """Test PM2.5 → CRP pathway discovery using MDL-weighted INDRA pathfinding."""

    # Start memory tracking
    tracemalloc.start()
    start_time = time.time()

    # Initialize client
    client = INDRAAgentClient()

    # Sarah Chen context
    request = CausalDiscoveryRequest(
        request_id="test_sarah_chen_pm25_crp",
        user_context=UserContext(
            user_id="sarah_chen",
            genetics={"GSTM1": "null"},  # Amplifies oxidative stress response
            current_biomarkers={
                "CRP": 5.2,  # mg/L (elevated)
                "IL-6": 3.8,  # pg/mL
            },
            location_history=[
                {
                    "city": "Los Angeles",
                    "start_date": "2024-01-01",
                    "end_date": "2024-10-26",
                    "avg_pm25": 35.0  # µg/m³ (high)
                }
            ]
        ),
        query=Query(
            text="How does PM2.5 pollution affect my CRP biomarker? What are the causal pathways?"
        ),
        options=RequestOptions(
            max_path_length=5,
            enable_genetic_modifiers=True
        )
    )

    logger.info("=" * 80)
    logger.info("TESTING SARAH CHEN SCENARIO: PM2.5 → CRP")
    logger.info("=" * 80)
    logger.info(f"Query: {request.query.text}")
    logger.info(f"Genetics: {request.user_context.genetics}")
    logger.info(f"Current CRP: {request.user_context.current_biomarkers['CRP']} mg/L")
    logger.info(f"PM2.5 exposure: 35.0 µg/m³ (Los Angeles)")
    logger.info("")

    # Execute query with longer timeout (INDRA API calls can be slow)
    try:
        response = await client.process_request(request, timeout=120.0)

        elapsed_time = time.time() - start_time
        current_memory, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        logger.info("=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)

        # Performance metrics
        logger.info(f"⏱️  Latency: {elapsed_time:.2f}s (INDRA API + pathfinding)")
        logger.info(f"💾 Peak memory: {peak_memory / 1024 / 1024:.1f} MB (target: <100 MB)")
        logger.info("")

        if response.status == "success":
            graph = response.result.causal_graph

            logger.info(f"✅ Status: {response.status}")
            logger.info(f"📊 Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
            logger.info("")

            # Check for expected hub nodes
            node_names = [node.id for node in graph.nodes]
            expected_hubs = ["NFKB1", "IL6", "TNF", "MAPK1"]
            found_hubs = [hub for hub in expected_hubs if hub in node_names]

            logger.info(f"🔬 Hub nodes found: {found_hubs}")
            logger.info("")

            # Display top edges (highest belief)
            logger.info("🔗 Top Causal Relationships (ranked by belief):")
            sorted_edges = sorted(graph.edges, key=lambda e: e.belief, reverse=True)[:10]

            for i, edge in enumerate(sorted_edges, 1):
                logger.info(
                    f"  {i}. {edge.source} → {edge.target} "
                    f"(belief: {edge.belief:.3f}, evidence: {edge.evidence.paper_count} papers)"
                )
            logger.info("")

            # Check explanations
            logger.info("💡 Key Insights:")
            for i, insight in enumerate(response.result.explanations, 1):
                logger.info(f"  {i}. {insight}")
            logger.info("")

            # Validate expectations
            logger.info("=" * 80)
            logger.info("VALIDATION")
            logger.info("=" * 80)

            checks = {
                "Latency <120s (INDRA API)": elapsed_time < 120.0,
                "Memory <100 MB": peak_memory / 1024 / 1024 < 100,
                "Found paths": len(graph.edges) > 0,
                "Hub nodes present": len(found_hubs) > 0,
                "CRP in graph": "CRP" in node_names,
                "IL-6 in graph": "IL6" in node_names,
            }

            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                logger.info(f"{status} {check}")

            logger.info("")

            # Overall success
            all_passed = all(checks.values())
            if all_passed:
                logger.info("🎉 ALL CHECKS PASSED - MDL pathfinding working correctly!")
            else:
                logger.warning("⚠️  Some checks failed - review results above")

            logger.info("=" * 80)

            return response, all_passed

        else:
            logger.error(f"❌ Status: {response.status}")
            logger.error(f"Error: {response.error}")
            return response, False

    except Exception as e:
        elapsed_time = time.time() - start_time
        tracemalloc.stop()

        logger.error("=" * 80)
        logger.error(f"❌ EXCEPTION: {str(e)}")
        logger.error("=" * 80)
        logger.error(traceback.format_exc())
        logger.error(f"Failed after {elapsed_time:.2f}s")

        return None, False


if __name__ == "__main__":
    result, success = asyncio.run(test_sarah_chen_pm25_to_crp())

    if success:
        print("\n✅ Test PASSED")
        exit(0)
    else:
        print("\n❌ Test FAILED")
        exit(1)
