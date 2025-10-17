"""Agent registry for dynamic agent discovery and configuration.

This module provides a registry system for managing agents in the INDRA
causal discovery system, following the Lobster architecture pattern.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from langgraph.prebuilt.chat_agent_executor import AgentState

from indra_agent.agents.state import (
    INDRAQueryState,
    MeshEnrichmentState,
    WebResearcherState,
)
from indra_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for a single agent in the system.

    Attributes:
        name: Internal identifier for the agent (e.g., "mesh_enrichment")
        display_name: Human-readable name shown to users
        description: Brief description of agent capabilities
        factory_function: Import path to factory function (e.g., "module:function")
        state_schema: Optional state schema class for agent
        handoff_tool_name: Optional custom name for handoff tool
        handoff_tool_description: Optional description for handoff tool
        tags: List of tags for categorization (e.g., ["enrichment", "ontology"])
        enabled: Whether agent is active
        dependencies: List of agent names this agent depends on
        metadata: Additional metadata for agent
    """

    name: str
    display_name: str
    description: str
    factory_function: str  # e.g., "indra_agent.agents.mesh_enrichment_agent:create_mesh_enrichment_agent"
    state_schema: Optional[Type[AgentState]] = None
    handoff_tool_name: Optional[str] = None
    handoff_tool_description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.name:
            raise ValueError("Agent name cannot be empty")
        if not self.factory_function:
            raise ValueError(f"Agent {self.name} must have a factory_function")


# Global agent registry
AGENT_REGISTRY: Dict[str, AgentConfig] = {
    "mesh_enrichment": AgentConfig(
        name="mesh_enrichment",
        display_name="MeSH Semantic Enrichment Specialist",
        description="Specialist in expanding biomedical queries using MeSH ontology from Writer Knowledge Graph. Enriches entities with synonyms, hierarchical relationships, and related concepts.",
        factory_function="indra_agent.agents.mesh_enrichment_agent:create_mesh_enrichment_agent",
        state_schema=MeshEnrichmentState,
        handoff_tool_name="consult_mesh_enrichment_specialist",
        handoff_tool_description="Consult the MeSH enrichment specialist to expand biomedical terms with ontology knowledge. Use when you need to find synonyms, broader/narrower terms, or related concepts for biological entities.",
        tags=["enrichment", "ontology", "semantic"],
        enabled=True,
        metadata={
            "requires_writer_kg": True,
            "output_format": "mesh_enriched_entities",
        },
    ),
    "indra_query_agent": AgentConfig(
        name="indra_query_agent",
        display_name="INDRA Causal Pathway Specialist",
        description="Specialist in querying the INDRA bio-ontology to discover causal paths between environmental exposures, molecular mechanisms, and clinical biomarkers. Builds evidence-based causal graphs.",
        factory_function="indra_agent.agents.indra_query_agent:create_indra_query_agent",
        state_schema=INDRAQueryState,
        handoff_tool_name="consult_indra_pathway_specialist",
        handoff_tool_description="Consult the INDRA pathway specialist to find causal relationships in biological systems. Use when you need to discover mechanistic pathways between exposures and biomarkers.",
        tags=["causality", "pathways", "biology"],
        enabled=True,
        dependencies=["mesh_enrichment"],  # Can use MeSH-enriched entities
        metadata={
            "api_endpoint": "https://network.indra.bio",
            "max_depth": 4,
            "output_format": "causal_graph",
        },
    ),
    "web_researcher": AgentConfig(
        name="web_researcher",
        display_name="Environmental Data Research Specialist",
        description="Specialist in fetching real-time environmental data (air quality, pollution metrics) based on location history. Calculates exposure changes across locations.",
        factory_function="indra_agent.agents.web_researcher:create_web_researcher_agent",
        state_schema=WebResearcherState,
        handoff_tool_name="consult_environmental_researcher",
        handoff_tool_description="Consult the environmental researcher to fetch pollution data and calculate exposure changes. Use when you have location history and need environmental context.",
        tags=["environment", "pollution", "research"],
        enabled=True,
        metadata={
            "api_provider": "iqair",
            "output_format": "environmental_data",
        },
    ),
}


def register_agent(agent_config: AgentConfig) -> None:
    """Register a new agent in the global registry.

    Args:
        agent_config: Agent configuration to register

    Raises:
        ValueError: If agent with same name already exists
    """
    if agent_config.name in AGENT_REGISTRY:
        raise ValueError(f"Agent '{agent_config.name}' is already registered")

    AGENT_REGISTRY[agent_config.name] = agent_config
    logger.info(f"Registered agent: {agent_config.display_name} ({agent_config.name})")


def unregister_agent(agent_name: str) -> None:
    """Remove an agent from the registry.

    Args:
        agent_name: Name of agent to remove

    Raises:
        KeyError: If agent doesn't exist
    """
    if agent_name not in AGENT_REGISTRY:
        raise KeyError(f"Agent '{agent_name}' not found in registry")

    del AGENT_REGISTRY[agent_name]
    logger.info(f"Unregistered agent: {agent_name}")


