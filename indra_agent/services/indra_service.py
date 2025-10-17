"""INDRA API service with caching and fallback support.

This service handles all communication with the INDRA bio-ontology database,
including entity grounding via Network Search API and path search with fallback
to cached responses for reliability.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from indra_agent.config.cached_responses import get_cached_path
from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class INDRAService:
    """Service for querying INDRA bio-ontology database."""

    def __init__(self):
        """Initialize INDRA service."""
        self.settings = get_settings()
        self.base_url = self.settings.indra_base_url  # network.indra.bio
        self.timeout = self.settings.indra_timeout
        self.cache: Dict[str, List[Dict]] = {}
        self.entity_cache: Dict[str, Dict] = {}  # Cache for entity resolution
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> bool:
        """Check if INDRA Network Search API is available.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/health"
            response = await self.client.get(url)
            response.raise_for_status()
            logger.info("INDRA Network Search API is healthy")
            return True
        except Exception as e:
            logger.warning(f"INDRA Network Search API health check failed: {e}")
            return False

    async def autocomplete_entity(
        self, prefix: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for entities using autocomplete.

        Args:
            prefix: Text prefix to search for (e.g., "PM2.5", "CRP")
            limit: Maximum number of results

        Returns:
            List of entity matches with name, database, id
        """
        try:
            url = f"{self.base_url}/api/autocomplete"
            params = {"prefix": prefix, "limit": limit}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # API returns list of lists: [["CRP", "HGNC", "2367"], ...]
            # Convert to list of dicts for easier handling
            matches = []
            for item in data:
                if isinstance(item, list) and len(item) >= 3:
                    matches.append({
                        "name": item[0],
                        "database": item[1],
                        "id": item[2]
                    })

            logger.info(f"Autocomplete found {len(matches)} matches for '{prefix}'")
            return matches

        except httpx.HTTPError as e:
            logger.error(f"HTTP error in autocomplete: {e}")
            return []
        except Exception as e:
            logger.error(f"Error in autocomplete: {e}")
            return []

    async def resolve_node_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Resolve a node by name to check if it exists in the graph.

        Args:
            name: Node name (e.g., "CRP", "IL-6")

        Returns:
            Node data if found, None otherwise
        """
        # Check cache first
        cache_key = f"name:{name}"
        if cache_key in self.entity_cache:
            return self.entity_cache[cache_key]

        try:
            url = f"{self.base_url}/api/node-name-in-graph"
            params = {"node-name": name}  # Fixed: OpenAPI schema requires "node-name" not "name"

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            node_data = response.json()
            self.entity_cache[cache_key] = node_data
            logger.info(f"Resolved node by name: {name}")
            return node_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Node not found by name: {name}")
                return None
            logger.error(f"HTTP error resolving node by name: {e}")
            return None
        except Exception as e:
            logger.error(f"Error resolving node by name: {e}")
            return None

    async def resolve_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Resolve a node by ID to check if it exists in the graph.

        Args:
            node_id: Node ID in CURIE format (e.g., "hgnc:2367", "mesh:D052638")

        Returns:
            Node data if found, None otherwise
        """
        # Check cache first
        cache_key = f"id:{node_id}"
        if cache_key in self.entity_cache:
            return self.entity_cache[cache_key]

        try:
            # Parse CURIE format to db-name and db-id
            if ":" not in node_id:
                logger.warning(f"Node ID not in CURIE format: {node_id}")
                return None

            db_name, db_id = node_id.split(":", 1)

            url = f"{self.base_url}/api/node-id-in-graph"
            # Fixed: OpenAPI schema requires "db-name" and "db-id" not "id"
            params = {"db-name": db_name.lower(), "db-id": db_id}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            node_data = response.json()
            self.entity_cache[cache_key] = node_data
            logger.info(f"Resolved node by ID: {node_id}")
            return node_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Node not found by ID: {node_id}")
                return None
            logger.error(f"HTTP error resolving node by ID: {e}")
            return None
        except Exception as e:
            logger.error(f"Error resolving node by ID: {e}")
            return None

    async def get_xrefs(self, query: str) -> List[Dict[str, Any]]:
        """Get cross-references for an entity.

        Args:
            query: Entity identifier or name (e.g., "hgnc:2367", "CRP")

        Returns:
            List of cross-reference mappings
        """
        try:
            url = f"{self.base_url}/api/xrefs"
            params = {"query": query}

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            xrefs = response.json()
            logger.info(f"Found {len(xrefs)} cross-references for '{query}'")
            return xrefs

        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting xrefs: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting xrefs: {e}")
            return []

    async def ground_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Ground an entity using Network Search API.

        This method attempts to resolve an entity name to a proper graph node
        using autocomplete followed by node resolution.

        Args:
            entity_name: Entity name to ground (e.g., "PM2.5", "CRP")

        Returns:
            Grounded entity data with id, name, and grounding info
        """
        # Try autocomplete first
        matches = await self.autocomplete_entity(entity_name, limit=5)

        if not matches:
            logger.warning(f"No autocomplete matches for '{entity_name}'")
            return None

        # Find exact or best match
        best_match = None
        for match in matches:
            match_name = match.get("name", "").lower()
            if match_name == entity_name.lower():
                best_match = match
                break

        if not best_match:
            best_match = matches[0]  # Take first result

        # Construct CURIE format ID (e.g., "hgnc:2367")
        database = best_match.get("database", "").lower()
        entity_id = best_match.get("id", "")
        curie_id = f"{database}:{entity_id}" if database and entity_id else None

        # Try to resolve by CURIE ID if available
        if curie_id:
            node_data = await self.resolve_node_by_id(curie_id)
            if node_data:
                return node_data

        # Try to resolve by name
        node_name = best_match.get("name")
        if node_name:
            node_data = await self.resolve_node_by_name(node_name)
            if node_data:
                return node_data

        logger.warning(f"Could not fully resolve entity: {entity_name}")
        # Return best match with CURIE ID for downstream use
        return {
            "name": best_match.get("name"),
            "database": database.upper(),
            "id": curie_id
        }

    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find causal paths between source and target entities.

        This method:
        1. Checks runtime cache
        2. Checks pre-cached responses
        3. Queries INDRA Network Search API /query endpoint
        4. Parses response according to OpenAPI schema

        Args:
            source: Source entity name (e.g., "PM2.5")
            target: Target entity name (e.g., "CRP")
            max_depth: Maximum path depth (depth_limit parameter)
            use_cache: Whether to use cached responses

        Returns:
            List of path dicts with nodes and edges
        """
        # Check runtime cache first
        cache_key = f"{source}_{target}_{max_depth}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using cached path for {source} → {target}")
            return self.cache[cache_key]

        # Try pre-cached responses first
        cached = get_cached_path(source, target)
        if cached and use_cache:
            logger.info(f"Using pre-cached path for {source} → {target}")
            self.cache[cache_key] = cached
            return cached

        # Query live INDRA Network Search API
        logger.info(f"Querying INDRA Network Search API: {source} → {target}")
        try:
            paths = await self._query_path_search(source, target, max_depth)
            if paths:
                self.cache[cache_key] = paths
                logger.info(f"Found {len(paths)} paths from {source} → {target}")
                return paths
        except Exception as e:
            logger.error(f"Error querying INDRA API: {e}")

        # Fallback to empty result
        logger.warning(f"No paths found for {source} → {target}")
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
            response = await self.client.post(url, json=query_payload, timeout=30.0)
            response.raise_for_status()

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

        # Check if query timed out
        if data.get("timed_out", False):
            logger.warning("INDRA query timed out")
            return paths

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

    def _parse_grounding(self, identifier: str) -> Dict[str, str]:
        """Parse grounding identifier.

        Args:
            identifier: INDRA identifier (e.g., "HGNC:6018")

        Returns:
            Dict with database and id
        """
        if ":" in identifier:
            db, id_val = identifier.split(":", 1)
            return {"db": db, "id": id_val}
        return {"db": "UNKNOWN", "id": identifier}

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
