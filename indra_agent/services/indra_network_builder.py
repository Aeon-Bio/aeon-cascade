"""INDRA network builder - Download complete causal topology.

This module builds COMPLETE factor graphs from INDRA's 20M+ statement database.
No more 3-hop limitations. No more invented parameters.

Key capabilities:
1. Download full INDRA network for gene sets (one-time, cached)
2. Build NetworkX graphs with ALL intermediates
3. Extract synergy structure from REAL topology (not made-up ω values)
4. Enable multi-scale analysis across actual biological pathways

Strategy:
- Use INDRA's preassembled networks (already deduplicated + belief scored)
- Cache downloaded networks locally (avoid re-downloading)
- Build factor graphs from complete topology
- Synergy emerges from STRUCTURE, not invented parameters

NO 3AM PAGES.
"""

import asyncio
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from indra_agent.core.observability import get_observability
from indra_agent.services.indra_production_client import (
    INDRAProductionClient,
    get_indra_client,
)

logger = logging.getLogger(__name__)
obs = get_observability()


@dataclass
class NetworkStats:
    """Statistics about downloaded INDRA network."""

    num_nodes: int
    num_edges: int
    num_statements: int
    avg_belief: float
    avg_evidence_per_edge: float
    max_path_length: int
    convergent_nodes: List[str]  # Nodes with multiple incoming edges
    divergent_nodes: List[str]  # Nodes with multiple outgoing edges


