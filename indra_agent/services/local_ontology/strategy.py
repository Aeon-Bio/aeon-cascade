"""Ontology Query Strategy Pattern.

Defines the interface for pluggable ontology query backends.
Allows swapping between INDRA Network API, local hybrid storage, and cached fallback.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set


class OntologyQueryStrategy(ABC):
    """Abstract base class for ontology query strategies.

    All strategies must implement these methods to provide compatible interfaces
    for the INDRAService layer. Responses should match INDRA API format.
    """

    @abstractmethod
    async def autocomplete_entity(
        self,
        prefix: str,
        limit: int = 10,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Fuzzy search for entity names starting with prefix.

        Args:
            prefix: Text prefix to search for
            limit: Maximum number of results
            namespaces: Optional list of database namespaces to filter (e.g., ["HGNC", "MESH"])

        Returns:
            List of entity dicts with keys: name, database, id, score
            Example: [{"name": "Particulate Matter", "database": "MESH", "id": "D052638", "score": 0.95}]
        """
        pass

    @abstractmethod
    async def find_causal_paths(
        self,
        source: str,
        target: str,
        max_depth: int = 3,
        allowed_namespaces: Optional[Set[str]] = None
    ) -> List[List[Dict]]:
        """Find causal paths from source entity to target entity.

        Args:
            source: Source entity ID (e.g., "mesh:D052638")
            target: Target entity ID (e.g., "hgnc:2367")
            max_depth: Maximum path length (default: 3 hops)
            allowed_namespaces: Optional set of allowed intermediate namespaces

        Returns:
            List of paths, where each path is a list of statement dicts.
            Each statement has keys: subj, obj, stmt_type, belief, evidence_count
        """
        pass

    @abstractmethod
    async def find_shared_regulators(
        self,
        biomarkers: List[str],
        regulator_type: str = "all",
        min_belief: float = 0.5
    ) -> List[Dict]:
        """Find common upstream regulators of multiple biomarkers.

        Args:
            biomarkers: List of entity IDs (e.g., ["hgnc:2367", "hgnc:6018"])
            regulator_type: Type of regulation ("activates", "inhibits", "all")
            min_belief: Minimum belief score threshold

        Returns:
            List of regulator dicts with keys: id, name, database, targets, evidence_count
        """
        pass

    @abstractmethod
    async def get_multi_interactors(
        self,
        entity_ids: List[str],
        interaction_types: Optional[List[str]] = None,
        limit_per_entity: int = 20
    ) -> Dict[str, List[Dict]]:
        """Get interactors (neighbors) for multiple entities.

        Args:
            entity_ids: List of entity IDs
            interaction_types: Optional filter for statement types
            limit_per_entity: Maximum neighbors per entity

        Returns:
            Dict mapping entity_id -> list of interactor dicts.
            Each interactor has keys: id, name, database, stmt_type, belief
        """
        pass

    @abstractmethod
    async def ground_entity(
        self,
        text: str,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Ground a text string to ontology entities.

        Args:
            text: Text to ground (e.g., "particulate matter", "CRP")
            namespaces: Optional list of preferred namespaces

        Returns:
            List of grounded entities sorted by score.
            Each entity has keys: name, database, id, score
        """
        pass

    @abstractmethod
    async def get_entity_metadata(
        self,
        entity_id: str
    ) -> Optional[Dict]:
        """Get full metadata for an entity.

        Args:
            entity_id: Entity ID (e.g., "mesh:D052638")

        Returns:
            Dict with keys: id, name, database, definition, synonyms, xrefs
            Returns None if entity not found.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, bool]:
        """Check if backend services are available.

        Returns:
            Dict with service names as keys and availability status as values.
            Example: {"indra_api": True, "memgraph": True, "lightrag": False}
        """
        pass
