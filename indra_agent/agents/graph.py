"""LangGraph workflow for causal discovery system."""

import logging

from langchain_aws import ChatBedrock
from langgraph_supervisor import create_supervisor

from indra_agent.agents.indra_query_agent import create_indra_query_agent
from indra_agent.agents.mesh_enrichment_agent import create_mesh_enrichment_agent
from indra_agent.agents.state import OverallState
from indra_agent.agents.web_researcher import create_web_researcher_agent
from indra_agent.config.agent_config import SUPERVISOR_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.utils.handoff_tools import create_agent_handoff_tools

logger = logging.getLogger(__name__)


async def create_causal_discovery_graph():
    """Create the LangGraph workflow for causal discovery using langgraph_supervisor.

    Returns:
        Compiled LangGraph workflow with supervisor and specialist agents
    """
    logger.info("Creating causal discovery graph with langgraph_supervisor")

    settings = get_settings()

    # Initialize supervisor LLM
    supervisor_llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        model_kwargs={"temperature": SUPERVISOR_CONFIG.temperature},
    )

    # Create handoff tools for all enabled agents
    handoff_tools = create_agent_handoff_tools()
    logger.info(f"Created {len(handoff_tools)} handoff tools")

    # Create specialist agents with handoff tools
    agents = []

    # Conditionally add MeSH enrichment agent if Writer KG configured
    if settings.is_writer_configured:
        logger.info("Writer KG configured - including MeSH enrichment agent")
        mesh_agent = await create_mesh_enrichment_agent(handoff_tools=handoff_tools)
        agents.append(mesh_agent)

    # Always include INDRA query and web researcher agents
    indra_agent = await create_indra_query_agent(handoff_tools=handoff_tools)
    web_agent = await create_web_researcher_agent(handoff_tools=handoff_tools)
    agents.extend([indra_agent, web_agent])

    logger.info(f"Created {len(agents)} specialist agents")

    # Create supervisor workflow
    workflow = create_supervisor(
        agents=agents,
        model=supervisor_llm,
        prompt=SUPERVISOR_CONFIG.system_prompt,
        tools=handoff_tools,
        state_schema=OverallState,
        supervisor_name="supervisor",
    )

    # Compile workflow
    graph = workflow.compile()

    logger.info("Causal discovery graph compiled successfully")
    return graph
