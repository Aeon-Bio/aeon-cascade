"""Test whether INDRA has environmental → molecular pathways.

This answers DATA_ARCHITECTURE.md Q1:
- Does INDRA have PM2.5 → oxidative stress?
- Does INDRA have Ozone → inflammation?
- Does INDRA have Cigarette smoke → ROS?

If YES: We can use INDRA directly for environmental interventions
If NO: We need separate environmental exposure modeling layer
"""

import asyncio
import logging

from indra_agent.services.indra_production_client import INDRAProductionClient

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_environmental_pathways():
    """Test INDRA for environmental → molecular pathways."""

    test_cases = [
        # Test 1: PM2.5 → oxidative stress
        {
            "name": "PM2.5 → oxidative stress",
            "source": "Particulate Matter",  # Try full name
            "targets": ["oxidative stress", "ROS", "reactive oxygen species"],
        },
        # Test 2: Ozone → inflammation
        {
            "name": "Ozone → inflammation",
            "source": "Ozone",
            "targets": ["inflammation", "IL6", "TNF", "NF-κB"],
        },
        # Test 3: Cigarette smoke → ROS
        {
            "name": "Cigarette smoke → ROS",
            "source": "cigarette smoke",
            "targets": ["ROS", "reactive oxygen species", "oxidative stress"],
        },
        # Test 4: Air pollutants (MESH term) → biomarkers
        {
            "name": "Air pollutants → biomarkers",
            "source": "Air Pollutants",  # MESH:D000393
            "targets": ["CRP", "IL6", "oxidative stress"],
        },
    ]

    async with INDRAProductionClient() as client:
        for test in test_cases:
            logger.info("\n" + "=" * 80)
            logger.info(f"TEST: {test['name']}")
            logger.info("=" * 80)

            # Try querying for paths
            for target in test["targets"]:
                try:
                    statements = await client.get_paths_between(
                        [test["source"], target], preassemble=True
                    )

                    if statements:
                        logger.info(
                            f"\n✅ FOUND {len(statements)} statements: {test['source']} → {target}"
                        )

                        # Show first few statements
                        for stmt in statements[:3]:
                            subj = stmt.get("subj", {}).get("name", "?")
                            obj = stmt.get("obj", {}).get("name", "?")
                            stmt_type = stmt.get("type", "?")
                            belief = stmt.get("belief", 0.0)
                            evidence_count = len(stmt.get("evidence", []))

                            logger.info(
                                f"  {subj} --[{stmt_type}]--> {obj} "
                                f"(belief={belief:.2f}, evidence={evidence_count})"
                            )

                            # Show db_refs to verify ontology grounding
                            subj_refs = stmt.get("subj", {}).get("db_refs", {})
                            obj_refs = stmt.get("obj", {}).get("db_refs", {})

                            if subj_refs:
                                logger.info(f"    Source grounding: {subj_refs}")
                            if obj_refs:
                                logger.info(f"    Target grounding: {obj_refs}")

                    else:
                        logger.info(
                            f"❌ NO PATHS: {test['source']} → {target}"
                        )

                except Exception as e:
                    logger.error(
                        f"⚠️  ERROR querying {test['source']} → {target}: {e}"
                    )

    logger.info("\n" + "=" * 80)
    logger.info("CONCLUSION")
    logger.info("=" * 80)
    logger.info(
        "Check results above to determine if INDRA has environmental pathways."
    )
    logger.info(
        "If YES: Use INDRA directly (no separate exposure modeling needed)"
    )
    logger.info(
        "If NO: Need intermediate layer to map exposures → INDRA molecular entities"
    )


if __name__ == "__main__":
    asyncio.run(test_environmental_pathways())
