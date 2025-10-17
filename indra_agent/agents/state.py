"""State management for INDRA causal discovery agent system.

This module defines state structures for the multi-agent workflow,
following the Lobster architecture pattern with agent-specific state schemas.
"""

from typing import Any, Dict, List

from langgraph.prebuilt.chat_agent_executor import AgentState


class OverallState(AgentState):
    """Supervisor state for coordinating the causal discovery workflow.

    Following LangGraph 0.2.x pattern, the supervisor maintains minimal
    routing metadata while individual agents have their own state schemas.
    """

    # Meta routing information
    last_active_agent: str = ""
    conversation_id: str = ""

    # Task context for handoffs
    current_task: str = ""
    task_context: Dict[str, Any] = {}


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

    # Request context
    request_id: str = ""
    user_context: Dict[str, Any] = {}
    query: Dict[str, Any] = {}
    options: Dict[str, Any] = {}

    # Extracted information
    entities: List[str] = []
    mesh_enriched_entities: List[Dict[str, Any]] = []
    source_entities: List[str] = []
    target_entities: List[str] = []

    # Agent results
    indra_paths: List[Dict[str, Any]] = []
    environmental_data: Dict[str, Any] = {}
    causal_graph: Dict[str, Any] = {}
    explanations: List[str] = []

    # Metadata
    metadata: Dict[str, Any] = {}

    # Routing
    next_agent: str = ""
    current_agent: str = ""
