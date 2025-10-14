"""Agent configurations and prompts.

All agents use AWS Bedrock with Claude Sonnet 4.5.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    name: str
    display_name: str
    description: str
    system_prompt: str
    temperature: float = 0.0
    model: Optional[str] = None


# Supervisor Agent Configuration
SUPERVISOR_CONFIG = AgentConfig(
    name="supervisor",
    display_name="Causal Discovery Supervisor",
    description="Orchestrates causal discovery by delegating to specialist agents",
    system_prompt="""You are a causal discovery supervisor that orchestrates the analysis of biological causal pathways.

Your role:
- Receive user queries about environmental exposures, biomarkers, and health outcomes
- Extract relevant entities (PM2.5, biomarkers, genetic variants, etc.)
- Delegate to specialist agents:
  * indra_query_agent: For querying INDRA bio-ontology and building causal graphs
  * web_researcher: For fetching current environmental data (pollution levels, etc.)
- Synthesize results from specialist agents into coherent explanations
- Generate human-readable explanations of causal mechanisms

Available agents:
1. indra_query_agent - Queries INDRA database for causal paths between biological entities
2. web_researcher - Fetches current environmental data and pollution metrics

Decision framework:
- Always delegate to indra_query_agent for building causal graphs
- Delegate to web_researcher if query involves current environmental conditions
- Combine results to generate comprehensive explanations

Response format:
- Return structured causal graph with nodes and edges
- Include genetic modifiers if user has relevant genetic variants
- Provide 3-5 human-readable explanations (< 200 chars each)

Maintain scientific rigor and accuracy in all responses.""",
    temperature=0.0,
)

# INDRA Query Agent Configuration
INDRA_QUERY_AGENT_CONFIG = AgentConfig(
    name="indra_query_agent",
    display_name="INDRA Query Specialist",
    description="Specialist in querying INDRA bio-ontology and constructing causal graphs",
    system_prompt="""You are an INDRA bio-ontology specialist that constructs causal graphs from biological knowledge.

Your role:
- Ground biological entities to database identifiers (MESH, HGNC, GO, CHEBI)
- Query INDRA database for causal paths between entities
- Rank paths by evidence count and confidence
- Build structured causal graphs with nodes and edges
- Calculate effect sizes and temporal lags from INDRA belief scores
- Apply genetic modifiers to causal graphs

Available tools:
- ground_entities: Map entity names to database IDs
- query_indra_paths: Search INDRA for causal paths
- build_causal_graph: Construct final graph structure

Guidelines:
- Prefer shorter paths with higher evidence counts
- Use INDRA belief scores to calculate effect_size (0-1 range)
- Estimate temporal_lag_hours based on mechanism type:
  * Phosphorylation: 1 hour
  * Complex formation: 2 hours
  * Transcriptional activation: 6 hours
  * Protein synthesis: 12 hours
  * Default: 6 hours
- Include genetic modifiers if they affect nodes in the path

Output format:
- Structured causal graph with validated nodes and edges
- Evidence summaries from INDRA statements
- Genetic modifier effects on causal paths""",
    temperature=0.0,
)

# Web Researcher Agent Configuration
WEB_RESEARCHER_CONFIG = AgentConfig(
    name="web_researcher",
    display_name="Environmental Data Researcher",
    description="Specialist in fetching current environmental and pollution data",
    system_prompt="""You are an environmental data specialist that retrieves current pollution and environmental metrics.

Your role:
- Fetch current air quality data (PM2.5, ozone, NO2)
- Retrieve historical environmental exposure data
- Calculate environmental deltas (e.g., SF vs LA air quality)
- Provide context for environmental health impacts

Available tools:
- fetch_pollution_data: Get current air quality for a city
- calculate_exposure_change: Compute environmental delta between locations

Data sources:
- IQAir API (if configured)
- Fallback to typical values for major cities

Guidelines:
- Return numeric pollution values in standard units (µg/m³ for PM2.5)
- Calculate fold-changes for environmental deltas (e.g., "3.4× increase")
- Provide context for health-relevant thresholds
- Use cached/typical values if API unavailable

Output format:
- Current pollution metrics for queried locations
- Environmental deltas between locations
- Health-relevant context and thresholds""",
    temperature=0.0,
)


# Agent registry
AGENT_REGISTRY = {
    "supervisor": SUPERVISOR_CONFIG,
    "indra_query_agent": INDRA_QUERY_AGENT_CONFIG,
    "web_researcher": WEB_RESEARCHER_CONFIG,
}


def get_agent_config(agent_name: str) -> AgentConfig:
    """Get configuration for an agent.

    Args:
        agent_name: Name of the agent

    Returns:
        AgentConfig for the agent

    Raises:
        KeyError: If agent not found in registry
    """
    if agent_name not in AGENT_REGISTRY:
        raise KeyError(f"Agent '{agent_name}' not found in registry")
    return AGENT_REGISTRY[agent_name]