def get_agent_config(agent_name: str) -> Optional[AgentConfig]:
    """Get configuration for a specific agent.

    Args:
        agent_name: Name of agent to retrieve

    Returns:
        AgentConfig if found, None otherwise
    """
    return AGENT_REGISTRY.get(agent_name)


def get_all_agents() -> Dict[str, AgentConfig]:
    """Get all registered agents.

    Returns:
        Dictionary mapping agent names to configurations
    """
    return AGENT_REGISTRY.copy()


def get_worker_agents() -> Dict[str, AgentConfig]:
    """Get all worker agents (excluding supervisor).

    Returns:
        Dictionary mapping agent names to configurations
    """
    return {
        name: config
        for name, config in AGENT_REGISTRY.items()
        if name != "supervisor"
    }


def get_enabled_agents() -> Dict[str, AgentConfig]:
    """Get only enabled agents.

    Returns:
        Dictionary mapping enabled agent names to configurations
    """
    return {
        name: config
        for name, config in AGENT_REGISTRY.items()
        if config.enabled
    }


def get_agents_by_tag(tag: str) -> Dict[str, AgentConfig]:
    """Get agents with a specific tag.

    Args:
        tag: Tag to filter by

    Returns:
        Dictionary mapping agent names to configurations
    """
    return {
        name: config
        for name, config in AGENT_REGISTRY.items()
        if tag in config.tags
    }


def import_agent_factory(factory_path: str) -> Callable:
    """Import agent factory function from module path.

    Args:
        factory_path: Import path in format "module.path:function_name"

    Returns:
        Factory function callable

    Raises:
        ImportError: If module or function cannot be imported

    Example:
        >>> factory = import_agent_factory("indra_agent.agents.mesh:create_mesh_agent")
        >>> agent = await factory(data_manager=dm)
    """
    try:
        module_path, function_name = factory_path.split(":")
        module = __import__(module_path, fromlist=[function_name])
        factory = getattr(module, function_name)
        return factory
    except (ValueError, ImportError, AttributeError) as e:
        raise ImportError(f"Failed to import factory '{factory_path}': {e}")


def validate_agent_dependencies() -> List[str]:
    """Validate that all agent dependencies are satisfied.

    Returns:
        List of error messages (empty if all dependencies satisfied)
    """
    errors = []

    for agent_name, config in AGENT_REGISTRY.items():
        for dep in config.dependencies:
            if dep not in AGENT_REGISTRY:
                errors.append(
                    f"Agent '{agent_name}' depends on '{dep}' which is not registered"
                )
            elif not AGENT_REGISTRY[dep].enabled:
                errors.append(
                    f"Agent '{agent_name}' depends on '{dep}' which is disabled"
                )

    return errors


def get_agent_delegation_rules(agent_name: str) -> str:
    """Get delegation rules for supervisor to know when to use this agent.

    Args:
        agent_name: Name of agent

    Returns:
        Formatted delegation rules or generic message
    """
    # Define delegation rules for each agent
    delegation_rules = {
        "mesh_enrichment": """       - Expanding biomedical terminology with MeSH ontology.
       - Finding synonyms and alternative terms for biological entities.
       - Discovering hierarchical relationships (broader/narrower terms).
       - Semantic enrichment of user queries before INDRA lookup.""",

        "indra_query_agent": """       - Discovering causal pathways between biological entities.
       - Finding mechanistic relationships (e.g., PM2.5 → NF-κB → IL-6 → CRP).
       - Building evidence-based causal graphs from scientific literature.
       - Grounding biological entities to standard ontologies (MESH, HGNC, GO).
       - Ranking causal paths by evidence strength and belief scores.""",

        "web_researcher": """       - Fetching real-time environmental data (air quality, pollution).
       - Retrieving historical pollution metrics for specific locations.
       - Calculating exposure changes when user has location history.
       - Providing environmental context for causal pathway analysis.""",
    }

    agent_config = get_agent_config(agent_name)
    if not agent_config:
        return f"       - Tasks related to {agent_name}"

    return delegation_rules.get(agent_name, f"       - {agent_config.description}")


def get_agent_capability_summary(agent_name: str, max_tools: int = 5) -> str:
    """Get formatted capability summary for an agent.

    Args:
        agent_name: Name of agent
        max_tools: Maximum number of tools to show (not yet implemented)

    Returns:
        Formatted capability string
    """
    agent_config = get_agent_config(agent_name)
    if not agent_config:
        return f"Unknown agent: {agent_name}"

    summary = f"**{agent_config.display_name}** ({agent_name}): {agent_config.description}"

    # Add tags if present
    if agent_config.tags:
        summary += f" [Tags: {', '.join(agent_config.tags)}]"

    return summary


# Validate registry on module load
_validation_errors = validate_agent_dependencies()
if _validation_errors:
    logger.warning(f"Agent registry validation errors:\n" + "\n".join(_validation_errors))
