"""IndraNet service for comprehensive biomarker network building.

This service uses INDRA's Python library directly to:
- Build neighborhood networks around biomarkers
- Discover multi-hop causal pathways with MDL-based ranking
- Merge duplicates via preassembly
- Calculate belief scores from multiple sources
- Build signed NetworkX graphs with evidence
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from indra.statements import Statement
from indra.assemblers.indranet import IndraNetAssembler
import indra.sources.indra_db_rest as idr
from indra.explanation.pathfinding import open_dijkstra_search

from indra_agent.services.mdl_weight import create_mdl_weight_function

logger = logging.getLogger(__name__)

# Configure INDRA environment before first use
# INDRA library requires these environment variables to be set
def _configure_indra_environment():
    """Configure INDRA environment variables if not already set.

    INDRA's db_rest module requires INDRA_DB_REST_URL to be configured.
    We set sensible defaults here to avoid IndraConfigError.
    """
    # Set default INDRA DB REST URL if not configured
    if not os.environ.get('INDRA_DB_REST_URL'):
        default_url = os.getenv('INDRA_DB_REST_URL', 'https://db.indra.bio')
        os.environ['INDRA_DB_REST_URL'] = default_url
        logger.info(f"Set INDRA_DB_REST_URL to default: {default_url}")

    # API key is optional - set empty string if not provided
    if 'INDRA_DB_REST_API_KEY' not in os.environ:
        api_key = os.getenv('INDRA_DB_REST_API_KEY', '')
        os.environ['INDRA_DB_REST_API_KEY'] = api_key
        logger.info("INDRA_DB_REST_API_KEY not set - using public access")

# Call configuration at module import
_configure_indra_environment()


class IndraNetworkResult:
    """Result from IndraNet network building."""

    def __init__(
        self,
        graph: nx.DiGraph,
        statements: List[Statement],
        node_names: List[str],
        edge_count: int,
        belief_scores: Dict[Tuple[str, str], float],
        evidence_counts: Dict[Tuple[str, str], int],
    ):
        """Initialize result.

        Args:
            graph: NetworkX directed graph with belief scores
            statements: List of INDRA statements used
            node_names: List of node names in graph
            edge_count: Number of edges in graph
            belief_scores: Dict mapping (source, target) to belief score
            evidence_counts: Dict mapping (source, target) to evidence count
        """
        self.graph = graph
        self.statements = statements
        self.node_names = node_names
        self.edge_count = edge_count
        self.belief_scores = belief_scores
        self.evidence_counts = evidence_counts


class IndraNetService:
    """Build comprehensive biomarker networks using IndraNet assembler.

    The statement cache is designed for single-request scope to avoid memory leaks.
    For long-running services, call clear_cache() after each request.
    """

    # Cache size limit: max 50 queries × ~200 statements = ~10K statements (~50 MB)
    # After this, oldest entries are evicted (LRU)
    MAX_CACHE_SIZE = 50

    def __init__(self, grounding_service=None):
        """Initialize optimized IndraNet service.

        Args:
            grounding_service: Optional GroundingService for synonym expansion.
                             If not provided, will be lazy-initialized with Gilda (INDRA's official grounding).
        """
        self.grounding_service = grounding_service
        self.statement_cache: Dict[str, List[Statement]] = {}
        self._cache_access_order: List[str] = []  # Track LRU order
        logger.info("IndraNet service initialized")

    def clear_cache(self):
        """Clear statement cache to free memory.

        Call this after processing each request to prevent unbounded growth.
        """
        cache_size = len(self.statement_cache)
        if cache_size > 0:
            logger.info(f"Clearing statement cache ({cache_size} entries)")
            self.statement_cache.clear()
            self._cache_access_order.clear()

    def _evict_oldest_cache_entry(self):
        """Evict the oldest cache entry (LRU eviction)."""
        if self._cache_access_order:
            oldest_key = self._cache_access_order.pop(0)
            if oldest_key in self.statement_cache:
                del self.statement_cache[oldest_key]
                logger.debug(f"Evicted cache entry: {oldest_key}")


    async def build_biomarker_network(
        self,
        exposures: List[str],
        biomarkers: List[str],
        max_depth: int = 4,
        belief_threshold: float = 0.3,
    ) -> IndraNetworkResult:
        """Build network for pathfinding between exposures and biomarkers.

        Optimized strategy:
        1. Single efficient query for exposure→biomarker statements
        2. Skip preassembly (INDRA DB already pre-assembled)
        3. Build graph with belief filtering

        Args:
            exposures: List of exposure entities
            biomarkers: List of biomarker entities
            max_depth: Maximum path depth
            belief_threshold: Minimum belief score

        Returns:
            IndraNetworkResult with graph and metadata
        """
        logger.info(
            f"Building network: {len(exposures)} exposures → {len(biomarkers)} biomarkers"
        )

        # Fetch statements for all exposure→biomarker pairs
        all_statements: List[Statement] = []

        for exposure in exposures:
            for biomarker in biomarkers:
                logger.info(f"Fetching: {exposure} → {biomarker}")
                stmts = await self._get_path_statements_optimized(exposure, biomarker)
                all_statements.extend(stmts)
                logger.info(f"Got {len(stmts)} statements")

        if not all_statements:
            logger.warning("No statements - empty network")
            return IndraNetworkResult(
                graph=nx.DiGraph(),
                statements=[],
                node_names=[],
                edge_count=0,
                belief_scores={},
                evidence_counts={},
            )

        logger.info(f"Got {len(all_statements)} statements")

        # Skip preassembly - INDRA DB statements already pre-assembled!
        # Just filter by belief threshold
        filtered_stmts = [s for s in all_statements if s.belief >= belief_threshold]
        logger.info(f"Filtered to {len(filtered_stmts)} high-belief statements")

        # Build graph
        graph, belief_scores, evidence_counts = self._build_signed_graph(
            filtered_stmts, belief_threshold
        )

        logger.info(
            f"Built graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )

        return IndraNetworkResult(
            graph=graph,
            statements=filtered_stmts,
            node_names=list(graph.nodes()),
            edge_count=graph.number_of_edges(),
            belief_scores=belief_scores,
            evidence_counts=evidence_counts,
        )

    async def _get_path_statements_optimized(
        self, source: str, target: str
    ) -> List[Statement]:
        """Exhaustive synonym-based path discovery.

        ARCHITECTURE: This is NOT a simple "grounding" problem.
        Instead, we query INDRA with ALL synonym combinations to let
        molecular intermediates EMERGE from graph structure.

        Strategy:
        1. Get ALL synonyms for source and target (via Writer KG MeSH)
        2. Query INDRA with every synonym combination (parallel)
        3. Merge results - duplicates filtered by INDRA's belief scoring
        4. Let intermediates emerge from merged graph

        This discovers latent causal structures that would be invisible
        with single-name queries.

        Args:
            source: Source entity name (will be expanded to synonyms)
            target: Target entity name (will be expanded to synonyms)

        Returns:
            List of INDRA statements from ALL synonym combinations
        """
        cache_key = f"opt:{source}:{target}"
        if cache_key in self.statement_cache:
            logger.debug(f"Cache hit: {source} → {target}")
            # Move to end of LRU list (most recently used)
            self._cache_access_order.remove(cache_key)
            self._cache_access_order.append(cache_key)
            return self.statement_cache[cache_key]

        # Get ALL synonyms for exhaustive search
        # Use injected grounding service or lazy-initialize with Gilda (INDRA's official grounding)
        if not self.grounding_service:
            from indra_agent.services.grounding_service import GroundingService

            # use_gilda=True - precise entity grounding via INDRA's official service
            # local_ontology=None - skip Memgraph (causes imprecise CONTAINS substring matches)
            self.grounding_service = GroundingService(local_ontology=None, use_gilda=True)
            logger.info("Lazy-initialized GroundingService with Gilda (precise grounding, no Memgraph)")

        source_synonyms = await self.grounding_service.get_all_synonyms(source)
        target_synonyms = await self.grounding_service.get_all_synonyms(target)

        logger.info(f"Exhaustive search: {len(source_synonyms)} source × {len(target_synonyms)} target synonyms")
        logger.debug(f"Source synonyms for '{source}': {source_synonyms[:5]}...")
        logger.debug(f"Target synonyms for '{target}': {target_synonyms[:5]}...")

        async def fetch_combination(src_syn: str, tgt_syn: str) -> List[Statement]:
            """Query INDRA for one synonym combination."""
            try:
                def fetch():
                    processor = idr.get_statements(
                        subject=src_syn,
                        object=tgt_syn,
                        limit=200,
                        persist=False,
                        ev_limit=5,
                        sort_by='ev_count',
                        timeout=30,
                        tries=2
                    )
                    return processor.statements

                stmts = await asyncio.to_thread(fetch)
                if stmts:
                    logger.debug(f"Found {len(stmts)} statements: {src_syn} → {tgt_syn}")
                return stmts
            except Exception as e:
                logger.debug(f"Query failed for {src_syn} → {tgt_syn}: {e}")
                return []

        # Query all synonym combinations in parallel (with concurrency limit)
        from asyncio import Semaphore
        sem = Semaphore(5)  # Max 5 concurrent INDRA queries

        async def fetch_with_limit(src_syn: str, tgt_syn: str):
            async with sem:
                return await fetch_combination(src_syn, tgt_syn)

        # Create all tasks
        tasks = [
            fetch_with_limit(src_syn, tgt_syn)
            for src_syn in source_synonyms
            for tgt_syn in target_synonyms
        ]

        # Execute all queries in parallel
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results (flatten list of lists)
        statements = []
        for result in all_results:
            if isinstance(result, list):
                statements.extend(result)
            elif isinstance(result, Exception):
                logger.debug(f"Query task failed: {result}")

        # INDRA statements have hash-based deduplication built-in
        # (multiple queries returning same statement will have same hash)
        unique_statements = {stmt.get_hash(): stmt for stmt in statements}
        statements = list(unique_statements.values())

        logger.info(
            f"Exhaustive search complete: {len(statements)} unique statements "
            f"from {len(source_synonyms)} × {len(target_synonyms)} combinations"
        )

        # LRU eviction if cache is full
        if len(self.statement_cache) >= self.MAX_CACHE_SIZE:
            self._evict_oldest_cache_entry()

        self.statement_cache[cache_key] = statements
        self._cache_access_order.append(cache_key)
        return statements


    def _build_signed_graph(
        self, statements: List[Statement], belief_threshold: float = 0.5
    ) -> Tuple[nx.DiGraph, Dict[Tuple[str, str], float], Dict[Tuple[str, str], int]]:
        """Build signed NetworkX graph from statements.

        Uses IndraNet assembler to create a graph with:
        - Belief scores on edges
        - Signed edges (activation/inhibition)
        - Evidence counts
        - Node metadata

        Args:
            statements: Preassembled INDRA statements
            belief_threshold: Minimum belief score to include edge

        Returns:
            Tuple of (graph, belief_scores, evidence_counts)
        """
        if not statements:
            return nx.DiGraph(), {}, {}

        logger.info(f"Building signed graph from {len(statements)} statements")

        try:
            # Create IndraNet assembler
            assembler = IndraNetAssembler(statements)

            # Make model (creates NetworkX graph)
            # NOTE: 'signed' is a graph_type, NOT a method!
            # Valid methods: 'df', 'preassembly'
            # Valid graph_types: 'multi_graph', 'digraph', 'signed'
            graph = assembler.make_model(
                graph_type="signed",  # CORRECT: Use signed graph (activation/inhibition)
            )

            # Check if graph was created successfully
            if graph is None:
                logger.warning("IndraNet assembler returned None - creating empty graph")
                return nx.DiGraph(), {}, {}

            # Extract belief scores and evidence counts from edge data
            belief_scores: Dict[Tuple[str, str], float] = {}
            evidence_counts: Dict[Tuple[str, str], int] = {}

            # Filter edges by belief threshold
            edges_to_remove = []

            for source, target, data in graph.edges(data=True):
                belief = data.get("belief", 0.5)
                evidence = data.get("evidence_count", 0)

                # Store metadata
                belief_scores[(source, target)] = belief
                evidence_counts[(source, target)] = evidence

                # Mark for removal if below threshold
                if belief < belief_threshold:
                    edges_to_remove.append((source, target))

            # Remove low-confidence edges
            graph.remove_edges_from(edges_to_remove)

            logger.info(
                f"Graph built: {graph.number_of_nodes()} nodes, "
                f"{graph.number_of_edges()} edges (filtered {len(edges_to_remove)} low-confidence)"
            )

            return graph, belief_scores, evidence_counts

        except Exception as e:
            logger.error(f"Error building signed graph: {e}", exc_info=True)
            return nx.DiGraph(), {}, {}

    async def get_multi_interactors(
        self,
        nodes: List[str],
        downstream: bool = True,
        allowed_ns: Optional[List[str]] = None,
        belief_cutoff: float = 0.6,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get direct interactors (neighbors) via exhaustive synonym search.

        ARCHITECTURE: Query INDRA with ALL synonyms for each node to discover
        latent neighbors that would be missed with single-name queries.

        Strategy:
        1. For each input node, expand to ALL synonyms (via Writer KG)
        2. Query INDRA for statements where each synonym is:
           - downstream=True: SUBJECT (node → ?)
           - downstream=False: OBJECT (? → node)
        3. Merge results, deduplicate by statement hash
        4. Collect unique neighbor entities
        5. Rank by belief × evidence

        Args:
            nodes: List of node names (e.g., ["PM2.5", "CRP"])
            downstream: If True, get downstream targets; if False, get upstream sources
            allowed_ns: Filter to specific namespaces (not used in Python implementation)
            belief_cutoff: Minimum belief score (0.0-1.0)
            max_results: Maximum number of results to return

        Returns:
            List of interactor dicts with name, namespace, identifier, belief, evidence_count
        """
        logger.info(f"Getting multi_interactors for {nodes} (downstream={downstream})")

        # Fetch statements for each node's neighborhood
        try:
            all_statements: List[Statement] = []

            # Use injected grounding service or lazy-initialize with Gilda (INDRA's official grounding)
            if not self.grounding_service:
                from indra_agent.services.grounding_service import GroundingService

                # use_gilda=True - precise entity grounding via INDRA's official service
                # local_ontology=None - skip Memgraph (causes imprecise CONTAINS substring matches)
                self.grounding_service = GroundingService(local_ontology=None, use_gilda=True)
                logger.info("Lazy-initialized GroundingService with Gilda (precise grounding, no Memgraph)")

            for node in nodes:
                cache_key = f"neighbors:{node}:{downstream}"
                if cache_key in self.statement_cache:
                    logger.debug(f"Cache hit: neighbors for {node}")
                    # Move to end of LRU list
                    self._cache_access_order.remove(cache_key)
                    self._cache_access_order.append(cache_key)
                    all_statements.extend(self.statement_cache[cache_key])
                    continue

                # Get ALL synonyms for exhaustive neighborhood discovery
                node_synonyms = await self.grounding_service.get_all_synonyms(node)
                logger.info(f"Expanding '{node}' to {len(node_synonyms)} synonyms for neighbor search")
                logger.debug(f"Node synonyms: {node_synonyms[:5]}...")

                # Query with all synonyms
                from asyncio import Semaphore
                sem = Semaphore(5)  # Max 5 concurrent queries

                async def fetch_neighbor_for_synonym(syn: str):
                    """Query neighbors for one synonym."""
                    try:
                        def fetch():
                            processor = idr.get_statements(
                                subject=syn if downstream else None,
                                object=syn if not downstream else None,
                                limit=150,
                                persist=False,
                                ev_limit=3,
                                sort_by='ev_count',
                                timeout=20,
                                tries=2
                            )
                            return processor.statements

                        async with sem:
                            stmts = await asyncio.to_thread(fetch)
                        if stmts:
                            logger.debug(f"Found {len(stmts)} neighbors for synonym '{syn}'")
                        return stmts
                    except Exception as e:
                        logger.debug(f"Query failed for neighbors of '{syn}': {e}")
                        return []

                # Query all synonyms in parallel
                tasks = [fetch_neighbor_for_synonym(syn) for syn in node_synonyms]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Merge and deduplicate
                node_statements = []
                for result in results:
                    if isinstance(result, list):
                        node_statements.extend(result)

                # Deduplicate by statement hash
                unique_stmts = {stmt.get_hash(): stmt for stmt in node_statements}
                node_statements = list(unique_stmts.values())

                logger.info(
                    f"Exhaustive neighbor search for '{node}': {len(node_statements)} unique statements "
                    f"from {len(node_synonyms)} synonyms"
                )

                # LRU eviction if cache is full
                if len(self.statement_cache) >= self.MAX_CACHE_SIZE:
                    self._evict_oldest_cache_entry()

                self.statement_cache[cache_key] = node_statements
                self._cache_access_order.append(cache_key)
                all_statements.extend(node_statements)

            if not all_statements:
                logger.warning(f"No statements found for neighbors of {nodes}")
                return []

            # Extract unique interactors from statements
            interactor_map: Dict[str, Dict[str, Any]] = {}

            for stmt in all_statements:
                # Skip low-belief statements
                if stmt.belief < belief_cutoff:
                    continue

                # Extract agents based on direction
                source_agent = None
                target_agent = None

                # Handle different statement types
                if hasattr(stmt, 'subj') and hasattr(stmt, 'obj'):
                    source_agent = stmt.subj
                    target_agent = stmt.obj
                elif hasattr(stmt, 'enz') and hasattr(stmt, 'sub'):
                    source_agent = stmt.enz
                    target_agent = stmt.sub
                else:
                    # Skip statements without clear subject/object
                    continue

                # Determine neighbor based on direction
                neighbor_agent = None
                if downstream:
                    # Looking for targets (nodes → ?)
                    if source_agent and source_agent.name in nodes and target_agent:
                        neighbor_agent = target_agent
                else:
                    # Looking for sources (? → nodes)
                    if target_agent and target_agent.name in nodes and source_agent:
                        neighbor_agent = source_agent

                if not neighbor_agent or neighbor_agent.name in nodes:
                    continue  # Skip input nodes

                # Aggregate interactor data
                neighbor_name = neighbor_agent.name
                if neighbor_name not in interactor_map:
                    interactor_map[neighbor_name] = {
                        "name": neighbor_name,
                        "namespace": neighbor_agent.db_refs.get('HGNC', neighbor_agent.db_refs.get('UP', 'NAME')),
                        "identifier": neighbor_agent.db_refs.get('HGNC', neighbor_agent.db_refs.get('UP', '')),
                        "max_belief": stmt.belief,
                        "total_evidence": len(stmt.evidence),
                        "statement_count": 1
                    }
                else:
                    # Update aggregated data
                    interactor_map[neighbor_name]["max_belief"] = max(
                        interactor_map[neighbor_name]["max_belief"], stmt.belief
                    )
                    interactor_map[neighbor_name]["total_evidence"] += len(stmt.evidence)
                    interactor_map[neighbor_name]["statement_count"] += 1

            # Convert to list and add final fields
            interactors = []
            for neighbor_name, data in interactor_map.items():
                interactors.append({
                    "name": neighbor_name,
                    "namespace": data["namespace"],
                    "identifier": data["identifier"],
                    "belief": data["max_belief"],
                    "evidence_count": data["total_evidence"]
                })

            # Sort by composite score (belief × evidence)
            interactors.sort(key=lambda x: x["belief"] * x["evidence_count"], reverse=True)

            logger.info(f"Found {len(interactors)} unique interactors for {nodes}")
            return interactors[:max_results]

        except Exception as e:
            logger.error(f"Error getting multi_interactors: {e}", exc_info=True)
            return []

    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find MDL-optimal causal paths.

        Args:
            source: Source entity
            target: Target entity
            max_depth: Maximum path depth
            use_cache: Whether to use caching

        Returns:
            List of path dicts
        """
        logger.info(f"Finding paths: {source} → {target}")

        try:
            network_result = await self.build_biomarker_network(
                exposures=[source],
                biomarkers=[target],
                max_depth=max_depth,
                belief_threshold=0.3
            )

            if network_result.edge_count == 0:
                return []

            paths = self._convert_graph_to_paths(network_result, source, target, max_depth)
            logger.info(f"Found {len(paths)} paths")
            return paths

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            return []

    def _convert_graph_to_paths(
        self,
        network_result: IndraNetworkResult,
        source: str,
        target: str,
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """Convert NetworkX graph to path format for compatibility.

        Args:
            network_result: IndraNetworkResult with graph
            source: Source node name
            target: Target node name
            max_depth: Maximum path length

        Returns:
            List of path dicts compatible with old format
        """
        try:
            import networkx as nx
            from indra_agent.services.mdl_weight import compute_mdl_weight

            # Pre-compute MDL weights as edge attributes
            # Set on ALL edge keys in MultiDiGraph
            for u, v, key, data in network_result.graph.edges(keys=True, data=True):
                mdl_cost = compute_mdl_weight(network_result.graph, u, v, biomarker_values=None)
                network_result.graph[u][v][key]['mdl_weight'] = mdl_cost

            # Find shortest path using MDL weights
            # Use NetworkX's simple shortest_path instead of open_dijkstra_search
            # (open_dijkstra_search doesn't handle MultiDiGraph properly)
            try:
                # Find single shortest path with MDL weights
                path_nodes = nx.shortest_path(
                    network_result.graph,
                    source=source,
                    target=target,
                    weight='mdl_weight'
                )
                path_list = [path_nodes]
                logger.info(f"Found MDL-optimal path with {len(path_nodes)} nodes")

            except (nx.NodeNotFound, nx.NetworkXNoPath, nx.NetworkXError) as e:
                logger.warning(f"No path found in graph: {source} → {target}, error: {e}")
                return []

            # Convert each path to old format
            formatted_paths = []
            for path_nodes in path_list:
                # Build nodes list
                nodes = []
                for node_name in path_nodes:
                    nodes.append({
                        "id": node_name,
                        "name": node_name,
                        "grounding": {"db": "", "id": ""}
                    })

                # Build edges list
                edges = []
                for i in range(len(path_nodes) - 1):
                    src = path_nodes[i]
                    tgt = path_nodes[i + 1]

                    # Get edge data (handle MultiDiGraph - may have multiple edges)
                    # For MultiDiGraph, iterate over all edges between src and tgt
                    edge_data = {}
                    if network_result.graph.has_edge(src, tgt):
                        # Get first edge data (there may be multiple, take first)
                        edge_data = list(network_result.graph[src][tgt].values())[0]

                    belief = network_result.belief_scores.get((src, tgt), 0.5)
                    evidence_count = network_result.evidence_counts.get((src, tgt), 0)

                    # Determine relationship from edge sign
                    # NOTE: Map to Pydantic enum values: ["activates", "inhibits", "increases", "decreases"]
                    sign = edge_data.get("sign", 0)
                    if sign > 0:
                        relationship = "activates"
                    elif sign < 0:
                        relationship = "inhibits"
                    else:
                        # Unsigned edge (sign=0) - use generic "increases"
                        # This avoids ValidationError from "regulates" not in enum
                        relationship = "increases"

                    # Extract PMIDs from statements that created this edge
                    pmids = self._extract_pmids_for_edge(
                        network_result.statements, src, tgt
                    )

                    # FIX: IndraNetAssembler doesn't populate evidence_count on edges
                    # Use PMID count as fallback (underestimate, but better than 0)
                    if evidence_count == 0 and pmids:
                        evidence_count = len(pmids)
                        logger.debug(f"Using PMID count for evidence: {src}→{tgt} = {evidence_count}")

                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relationship": relationship,
                        "evidence_count": evidence_count,
                        "belief": belief,
                        "statement_type": edge_data.get("stmt_type", "Activation"),
                        "pmids": pmids[:3],  # Limit to top 3 PMIDs for brevity
                        "db_url_edge": ""
                    })

                # Calculate path belief (average of edge beliefs)
                avg_belief = sum(e["belief"] for e in edges) / len(edges) if edges else 0.5

                formatted_paths.append({
                    "nodes": nodes,
                    "edges": edges,
                    "path_belief": avg_belief
                })

            return formatted_paths

        except Exception as e:
            logger.error(f"Error converting graph to paths: {e}", exc_info=True)
            return []

    def rank_paths(self, paths: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank paths by evidence and confidence.

        Args:
            paths: List of path dicts

        Returns:
            Sorted list of paths (best first)
        """
        def score_path(path: Dict) -> float:
            """Calculate composite score for path."""
            # Count total evidence
            total_evidence = sum(
                edge.get("evidence_count", 0) for edge in path.get("edges", [])
            )
            evidence_score = min(total_evidence / 20.0, 1.0)

            # Average belief
            avg_belief = path.get("path_belief", 0.5)

            # Path length (shorter is better)
            path_length = len(path.get("nodes", []))
            length_score = 1.0 / path_length if path_length > 0 else 0

            # Weighted combination
            return 0.4 * evidence_score + 0.3 * avg_belief + 0.3 * length_score

        paths_sorted = sorted(paths, key=score_path, reverse=True)
        return paths_sorted

    def _extract_pmids_for_edge(
        self, statements: List[Statement], source: str, target: str
    ) -> List[str]:
        """Extract PMIDs from statements that support an edge.

        Args:
            statements: List of INDRA statements
            source: Source node name
            target: Target node name

        Returns:
            List of PMIDs (strings)
        """
        pmids = []

        try:
            for stmt in statements:
                # Check if statement involves both source and target
                # INDRA statements have subj and obj attributes (or enz/sub, etc.)
                stmt_agents = []

                # Get all agents from statement
                if hasattr(stmt, 'subj') and stmt.subj:
                    stmt_agents.append(stmt.subj.name)
                if hasattr(stmt, 'obj') and stmt.obj:
                    stmt_agents.append(stmt.obj.name)
                if hasattr(stmt, 'enz') and stmt.enz:
                    stmt_agents.append(stmt.enz.name)
                if hasattr(stmt, 'sub') and stmt.sub:
                    stmt_agents.append(stmt.sub.name)
                if hasattr(stmt, 'agent') and stmt.agent:
                    stmt_agents.append(stmt.agent.name)
                if hasattr(stmt, 'members') and stmt.members:
                    stmt_agents.extend([m.name for m in stmt.members if m])

                # Check if this statement involves the edge
                if source in stmt_agents and target in stmt_agents:
                    # Extract PMIDs from evidence
                    for evidence in stmt.evidence:
                        pmid = evidence.pmid
                        if pmid and pmid not in pmids:
                            pmids.append(pmid)

        except Exception as e:
            logger.warning(f"Error extracting PMIDs for edge {source}→{target}: {e}")

        return pmids

    def discover_intermediate_biomarkers(
        self,
        graph: nx.DiGraph,
        exposure: str,
        known_biomarkers: List[str],
        min_centrality: float = 0.1,
    ) -> List[Tuple[str, float]]:
        """Discover new biomarkers by analyzing graph centrality.

        Strategy:
        1. Find nodes between exposure and known biomarkers
        2. Calculate betweenness centrality
        3. Filter by node properties (secreted, measurable)
        4. Rank by centrality + evidence

        Args:
            graph: NetworkX graph from build_biomarker_network
            exposure: Exposure entity (e.g., "PM2.5")
            known_biomarkers: List of known biomarker names
            min_centrality: Minimum centrality score (default: 0.1)

        Returns:
            List of (biomarker_name, centrality_score) sorted by score
        """
        if not graph.nodes():
            return []

        logger.info(
            f"Discovering intermediate biomarkers between {exposure} and {known_biomarkers}"
        )

        try:
            # Calculate betweenness centrality
            centrality = nx.betweenness_centrality(graph, weight="belief")

            # Find intermediate nodes (not exposure, not already known biomarkers)
            known_set = set(known_biomarkers + [exposure])
            intermediate_nodes = [
                (node, score)
                for node, score in centrality.items()
                if node not in known_set and score >= min_centrality
            ]

            # Sort by centrality
            intermediate_nodes.sort(key=lambda x: x[1], reverse=True)

            logger.info(f"Found {len(intermediate_nodes)} intermediate biomarkers")

            return intermediate_nodes

        except Exception as e:
            logger.error(f"Error discovering biomarkers: {e}", exc_info=True)
            return []
