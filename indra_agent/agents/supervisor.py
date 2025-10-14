"""Supervisor agent for orchestrating causal discovery workflow."""

import logging
import time
from typing import Dict, Literal

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import SUPERVISOR_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.core.models import CausalGraph, Metadata
from indra_agent.services.graph_builder import GraphBuilderService

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Supervisor agent that orchestrates the causal discovery workflow."""

    def __init__(self):
        """Initialize supervisor agent."""
        self.settings = get_settings()
        self.config = SUPERVISOR_CONFIG
        self.graph_builder = GraphBuilderService()

        # Initialize LLM (AWS Bedrock)
        self.llm = ChatBedrock(
            model_id=self.settings.agent_model,
            region_name=self.settings.aws_region,
            model_kwargs={"temperature": self.config.temperature},
        )

        self.start_time = None

    async def __call__(
        self, state: OverallState, config: RunnableConfig
    ) -> Dict:
        """Execute supervisor agent.

        Args:
            state: Current workflow state
            config: Runnable configuration

        Returns:
            Updated state dict
        """
        if self.start_time is None:
            self.start_time = time.time()

        current_agent = state.get("current_agent", "")

        logger.info(f"Supervisor executing (current_agent: {current_agent})")

        # Initial routing
        if not current_agent:
            return self._initial_routing(state)

        # After INDRA agent
        if current_agent == "indra_query_agent":
            return await self._after_indra_agent(state)

        # After web researcher
        if current_agent == "web_researcher":
            return self._after_web_researcher(state)

        # Default: end
        return {"next_agent": "END"}

    def _initial_routing(self, state: OverallState) -> Dict:
        """Initial routing logic.

        Args:
            state: Current state

        Returns:
            Routing decision
        """
        query_text = state.get("query", {}).get("text", "").lower()

        # Determine if we need environmental data
        needs_environmental = any(
            keyword in query_text
            for keyword in ["air quality", "pollution", "los angeles", "la", "move", "city"]
        )

        if needs_environmental and state.get("user_context", {}).get("location_history"):
            # Start with environmental data
            logger.info("Routing to web_researcher first")
            return {"next_agent": "web_researcher"}
        else:
            # Start with INDRA
            logger.info("Routing to indra_query_agent first")
            return {"next_agent": "indra_query_agent"}

    async def _after_indra_agent(self, state: OverallState) -> Dict:
        """Handle state after INDRA agent execution.

        Args:
            state: Current state

        Returns:
            Routing decision
        """
        # Check if we have environmental data
        if not state.get("environmental_data") and state.get("user_context", {}).get(
            "location_history"
        ):
            # Need environmental data
            logger.info("INDRA agent done, routing to web_researcher")
            return {"next_agent": "web_researcher"}

        # We have everything, finalize
        logger.info("INDRA agent done, finalizing")
        return self._finalize_response(state)

    def _after_web_researcher(self, state: OverallState) -> Dict:
        """Handle state after web researcher execution.

        Args:
            state: Current state

        Returns:
            Routing decision
        """
        # Check if we have causal graph
        if not state.get("causal_graph"):
            # Need INDRA data
            logger.info("Web researcher done, routing to indra_query_agent")
            return {"next_agent": "indra_query_agent"}

        # We have everything, finalize
        logger.info("Web researcher done, finalizing")
        return self._finalize_response(state)

    def _finalize_response(self, state: OverallState) -> Dict:
        """Finalize the response with explanations.

        Args:
            state: Current state

        Returns:
            Final state update
        """
        logger.info("Finalizing response")

        # Get causal graph
        causal_graph_dict = state.get("causal_graph", {})
        causal_graph = CausalGraph(**causal_graph_dict)

        # Get environmental data
        environmental_data = state.get("environmental_data", {})

        # Get genetics
        genetics = state.get("user_context", {}).get("genetics", {})

        # Generate explanations
        explanations = self.graph_builder.generate_explanations(
            causal_graph=causal_graph,
            environmental_data=environmental_data,
            genetics=genetics,
        )

        # Calculate metadata
        query_time_ms = int((time.time() - self.start_time) * 1000)
        indra_paths = state.get("indra_paths", [])
        total_evidence = sum(
            sum(edge.get("evidence_count", 0) for edge in path.get("edges", []))
            for path in indra_paths
        )

        metadata = Metadata(
            query_time_ms=query_time_ms,
            indra_paths_explored=len(indra_paths),
            total_evidence_papers=total_evidence,
        )

        return {
            "explanations": explanations,
            "metadata": metadata.model_dump(),
            "next_agent": "END",
        }


# Factory function for agent
async def create_supervisor_agent() -> SupervisorAgent:
    """Create supervisor agent instance.

    Returns:
        SupervisorAgent instance
    """
    return SupervisorAgent()
