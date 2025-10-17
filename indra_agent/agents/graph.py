"""LangGraph workflow for causal discovery system."""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from indra_agent.agents.indra_query_agent import create_indra_query_agent
from indra_agent.agents.mesh_enrichment_agent import create_mesh_enrichment_agent
from indra_agent.agents.state import OverallState
from indra_agent.agents.supervisor import create_supervisor_agent
from indra_agent.agents.web_researcher import create_web_researcher_agent

logger = logging.getLogger(__name__)


def create_causal_discovery_graph():
    """Create the LangGraph workflow for causal discovery.

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Creating causal discovery graph")

    # Create workflow graph
    workflow = StateGraph(OverallState)

    # Create agent instances (factory functions return coroutines, need to be called at runtime)
    # For now we'll use async wrapper pattern
    async def supervisor_node(state: OverallState, config):
        agent = await create_supervisor_agent()
        return await agent(state, config)

    async def mesh_enrichment_node(state: OverallState, config):
        agent = await create_mesh_enrichment_agent()
        result = await agent(state, config)
        await agent.cleanup()
        return result

    async def indra_query_node(state: OverallState, config):
        agent = await create_indra_query_agent()
        result = await agent(state, config)
        await agent.cleanup()
        return result

    async def web_researcher_node(state: OverallState, config):
        agent = await create_web_researcher_agent()
        result = await agent(state, config)
        await agent.cleanup()
        return result

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("mesh_enrichment", mesh_enrichment_node)
    workflow.add_node("indra_query_agent", indra_query_node)
    workflow.add_node("web_researcher", web_researcher_node)

    # Define routing logic
    def route_supervisor(
        state: OverallState,
    ) -> Literal["mesh_enrichment", "indra_query_agent", "web_researcher", END]:
        """Route from supervisor to next agent or END.

        Args:
            state: Current state

        Returns:
            Next node name
        """
        next_agent = state.get("next_agent", "END")
        logger.info(f"Routing from supervisor to: {next_agent}")

        if next_agent == "END":
            return END
        return next_agent

    # Add edges
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "mesh_enrichment": "mesh_enrichment",
            "indra_query_agent": "indra_query_agent",
            "web_researcher": "web_researcher",
            END: END,
        },
    )

    # MeSH enrichment always goes to INDRA query agent
    workflow.add_edge("mesh_enrichment", "indra_query_agent")

    # INDRA and web researcher return to supervisor
    workflow.add_edge("indra_query_agent", "supervisor")
    workflow.add_edge("web_researcher", "supervisor")

    # Set entry point
    workflow.set_entry_point("supervisor")

    # Compile
    graph = workflow.compile()

    logger.info("Causal discovery graph compiled successfully")

    return graph