class INDRANetworkCache:
    """Disk-based cache for downloaded INDRA networks.

    Cache key: frozenset of gene symbols (order-independent)
    Cache value: NetworkX DiGraph with statement data

    Cache invalidation: 7 days (INDRA updates weekly)
    """

    def __init__(self, cache_dir: str = ".indra_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_age_days = 7

    def _cache_key(self, genes: List[str]) -> str:
        """Generate cache key from gene list."""
        return "_".join(sorted(genes)) + ".pkl"

    def get(self, genes: List[str]) -> Optional[nx.DiGraph]:
        """Retrieve cached network if exists and fresh."""
        cache_file = self.cache_dir / self._cache_key(genes)

        if not cache_file.exists():
            return None

        # Check age
        import time

        age_days = (time.time() - cache_file.stat().st_mtime) / 86400
        if age_days > self.max_age_days:
            logger.info(f"Cache expired ({age_days:.1f} days old), re-downloading")
            cache_file.unlink()
            return None

        logger.info(f"Cache hit for {len(genes)} genes ({age_days:.1f} days old)")

        with open(cache_file, "rb") as f:
            return pickle.load(f)

    def set(self, genes: List[str], graph: nx.DiGraph) -> None:
        """Store network in cache."""
        cache_file = self.cache_dir / self._cache_key(genes)

        with open(cache_file, "wb") as f:
            pickle.dump(graph, f)

        logger.info(f"Cached network: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")


class INDRANetworkBuilder:
    """Build complete causal networks from INDRA database.

    Unlike the old approach (3-hop API queries), this downloads FULL networks
    including ALL intermediates. This enables:
    1. Factor graph construction from real topology
    2. Synergy detection from convergent pathways
    3. Multi-scale analysis across complete chains

    Usage:
        async with INDRANetworkBuilder() as builder:
            graph = await builder.build_network(["BRAF", "MAP2K1", "MAPK1"])
            stats = builder.compute_stats(graph)
            print(f"Downloaded {stats.num_nodes} nodes, {stats.num_edges} edges")
    """

    def __init__(self, cache_dir: str = ".indra_cache"):
        """Initialize network builder with cache."""
        self.cache = INDRANetworkCache(cache_dir)
        self.client: Optional[INDRAProductionClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = INDRAProductionClient()
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def build_network(
        self,
        genes: List[str],
        preassemble: bool = True,
        use_cache: bool = True,
    ) -> nx.DiGraph:
        """Build complete causal network for gene set.

        This downloads ALL paths between genes, not just 3-hop neighbors.
        Result includes all intermediates (NF-κB, oxidative stress, etc.).

        Args:
            genes: List of HGNC gene symbols
            preassemble: Whether to run INDRA preassembly (deduplication)
            use_cache: Whether to use cached networks

        Returns:
            NetworkX DiGraph with:
            - Nodes: Gene symbols, molecular entities, biomarkers
            - Edges: Causal relationships with belief scores
            - Edge attributes: statements, evidence, belief, effect_type

        Example:
            graph = await builder.build_network(["BRAF", "MAP2K1", "MAPK1"])
            # Returns complete network with ALL intermediates
        """
        logger.info(f"Building network for {len(genes)} genes: {genes}")

        # Check cache
        if use_cache:
            cached = self.cache.get(genes)
            if cached is not None:
                obs.record_indra_call(latency_ms=0, cache_hit=True)
                return cached

        # Download from INDRA
        with obs.trace_operation("indra_network_download", num_genes=len(genes)):
            statements = await self.client.get_paths_between(genes, preassemble=preassemble)

        logger.info(f"Downloaded {len(statements)} statements from INDRA")

        # Build NetworkX graph
        graph = self._build_graph_from_statements(statements)

        # Cache result
        if use_cache:
            self.cache.set(genes, graph)

        return graph

    def _build_graph_from_statements(
        self, statements: List[Dict[str, Any]]
    ) -> nx.DiGraph:
        """Convert INDRA statements to NetworkX DiGraph.

        Each statement becomes one or more edges with:
        - source: subject of statement (agent doing the action)
        - target: object of statement (agent being acted upon)
        - belief: INDRA belief score [0, 1]
        - evidence: list of supporting papers
        - statement_type: Phosphorylation, Activation, etc.
        - effect_type: "activates" | "inhibits" | "increases" | "decreases"

        Args:
            statements: List of INDRA statements (from API)

        Returns:
            NetworkX DiGraph with statement metadata
        """
        graph = nx.DiGraph()

        for stmt in statements:
            # Extract source and target entities
            source = self._extract_agent(stmt.get("subj"))
            target = self._extract_agent(stmt.get("obj"))

            if not source or not target:
                continue  # Skip malformed statements

            # Determine effect type
            stmt_type = stmt.get("type")
            effect_type = self._infer_effect_type(stmt_type)

            # Extract metadata
            belief = stmt.get("belief", 0.5)
            evidence = stmt.get("evidence", [])

            # Add edge (multi-edge graph, can have multiple statement types)
            if graph.has_edge(source, target):
                # Merge with existing edge
                existing = graph[source][target]
                existing["statements"].append(stmt)
                existing["evidence"].extend(evidence)
                existing["belief"] = max(existing["belief"], belief)  # Use strongest belief
            else:
                # Create new edge
                graph.add_edge(
                    source,
                    target,
                    statements=[stmt],
                    evidence=evidence,
                    belief=belief,
                    effect_type=effect_type,
                    statement_type=stmt_type,
                )

        logger.info(
            f"Built graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )

        return graph

    def _extract_agent(self, agent_dict: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract entity name from INDRA agent dict.

        INDRA agents have complex structure:
        {
            "name": "BRAF",
            "db_refs": {"HGNC": "1097", "UP": "P15056"},
            "mods": [...],
            "mutations": [...]
        }

        For now, use simple name extraction. Could extend to include
        post-translational modifications if needed.

        Args:
            agent_dict: INDRA agent structure

        Returns:
            Entity name (gene symbol, protein name, etc.)
        """
        if not agent_dict:
            return None

        name = agent_dict.get("name")
        if not name:
            return None

        # Normalize to uppercase (BRAF, not Braf)
        return name.upper()

    def _infer_effect_type(self, stmt_type: str) -> str:
        """Infer effect type from INDRA statement type.

        INDRA has ~50 statement types. Map to our 4 canonical effect types:
        - activates: Activation, Phosphorylation (activating)
        - inhibits: Inhibition, Dephosphorylation
        - increases: IncreaseAmount, Stabilization
        - decreases: DecreaseAmount, Degradation

        Args:
            stmt_type: INDRA statement type

        Returns:
            Effect type for our API
        """
        ACTIVATION_TYPES = {
            "Activation",
            "Phosphorylation",
            "Ubiquitination",
            "Acetylation",
        }
        INHIBITION_TYPES = {
            "Inhibition",
            "Dephosphorylation",
            "Deubiquitination",
            "Deacetylation",
        }
        INCREASE_TYPES = {"IncreaseAmount", "Stabilization"}
        DECREASE_TYPES = {"DecreaseAmount", "Degradation"}

        if stmt_type in ACTIVATION_TYPES:
            return "activates"
        elif stmt_type in INHIBITION_TYPES:
            return "inhibits"
        elif stmt_type in INCREASE_TYPES:
            return "increases"
        elif stmt_type in DECREASE_TYPES:
            return "decreases"
        else:
            # Default to generic activation
            return "activates"

    def compute_stats(self, graph: nx.DiGraph) -> NetworkStats:
        """Compute statistics about downloaded network.

        Useful for:
        1. Debugging (did we get the expected network?)
        2. Performance tracking (how big are our graphs?)
        3. Synergy detection (which nodes are convergent?)

        Args:
            graph: NetworkX DiGraph from build_network()

        Returns:
            NetworkStats with topology metrics
        """
        num_nodes = graph.number_of_nodes()
        num_edges = graph.number_of_edges()

        # Count total statements
        num_statements = sum(
            len(data["statements"]) for _, _, data in graph.edges(data=True)
        )

        # Average belief and evidence
        beliefs = [data["belief"] for _, _, data in graph.edges(data=True)]
        avg_belief = sum(beliefs) / len(beliefs) if beliefs else 0.0

        evidence_counts = [
            len(data["evidence"]) for _, _, data in graph.edges(data=True)
        ]
        avg_evidence = (
            sum(evidence_counts) / len(evidence_counts) if evidence_counts else 0.0
        )

        # Max path length (longest shortest path)
        try:
            # Only consider connected components
            if nx.is_weakly_connected(graph):
                max_path_length = nx.diameter(graph)
            else:
                # Find largest component
                largest_cc = max(nx.weakly_connected_components(graph), key=len)
                subgraph = graph.subgraph(largest_cc)
                max_path_length = nx.diameter(subgraph)
        except nx.NetworkXError:
            max_path_length = 0

        # Convergent nodes (multiple inputs = potential synergy)
        convergent_nodes = [
            node for node in graph.nodes() if graph.in_degree(node) > 1
        ]

        # Divergent nodes (multiple outputs = broadcast hubs)
        divergent_nodes = [
            node for node in graph.nodes() if graph.out_degree(node) > 1
        ]

        logger.info(
            f"Network stats: {num_nodes} nodes, {num_edges} edges, "
            f"max_path_length={max_path_length}, "
            f"{len(convergent_nodes)} convergent nodes"
        )

        return NetworkStats(
            num_nodes=num_nodes,
            num_edges=num_edges,
            num_statements=num_statements,
            avg_belief=avg_belief,
            avg_evidence_per_edge=avg_evidence,
            max_path_length=max_path_length,
            convergent_nodes=convergent_nodes,
            divergent_nodes=divergent_nodes,
        )

    def find_convergent_pathways(
        self, graph: nx.DiGraph, min_inputs: int = 2
    ) -> Dict[str, List[Tuple[str, str]]]:
        """Find nodes with multiple incoming pathways (synergy candidates).

        These are nodes where multiple upstream effectors converge, potentially
        creating super-additive effects. Example:

        PM2.5 ──→ Oxidative Stress ──→ NF-κB
                                         ↓
        Smoking ──→ Oxidative Stress ──→ IL-6

        Here, oxidative stress is convergent (multiple inputs).
        NF-κB → IL-6 could show synergy if both PM2.5 and smoking are present.

        Args:
            graph: NetworkX DiGraph
            min_inputs: Minimum number of incoming edges to qualify as convergent

        Returns:
            Dict mapping convergent node → list of (source, edge_type) pairs

        Example:
            convergent = builder.find_convergent_pathways(graph)
            # {
            #   "oxidative_stress": [("PM2.5", "increases"), ("smoking", "increases")],
            #   "IL-6": [("NF-κB", "activates"), ("TNF-α", "activates")]
            # }
        """
        convergent = {}

        for node in graph.nodes():
            in_edges = list(graph.in_edges(node, data=True))

            if len(in_edges) >= min_inputs:
                # Record all input pathways
                pathways = [
                    (source, data["effect_type"]) for source, _, data in in_edges
                ]
                convergent[node] = pathways

        logger.info(f"Found {len(convergent)} convergent nodes (min_inputs={min_inputs})")

        return convergent

    def extract_synergy_structure(
        self, graph: nx.DiGraph
    ) -> List[Dict[str, Any]]:
        """Extract synergy structure from network topology.

        This identifies pairs of pathways that could exhibit synergistic effects
        based on TOPOLOGY alone (no invented ω parameters).

        Synergy criteria:
        1. Two+ pathways converge on same intermediate node
        2. Intermediate node has downstream effects on target biomarker
        3. Both pathways have reasonable belief (>0.5)

        Args:
            graph: NetworkX DiGraph

        Returns:
            List of synergy candidates with structure:
            {
                "convergent_node": "oxidative_stress",
                "upstream_effectors": ["PM2.5", "smoking"],
                "downstream_targets": ["IL-6", "CRP"],
                "pathway_beliefs": [0.78, 0.82],
                "synergy_hypothesis": "PM2.5 + smoking → oxidative stress → IL-6"
            }

        These are HYPOTHESES, not predictions. Actual synergy magnitude requires
        experimental data or factor graph inference.
        """
        convergent = self.find_convergent_pathways(graph, min_inputs=2)
        synergy_candidates = []

        for node, pathways in convergent.items():
            # Get upstream effectors
            upstream = [source for source, _ in pathways]

            # Get downstream targets
            downstream = list(graph.successors(node))

            if not downstream:
                continue  # No downstream effects, can't have synergy on biomarkers

            # Get pathway beliefs
            beliefs = [
                graph[source][node]["belief"] for source, _ in pathways
            ]

            # Filter weak pathways
            if any(b < 0.5 for b in beliefs):
                continue

            # Record synergy candidate
            synergy_candidates.append(
                {
                    "convergent_node": node,
                    "upstream_effectors": upstream,
                    "downstream_targets": downstream,
                    "pathway_beliefs": beliefs,
                    "synergy_hypothesis": f"{' + '.join(upstream)} → {node} → {', '.join(downstream)}",
                }
            )

        logger.info(f"Extracted {len(synergy_candidates)} synergy candidates from topology")

        return synergy_candidates


# Convenience function for one-shot network building
async def build_indra_network(
    genes: List[str],
    cache_dir: str = ".indra_cache",
) -> Tuple[nx.DiGraph, NetworkStats]:
    """Build complete INDRA network for genes (convenience wrapper).

    Usage:
        graph, stats = await build_indra_network(["BRAF", "MAP2K1", "MAPK1"])
        print(f"Downloaded {stats.num_nodes} nodes, max path length: {stats.max_path_length}")

    Args:
        genes: List of gene symbols
        cache_dir: Directory for network cache

    Returns:
        (graph, stats) tuple
    """
    async with INDRANetworkBuilder(cache_dir=cache_dir) as builder:
        graph = await builder.build_network(genes)
        stats = builder.compute_stats(graph)
        return graph, stats
