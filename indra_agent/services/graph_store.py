"""In-memory graph storage for MVP.

For production, replace with Redis or PostgreSQL.
"""

import logging
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from indra_agent.core.models import CausalGraph

logger = logging.getLogger(__name__)


class GraphStore:
    """In-memory graph storage with TTL and LRU eviction."""

    def __init__(self, max_size: int = 100, ttl_hours: int = 24):
        """Initialize graph store.

        Args:
            max_size: Maximum number of graphs to store
            ttl_hours: Time-to-live in hours
        """
        self.graphs: OrderedDict[str, Dict] = OrderedDict()
        self.max_size = max_size
        self.ttl_hours = ttl_hours

    def store(self, graph_id: str, graph: CausalGraph, baseline_values: Optional[Dict[str, float]] = None) -> None:
        """Store graph with metadata.

        Args:
            graph_id: Unique identifier for graph
            graph: CausalGraph to store
            baseline_values: Baseline values for nodes (optional)
        """
        # Evict oldest if at capacity
        if len(self.graphs) >= self.max_size:
            self.graphs.popitem(last=False)  # Remove oldest (FIFO)

        self.graphs[graph_id] = {
            "graph": graph,
            "baseline_values": baseline_values or {},
            "timestamp": datetime.now(timezone.utc),
        }

        logger.info(f"Stored graph {graph_id} with {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    def retrieve(self, graph_id: str) -> Dict:
        """Retrieve graph if not expired.

        Args:
            graph_id: Graph identifier

        Returns:
            Dict with graph and baseline_values

        Raises:
            ValueError: If graph not found or expired
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        entry = self.graphs[graph_id]
        age = datetime.now(timezone.utc) - entry["timestamp"]

        if age > timedelta(hours=self.ttl_hours):
            del self.graphs[graph_id]
            raise ValueError(f"Graph {graph_id} expired (age: {age})")

        # Move to end (LRU)
        self.graphs.move_to_end(graph_id)

        return {
            "graph": entry["graph"],
            "baseline_values": entry["baseline_values"],
        }

    def delete(self, graph_id: str) -> None:
        """Delete graph from store.

        Args:
            graph_id: Graph identifier
        """
        if graph_id in self.graphs:
            del self.graphs[graph_id]
            logger.info(f"Deleted graph {graph_id}")

    def clear_expired(self) -> int:
        """Clear all expired graphs.

        Returns:
            Number of graphs deleted
        """
        now = datetime.now(timezone.utc)
        expired_ids = []

        for graph_id, entry in self.graphs.items():
            age = now - entry["timestamp"]
            if age > timedelta(hours=self.ttl_hours):
                expired_ids.append(graph_id)

        for graph_id in expired_ids:
            del self.graphs[graph_id]

        if expired_ids:
            logger.info(f"Cleared {len(expired_ids)} expired graphs")

        return len(expired_ids)

    def size(self) -> int:
        """Get current number of stored graphs.

        Returns:
            Number of graphs
        """
        return len(self.graphs)


# Global instance (singleton)
_graph_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """Get or create global graph store instance.

    Returns:
        GraphStore instance
    """
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore(max_size=100, ttl_hours=24)
    return _graph_store
