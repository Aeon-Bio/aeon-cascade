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
            return await self._initial_routing(state)

        # After MeSH enrichment agent
        if current_agent == "mesh_enrichment":
            # MeSH enrichment done, entities enriched
            # Routing is handled by workflow edge (mesh_enrichment -> indra_query_agent)
            logger.info("MeSH enrichment done, proceeding to INDRA query")
            return {}  # Empty dict, routing handled by workflow edge

        # After INDRA agent
        if current_agent == "indra_query_agent":
            return await self._after_indra_agent(state)

        # After web researcher
        if current_agent == "web_researcher":
            return await self._after_web_researcher(state)

        # Default: end
        return {"next_agent": "END"}

    async def _initial_routing(self, state: OverallState) -> Dict:
        """Initial routing logic - always start with MeSH enrichment if configured.

        Args:
            state: Current state

        Returns:
            Routing decision
        """
        # Check if Writer KG is configured for MeSH enrichment
        if self.settings.is_writer_configured:
            logger.info("Writer KG configured - routing to mesh_enrichment first")
            return {"next_agent": "mesh_enrichment"}

        # Fall back to legacy routing without MeSH enrichment
        query_text = state.get("query", {}).get("text", "")
        user_context = state.get("user_context", {})

        # Use LLM to determine routing
        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""Analyze this causal discovery query and determine which specialist agent to route to first.

Query: {query_text}
User Context: Has location history: {bool(user_context.get('location_history'))}
Has biomarkers: {list(user_context.get('current_biomarkers', {}).keys())}
Has genetics: {bool(user_context.get('genetics'))}

Decision Rules:
1. If query involves environmental conditions (air quality, pollution, location changes) AND user has location history -> route to 'web_researcher'
2. Otherwise -> route to 'indra_query_agent'

Respond with ONLY the agent name: 'web_researcher' or 'indra_query_agent'"""),
        ]

        response = await self.llm.ainvoke(messages)
        next_agent = response.content.strip().lower()

        # Validate response
        if "web_researcher" in next_agent and user_context.get("location_history"):
            logger.info("LLM routing to web_researcher first (no MeSH enrichment)")
            return {"next_agent": "web_researcher"}
        else:
            logger.info("LLM routing to indra_query_agent first (no MeSH enrichment)")
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
        return await self._finalize_response(state)

    async def _after_web_researcher(self, state: OverallState) -> Dict:
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
        return await self._finalize_response(state)

    async def _finalize_response(self, state: OverallState) -> Dict:
        """Finalize the response with explanations using LLM.

        Args:
            state: Current state

        Returns:
            Final state update
        """
        logger.info("Finalizing response with LLM-generated explanations")

        # Get causal graph with defensive handling
        causal_graph_dict = state.get("causal_graph", {})

        # Ensure required fields exist
        if not causal_graph_dict or "nodes" not in causal_graph_dict:
            causal_graph_dict = {"nodes": [], "edges": [], "genetic_modifiers": []}

        causal_graph = CausalGraph(**causal_graph_dict)

        # Get environmental data
        environmental_data = state.get("environmental_data", {})

        # Get genetics
        genetics = state.get("user_context", {}).get("genetics", {})

        # Get query
        query_text = state.get("query", {}).get("text", "")

        # Use LLM to generate explanations
        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""Generate 3-5 concise explanations (each <200 chars) for this causal discovery result.

Query: {query_text}

Causal Graph:
- Nodes: {len(causal_graph.nodes)} ({', '.join([n.name for n in causal_graph.nodes[:5]])})
- Edges: {len(causal_graph.edges)} causal relationships

Environmental Data: {environmental_data.get('summary', 'None')}
Genetic Context: {list(genetics.keys()) if genetics else 'None'}

Priority order:
1. Environmental exposure changes (if present)
2. Genetic modifiers (if present)
3. Strongest causal relationship (highest evidence)
4. Overall causal mechanism summary
5. Expected health outcome

Format as a JSON list of strings: ["explanation 1", "explanation 2", ...]
Each explanation must be <200 characters."""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            import json
            explanations = json.loads(response.content.strip())
            logger.info(f"LLM generated {len(explanations)} explanations")
        except Exception as e:
            logger.warning(f"LLM explanation generation failed: {e}, using fallback")
            # Fallback to service-based explanations
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
