"""INDRA network builder v2 - ZERO HARDCODING, complete ontology support.

This module uses INDRA's native ontology grounding across ALL supported databases:
- HGNC (genes)
- CHEBI (chemicals)
- MESH (diseases, chemicals, processes)
- GO (biological processes)
- PUBCHEM, CHEMBL, HMDB (chemicals)
- UP/UniProt (proteins)

NO HARDCODED MAPPINGS. All grounding comes directly from INDRA statements.

Key principle: INDRA provides complete `db_refs` dict for every agent.
We just preserve it. That's it. No invention.
"""

import asyncio
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from indra_agent.core.observability import get_observability
from indra_agent.services.indra_production_client import INDRAProductionClient

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
    convergent_nodes: List[str]
    divergent_nodes: List[str]
    ontology_coverage: Dict[str, int]  # Which ontologies appear (HGNC, CHEBI, etc.)


class INDRANetworkCache:
    """Disk-based cache for downloaded INDRA networks."""

    def __init__(self, cache_dir: str = ".indra_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_age_days = 7

    def _cache_key(self, genes: List[str]) -> str:
        return "_".join(sorted(genes)) + ".pkl"

    def get(self, genes: List[str]) -> Optional[nx.DiGraph]:
        cache_file = self.cache_dir / self._cache_key(genes)

        if not cache_file.exists():
            return None

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
        cache_file = self.cache_dir / self._cache_key(genes)

        with open(cache_file, "wb") as f:
            pickle.dump(graph, f)

        logger.info(
            f"Cached network: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )


class INDRANetworkBuilderV2:
    """Build complete causal networks with ZERO hardcoding.

    All ontology grounding comes from INDRA's native `db_refs`.
    Supports ALL ontologies INDRA provides: HGNC, CHEBI, MESH, GO, PUBCHEM, CHEMBL, HMDB, UP.

    NO invented mappings. NO hardcoded entity names.
    """

    def __init__(self, cache_dir: str = ".indra_cache"):
        self.cache = INDRANetworkCache(cache_dir)
        self.client: Optional[INDRAProductionClient] = None

    async def __aenter__(self):
        self.client = INDRAProductionClient()
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def build_network(
        self,
        genes: List[str],
        preassemble: bool = True,
        use_cache: bool = True,
    ) -> nx.DiGraph:
        """Build complete causal network with INDRA's native ontology grounding.

        Args:
            genes: List of gene symbols (can be ANY entity INDRA recognizes)
            preassemble: Whether to run INDRA preassembly
            use_cache: Whether to use cached networks

        Returns:
            NetworkX DiGraph where:
            - Node IDs: Entity names (uppercase, from INDRA)
            - Node attributes: {
                "db_refs": {"HGNC": "6018", "UP": "P05231", ...},  # ALL ontologies
                "original_name": "IL6"  # Preserve INDRA casing
              }
            - Edge attributes: {
                "statements": [...],
                "evidence": [...],
                "belief": 0.95,
                "effect_type": "activates",
                "statement_type": "Activation"
              }
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
            statements = await self.client.get_paths_between(
                genes, preassemble=preassemble
            )

        logger.info(f"Downloaded {len(statements)} statements from INDRA")

        # Build NetworkX graph with complete ontology grounding
        graph = self._build_graph_from_statements(statements)

        # Cache result
        if use_cache:
            self.cache.set(genes, graph)

        return graph

    def _build_graph_from_statements(
        self, statements: List[Dict[str, Any]]
    ) -> nx.DiGraph:
        """Convert INDRA statements to NetworkX DiGraph.

        CRITICAL: Preserves ALL ontology grounding from INDRA's db_refs.
        NO hardcoding. NO name normalization beyond uppercase.

        Args:
            statements: List of INDRA statements

        Returns:
            NetworkX DiGraph with node attributes containing complete db_refs
        """
        graph = nx.DiGraph()

        for stmt in statements:
            # Extract agents with COMPLETE ontology grounding
            source_name, source_refs = self._extract_agent_with_grounding(
                stmt.get("subj")
            )
            target_name, target_refs = self._extract_agent_with_grounding(
                stmt.get("obj")
            )

            if not source_name or not target_name:
                continue  # Skip malformed statements

            # Add nodes with ontology grounding (if not already added)
            if not graph.has_node(source_name):
                graph.add_node(
                    source_name,
                    db_refs=source_refs,  # Complete ontology grounding
                    original_name=stmt.get("subj", {}).get(
                        "name"
                    ),  # Preserve INDRA casing
                )

            if not graph.has_node(target_name):
                graph.add_node(
                    target_name,
                    db_refs=target_refs,
                    original_name=stmt.get("obj", {}).get("name"),
                )

            # Determine effect type
            stmt_type = stmt.get("type")
            effect_type = self._infer_effect_type(stmt_type)

            # Extract metadata
            belief = stmt.get("belief", 0.5)
            evidence = stmt.get("evidence", [])

            # Add edge
            if graph.has_edge(source_name, target_name):
                # Merge with existing edge
                existing = graph[source_name][target_name]
                existing["statements"].append(stmt)
                existing["evidence"].extend(evidence)
                existing["belief"] = max(existing["belief"], belief)
            else:
                # Create new edge
                graph.add_edge(
                    source_name,
                    target_name,
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

    def _extract_agent_with_grounding(
        self, agent_dict: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[str], Dict[str, str]]:
        """Extract entity name and COMPLETE ontology grounding from INDRA agent.

        INDRA provides grounding across ALL these ontologies:
        - HGNC: genes (e.g., "6018" for IL6)
        - UP/UniProt: proteins (e.g., "P05231" for IL6)
        - EGID: Entrez Gene IDs
        - CHEBI: chemicals (e.g., "CHEBI:29678" for sodium arsenite)
        - MESH: chemicals, diseases, processes (e.g., "C017947")
        - PUBCHEM: chemicals (e.g., "443495")
        - CHEMBL: chemicals (e.g., "CHEMBL1909078")
        - HMDB: metabolites
        - GO: biological processes
        - CAS: Chemical Abstracts Service registry numbers

        We preserve ALL of these. NO filtering. NO hardcoding.

        Args:
            agent_dict: INDRA agent structure from statement

        Returns:
            Tuple of (entity_name_uppercase, complete_db_refs_dict)
        """
        if not agent_dict:
            return None, {}

        name = agent_dict.get("name")
        if not name:
            return None, {}

        # Get COMPLETE database references (all ontologies INDRA provides)
        db_refs = agent_dict.get("db_refs", {})

        # Normalize name to uppercase for NetworkX node IDs (consistency)
        # But preserve original casing in node attributes
        return name.upper(), db_refs

    def _infer_effect_type(self, stmt_type: str) -> str:
        """Infer effect type from INDRA statement type.

        Maps INDRA's 50+ statement types to our 4 canonical types.
        This is the ONLY normalization we do (statement type → effect type).
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
        """Compute statistics including ontology coverage."""
        num_nodes = graph.number_of_nodes()
        num_edges = graph.number_of_edges()

        # Count total statements
        num_statements = sum(
            len(data["statements"]) for _, _, data in graph.edges(data=True)
        )

        # Average belief and evidence
        beliefs = [data["belief"] for _, _, data in graph.edges(data=True)]
        avg_belief = sum(beliefs) / len(beliefs) if beliefs else 0.0

        evidence_counts = [len(data["evidence"]) for _, _, data in graph.edges(data=True)]
        avg_evidence = (
            sum(evidence_counts) / len(evidence_counts) if evidence_counts else 0.0
        )

        # Max path length
        try:
            if nx.is_weakly_connected(graph):
                max_path_length = nx.diameter(graph)
            else:
                largest_cc = max(nx.weakly_connected_components(graph), key=len)
                subgraph = graph.subgraph(largest_cc)
                max_path_length = nx.diameter(subgraph)
        except nx.NetworkXError:
            max_path_length = 0

        # Convergent/divergent nodes
        convergent_nodes = [node for node in graph.nodes() if graph.in_degree(node) > 1]
        divergent_nodes = [node for node in graph.nodes() if graph.out_degree(node) > 1]

        # Ontology coverage (which databases appear in db_refs)
        ontology_counts = {}
        for node, data in graph.nodes(data=True):
            db_refs = data.get("db_refs", {})
            for db_name in db_refs.keys():
                ontology_counts[db_name] = ontology_counts.get(db_name, 0) + 1

        logger.info(
            f"Network stats: {num_nodes} nodes, {num_edges} edges, "
            f"max_path_length={max_path_length}, "
            f"{len(convergent_nodes)} convergent nodes"
        )
        logger.info(f"Ontology coverage: {dict(sorted(ontology_counts.items()))}")

        return NetworkStats(
            num_nodes=num_nodes,
            num_edges=num_edges,
            num_statements=num_statements,
            avg_belief=avg_belief,
            avg_evidence_per_edge=avg_evidence,
            max_path_length=max_path_length,
            convergent_nodes=convergent_nodes,
            divergent_nodes=divergent_nodes,
            ontology_coverage=ontology_counts,
        )

    def find_convergent_pathways(
        self, graph: nx.DiGraph, min_inputs: int = 2
    ) -> Dict[str, List[Tuple[str, str]]]:
        """Find convergent nodes (synergy candidates)."""
        convergent = {}

        for node in graph.nodes():
            in_edges = list(graph.in_edges(node, data=True))

            if len(in_edges) >= min_inputs:
                pathways = [(source, data["effect_type"]) for source, _, data in in_edges]
                convergent[node] = pathways

        logger.info(f"Found {len(convergent)} convergent nodes (min_inputs={min_inputs})")

        return convergent

    def extract_synergy_structure(self, graph: nx.DiGraph) -> List[Dict[str, Any]]:
        """Extract synergy structure from topology (no hardcoding)."""
        convergent = self.find_convergent_pathways(graph, min_inputs=2)
        synergy_candidates = []

        for node, pathways in convergent.items():
            upstream = [source for source, _ in pathways]
            downstream = list(graph.successors(node))

            if not downstream:
                continue

            beliefs = [graph[source][node]["belief"] for source, _ in pathways]

            if any(b < 0.5 for b in beliefs):
                continue

            synergy_candidates.append(
                {
                    "convergent_node": node,
                    "upstream_effectors": upstream,
                    "downstream_targets": downstream,
                    "pathway_beliefs": beliefs,
                    "synergy_hypothesis": f"{' + '.join(upstream)} → {node} → {', '.join(downstream)}",
                    "ontology_grounding": graph.nodes[node].get(
                        "db_refs", {}
                    ),  # Include grounding
                }
            )

        logger.info(f"Extracted {len(synergy_candidates)} synergy candidates from topology")

        return synergy_candidates

    def get_node_ontologies(self, graph: nx.DiGraph, node: str) -> Dict[str, str]:
        """Get all ontology groundings for a node.

        Returns:
            Dict mapping database names to IDs (e.g., {"HGNC": "6018", "UP": "P05231"})
        """
        if not graph.has_node(node):
            return {}

        return graph.nodes[node].get("db_refs", {})

    def find_nodes_by_ontology(
        self, graph: nx.DiGraph, database: str, identifier: str
    ) -> List[str]:
        """Find all nodes with a specific ontology grounding.

        Example:
            # Find all nodes with CHEBI grounding
            chemical_nodes = builder.find_nodes_by_ontology(graph, "CHEBI", "CHEBI:29678")

        Args:
            graph: NetworkX graph
            database: Database name (e.g., "CHEBI", "HGNC", "MESH")
            identifier: Database identifier

        Returns:
            List of node names matching this grounding
        """
        matching_nodes = []

        for node, data in graph.nodes(data=True):
            db_refs = data.get("db_refs", {})
            if db_refs.get(database) == identifier:
                matching_nodes.append(node)

        return matching_nodes


# Convenience function
async def build_indra_network(
    genes: List[str], cache_dir: str = ".indra_cache"
) -> Tuple[nx.DiGraph, NetworkStats]:
    """Build complete INDRA network with ZERO hardcoding.

    Usage:
        graph, stats = await build_indra_network(["CRP", "IL6", "TNF"])

        # Check ontology coverage
        print(f"Ontologies: {stats.ontology_coverage}")
        # → {"HGNC": 5, "UP": 5, "CHEBI": 15, "MESH": 20, ...}

        # Get specific node's groundings
        il6_refs = graph.nodes["IL6"]["db_refs"]
        # → {"HGNC": "6018", "UP": "P05231", "EGID": "3569"}
    """
    async with INDRANetworkBuilderV2(cache_dir=cache_dir) as builder:
        graph = await builder.build_network(genes)
        stats = builder.compute_stats(graph)
        return graph, stats
