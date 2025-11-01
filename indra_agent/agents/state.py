"""State management for INDRA causal discovery agent system.

This module defines state structures for the multi-agent workflow,
following the Lobster architecture pattern with agent-specific state schemas.
"""

from typing import Annotated, Any, Dict, List, Optional

from langgraph.prebuilt.chat_agent_executor import AgentState
from indra_agent.core.progress import ProgressEmitter


# Lang Graph reducer: last write wins (rightmost value in update sequence)
def replace_reducer(x: Any, y: Any) -> Any:
    """LangGraph reducer: keep last non-empty value (allows concurrent updates).

    Args:
        x: Current/left value
        y: New/right value (from update)

    Returns:
        y if y is not None/empty, otherwise x

    This implements "last write wins" semantics while treating None and
    empty dicts as non-updates to prevent accidental clearing of state.
    """
    # If new value (y) is None or empty dict, keep current (x)
    if y is None or (isinstance(y, dict) and not y):
        return x
    # Otherwise, return new value (y) - "last write wins"
    return y


class OverallState(AgentState):
    """Supervisor state for coordinating the causal discovery workflow.

    This state tracks all data flowing through the multi-agent system,
    including request context, agent results, and routing information.
    """

    # Request context (with reducers to handle concurrent agent updates)
    request_id: Annotated[str, replace_reducer] = ""
    user_context: Annotated[Dict[str, Any], replace_reducer] = {}
    query: Annotated[Dict[str, Any], replace_reducer] = {}
    options: Annotated[Dict[str, Any], replace_reducer] = {}

    # Extracted information (with reducers for concurrent updates)
    entities: Annotated[List[str], replace_reducer] = []
    mesh_enriched_entities: Annotated[List[Dict[str, Any]], replace_reducer] = []
    source_entities: Annotated[List[str], replace_reducer] = []
    target_entities: Annotated[List[str], replace_reducer] = []

    # Agent results
    indra_paths: Annotated[List[Dict[str, Any]], replace_reducer] = []
    environmental_data: Annotated[Dict[str, Any], replace_reducer] = {}
    causal_graph: Annotated[Dict[str, Any], replace_reducer] = {}
    explanations: Annotated[List[str], replace_reducer] = []

    # Metadata
    metadata: Annotated[Dict[str, Any], replace_reducer] = {}
    predictions: Annotated[Dict[str, Any], replace_reducer] = {}

    # Routing (with reducers for concurrent updates)
    next_agent: Annotated[str, replace_reducer] = ""
    current_agent: Annotated[str, replace_reducer] = ""

    # Progress tracking: progress_emitter passed via config["configurable"]
    # NOT in state (causes pickle errors when deep copied by LangGraph)

    # ReAct agent internal state (from create_react_agent)
    remaining_steps: int = 10


class MeshEnrichmentState(AgentState):
    """State for the MeSH enrichment agent."""

    next: str

    # Task description
    task_description: str  # Description of enrichment task

    # Input
    query_text: str  # Original user query
    biomedical_terms: List[str]  # Extracted terms to enrich

    # Output
    mesh_enriched_entities: List[Dict[str, Any]]  # Enriched entities with MeSH metadata

    # Intermediate
    enrichment_status: Dict[str, Any]  # Status of enrichment process


class INDRAQueryState(AgentState):
    """State for the INDRA query agent."""

    next: str

    # Task description
    task_description: str  # Description of query task

    # Input
    query_text: str  # Original user query
    focus_biomarkers: List[str]  # User-specified biomarkers
    mesh_enriched_entities: List[Dict[str, Any]]  # From MeSH agent (optional)
    genetics: Dict[str, Any]  # User genetic context

    # Entity resolution
    entities: List[str]  # Extracted entities
    grounded_entities: Dict[str, Any]  # Grounded to database IDs
    source_entities: List[str]  # Environmental exposures
    target_entities: List[str]  # Biomarkers

    # INDRA results
    indra_paths: List[Dict[str, Any]]  # Raw paths from INDRA API
    ranked_paths: List[Dict[str, Any]]  # Paths ranked by evidence
    causal_graph: Dict[str, Any]  # Structured causal graph

    # Intermediate outputs
    grounding_status: Dict[str, Any]  # Entity grounding results
    query_status: Dict[str, Any]  # INDRA API query status


class WebResearcherState(AgentState):
    """State for the web researcher agent."""

    next: str

    # Task description
    task_description: str  # Description of research task

    # Input
    query_text: str  # Original user query
    location_history: List[Dict[str, Any]]  # User location history
    target_pollutants: List[str]  # Pollutants to fetch (e.g., PM2.5, ozone)

    # Environmental data results
    environmental_data: Dict[str, Any]  # Fetched pollution data
    exposure_deltas: Dict[str, Any]  # Calculated exposure changes

    # Intermediate outputs
    api_calls: List[Dict[str, Any]]  # Record of API calls made
    data_quality: Dict[str, Any]  # Quality metrics for fetched data


# Legacy state for backward compatibility during migration
class LegacyOverallState(AgentState):
    """Legacy shared state structure (deprecated).

    This is maintained for backward compatibility during migration.
    New code should use agent-specific state schemas above.
    """

    # Request context (with reducers to handle concurrent agent updates)
    request_id: Annotated[str, replace_reducer] = ""
    user_context: Annotated[Dict[str, Any], replace_reducer] = {}
    query: Annotated[Dict[str, Any], replace_reducer] = {}
    options: Annotated[Dict[str, Any], replace_reducer] = {}

    # Extracted information (with reducers for concurrent updates)
    entities: Annotated[List[str], replace_reducer] = []
    mesh_enriched_entities: Annotated[List[Dict[str, Any]], replace_reducer] = []
    source_entities: Annotated[List[str], replace_reducer] = []
    target_entities: Annotated[List[str], replace_reducer] = []

    # Agent results
    indra_paths: Annotated[List[Dict[str, Any]], replace_reducer] = []
    environmental_data: Annotated[Dict[str, Any], replace_reducer] = {}
    causal_graph: Annotated[Dict[str, Any], replace_reducer] = {}
    explanations: Annotated[List[str], replace_reducer] = []

    # Metadata
    metadata: Annotated[Dict[str, Any], replace_reducer] = {}

    # Routing (with reducers for concurrent updates)
    next_agent: Annotated[str, replace_reducer] = ""
    current_agent: Annotated[str, replace_reducer] = ""
