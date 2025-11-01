"""Example: Download complete INDRA network and detect synergy structure.

This demonstrates the NEW approach:
1. Download FULL network (not 3-hop limited)
2. Build NetworkX graph with ALL intermediates
3. Extract synergy structure from TOPOLOGY
4. NO INVENTED PARAMETERS

Compare to old approach:
- OLD: Query INDRA API for 3-hop paths, miss complex mechanisms
- NEW: Download complete network, see full causal chains

Run:
    python -m indra_agent.examples.download_full_network
"""

import asyncio
import logging

from indra_agent.services.indra_network_builder import INDRANetworkBuilder

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Download complete INDRA network for Sarah Chen's case."""

    # Sarah Chen's key biomarkers + environmental exposure
    genes = [
        "CRP",  # C-reactive protein (inflammation)
        "IL6",  # Interleukin-6 (cytokine)
        "NFKB1",  # NF-κB (transcription factor)
        "TNF",  # Tumor necrosis factor
        "INS",  # Insulin (metabolic)
        "IRS1",  # Insulin receptor substrate 1
        "MAPK8",  # JNK (stress kinase)
    ]

    logger.info("=" * 80)
    logger.info("Downloading complete INDRA network")
    logger.info(f"Genes: {genes}")
    logger.info("=" * 80)

    async with INDRANetworkBuilder() as builder:
        # Download full network (may take 10-30s first time)
        graph = await builder.build_network(genes, use_cache=True)

        # Compute statistics
        stats = builder.compute_stats(graph)

        logger.info("\n" + "=" * 80)
        logger.info("NETWORK STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Nodes: {stats.num_nodes}")
        logger.info(f"Edges: {stats.num_edges}")
        logger.info(f"Statements: {stats.num_statements}")
        logger.info(f"Average belief: {stats.avg_belief:.3f}")
        logger.info(f"Average evidence per edge: {stats.avg_evidence_per_edge:.1f}")
        logger.info(f"Max path length: {stats.max_path_length}")
        logger.info(f"Convergent nodes: {len(stats.convergent_nodes)}")
        logger.info(f"Divergent nodes: {len(stats.divergent_nodes)}")

        # Find convergent pathways (synergy candidates)
        convergent = builder.find_convergent_pathways(graph, min_inputs=2)

        logger.info("\n" + "=" * 80)
        logger.info("CONVERGENT PATHWAYS (Synergy Candidates)")
        logger.info("=" * 80)

        for node, pathways in list(convergent.items())[:10]:  # Show top 10
            logger.info(f"\n{node}:")
            for source, effect_type in pathways:
                belief = graph[source][node]["belief"]
                evidence_count = len(graph[source][node]["evidence"])
                logger.info(
                    f"  ← {source} ({effect_type}): "
                    f"belief={belief:.3f}, evidence={evidence_count}"
                )

        # Extract synergy structure
        synergy = builder.extract_synergy_structure(graph)

        logger.info("\n" + "=" * 80)
        logger.info("SYNERGY STRUCTURE FROM TOPOLOGY")
        logger.info("=" * 80)

        for candidate in synergy[:5]:  # Show top 5
            logger.info(f"\nHypothesis: {candidate['synergy_hypothesis']}")
            logger.info(f"  Convergent node: {candidate['convergent_node']}")
            logger.info(f"  Upstream effectors: {candidate['upstream_effectors']}")
            logger.info(f"  Downstream targets: {candidate['downstream_targets']}")
            logger.info(
                f"  Pathway beliefs: {[f'{b:.3f}' for b in candidate['pathway_beliefs']]}"
            )

        # Show example synergy: PM2.5 + smoking → oxidative stress
        logger.info("\n" + "=" * 80)
        logger.info("EXAMPLE SYNERGY: Multi-pathway convergence")
        logger.info("=" * 80)

        if "NFKB1" in stats.convergent_nodes:
            in_edges = list(graph.in_edges("NFKB1", data=True))
            logger.info(
                f"\nNF-κB has {len(in_edges)} incoming pathways (potential synergy):"
            )
            for source, target, data in in_edges:
                logger.info(
                    f"  {source} → {target} ({data['effect_type']}): "
                    f"belief={data['belief']:.3f}, "
                    f"evidence={len(data['evidence'])}"
                )

            # Show downstream effects
            out_edges = list(graph.out_edges("NFKB1", data=True))
            logger.info(f"\nNF-κB has {len(out_edges)} downstream targets:")
            for source, target, data in out_edges[:5]:
                logger.info(
                    f"  {source} → {target} ({data['effect_type']}): "
                    f"belief={data['belief']:.3f}"
                )

        logger.info("\n" + "=" * 80)
        logger.info("NEXT STEPS")
        logger.info("=" * 80)
        logger.info("1. Factor graph construction from this topology")
        logger.info("2. Belief propagation using REAL belief scores")
        logger.info("3. Synergy detection from convergent pathways")
        logger.info("4. NO INVENTED PARAMETERS - all from INDRA database")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
