"""LocalOntologyAdapter: Writer KG-compatible interface for local ontology.

Provides a drop-in replacement for Writer KG service using local Memgraph ontology.
Compatible with GroundingService API expectations.
"""

import logging
from typing import Dict, List, Optional

from indra_agent.services.local_ontology import LocalHybridStrategy

logger = logging.getLogger(__name__)


class LocalOntologyAdapter:
    """Adapter providing Writer KG-compatible API for local ontology.

    This class wraps LocalHybridStrategy to provide the same API surface
    that GroundingService expects from Writer KG service.
    """

    def __init__(self):
        """Initialize adapter with LocalHybridStrategy."""
        self.strategy = LocalHybridStrategy()
        self._initialized = False
        logger.info("LocalOntologyAdapter created (not yet initialized)")

    async def initialize(self):
        """Initialize the local ontology connection."""
        if not self._initialized:
            await self.strategy.initialize()
            self._initialized = True
            logger.info("LocalOntologyAdapter initialized")

    async def close(self):
        """Close the local ontology connection."""
        if self._initialized:
            await self.strategy.close()
            self._initialized = False
            logger.info("LocalOntologyAdapter closed")

    async def find_mesh_term(self, query: str) -> Optional[Dict]:
        """Find MeSH term by name (Writer KG-compatible API).

        Args:
            query: Entity name to search for

        Returns:
            Dict with Writer KG-compatible schema:
                {
                    "mesh_id": "D052638",
                    "mesh_label": "Particulate Matter",
                    "synonyms": ["PM", "PM2.5", ...]
                }
            or None if not found
        """
        if not self._initialized:
            await self.initialize()

        # Search MESH namespace
        results = await self.strategy.autocomplete_entity(
            query,
            limit=1,
            namespaces=["MESH"]
        )

        if not results:
            logger.debug(f"No MESH term found for: {query}")
            return None

        best_match = results[0]

        # Convert to Writer KG schema
        # IDs are stored as "mesh:D052638", extract just "D052638"
        mesh_id = best_match['id']
        if ':' in mesh_id:
            mesh_id = mesh_id.split(':', 1)[1]

        result = {
            "mesh_id": mesh_id,
            "mesh_label": best_match['name'],
            "synonyms": best_match.get('synonyms', [])
        }

        logger.debug(f"Found MESH term: {result['mesh_label']} ({result['mesh_id']})")
        return result

    async def get_mesh_synonyms(self, mesh_id: str) -> List[str]:
        """Get synonyms for a MESH ID.

        Args:
            mesh_id: MeSH ID (e.g., "D052638" or "mesh:D052638")

        Returns:
            List of synonyms
        """
        if not self._initialized:
            await self.initialize()

        # Normalize ID format
        if not mesh_id.startswith('mesh:'):
            mesh_id = f"mesh:{mesh_id}"

        # Get entity metadata
        metadata = await self.strategy.get_entity_metadata(mesh_id)

        if not metadata:
            logger.debug(f"No metadata found for MESH ID: {mesh_id}")
            return []

        synonyms = metadata.get('synonyms', [])
        logger.debug(f"Found {len(synonyms)} synonyms for {mesh_id}")
        return synonyms

    async def get_canonical_name(self, mesh_id: str) -> Optional[str]:
        """Get canonical name for a MESH ID.

        Args:
            mesh_id: MeSH ID (e.g., "D052638" or "mesh:D052638")

        Returns:
            Canonical name or None
        """
        if not self._initialized:
            await self.initialize()

        # Normalize ID format
        if not mesh_id.startswith('mesh:'):
            mesh_id = f"mesh:{mesh_id}"

        # Get entity metadata
        metadata = await self.strategy.get_entity_metadata(mesh_id)

        if not metadata:
            logger.debug(f"No metadata found for MESH ID: {mesh_id}")
            return None

        name = metadata.get('name')
        logger.debug(f"Canonical name for {mesh_id}: {name}")
        return name

    async def search_entities(
        self,
        query: str,
        namespaces: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Generic entity search across ontologies.

        Args:
            query: Search query
            namespaces: Optional list of namespaces to search
            limit: Maximum results

        Returns:
            List of entity dicts with keys: id, name, database, synonyms
        """
        if not self._initialized:
            await self.initialize()

        results = await self.strategy.autocomplete_entity(
            query,
            limit=limit,
            namespaces=namespaces
        )

        logger.debug(f"Found {len(results)} entities for query: {query}")
        return results
