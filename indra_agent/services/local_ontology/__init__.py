"""Local Ontology Query System.

Hybrid architecture combining LightRAG (semantic search with PubMedBERT)
and Memgraph (property graph with Cypher queries) for self-hosted ontology querying.

This module provides a drop-in replacement for INDRA Network Search API,
offering 10x faster queries at zero marginal cost.
"""

from indra_agent.services.local_ontology.strategy import OntologyQueryStrategy
from indra_agent.services.local_ontology.local_hybrid_strategy import LocalHybridStrategy
from indra_agent.services.local_ontology.memgraph_client import MemgraphClient
from indra_agent.services.local_ontology.lightrag_client import LightRAGClient

__all__ = [
    "OntologyQueryStrategy",
    "LocalHybridStrategy",
    "MemgraphClient",
    "LightRAGClient"
]
