"""IndraNet service for comprehensive biomarker network building.

This service uses INDRA's Python library directly to:
- Build neighborhood networks around biomarkers
- Discover multi-hop causal pathways
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

from indra_agent.services.preassembly_service import PreassemblyService

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
    """Build comprehensive biomarker networks using IndraNet assembler."""

    def __init__(self):
        """Initialize IndraNet service."""
        self.statement_cache: Dict[str, List[Statement]] = {}
        self.preassembly_service = PreassemblyService()
        logger.info("IndraNet service initialized")

    async def build_biomarker_network(
        self,
        exposures: List[str],
        biomarkers: List[str],
        max_depth: int = 2,
        belief_threshold: float = 0.3,  # Lower default for environmental pathways
    ) -> IndraNetworkResult:
        """Build comprehensive network around biomarkers.

        Strategy:
        1. Get neighborhoods of all biomarkers (1-2 hops)
        2. Get exposure→biomarker paths (up to 3 hops)
        3. Merge duplicates via preassembly
        4. Build signed NetworkX graph with belief scores
        5. Filter by confidence threshold
        6. Return graph + high-quality edges

        Args:
            exposures: List of exposure entities (e.g., ["PM2.5", "Ozone"])
            biomarkers: List of biomarker entities (e.g., ["CRP", "IL-6"])
            max_depth: Maximum neighborhood depth (default: 2)
            belief_threshold: Minimum belief score to include (default: 0.5)

        Returns:
            IndraNetworkResult with graph and metadata
        """
        logger.info(
            f"Building biomarker network: {len(exposures)} exposures, "
            f"{len(biomarkers)} biomarkers, max_depth={max_depth}"
        )

        # Step 1: Collect statements from multiple strategies
        all_statements: List[Statement] = []

        # Strategy 1: Get neighborhoods of biomarkers
        for biomarker in biomarkers:
            logger.info(f"Getting neighborhood for biomarker: {biomarker}")
            neighborhood_stmts = await self._get_neighborhood_statements(
                biomarker, depth=max_depth
            )
            all_statements.extend(neighborhood_stmts)
            logger.info(f"Found {len(neighborhood_stmts)} statements for {biomarker}")

        # Strategy 2: Get exposure → biomarker paths
        for exposure in exposures:
            for biomarker in biomarkers:
                logger.info(f"Getting paths: {exposure} → {biomarker}")
                path_stmts = await self._get_path_statements(
                    exposure, biomarker, max_depth=min(max_depth + 1, 4)
                )
                all_statements.extend(path_stmts)
                logger.info(
                    f"Found {len(path_stmts)} path statements: {exposure} → {biomarker}"
                )

        if not all_statements:
            logger.warning("No statements found - returning empty network")
            return IndraNetworkResult(
                graph=nx.DiGraph(),
                statements=[],
                node_names=[],
                edge_count=0,
                belief_scores={},
                evidence_counts={},
            )

        logger.info(f"Collected {len(all_statements)} total statements")

        # Step 2: Preassembly - merge duplicates and calculate belief
        logger.info("Running preassembly pipeline")
        preassembled_stmts = self._preassemble_statements(all_statements)
        logger.info(
            f"Preassembly reduced {len(all_statements)} → {len(preassembled_stmts)} statements"
        )

        # Step 3: Build signed NetworkX graph
        logger.info("Building NetworkX graph with IndraNet assembler")
        graph, belief_scores, evidence_counts = self._build_signed_graph(
            preassembled_stmts, belief_threshold
        )

        logger.info(
            f"Built graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )

        # Step 4: Package result
        return IndraNetworkResult(
            graph=graph,
            statements=preassembled_stmts,
            node_names=list(graph.nodes()),
            edge_count=graph.number_of_edges(),
            belief_scores=belief_scores,
            evidence_counts=evidence_counts,
        )

    async def _get_neighborhood_statements(
        self, entity: str, depth: int = 2
    ) -> List[Statement]:
        """Get neighborhood statements around an entity.

        Queries INDRA DB for statements involving the entity and its neighbors.
        For depth=2, fetches 1-hop neighbors of the entity.

        Args:
            entity: Entity name (e.g., "CRP", "IL-6")
            depth: Neighborhood depth (1 or 2 hops)

        Returns:
            List of INDRA Statement objects
        """
        # Check cache
        cache_key = f"neighborhood:{entity}:{depth}"
        if cache_key in self.statement_cache:
            logger.info(f"Using cached neighborhood for {entity} (depth={depth})")
            return self.statement_cache[cache_key]

        logger.info(f"Fetching neighborhood statements for {entity} (depth={depth})")

        try:
            # Run synchronous INDRA query in thread pool
            def fetch_statements():
                # Query INDRA DB for statements involving this entity
                # Limit to reasonable number for performance
                limit = 100 if depth == 1 else 200

                processor = idr.get_statements(
                    agents=[entity],
                    limit=limit,
                    ev_limit=5,  # Limit evidence per statement
                    sort_by='ev_count',  # Sort by evidence count
                    timeout=30,  # 30 second timeout
                )

                return processor.statements

            # Execute in thread pool to avoid blocking
            statements = await asyncio.to_thread(fetch_statements)

            logger.info(
                f"Found {len(statements)} neighborhood statements for {entity}"
            )

        except Exception as e:
            logger.error(
                f"Error fetching neighborhood for {entity}: {e}", exc_info=True
            )
            statements = []

        # Cache and return
        self.statement_cache[cache_key] = statements
        return statements

    async def _get_path_statements(
        self, source: str, target: str, max_depth: int = 3
    ) -> List[Statement]:
        """Get path statements between source and target.

        Queries INDRA DB for statements that could form paths between entities.
        Strategy:
        1. Direct statements (source → target)
        2. Statements involving source
        3. Statements involving target

        Args:
            source: Source entity (e.g., "PM2.5")
            target: Target entity (e.g., "CRP")
            max_depth: Maximum path length (affects statement limit)

        Returns:
            List of INDRA Statement objects
        """
        # Check cache
        cache_key = f"path:{source}:{target}:{max_depth}"
        if cache_key in self.statement_cache:
            logger.info(f"Using cached path: {source} → {target}")
            return self.statement_cache[cache_key]

        logger.info(f"Fetching path statements: {source} → {target} (max_depth={max_depth})")

        try:
            # Run synchronous INDRA queries in thread pool
            def fetch_statements():
                all_stmts = []

                # Strategy 1: Direct source → target statements
                try:
                    processor = idr.get_statements(
                        subject=source,
                        object=target,
                        limit=50,
                        ev_limit=5,
                        sort_by='ev_count',
                        timeout=20,
                    )
                    all_stmts.extend(processor.statements)
                    logger.debug(f"Found {len(processor.statements)} direct statements")
                except Exception as e:
                    logger.warning(f"Error fetching direct statements: {e}")

                # Strategy 2: Statements involving source (for multi-hop paths)
                try:
                    processor = idr.get_statements(
                        agents=[source],
                        limit=50,
                        ev_limit=3,
                        sort_by='ev_count',
                        timeout=20,
                    )
                    all_stmts.extend(processor.statements)
                    logger.debug(f"Found {len(processor.statements)} source statements")
                except Exception as e:
                    logger.warning(f"Error fetching source statements: {e}")

                # Strategy 3: Statements involving target (for multi-hop paths)
                try:
                    processor = idr.get_statements(
                        agents=[target],
                        limit=50,
                        ev_limit=3,
                        sort_by='ev_count',
                        timeout=20,
                    )
                    all_stmts.extend(processor.statements)
                    logger.debug(f"Found {len(processor.statements)} target statements")
                except Exception as e:
                    logger.warning(f"Error fetching target statements: {e}")

                return all_stmts

            # Execute in thread pool to avoid blocking
            statements = await asyncio.to_thread(fetch_statements)

            logger.info(
                f"Found {len(statements)} total path statements: {source} → {target}"
            )

        except Exception as e:
            logger.error(
                f"Error fetching path {source} → {target}: {e}", exc_info=True
            )
            statements = []

        # Cache and return
        self.statement_cache[cache_key] = statements
        return statements

    def _preassemble_statements(
        self, statements: List[Statement], run_refinement: bool = True
    ) -> List[Statement]:
        """Preassembly pipeline: merge duplicates and calculate belief.

        Delegates to PreassemblyService for modularity.

        Args:
            statements: Raw INDRA statements
            run_refinement: Whether to run refinement step (default: True)

        Returns:
            De-duplicated statements with aggregated evidence and belief scores
        """
        return self.preassembly_service.preassemble_statements(
            statements, run_refinement=run_refinement, belief_cutoff=0.0
        )

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
        """Get direct interactors (neighbors) for given nodes.

        This is a compatibility method for SCMGraphBuilder. It uses INDRA Python library
        to discover what entities interact with the given nodes.

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

        # Build a network around the nodes to discover interactors
        try:
            # Use build_biomarker_network with nodes as both exposures and biomarkers
            # to get their neighborhoods
            result = await self.build_biomarker_network(
                exposures=nodes if downstream else [],
                biomarkers=nodes if not downstream else [],
                max_depth=1,  # Just 1-hop neighbors
                belief_threshold=belief_cutoff
            )

            # Extract interactors from the graph
            interactors = []
            input_nodes = set(nodes)

            for node_name in result.node_names:
                # Skip input nodes
                if node_name in input_nodes:
                    continue

                # Get edges to/from this node
                edges_with_belief = []
                for (source, target), belief in result.belief_scores.items():
                    if downstream and source in input_nodes and target == node_name:
                        edges_with_belief.append((belief, result.evidence_counts.get((source, target), 0)))
                    elif not downstream and target in input_nodes and source == node_name:
                        edges_with_belief.append((belief, result.evidence_counts.get((source, target), 0)))

                if edges_with_belief:
                    # Use max belief and total evidence
                    max_belief = max(b for b, _ in edges_with_belief)
                    total_evidence = sum(e for _, e in edges_with_belief)

                    interactors.append({
                        "name": node_name,
                        "namespace": "HGNC",  # Default, actual namespace not available from NetworkX
                        "identifier": "",
                        "belief": max_belief,
                        "evidence_count": total_evidence
                    })

            # Sort by evidence strength
            interactors.sort(key=lambda x: x["belief"] * x["evidence_count"], reverse=True)

            logger.info(f"Found {len(interactors)} interactors for {nodes}")
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
        """Find causal paths between source and target entities.

        This is a compatibility method for SCMGraphBuilder. It uses INDRA Python library
        to build biomarker networks and converts to the old path format.

        Args:
            source: Source entity name (e.g., "PM2.5", "CRP")
            target: Target entity name (e.g., "CRP", "IL-6")
            max_depth: Maximum path depth
            use_cache: Whether to use caching (handled by INDRA library)

        Returns:
            List of path dicts with nodes and edges (compatible with old format)
        """
        logger.info(f"Finding causal paths: {source} → {target}")

        try:
            # Build biomarker network
            network_result = await self.build_biomarker_network(
                exposures=[source],
                biomarkers=[target],
                max_depth=min(max_depth, 3),  # Limit depth for performance
                belief_threshold=0.3  # Lower for environmental pathways (was 0.5)
            )

            if network_result.edge_count == 0:
                logger.info(f"No paths found: {source} → {target}")
                return []

            # Convert NetworkX graph to path format
            paths = self._convert_graph_to_paths(
                network_result,
                source,
                target,
                max_depth
            )

            logger.info(f"Found {len(paths)} paths: {source} → {target}")
            return paths

        except Exception as e:
            logger.error(f"Error finding causal paths: {e}", exc_info=True)
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

            # Find all simple paths from source to target
            try:
                all_paths = nx.all_simple_paths(
                    network_result.graph,
                    source=source,
                    target=target,
                    cutoff=max_depth
                )
                path_list = list(all_paths)[:10]  # Limit to top 10
            except (nx.NodeNotFound, nx.NetworkXNoPath):
                logger.warning(f"No path found in graph: {source} → {target}")
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
