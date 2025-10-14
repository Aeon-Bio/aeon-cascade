"""LangGraph state definitions for causal discovery workflow."""

from typing import Any, Dict, List, Literal

from typing_extensions import TypedDict


class OverallState(TypedDict, total=False):
    """Overall state for the causal discovery workflow.

    This state is shared across all agents in the supervisor graph.
    """

    # Messages (LangGraph message handling)
    messages: List[Any]

    # Request context
    request_id: str
    user_context: Dict[str, Any]
    query: Dict[str, Any]
    options: Dict[str, Any]

    # Extracted information
    entities: List[str]
    source_entities: List[str]  # Environmental exposures
    target_entities: List[str]  # Biomarkers

    # Agent results
    indra_paths: List[Dict[str, Any]]  # INDRA query results
    environmental_data: Dict[str, Any]  # Web researcher results
    causal_graph: Dict[str, Any]  # Final causal graph
    explanations: List[str]  # Human-readable explanations

    # Metadata
    metadata: Dict[str, Any]

    # Routing
    next_agent: Literal["indra_query_agent", "web_researcher", "END"]
    current_agent: str
