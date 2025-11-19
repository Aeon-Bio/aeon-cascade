"""INDRA HTTP API service for experimental intervention discovery methods.

This service provides HTTP API wrappers for experimental intervention discovery
features that rely on INDRA Network Search API endpoints not available in the
Python INDRA library (specifically: shared_regulators query parameter).

ARCHITECTURE NOTE:
==================
This service uses INDRA's HTTP Network Search API (network.indra.bio/api/query)
which provides features like shared_regulators queries that are NOT available in
the Python `indra.sources.indra_db_rest` module. This is why these methods cannot
be migrated to IndraNetService (which uses Python library).

Production causal discovery uses IndraNetService (Python library).
Experimental intervention discovery uses this service (HTTP API).

These endpoints are marked deprecated=True and will be removed or migrated when
INDRA adds shared_regulators support to Python library.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class InterventionDiscoveryService:
    """HTTP API client for INDRA Network Search experimental features.

    KOLMOGOROV-MINIMAL: This class contains ONLY methods required by experimental
    intervention discovery endpoints. All production code uses IndraNetService.
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        """Initialize intervention discovery service.

        Args:
            client: Optional shared HTTP client. If not provided, creates a new one.
        """
        self.settings = get_settings()
        self.base_url = self.settings.indra_base_url  # network.indra.bio
        self.timeout = self.settings.indra_timeout
        self.cache: Dict[str, List[Dict]] = {}
        self.intervention_cache: Dict[str, Any] = {}  # Cache for intervention discovery results
        self._owns_client = client is None  # Track if we own the client
        self.client = client if client is not None else httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _fetch_with_retry(self, method: str, url: str, **kwargs):
        """Fetch with automatic retry on transient errors.

        Args:
            method: HTTP method (get, post, etc.)
            url: URL to fetch
            **kwargs: Additional arguments for the request

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: On non-retryable errors or after max retries
        """
        response = await getattr(self.client, method)(url, **kwargs)
        response.raise_for_status()
        return response

    async def _resolve_to_name(self, entity: str) -> Optional[str]:
        """Resolve database ID or alternative name to entity name for INDRA API.

        CRITICAL: INDRA Network Search API accepts entity names (e.g., "Particulate Matter", "IL6", "CRP")
        and automatically resolves them to database IDs internally.

        Strategy:
        1. If entity is database ID (contains colon), query Writer KG for canonical MeSH label
        2. If entity is HGNC gene, use INDRA's node-name-in-graph to get canonical name
        3. Otherwise, assume it's already a valid name and return as-is

        Args:
            entity: Entity name (e.g., "IL6", "particulate matter") or ID (e.g., "HGNC:6018", "MESH:D052638")

        Returns:
            Entity name for INDRA API (e.g., "Particulate Matter", "IL6", "CRP"), or None if resolution fails
        """
        # Import mappings from grounding service
        from indra_agent.services.grounding_service import GroundingService

        # Strategy 1: If CURIE format (db:id), resolve dynamically
        if ":" in entity:
            db_name, db_id = entity.split(":", 1)
            db_name_lower = db_name.lower()

            # For MESH IDs: Query Writer KG for canonical label
            if db_name_lower == "mesh":
                try:
                    from indra_agent.services.writer_kg_service import WriterKGService
                    writer_kg = WriterKGService()

                    # Query Writer KG for this MESH ID
                    mesh_data = await writer_kg.find_mesh_term(db_id)
                    await writer_kg.cleanup()

                    if mesh_data and mesh_data.get("mesh_label"):
                        canonical_name = mesh_data["mesh_label"]
                        logger.info(f"Resolved {entity} → {canonical_name} (Writer KG)")
                        return canonical_name
                    else:
                        logger.warning(f"Writer KG could not resolve MESH:{db_id}")
                except Exception as e:
                    logger.warning(f"Error querying Writer KG for {entity}: {e}")

            # Fallback: Check hardcoded mapping (legacy support)
            hardcoded_name = GroundingService.DATABASE_ID_TO_NAME.get(entity)
            if hardcoded_name:
                logger.info(f"Resolved {entity} → {hardcoded_name} (hardcoded fallback)")
                return hardcoded_name

            # Last resort: entity ID could not be resolved
            logger.warning(f"Could not resolve entity ID to name: {entity}")
            return None

        # Strategy 2: Check if it's a known MESH shorthand that needs Writer KG resolution
        # Examples: "PM2.5" → "Particulate Matter", "O3" → "Ozone"
        known_mesh_shorthands = {"PM2.5": "D052638", "O3": "D010126", "NO2": None}  # Map to MESH IDs

        if entity in known_mesh_shorthands:
            mesh_id = known_mesh_shorthands[entity]
            if mesh_id:
                try:
                    from indra_agent.services.writer_kg_service import WriterKGService
                    writer_kg = WriterKGService()
                    mesh_data = await writer_kg.find_mesh_term(mesh_id)
                    await writer_kg.cleanup()

                    if mesh_data and mesh_data.get("mesh_label"):
                        canonical_name = mesh_data["mesh_label"]
                        logger.info(f"Resolved shorthand {entity} → {canonical_name} (Writer KG)")
                        return canonical_name
                except Exception as e:
                    logger.warning(f"Writer KG resolution failed for {entity}: {e}")

        # Strategy 3: Entity is already a name - return as-is
        logger.debug(f"Using entity name as-is: {entity}")
        return entity

    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find causal paths between source and target entities.

        This method:
        1. Resolves database IDs to entity names (if needed)
        2. Checks runtime cache
        3. Tries direct path query
        4. If no direct paths, attempts multi-hop discovery via neighborhood expansion
        5. Parses response according to OpenAPI schema

        Args:
            source: Source entity name (e.g., "PM2.5") or ID (e.g., "MESH:D052638")
            target: Target entity name (e.g., "CRP") or ID (e.g., "HGNC:2367")
            max_depth: Maximum path depth (depth_limit parameter)
            use_cache: Whether to use cached responses

        Returns:
            List of path dicts with nodes and edges
        """
        # Resolve database IDs to entity names (INDRA API requires names, not IDs)
        source_name = await self._resolve_to_name(source)
        target_name = await self._resolve_to_name(target)

        if not source_name or not target_name:
            logger.warning(f"Could not resolve entities: {source} → {target}")
            return []

        # Check runtime cache first (using resolved names)
        cache_key = f"{source_name}_{target_name}_{max_depth}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using runtime cache for {source_name} → {target_name}")
            return self.cache[cache_key]

        # Strategy 1: Try direct path query
        logger.info(f"Querying INDRA Network Search API: {source_name} → {target_name}")
        try:
            paths = await self._query_path_search(source_name, target_name, max_depth)
            if paths:
                self.cache[cache_key] = paths
                logger.info(f"Found {len(paths)} direct paths from {source_name} → {target_name}")
                return paths
        except Exception as e:
            logger.error(f"Error querying INDRA API (direct): {e}")

        # Strategy 2: Multi-hop discovery via neighborhood expansion
        logger.info(f"No direct paths found. Attempting multi-hop discovery for {source_name} → {target_name}")
        try:
            multi_hop_paths = await self._find_multi_hop_paths(source_name, target_name, max_depth)
            if multi_hop_paths:
                self.cache[cache_key] = multi_hop_paths
                logger.info(f"Found {len(multi_hop_paths)} multi-hop paths from {source_name} → {target_name}")
                return multi_hop_paths
        except Exception as e:
            logger.error(f"Error in multi-hop discovery: {e}")

        # Fallback to empty result
        logger.warning(f"No paths found for {source_name} → {target_name}")
        return []

    async def _query_path_search(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """Query INDRA Network Search API for causal paths.

        Uses POST /api/query endpoint with NetworkSearchQuery schema.

        Args:
            source: Source entity name (e.g., "PM2.5")
            target: Target entity name (e.g., "CRP")
            max_depth: Maximum path depth (depth_limit parameter)

        Returns:
            List of path dicts with nodes and edges (parsed from OpenAPI response)
        """
        try:
            url = f"{self.base_url}/api/query"

            # Build NetworkSearchQuery according to OpenAPI schema
            query_payload = {
                "source": source,
                "target": target,
                "depth_limit": max_depth,
                "weighted": "belief",  # Use belief scores for path weighting
                "belief_cutoff": 0.5,  # Filter low-confidence edges
                "k_shortest": 10,  # Get top 10 paths
                "filter_curated": True,  # Prefer curated sources
                "curated_db_only": False,  # But don't exclude non-curated
                "fplx_expand": True,  # Expand protein families
                "format": "json"
            }

            logger.info(f"POST {url} with query: {source} → {target}")
            # Use retry wrapper for reliable network call
            response = await self._fetch_with_retry("post", url, json=query_payload, timeout=30.0)

            data = response.json()

            # Parse response according to OpenAPI Results schema
            return self._parse_path_response(data)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying INDRA path search: {e}")
            return []
        except Exception as e:
            logger.error(f"Error querying INDRA path search: {e}")
            return []

    def _parse_path_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse INDRA Network Search API response according to OpenAPI schema.

        Response structure: Results → PathResultData → paths[source_name][] → Path
        Each Path has: path (array of Nodes), edge_data (array of EdgeData)

        Args:
            data: Raw response from INDRA API (Results schema)

        Returns:
            List of parsed path dicts with nodes and edges
        """
        paths = []

        # Check if query timed out (but may still have partial results)
        if data.get("timed_out", False):
            logger.warning("INDRA query timed out (may have partial results)")

        # Extract path_results (PathResultData schema)
        path_results = data.get("path_results")
        if not path_results:
            logger.warning("No path_results in response")
            return paths

        # Extract paths dict: {source_name: [Path, Path, ...]}
        paths_dict = path_results.get("paths", {})
        if not paths_dict:
            logger.warning("No paths found in path_results")
            return paths

        # Iterate through all source keys (usually just one)
        for source_name, path_list in paths_dict.items():
            for path_data in path_list:
                # Parse nodes from path array (Node schema)
                nodes = []
                for node in path_data.get("path", []):
                    nodes.append({
                        "id": node.get("name", ""),  # Use name as ID
                        "name": node.get("name", ""),
                        "grounding": {
                            "db": node.get("namespace", ""),
                            "id": node.get("identifier", "")
                        }
                    })

                # Parse edges from edge_data array (EdgeData schema)
                edges = []
                for edge_data in path_data.get("edge_data", []):
                    # Extract source and target from 2-element edge array
                    edge_nodes = edge_data.get("edge", [])
                    if len(edge_nodes) < 2:
                        continue

                    source_node = edge_nodes[0]
                    target_node = edge_nodes[1]

                    # Aggregate evidence across all statement types
                    statements_dict = edge_data.get("statements", {})
                    total_evidence = 0
                    all_stmt_types = []
                    all_hashes = []

                    for stmt_type, stmt_support in statements_dict.items():
                        all_stmt_types.append(stmt_type)
                        # Sum source counts for this statement type
                        source_counts = stmt_support.get("source_counts", {})
                        total_evidence += sum(source_counts.values())

                        # Extract statement hashes
                        for stmt in stmt_support.get("statements", [])[:3]:
                            stmt_hash = stmt.get("stmt_hash")
                            if stmt_hash:
                                all_hashes.append(f"HASH:{stmt_hash}")

                    # Use first statement type as primary
                    primary_stmt_type = all_stmt_types[0] if all_stmt_types else "Activation"
                    relationship = self._map_statement_type(primary_stmt_type)

                    edges.append({
                        "source": source_node.get("name", ""),
                        "target": target_node.get("name", ""),
                        "relationship": relationship,
                        "evidence_count": total_evidence,
                        "belief": edge_data.get("belief", 0.5),
                        "statement_type": primary_stmt_type,
                        "pmids": all_hashes[:5],  # Limit to 5
                        "db_url_edge": edge_data.get("db_url_edge", "")
                    })

                # Calculate path belief (can use edge weights)
                avg_belief = sum(e["belief"] for e in edges) / len(edges) if edges else 0.5

                paths.append({
                    "nodes": nodes,
                    "edges": edges,
                    "path_belief": avg_belief
                })

        logger.info(f"Parsed {len(paths)} paths from INDRA response")
        return paths

    def _map_statement_type(self, stmt_type: str) -> str:
        """Map INDRA statement type to relationship.

        Args:
            stmt_type: INDRA statement type

        Returns:
            Relationship type (activates, inhibits, increases, decreases)
        """
        type_map = {
            "Activation": "activates",
            "Inhibition": "inhibits",
            "IncreaseAmount": "increases",
            "DecreaseAmount": "decreases",
            "Phosphorylation": "activates",
            "Complex": "activates",
            "RegulateActivity": "activates",
        }
        return type_map.get(stmt_type, "activates")

    async def get_multi_interactors(
        self,
        nodes: List[str],
        downstream: bool = True,
        allowed_ns: Optional[List[str]] = None,
        belief_cutoff: float = 0.6,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get direct interactors (neighbors) for given nodes.

        Uses INDRA's multi_interactors endpoint to efficiently discover
        what entities interact with the given nodes.

        Args:
            nodes: List of node names (e.g., ["Particulate Matter"])
            downstream: If True, get downstream targets; if False, get upstream sources
            allowed_ns: Filter to specific namespaces (e.g., ["HGNC", "UP", "CHEBI"])
            belief_cutoff: Minimum belief score (0.0-1.0)
            max_results: Maximum number of results to return

        Returns:
            List of interactor dicts with name, database, belief, evidence_count
        """
        try:
            url = f"{self.base_url}/api/multi_interactors"

            # Build request payload
            payload = {
                "nodes": nodes,
                "downstream": downstream,
                "belief_cutoff": belief_cutoff,
                "max_results": max_results,
                "curated_db_only": False,  # Include all sources
            }

            # Add namespace filter if specified
            if allowed_ns:
                payload["allowed_ns"] = allowed_ns

            logger.info(f"Querying multi_interactors: {nodes} (downstream={downstream})")
            response = await self._fetch_with_retry("post", url, json=payload, timeout=30.0)

            data = response.json()

            # Parse interactors from edge_data
            # Response structure: { "edge_data": [{ "edge": [source_node, target_node], "statements": {...} }] }
            interactors = []
            edge_data_list = data.get("edge_data", [])

            for edge_data in edge_data_list:
                edge_nodes = edge_data.get("edge", [])
                if len(edge_nodes) < 2:
                    continue

                # edge[0] is source (our input node), edge[1] is the interactor
                target_node = edge_nodes[1] if downstream else edge_nodes[0]

                # Calculate belief and evidence from statements
                statements_dict = edge_data.get("statements", {})
                total_evidence = 0
                max_belief = 0.0

                for stmt_type, stmt_data in statements_dict.items():
                    # Sum evidence across all sources
                    source_counts = stmt_data.get("source_counts", {})
                    total_evidence += sum(source_counts.values())

                    # Get max belief from all statements
                    for stmt in stmt_data.get("statements", []):
                        belief = stmt.get("belief", 0.0)
                        max_belief = max(max_belief, belief)

                interactors.append({
                    "name": target_node.get("name", ""),
                    "namespace": target_node.get("namespace", ""),
                    "identifier": target_node.get("identifier", ""),
                    "belief": max_belief,
                    "evidence_count": total_evidence,
                })

            # Sort by evidence strength (belief * evidence_count)
            interactors.sort(key=lambda x: x["belief"] * x["evidence_count"], reverse=True)

            logger.info(f"Found {len(interactors)} interactors for {nodes}")
            return interactors[:max_results]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying multi_interactors: {e}")
            return []
        except Exception as e:
            logger.error(f"Error querying multi_interactors: {e}")
            return []

    async def _find_multi_hop_paths(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """Find multi-hop paths using INDRA neighborhood expansion.

        Strategy:
        1. Get downstream interactors from source using multi_interactors API
        2. Filter to biological entities (proteins, genes, processes)
        3. Query paths from each interactor to target
        4. Prepend source → interactor edge to create complete paths

        This discovers actual causal relationships from the literature,
        not hardcoded assumptions.

        Args:
            source: Source entity name (e.g., "Particulate Matter")
            target: Target entity name (e.g., "CRP")
            max_depth: Maximum total path length

        Returns:
            List of multi-hop path dicts
        """
        # Step 1: Get downstream biological targets from source
        logger.info(f"Discovering downstream targets from {source}")
        interactors = await self.get_multi_interactors(
            nodes=[source],
            downstream=True,
            allowed_ns=["HGNC", "UP", "CHEBI", "GO", "FPLX"],  # Biological entities only
            belief_cutoff=0.5,
            max_results=20,  # Top 20 by evidence
        )

        if not interactors:
            logger.warning(f"No downstream interactors found for {source}")
            return []

        logger.info(f"Found {len(interactors)} downstream targets: {[i['name'] for i in interactors[:5]]}")

        # Step 2: For each interactor, try to build path to target
        # Strategy depends on whether source is in INDRA's graph or not
        is_environmental_source = source in ["PM2.5", "Particulate Matter", "Air Pollutants", "Ozone", "O3"]

        all_paths = []

        if is_environmental_source:
            # For environmental exposures: Build synthetic environmental → molecular edge + INDRA molecular chain
            # Use discovered interactors instead of hardcoded ones
            for interactor in interactors[:5]:  # Top 5 by evidence
                interactor_name = interactor["name"]
                try:
                    # Query molecular chain: interactor → target (INDRA has this)
                    molecular_chain = await self._query_path_search(interactor_name, target, max_depth=3)
                    if not molecular_chain:
                        continue

                    # Add synthetic environmental → molecular edge based on literature evidence
                    for molecular_path in molecular_chain[:2]:  # Top 2 paths per interactor
                        synthetic_path = self._add_environmental_edge(
                            source, interactor_name, molecular_path, interactor["belief"], interactor["evidence_count"]
                        )
                        if synthetic_path:
                            all_paths.append(synthetic_path)

                    logger.info(f"Built {len(all_paths)} paths via {interactor_name} (environmental → molecular)")

                except Exception as e:
                    logger.debug(f"Could not build path through {interactor_name}: {e}")
                    continue
        else:
            # For molecular → molecular: Use standard chaining with discovered interactors
            for interactor in interactors[:8]:  # Top 8 by evidence
                interactor_name = interactor["name"]
                try:
                    # Query segment 1: source → interactor (already have this relationship)
                    # Query segment 2: interactor → target
                    segment2 = await self._query_path_search(interactor_name, target, max_depth=2)
                    if not segment2:
                        continue

                    # Build chained path with the known source → interactor edge
                    for path2 in segment2[:2]:
                        chained_path = self._build_chained_path_with_interactor(
                            source, interactor, path2
                        )
                        if chained_path and len(chained_path["nodes"]) <= max_depth + 1:
                            all_paths.append(chained_path)

                    logger.info(f"Found {len(all_paths)} chained paths via {interactor_name}")

                except Exception as e:
                    logger.debug(f"Could not chain through {interactor_name}: {e}")
                    continue

        # Return top paths ranked by evidence
        if all_paths:
            return self.rank_paths(all_paths)[:10]

        return []

    def _add_environmental_edge(
        self, env_source: str, molecular_target: str, molecular_path: Dict,
        belief: float, evidence_count: int
    ) -> Optional[Dict[str, Any]]:
        """Prepend environmental → molecular edge to a molecular path using INDRA evidence.

        Args:
            env_source: Environmental exposure (e.g., "PM2.5")
            molecular_target: First molecular node (e.g., "TNF")
            molecular_path: INDRA molecular path starting from molecular_target
            belief: Belief score from INDRA multi_interactors
            evidence_count: Number of papers supporting this relationship

        Returns:
            Complete path with environmental → molecular edge prepended
        """
        try:
            # Create synthetic environmental node
            env_node = {
                "id": env_source,
                "name": env_source,
                "grounding": {"db": "MESH", "id": ""}  # Environmental exposure
            }

            # Create environmental → molecular edge using INDRA's evidence
            # The belief and evidence_count come from multi_interactors API
            env_edge = {
                "source": env_source,
                "target": molecular_target,
                "relationship": "increases",  # Environmental exposures typically increase biological activity
                "evidence_count": evidence_count,  # From INDRA literature
                "belief": belief,  # From INDRA
                "statement_type": "IncreaseAmount",
                "pmids": [],  # Available in INDRA but not fetched here
                "db_url_edge": "",
                "source_type": "multi_interactors"  # Mark as from multi_interactors API
            }

            # Prepend environmental node and edge to molecular path
            complete_nodes = [env_node] + molecular_path["nodes"]
            complete_edges = [env_edge] + molecular_path["edges"]

            # Recalculate belief (average across all edges)
            all_beliefs = [e["belief"] for e in complete_edges]
            avg_belief = sum(all_beliefs) / len(all_beliefs) if all_beliefs else 0.5

            return {
                "nodes": complete_nodes,
                "edges": complete_edges,
                "path_belief": avg_belief,
                "multi_hop": True,
                "has_environmental_source": True  # Flag for downstream processing
            }

        except Exception as e:
            logger.error(f"Error adding environmental edge: {e}")
            return None

    def _build_chained_path_with_interactor(
        self, source: str, interactor: Dict, downstream_path: Dict
    ) -> Optional[Dict[str, Any]]:
        """Build a chained path: source → interactor → ... → target.

        Args:
            source: Source entity name
            interactor: Interactor dict from multi_interactors (has name, belief, evidence_count)
            downstream_path: INDRA path from interactor to target

        Returns:
            Complete chained path, or None if chaining fails
        """
        try:
            interactor_name = interactor["name"]

            # Create source node
            source_node = {
                "id": source,
                "name": source,
                "grounding": {"db": "", "id": ""}
            }

            # Create source → interactor edge using multi_interactors evidence
            edge_to_interactor = {
                "source": source,
                "target": interactor_name,
                "relationship": "activates",  # Generic relationship
                "evidence_count": interactor["evidence_count"],
                "belief": interactor["belief"],
                "statement_type": "Activation",
                "pmids": [],
                "db_url_edge": "",
                "source_type": "multi_interactors"
            }

            # Prepend source node and edge to downstream path
            complete_nodes = [source_node] + downstream_path["nodes"]
            complete_edges = [edge_to_interactor] + downstream_path["edges"]

            # Calculate combined belief
            all_beliefs = [e["belief"] for e in complete_edges]
            avg_belief = sum(all_beliefs) / len(all_beliefs) if all_beliefs else 0.5

            return {
                "nodes": complete_nodes,
                "edges": complete_edges,
                "path_belief": avg_belief,
                "multi_hop": True,
            }

        except Exception as e:
            logger.error(f"Error building chained path with interactor: {e}")
            return None

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

    # ============================================================================
    # EXPERIMENTAL: Multi-Biomarker Intervention Discovery
    # ============================================================================

    async def find_shared_regulators(
        self,
        biomarkers: List[str],
        max_depth: int = 3,
        min_coverage: int = 2,
        belief_cutoff: float = 0.6,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find nodes that regulate multiple biomarkers (intervention targets).

        Uses INDRA's shared_regulators query parameter to find common
        upstream regulators that affect multiple biomarkers simultaneously.

        NOTE: This uses HTTP API feature (shared_regulators=True) that is NOT
        available in Python INDRA library.

        Args:
            biomarkers: List of biomarker names (e.g., ["CRP", "IL6", "TNF"])
            max_depth: Maximum upstream distance to search
            min_coverage: Minimum number of biomarkers a regulator must affect
            belief_cutoff: Minimum belief score
            use_cache: Whether to use cached results

        Returns:
            List of intervention candidates sorted by coverage and evidence:
            [
                {
                    "node": "NF-kB",
                    "affected_biomarkers": ["CRP", "IL6", "TNF"],
                    "coverage": 3,
                    "avg_belief": 0.85,
                    "total_evidence": 450,
                    "intervention_score": 0.92  # Multi-factor score
                },
                ...
            ]
        """
        # Check cache first
        cache_key = f"shared_reg:{'_'.join(sorted(biomarkers))}:{max_depth}:{min_coverage}:{belief_cutoff}"
        if use_cache and cache_key in self.intervention_cache:
            logger.info(f"Using cached shared regulators for {len(biomarkers)} biomarkers")
            return self.intervention_cache[cache_key]

        logger.info(f"Finding shared regulators for {len(biomarkers)} biomarkers")

        # Strategy 1: Use INDRA's shared_regulators API for biomarker pairs
        regulators_map = {}  # node_name → {biomarkers, beliefs, evidence}

        # Query for all pairs to build complete regulator map
        for i in range(len(biomarkers)):
            for j in range(i + 1, len(biomarkers)):
                source_name = await self._resolve_to_name(biomarkers[i])
                target_name = await self._resolve_to_name(biomarkers[j])

                if not source_name or not target_name:
                    continue

                try:
                    url = f"{self.base_url}/api/query"
                    payload = {
                        "source": source_name,
                        "target": target_name,
                        "shared_regulators": True,  # ← INDRA's built-in feature! (HTTP API only)
                        "depth_limit": max_depth,
                        "belief_cutoff": belief_cutoff,
                        "filter_curated": True,
                    }

                    response = await self._fetch_with_retry("post", url, json=payload, timeout=30.0)
                    data = response.json()

                    # Parse shared_regulators_results
                    shared_reg_results = data.get("shared_regulators_results")
                    if not shared_reg_results:
                        continue

                    # Extract regulators from source_data (regulators → source)
                    for edge_data in shared_reg_results.get("source_data", []):
                        regulator_node = edge_data.get("edge", [])[0]  # First node is regulator
                        if not regulator_node:
                            continue

                        reg_name = regulator_node.get("name", "")
                        if not reg_name:
                            continue

                        # Initialize regulator entry
                        if reg_name not in regulators_map:
                            regulators_map[reg_name] = {
                                "node": reg_name,
                                "namespace": regulator_node.get("namespace", ""),
                                "identifier": regulator_node.get("identifier", ""),
                                "affected_biomarkers": set(),
                                "beliefs": [],
                                "evidence_counts": [],
                            }

                        # Track that this regulator affects both biomarkers in this pair
                        regulators_map[reg_name]["affected_biomarkers"].add(source_name)
                        regulators_map[reg_name]["affected_biomarkers"].add(target_name)
                        regulators_map[reg_name]["beliefs"].append(edge_data.get("belief", 0.5))

                        # Count evidence
                        statements_dict = edge_data.get("statements", {})
                        total_ev = sum(
                            sum(s.get("source_counts", {}).values())
                            for s in statements_dict.values()
                        )
                        regulators_map[reg_name]["evidence_counts"].append(total_ev)

                    logger.info(
                        f"Found {len(shared_reg_results.get('source_data', []))} shared regulators "
                        f"for {source_name} ↔ {target_name}"
                    )

                except Exception as e:
                    logger.debug(f"Error querying shared regulators for {source_name}, {target_name}: {e}")
                    continue

        # Strategy 2: Calculate intervention scores
        intervention_candidates = []
        for reg_data in regulators_map.values():
            biomarker_coverage = len(reg_data["affected_biomarkers"])

            # Filter by minimum coverage
            if biomarker_coverage < min_coverage:
                continue

            # Calculate metrics
            avg_belief = sum(reg_data["beliefs"]) / len(reg_data["beliefs"]) if reg_data["beliefs"] else 0.5
            total_evidence = sum(reg_data["evidence_counts"])
            coverage_ratio = biomarker_coverage / len(biomarkers)

            # Multi-factor intervention score:
            # - 40%: Coverage (how many biomarkers affected)
            # - 30%: Evidence strength (total papers)
            # - 30%: Belief (confidence)
            evidence_score = min(total_evidence / 50.0, 1.0)
            intervention_score = (
                0.4 * coverage_ratio +
                0.3 * evidence_score +
                0.3 * avg_belief
            )

            intervention_candidates.append({
                "node": reg_data["node"],
                "namespace": reg_data["namespace"],
                "identifier": reg_data["identifier"],
                "affected_biomarkers": list(reg_data["affected_biomarkers"]),
                "coverage": biomarker_coverage,
                "coverage_ratio": coverage_ratio,
                "avg_belief": avg_belief,
                "total_evidence": total_evidence,
                "intervention_score": intervention_score,
            })

        # Sort by intervention score (highest first)
        intervention_candidates.sort(key=lambda x: x["intervention_score"], reverse=True)

        logger.info(
            f"Found {len(intervention_candidates)} intervention candidates "
            f"(min coverage: {min_coverage}/{len(biomarkers)} biomarkers)"
        )

        return intervention_candidates

    async def discover_intervention_hubs(
        self,
        biomarkers: List[str],
        exposures: Optional[List[str]] = None,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """Discover intervention hubs using multi-strategy graph analysis.

        Combines multiple approaches:
        1. Shared regulators (INDRA API)
        2. Betweenness centrality (graph theory)
        3. Layered causal analysis (practical health model)

        Args:
            biomarkers: Target biomarkers to affect
            exposures: Optional environmental/lifestyle exposures (root causes)
            max_depth: Maximum path depth

        Returns:
            {
                "intervention_hubs": [
                    {
                        "node": "NF-kB",
                        "intervention_type": "signaling",  # signaling, metabolic, epigenetic
                        "affected_biomarkers": ["CRP", "IL6"],
                        "upstream_exposures": ["PM2.5", "Stress"],
                        "intervention_score": 0.92,
                        "actionability": "high",  # high, medium, low
                        "druggable": True,
                        "reasoning": "Central inflammatory regulator..."
                    },
                    ...
                ],
                "network_summary": {
                    "total_hubs": 5,
                    "avg_coverage": 2.4,
                    "total_paths_analyzed": 23
                }
            }
        """
        logger.info(f"Discovering intervention hubs for {len(biomarkers)} biomarkers")

        # Step 1: Find shared regulators
        shared_regs = await self.find_shared_regulators(
            biomarkers=biomarkers,
            max_depth=max_depth,
            min_coverage=2,
            belief_cutoff=0.6,
        )

        # Step 2: Build composite graph to calculate betweenness centrality
        all_paths = []
        node_occurrences = {}  # Track how often each node appears in paths

        # Collect all pairwise paths between biomarkers
        for i in range(len(biomarkers)):
            for j in range(i + 1, len(biomarkers)):
                paths = await self.find_causal_paths(
                    source=biomarkers[i],
                    target=biomarkers[j],
                    max_depth=max_depth,
                )
                all_paths.extend(paths)

                # Count node occurrences (proxy for betweenness centrality)
                for path in paths:
                    for node in path.get("nodes", [])[1:-1]:  # Exclude source/target
                        node_name = node.get("name", "")
                        if node_name:
                            if node_name not in node_occurrences:
                                node_occurrences[node_name] = {
                                    "count": 0,
                                    "paths": [],
                                    "affected_biomarkers": set(),
                                }
                            node_occurrences[node_name]["count"] += 1
                            node_occurrences[node_name]["paths"].append(path)
                            node_occurrences[node_name]["affected_biomarkers"].add(biomarkers[i])
                            node_occurrences[node_name]["affected_biomarkers"].add(biomarkers[j])

        # Step 3: Merge shared regulators with betweenness analysis
        intervention_hubs = []
        seen_nodes = set()

        # Add shared regulators (highest priority)
        for reg in shared_regs[:10]:  # Top 10 shared regulators
            node_name = reg["node"]
            seen_nodes.add(node_name)

            # Check if this node also has high betweenness
            betweenness_data = node_occurrences.get(node_name, {})

            # Classify intervention type by namespace
            intervention_type = self._classify_intervention_type(reg.get("namespace", ""))

            # Assess actionability
            actionability = self._assess_actionability(
                node_name,
                reg.get("namespace", ""),
                reg["coverage"],
            )

            intervention_hubs.append({
                "node": node_name,
                "namespace": reg.get("namespace", ""),
                "identifier": reg.get("identifier", ""),
                "intervention_type": intervention_type,
                "affected_biomarkers": reg["affected_biomarkers"],
                "coverage": reg["coverage"],
                "coverage_ratio": reg["coverage_ratio"],
                "upstream_exposures": exposures if exposures else [],
                "intervention_score": reg["intervention_score"],
                "betweenness_count": betweenness_data.get("count", 0),
                "actionability": actionability,
                "druggable": intervention_type in ["signaling", "metabolic"],
                "avg_belief": reg["avg_belief"],
                "total_evidence": reg["total_evidence"],
                "reasoning": self._generate_intervention_reasoning(node_name, reg, intervention_type),
            })

        # Step 4: Add high-betweenness nodes not in shared regulators
        for node_name, data in sorted(
            node_occurrences.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )[:10]:
            if node_name in seen_nodes:
                continue

            # Require minimum path participation
            if data["count"] < 2:
                continue

            # Get first path for namespace info
            first_path = data["paths"][0] if data["paths"] else {}
            node_info = next(
                (n for n in first_path.get("nodes", []) if n.get("name") == node_name),
                {}
            )

            namespace = node_info.get("grounding", {}).get("db", "")
            intervention_type = self._classify_intervention_type(namespace)
            actionability = self._assess_actionability(node_name, namespace, len(data["affected_biomarkers"]))

            intervention_hubs.append({
                "node": node_name,
                "namespace": namespace,
                "identifier": node_info.get("grounding", {}).get("id", ""),
                "intervention_type": intervention_type,
                "affected_biomarkers": list(data["affected_biomarkers"]),
                "coverage": len(data["affected_biomarkers"]),
                "coverage_ratio": len(data["affected_biomarkers"]) / len(biomarkers),
                "upstream_exposures": exposures if exposures else [],
                "intervention_score": min(data["count"] / 10.0, 1.0),  # Normalize betweenness
                "betweenness_count": data["count"],
                "actionability": actionability,
                "druggable": intervention_type in ["signaling", "metabolic"],
                "avg_belief": 0.7,  # Default (not from shared_regulators API)
                "total_evidence": 0,  # Unknown
                "reasoning": f"High betweenness centrality (appears in {data['count']} paths), connects multiple biomarkers",
            })

        # Sort by intervention score
        intervention_hubs.sort(key=lambda x: x["intervention_score"], reverse=True)

        return {
            "intervention_hubs": intervention_hubs,
            "network_summary": {
                "total_hubs": len(intervention_hubs),
                "avg_coverage": sum(h["coverage"] for h in intervention_hubs) / len(intervention_hubs) if intervention_hubs else 0,
                "total_paths_analyzed": len(all_paths),
                "shared_regulators": len(shared_regs),
                "betweenness_hubs": len([h for h in intervention_hubs if h["betweenness_count"] > 0]),
            },
        }

    def _classify_intervention_type(self, namespace: str) -> str:
        """Classify node by intervention type based on database namespace."""
        namespace_upper = namespace.upper()
        if namespace_upper in ["HGNC", "UP"]:
            return "signaling"  # Proteins/genes
        elif namespace_upper in ["CHEBI", "PUBCHEM"]:
            return "metabolic"  # Small molecules
        elif namespace_upper in ["GO"]:
            return "process"  # Biological processes
        elif namespace_upper in ["MESH"]:
            return "environmental"  # Environmental/drugs
        else:
            return "unknown"

    def _assess_actionability(self, node_name: str, namespace: str, coverage: int) -> str:
        """Assess how actionable an intervention target is.

        Args:
            node_name: Node name
            namespace: Database namespace
            coverage: Number of biomarkers affected

        Returns:
            "high", "medium", or "low"
        """
        # Known druggable targets
        known_druggable = ["NF-kB", "NFKB1", "TNF", "IL6", "mTOR", "MAPK", "JAK", "STAT3"]

        # High actionability:
        # - Known druggable targets
        # - Affects many biomarkers
        # - Protein/gene targets
        if node_name in known_druggable or coverage >= 3:
            return "high"
        elif namespace.upper() in ["HGNC", "UP", "CHEBI"] or coverage >= 2:
            return "medium"
        else:
            return "low"

    def _generate_intervention_reasoning(
        self, node_name: str, reg_data: Dict, intervention_type: str
    ) -> str:
        """Generate human-readable reasoning for intervention recommendation."""
        coverage = reg_data["coverage"]
        biomarkers = ", ".join(reg_data["affected_biomarkers"][:3])
        evidence = reg_data["total_evidence"]

        reasoning_parts = []

        # Coverage
        if coverage >= 3:
            reasoning_parts.append(f"Regulates {coverage} biomarkers ({biomarkers})")
        elif coverage == 2:
            reasoning_parts.append(f"Shared regulator of {biomarkers}")
        else:
            reasoning_parts.append(f"Affects {biomarkers}")

        # Evidence
        if evidence > 100:
            reasoning_parts.append(f"{evidence} papers support this relationship")
        elif evidence > 50:
            reasoning_parts.append(f"Well-documented ({evidence} papers)")

        # Type-specific reasoning
        if intervention_type == "signaling":
            reasoning_parts.append("Central signaling molecule - good drug target")
        elif intervention_type == "metabolic":
            reasoning_parts.append("Metabolic target - modifiable via diet/supplements")

        return ". ".join(reasoning_parts) + "."

    async def find_minimal_biomarker_network(
        self,
        biomarkers: List[str],
        exposures: Optional[List[str]] = None,
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        """Find minimal subgraph connecting all biomarkers (Steiner tree approximation).

        This is the *shortest paths covering all biomarkers* - it finds the
        minimal causal network that explains how all biomarkers are connected.

        Args:
            biomarkers: List of biomarker names
            exposures: Optional root causes (environmental/lifestyle)
            max_depth: Maximum path length

        Returns:
            {
                "nodes": [...],  # All nodes in minimal network
                "edges": [...],  # All edges in minimal network
                "intervention_points": [...],  # Nodes with highest leverage
                "total_nodes": 12,
                "total_edges": 15,
                "avg_path_length": 2.3,
                "network_diameter": 4,  # Longest shortest path
            }
        """
        logger.info(f"Finding minimal network connecting {len(biomarkers)} biomarkers")

        # Greedy Steiner tree approximation:
        # 1. Start with first biomarker as root
        # 2. Iteratively add shortest path to nearest unconnected biomarker
        # 3. Build composite network from these paths

        connected_biomarkers = {biomarkers[0]}
        remaining_biomarkers = set(biomarkers[1:])

        all_nodes = {}  # node_name → node_data
        all_edges = []
        total_path_length = 0
        paths_used = 0

        # If exposures provided, start from exposures instead
        if exposures:
            # Connect exposures to first biomarker
            for exposure in exposures:
                paths = await self.find_causal_paths(exposure, biomarkers[0], max_depth=max_depth)
                if paths:
                    # Add first path
                    best_path = paths[0]
                    for node in best_path["nodes"]:
                        all_nodes[node["name"]] = node
                    all_edges.extend(best_path["edges"])
                    total_path_length += len(best_path["nodes"]) - 1
                    paths_used += 1

            connected_biomarkers.add(biomarkers[0])
            remaining_biomarkers = set(biomarkers[1:])

        # Greedy addition of remaining biomarkers
        while remaining_biomarkers:
            best_path = None
            best_target = None
            min_length = float('inf')

            # Find shortest path from any connected biomarker to any unconnected one
            for connected in connected_biomarkers:
                for target in remaining_biomarkers:
                    paths = await self.find_causal_paths(connected, target, max_depth=max_depth)
                    if paths:
                        path_length = len(paths[0]["nodes"]) - 1
                        if path_length < min_length:
                            min_length = path_length
                            best_path = paths[0]
                            best_target = target

            if not best_path:
                logger.warning(f"Could not connect remaining biomarkers: {remaining_biomarkers}")
                break

            # Add best path to network
            for node in best_path["nodes"]:
                all_nodes[node["name"]] = node
            all_edges.extend(best_path["edges"])
            total_path_length += len(best_path["nodes"]) - 1
            paths_used += 1

            # Mark target as connected
            connected_biomarkers.add(best_target)
            remaining_biomarkers.remove(best_target)

            logger.info(f"Connected {best_target} via path of length {len(best_path['nodes']) - 1}")

        # Calculate intervention points (nodes with high out-degree to biomarkers)
        node_to_biomarker_edges = {}
        for edge in all_edges:
            source = edge["source"]
            target = edge["target"]
            if target in biomarkers:
                if source not in node_to_biomarker_edges:
                    node_to_biomarker_edges[source] = []
                node_to_biomarker_edges[source].append(target)

        intervention_points = [
            {
                "node": node,
                "affected_biomarkers": targets,
                "coverage": len(targets),
            }
            for node, targets in node_to_biomarker_edges.items()
            if len(targets) >= 2  # Affects at least 2 biomarkers
        ]
        intervention_points.sort(key=lambda x: x["coverage"], reverse=True)

        # Calculate network metrics
        avg_path_length = total_path_length / paths_used if paths_used > 0 else 0

        # Network diameter: longest shortest path (approximation)
        network_diameter = max(
            (len(edge_list) for edge_list in [
                [e for e in all_edges if e["source"] == biomarkers[i] or e["target"] == biomarkers[i]]
                for i in range(len(biomarkers))
            ]),
            default=0
        )

        return {
            "nodes": list(all_nodes.values()),
            "edges": all_edges,
            "intervention_points": intervention_points,
            "connected_biomarkers": list(connected_biomarkers),
            "disconnected_biomarkers": list(remaining_biomarkers),
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "paths_used": paths_used,
            "avg_path_length": avg_path_length,
            "network_diameter": network_diameter,
        }
