"""State manager for causal discovery workflow.

Simplified version of DataManagerV2 focused on managing causal discovery state.
"""

import logging
from typing import Any, Dict, List, Optional

from indra_agent.core.models import CausalGraph

logger = logging.getLogger(__name__)


class StateManager:
    """Manages state for causal discovery workflow."""

    def __init__(self):
        """Initialize state manager."""
        # Request context
        self.request_id: Optional[str] = None
        self.user_context: Dict[str, Any] = {}
        self.query: Dict[str, Any] = {}

        # Extracted entities
        self.entities: List[str] = []
        self.source_entities: List[str] = []
        self.target_entities: List[str] = []

        # INDRA results
        self.indra_paths: List[Dict[str, Any]] = []

        # Environmental data
        self.environmental_data: Dict[str, Any] = {}

        # Final outputs
        self.causal_graph: Optional[CausalGraph] = None
        self.explanations: List[str] = []

        # Metadata
        self.metadata: Dict[str, Any] = {
            "paths_explored": 0,
            "total_evidence": 0,
        }

    def set_request_context(
        self,
        request_id: str,
        user_context: Dict[str, Any],
        query: Dict[str, Any],
    ):
        """Set request context.

        Args:
            request_id: Unique request identifier
            user_context: User context data
            query: Query information
        """
        self.request_id = request_id
        self.user_context = user_context
        self.query = query

        logger.info(f"Request context set: {request_id}")

    def store_entities(
        self,
        entities: List[str],
        source_entities: Optional[List[str]] = None,
        target_entities: Optional[List[str]] = None,
    ):
        """Store extracted entities.

        Args:
            entities: All extracted entities
            source_entities: Source entities (exposures)
            target_entities: Target entities (biomarkers)
        """
        self.entities = entities
        self.source_entities = source_entities or []
        self.target_entities = target_entities or []

        logger.info(
            f"Entities stored: {len(entities)} total, "
            f"{len(self.source_entities)} sources, "
            f"{len(self.target_entities)} targets"
        )

    def store_indra_paths(self, paths: List[Dict[str, Any]]):
        """Store INDRA query results.

        Args:
            paths: List of causal paths from INDRA
        """
        self.indra_paths = paths
        self.metadata["paths_explored"] = len(paths)

        # Count total evidence
        total_evidence = 0
        for path in paths:
            for edge in path.get("edges", []):
                total_evidence += edge.get("evidence_count", 0)
        self.metadata["total_evidence"] = total_evidence

        logger.info(f"INDRA paths stored: {len(paths)} paths, {total_evidence} evidence papers")

    def store_environmental_data(self, data: Dict[str, Any]):
        """Store environmental data.

        Args:
            data: Environmental exposure data
        """
        self.environmental_data = data
        logger.info(f"Environmental data stored for {data.get('current', {}).get('city', 'unknown')}")

    def store_causal_graph(self, graph: CausalGraph):
        """Store final causal graph.

        Args:
            graph: Constructed causal graph
        """
        self.causal_graph = graph
        logger.info(
            f"Causal graph stored: {len(graph.nodes)} nodes, "
            f"{len(graph.edges)} edges, "
            f"{len(graph.genetic_modifiers)} genetic modifiers"
        )

    def store_explanations(self, explanations: List[str]):
        """Store human-readable explanations.

        Args:
            explanations: List of explanation strings
        """
        self.explanations = explanations
        logger.info(f"Explanations stored: {len(explanations)} items")

    def get_genetics(self) -> Dict[str, str]:
        """Get user genetics.

        Returns:
            Dict of genetic variants
        """
        return self.user_context.get("genetics", {})

    def get_current_biomarkers(self) -> Dict[str, float]:
        """Get current biomarker values.

        Returns:
            Dict of biomarker values
        """
        return self.user_context.get("current_biomarkers", {})

    def get_location_history(self) -> List[Dict[str, Any]]:
        """Get location history.

        Returns:
            List of location history entries
        """
        return self.user_context.get("location_history", [])

    def get_focus_biomarkers(self) -> List[str]:
        """Get focus biomarkers from query.

        Returns:
            List of biomarker names
        """
        return self.query.get("focus_biomarkers", [])

    def has_causal_graph(self) -> bool:
        """Check if causal graph has been constructed.

        Returns:
            True if graph exists
        """
        return self.causal_graph is not None

    def reset(self):
        """Reset state for new request."""
        self.__init__()
        logger.info("State manager reset")
