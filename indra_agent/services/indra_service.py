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
            params = {"name": name}

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
            url = f"{self.base_url}/api/node-id-in-graph"
            params = {"id": node_id}

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

        This method attempts to:
        1. Ground entities using Network Search API
        2. Check pre-cached responses
        3. Fallback to empty result if no paths found

        Note: The Network Search API does not support path search.
        We rely on pre-cached responses for path discovery.

        Args:
            source: Source entity ID (e.g., "PM2.5")
            target: Target entity ID (e.g., "IL6")
            max_depth: Maximum path length
            use_cache: Whether to use cached responses

        Returns:
            List of path dicts with nodes and edges
        """
        # Check runtime cache first
        cache_key = f"{source}_{target}_{max_depth}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using cached path for {source} → {target}")
            return self.cache[cache_key]

        # Try to ground entities using Network Search API
        logger.info(f"Attempting to ground entities: {source}, {target}")
        source_grounded = await self.ground_entity(source)
        target_grounded = await self.ground_entity(target)

        if source_grounded:
            logger.info(f"Grounded source '{source}' to: {source_grounded.get('name', 'unknown')}")
        if target_grounded:
            logger.info(f"Grounded target '{target}' to: {target_grounded.get('name', 'unknown')}")

        # Try pre-cached responses
        cached = get_cached_path(source, target)
        if cached:
            logger.info(f"Using pre-cached path for {source} → {target}")
            self.cache[cache_key] = cached
            return cached

        # Network Search API does not support path search
        # Log warning and fallback to empty result
        logger.warning(
            f"No pre-cached paths available for {source} → {target}. "
            "Network Search API does not provide path search functionality."
        )

        # Fallback to empty result
        return []

    async def _query_path_search(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """DEPRECATED: Path search endpoint is not available in Network Search API.

        The Network Search API at network.indra.bio does not provide path search
        functionality. This method is kept for backward compatibility but always
        returns an empty list.

        Args:
            source: Source entity in INDRA format (e.g., "MESH:D052638")
            target: Target entity in INDRA format (e.g., "HGNC:6018")
            max_depth: Maximum path length

        Returns:
            Empty list (path search not supported)
        """
        logger.warning(
            "Path search endpoint is not available in Network Search API. "
            "Using pre-cached responses only."
        )
        return []

    def _parse_path_response(self, data: Dict) -> List[Dict[str, Any]]:
        """Parse INDRA path search response.

        Args:
            data: Raw response from INDRA API

        Returns:
            List of parsed path dicts
        """
        paths = []

        for path_data in data.get("paths", []):
            nodes = []
            for node in path_data.get("nodes", []):
                nodes.append(
                    {
                        "id": node.get("id", node.get("name", "")),
                        "name": node.get("name", ""),
                        "grounding": self._parse_grounding(node.get("id", "")),
                    }
                )

            edges = []
            for edge in path_data.get("edges", []):
                statements = edge.get("statements", [])
                evidence_count = len(statements)
                belief = edge.get("belief", 0.5)

                # Extract PMIDs from statements
                pmids = []
                for stmt in statements[:5]:  # Limit to first 5
                    evidence = stmt.get("evidence", [])
                    for ev in evidence[:2]:  # Limit to 2 per statement
                        pmid = ev.get("pmid")
                        if pmid:
                            pmids.append(f"PMID:{pmid}")

                # Determine relationship type
                stmt_type = statements[0].get("type", "Activation") if statements else "Activation"
                relationship = self._map_statement_type(stmt_type)

                edges.append(
                    {
                        "source": edge.get("source", ""),
                        "target": edge.get("target", ""),
                        "relationship": relationship,
                        "evidence_count": evidence_count,
                        "belief": belief,
                        "statement_type": stmt_type,
                        "pmids": pmids,
                    }
                )

            path_belief = path_data.get("path_belief", 0.5)

            paths.append(
                {"nodes": nodes, "edges": edges, "path_belief": path_belief}
            )

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
