"""INDRA API service with caching and fallback support.

This service handles all communication with the INDRA bio-ontology database,
including path search, evidence retrieval, and caching for reliability.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from indra_agent.config.cached_responses import get_cached_path
from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class INDRAService:
    """Service for querying INDRA bio-ontology database."""

    def __init__(self):
        """Initialize INDRA service."""
        self.settings = get_settings()
        self.base_url = self.settings.indra_base_url
        self.timeout = self.settings.indra_timeout
        self.cache: Dict[str, List[Dict]] = {}
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 4,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """Find causal paths between source and target entities.

        Args:
            source: Source entity ID (e.g., "PM2.5")
            target: Target entity ID (e.g., "IL6")
            max_depth: Maximum path length
            use_cache: Whether to use cached responses

        Returns:
            List of path dicts with nodes and edges
        """
        # Check cache first
        cache_key = f"{source}_{target}_{max_depth}"
        if use_cache and cache_key in self.cache:
            logger.info(f"Using cached path for {source} → {target}")
            return self.cache[cache_key]

        # Try pre-cached responses
        cached = get_cached_path(source, target)
        if cached:
            logger.info(f"Using pre-cached path for {source} → {target}")
            self.cache[cache_key] = cached
            return cached

        # Try live INDRA API
        try:
            paths = await self._query_path_search(source, target, max_depth)
            if paths:
                self.cache[cache_key] = paths
                return paths
        except Exception as e:
            logger.error(f"INDRA API error: {e}")

        # Fallback to empty result
        logger.warning(f"No paths found for {source} → {target}")
        return []

    async def _query_path_search(
        self, source: str, target: str, max_depth: int
    ) -> List[Dict[str, Any]]:
        """Query INDRA path search endpoint.

        Args:
            source: Source entity in INDRA format (e.g., "MESH:D052638")
            target: Target entity in INDRA format (e.g., "HGNC:6018")
            max_depth: Maximum path length

        Returns:
            List of paths from INDRA API
        """
        try:
            url = f"{self.base_url}/api/network/path_search"
            params = {
                "source": source,
                "target": target,
                "max_depth": max_depth,
                "k_shortest": 5,
                "stmt_filter": [
                    "Activation",
                    "Inhibition",
                    "IncreaseAmount",
                    "DecreaseAmount",
                ],
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            paths = self._parse_path_response(data)

            logger.info(f"Found {len(paths)} paths from {source} to {target}")
            return paths

        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying INDRA: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing INDRA response: {e}")
            raise

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
