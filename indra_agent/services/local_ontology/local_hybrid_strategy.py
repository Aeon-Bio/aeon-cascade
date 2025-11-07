"""Local Hybrid Strategy implementation.

Combines LightRAG (semantic search) with Memgraph (graph queries) for
comprehensive ontology querying without external API dependencies.
"""

import logging
from typing import Dict, List, Optional, Set

from indra_agent.services.local_ontology.strategy import OntologyQueryStrategy
from indra_agent.services.local_ontology.lightrag_client import LightRAGClient
from indra_agent.services.local_ontology.memgraph_client import MemgraphClient

logger = logging.getLogger(__name__)


class LocalHybridStrategy(OntologyQueryStrategy):
    """Hybrid local ontology query strategy.

    Uses LightRAG for semantic entity search and grounding,
    Memgraph for graph path finding and relationship traversal.
    """

    def __init__(
        self,
        memgraph_uri: str = "bolt://localhost:7687",
        lightrag_dir: str = "./lightrag_cache",
        embedding_model: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract"
    ):
        """Initialize hybrid strategy.

        Args:
            memgraph_uri: Memgraph Bolt URI
            lightrag_dir: LightRAG working directory
            embedding_model: HuggingFace embedding model
        """
        self.memgraph = MemgraphClient(uri=memgraph_uri)
        self.lightrag = LightRAGClient(
            working_dir=lightrag_dir,
            embedding_model=embedding_model
        )
        self._initialized = False

    async def initialize(self):
        """Initialize both backends."""
        if self._initialized:
            return

        await self.memgraph.connect()
        await self.lightrag.initialize()
        self._initialized = True
        logger.info("Local hybrid strategy initialized")

    async def autocomplete_entity(
        self,
        prefix: str,
        limit: int = 10,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Fuzzy search using Memgraph (faster for prefix matching).

        Args:
            prefix: Text prefix to search for
            limit: Maximum results
            namespaces: Optional namespace filter

        Returns:
            List of entity dicts: name, database, id, score
        """
        if not self._initialized:
            await self.initialize()

        # Use Memgraph for fast prefix search
        entities = await self.memgraph.search_entities(prefix, limit, namespaces)

        # Convert to INDRA format
        results = []
        for entity in entities:
            namespace, local_id = entity["id"].split(":", 1)
            results.append({
                "name": entity["name"],
                "database": namespace.upper(),
                "id": local_id,
                "score": 1.0 - (len(results) * 0.05)  # Decreasing score by rank
            })

        return results

    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 3,
        allowed_namespaces: Optional[Set[str]] = None
    ) -> List[List[Dict]]:
        """Find causal paths using Memgraph graph traversal.

        Args:
            source: Source entity ID (e.g., "mesh:D052638")
            target: Target entity ID (e.g., "hgnc:2367")
            max_depth: Maximum path length
            allowed_namespaces: Optional allowed intermediate namespaces

        Returns:
            List of paths (each path is list of statement dicts)
        """
        if not self._initialized:
            await self.initialize()

        # Use Memgraph for path finding
        paths = await self.memgraph.find_shortest_paths(
            source_id=source,
            target_id=target,
            max_depth=max_depth,
            allowed_namespaces=allowed_namespaces
        )

        # Convert to INDRA statement format
        indra_paths = []
        for path in paths:
            statements = []
            for edge in path:
                statements.append({
                    "stmt_type": edge["type"],
                    "belief": edge["belief"],
                    "evidence_count": edge.get("evidence_count", 1),
                    "pmids": edge.get("pmids", [])
                })
            indra_paths.append(statements)

        return indra_paths

    async def find_shared_regulators(
        self,
        biomarkers: List[str],
        regulator_type: str = "all",
        min_belief: float = 0.5
    ) -> List[Dict]:
        """Find shared regulators using Memgraph.

        Args:
            biomarkers: List of entity IDs
            regulator_type: Type of regulation (currently ignored, returns all)
            min_belief: Minimum belief threshold

        Returns:
            List of regulator dicts
        """
        if not self._initialized:
            await self.initialize()

        # Use Memgraph for shared regulator discovery
        regulators = await self.memgraph.find_shared_regulators(
            biomarker_ids=biomarkers,
            min_belief=min_belief
        )

        # Convert to INDRA format
        results = []
        for reg in regulators:
            namespace, local_id = reg["id"].split(":", 1)
            results.append({
                "id": local_id,
                "name": reg["name"],
                "database": namespace.upper(),
                "targets": reg["targets"],
                "evidence_count": reg["target_count"]  # Proxy for evidence
            })

        return results

    async def get_multi_interactors(
        self,
        entity_ids: List[str],
        interaction_types: Optional[List[str]] = None,
        limit_per_entity: int = 20
    ) -> Dict[str, List[Dict]]:
        """Get interactors for multiple entities using Memgraph.

        Args:
            entity_ids: List of entity IDs
            interaction_types: Optional filter (not yet implemented)
            limit_per_entity: Maximum neighbors per entity

        Returns:
            Dict mapping entity_id -> list of interactors
        """
        if not self._initialized:
            await self.initialize()

        results = {}
        for entity_id in entity_ids:
            # Get neighbors from Memgraph
            neighbors = await self.memgraph.get_neighbors(
                entity_id=entity_id,
                direction="both",
                limit=limit_per_entity
            )

            # Convert to INDRA format
            interactors = []
            for neighbor in neighbors:
                namespace, local_id = neighbor["id"].split(":", 1)
                interactors.append({
                    "id": local_id,
                    "name": neighbor["name"],
                    "database": namespace.upper(),
                    "stmt_type": neighbor["stmt_type"],
                    "belief": neighbor["belief"]
                })

            results[entity_id] = interactors

        return results

    async def ground_entity(
        self,
        text: str,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Ground text to entities using LightRAG semantic search.

        Args:
            text: Text to ground (e.g., "particulate matter", "CRP")
            namespaces: Optional namespace filter

        Returns:
            List of grounded entities with scores
        """
        if not self._initialized:
            await self.initialize()

        # Use LightRAG for semantic grounding
        results = await self.lightrag.ground_text(
            text=text,
            top_k=10,
            namespaces=namespaces
        )

        # Convert to INDRA format
        grounded = []
        for entity in results:
            if "id" in entity and ":" in entity["id"]:
                namespace, local_id = entity["id"].split(":", 1)
                grounded.append({
                    "name": entity.get("name", ""),
                    "database": namespace.upper(),
                    "id": local_id,
                    "score": entity.get("score", 0.5)
                })

        return grounded

    async def get_entity_metadata(
        self,
        entity_id: str
    ) -> Optional[Dict]:
        """Get entity metadata from Memgraph.

        Args:
            entity_id: Entity ID (e.g., "mesh:D052638")

        Returns:
            Dict with entity metadata or None
        """
        if not self._initialized:
            await self.initialize()

        entity = await self.memgraph.get_entity(entity_id)
        if not entity:
            return None

        # Convert to INDRA format
        namespace, local_id = entity["id"].split(":", 1)
        return {
            "id": local_id,
            "name": entity["name"],
            "database": namespace.upper(),
            "definition": entity.get("definition", ""),
            "synonyms": entity.get("synonyms", []),
            "xrefs": entity.get("xrefs", {})
        }

    async def health_check(self) -> Dict[str, bool]:
        """Check health of both backends.

        Returns:
            Dict with service availability
        """
        health = {}

        # Check Memgraph
        try:
            await self.memgraph.verify_connectivity()
            health["memgraph"] = True
        except Exception as e:
            logger.error(f"Memgraph health check failed: {e}")
            health["memgraph"] = False

        # Check LightRAG
        try:
            stats = await self.lightrag.get_stats()
            health["lightrag"] = stats.get("exists", False)
        except Exception as e:
            logger.error(f"LightRAG health check failed: {e}")
            health["lightrag"] = False

        return health

    async def close(self):
        """Close connections to backends."""
        await self.memgraph.close()
        # LightRAG has no persistent connection to close
        self._initialized = False
        logger.info("Local hybrid strategy closed")
