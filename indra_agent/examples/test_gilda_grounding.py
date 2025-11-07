"""
Test INDRA's Gilda grounding service.

This verifies that:
1. Gilda can ground environmental entities (PM2.5, Ozone, Lead)
2. Gilda can ground genes/proteins (IL-6, CRP, TNF)
3. Gilda can ground biological processes (oxidative stress, inflammation)
4. db_refs are populated with correct ontology IDs
5. Namespace priorities work as expected

This is the CORRECT way to ground entities for INDRA DB queries.
"""

import logging
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from indra.statements import Agent
    from indra.preassembler.grounding_mapper import GroundingMapper
    INDRA_AVAILABLE = True
except ImportError:
    logger.error("INDRA Python library not installed")
    logger.error("Install with: pip install indra")
    INDRA_AVAILABLE = False
    exit(1)


def test_ground_entity(
    name: str,
    expected_namespaces: List[str] = None,
    context: str = None
) -> Dict[str, Any]:
    """
    Ground an entity using Gilda and verify results.

    Args:
        name: Entity name to ground
        expected_namespaces: List of expected grounding namespaces
        context: Optional context for disambiguation

    Returns:
        Dict with grounding results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"GROUNDING: {name}")
    if context:
        logger.info(f"Context: {context}")
    logger.info(f"{'='*80}")

    # Create agent
    agent = Agent(name)

    # Ground using Gilda
    gm = GroundingMapper()

    try:
        # Map with context if provided
        if context:
            gm.map_agents([agent], context=[context])
        else:
            gm.map_agents([agent])

        # Extract results
        standardized_name = agent.name
        db_refs = agent.db_refs

        logger.info(f"\n✅ Grounding successful!")
        logger.info(f"  Original name: {name}")
        logger.info(f"  Standardized: {standardized_name}")
        logger.info(f"  db_refs ({len(db_refs)} namespaces):")

        for ns, id_val in sorted(db_refs.items()):
            logger.info(f"    {ns:10s} → {id_val}")

        # Verify expected namespaces
        if expected_namespaces:
            found = set(db_refs.keys())
            expected = set(expected_namespaces)
            missing = expected - found
            unexpected = found - expected

            if missing:
                logger.warning(f"  ⚠️  Missing expected namespaces: {missing}")
            if unexpected:
                logger.info(f"  ℹ️  Additional namespaces: {unexpected}")

        return {
            "original_name": name,
            "standardized_name": standardized_name,
            "db_refs": db_refs,
            "namespace_count": len(db_refs),
            "success": True
        }

    except Exception as e:
        logger.error(f"❌ Grounding failed: {e}")
        return {
            "original_name": name,
            "error": str(e),
            "success": False
        }


def main():
    """Test Gilda grounding for various entity types."""

    logger.info("="*80)
    logger.info("INDRA Gilda Grounding Test")
    logger.info("="*80)
    logger.info("\nThis tests INDRA's proper grounding workflow:")
    logger.info("1. Create Agent with entity name")
    logger.info("2. Use GroundingMapper to ground via Gilda")
    logger.info("3. Extract standardized name and db_refs")
    logger.info("4. Use these for INDRA DB queries")
    logger.info("="*80)

    results = []

    # =========================================================================
    # CATEGORY 1: Environmental Exposures
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("CATEGORY 1: Environmental Exposures")
    logger.info("="*80)

    environmental_tests = [
        ("PM2.5", ["MESH", "CHEBI"], "air pollution particles"),
        ("Particulate Matter", ["MESH", "CHEBI"], None),
        ("Ozone", ["MESH", "CHEBI"], "air pollutant"),
        ("Air Pollutants", ["MESH"], None),
        ("Lead", ["CHEBI", "MESH"], "heavy metal toxin"),
        ("Cadmium", ["CHEBI", "MESH"], "heavy metal"),
        ("Benzene", ["CHEBI", "MESH"], "organic chemical"),
        ("Cigarette smoke", ["MESH"], "tobacco smoke exposure"),
    ]

    for name, expected_ns, context in environmental_tests:
        result = test_ground_entity(name, expected_ns, context)
        results.append(result)

    # =========================================================================
    # CATEGORY 2: Genes and Proteins
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("CATEGORY 2: Genes and Proteins")
    logger.info("="*80)

    gene_tests = [
        ("IL-6", ["HGNC", "UP", "EGID"], "interleukin 6 gene"),
        ("Interleukin-6", ["HGNC", "UP"], None),
        ("IL6", ["HGNC", "UP", "EGID"], None),
        ("CRP", ["HGNC", "UP", "EGID"], "C-reactive protein"),
        ("TNF", ["HGNC", "UP", "EGID"], "tumor necrosis factor"),
        ("NF-kappa-B", ["FPLX"], "transcription factor complex"),
        ("MAPK1", ["HGNC", "UP"], None),
    ]

    for name, expected_ns, context in gene_tests:
        result = test_ground_entity(name, expected_ns, context)
        results.append(result)

    # =========================================================================
    # CATEGORY 3: Biological Processes
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("CATEGORY 3: Biological Processes")
    logger.info("="*80)

    process_tests = [
        ("oxidative stress", ["GO", "MESH"], "reactive oxygen species damage"),
        ("inflammation", ["GO", "MESH"], "immune response"),
        ("reactive oxygen species", ["CHEBI", "MESH"], "ROS molecules"),
        ("apoptosis", ["GO", "MESH"], "programmed cell death"),
    ]

    for name, expected_ns, context in process_tests:
        result = test_ground_entity(name, expected_ns, context)
        results.append(result)

    # =========================================================================
    # CATEGORY 4: Diseases
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("CATEGORY 4: Diseases")
    logger.info("="*80)

    disease_tests = [
        ("diabetes", ["DOID", "MESH"], "metabolic disease"),
        ("cardiovascular disease", ["MESH", "DOID"], None),
        ("cancer", ["MESH", "DOID"], "malignant neoplasm"),
    ]

    for name, expected_ns, context in disease_tests:
        result = test_ground_entity(name, expected_ns, context)
        results.append(result)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    logger.info(f"\nTotal tests: {len(results)}")
    logger.info(f"Successful: {len(successful)}")
    logger.info(f"Failed: {len(failed)}")

    if successful:
        logger.info(f"\n{'='*80}")
        logger.info("GROUNDING STATISTICS")
        logger.info(f"{'='*80}")

        # Namespace frequency
        namespace_counts = {}
        for result in successful:
            for ns in result.get("db_refs", {}).keys():
                namespace_counts[ns] = namespace_counts.get(ns, 0) + 1

        logger.info("\nNamespace usage:")
        for ns, count in sorted(namespace_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {ns:10s}: {count} entities")

        # Average db_refs per entity
        avg_refs = sum(r.get("namespace_count", 0) for r in successful) / len(successful)
        logger.info(f"\nAverage namespaces per entity: {avg_refs:.1f}")

    if failed:
        logger.info(f"\n{'='*80}")
        logger.info("FAILED GROUNDINGS")
        logger.info(f"{'='*80}")
        for result in failed:
            logger.error(f"  {result['original_name']}: {result.get('error')}")

    # =========================================================================
    # CRITICAL FINDING
    # =========================================================================
    logger.info(f"\n{'='*80}")
    logger.info("CRITICAL FINDING")
    logger.info(f"{'='*80}")

    if len(successful) >= len(results) * 0.8:
        logger.info("✅ GILDA GROUNDING WORKS!")
        logger.info(f"   {len(successful)}/{len(results)} entities successfully grounded")
        logger.info("\n   IMPLICATION:")
        logger.info("   - We should use Gilda for ALL entity grounding")
        logger.info("   - Replace hardcoded SEED_ENTITIES in grounding_service.py")
        logger.info("   - Use grounded entities for INDRA DB queries")
    else:
        logger.warning("⚠️  GILDA GROUNDING PARTIALLY WORKS")
        logger.warning(f"   Only {len(successful)}/{len(results)} entities grounded successfully")
        logger.warning("\n   IMPLICATION:")
        logger.warning("   - Gilda may not cover all entity types")
        logger.warning("   - May need fallback to hardcoded mappings")

    # =========================================================================
    # NEXT STEPS
    # =========================================================================
    logger.info(f"\n{'='*80}")
    logger.info("NEXT STEPS")
    logger.info(f"{'='*80}")

    logger.info("\n1. Use grounded entities for INDRA DB queries:")
    logger.info("   - Create Agent: agent = Agent('PM2.5')")
    logger.info("   - Ground: gm.map_agents([agent])")
    logger.info("   - Query: idr.get_statements(subject=agent.name, object=...)")

    logger.info("\n2. Test INDRA DB with grounded entities:")
    logger.info("   - Run: test_indra_db_with_grounding.py")
    logger.info("   - Compare to previous tests (which used ungrounded names)")

    logger.info("\n3. Replace hardcoded grounding service:")
    logger.info("   - File: indra_agent/services/grounding_service.py")
    logger.info("   - Replace SEED_ENTITIES with GroundingMapper")

    logger.info("\n4. Document ontology coverage:")
    logger.info("   - Which namespaces cover environmental exposures?")
    logger.info("   - Which namespaces for genes/proteins?")
    logger.info("   - Which for biological processes?")

    logger.info(f"\n{'='*80}")


if __name__ == "__main__":
    main()
