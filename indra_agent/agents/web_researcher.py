"""Web researcher agent for environmental data collection."""

import logging
from typing import Dict

from langchain_aws import ChatBedrock
from langchain_core.runnables import RunnableConfig

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import WEB_RESEARCHER_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.web_data_service import WebDataService
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class WebResearcherAgent:
    """Agent for fetching environmental and pollution data."""

    def __init__(self):
        """Initialize web researcher agent."""
        self.settings = get_settings()
        self.config = WEB_RESEARCHER_CONFIG

        # Initialize service
        self.web_service = WebDataService()

        # Initialize LLM (AWS Bedrock - not heavily used, but available)
        self.llm = ChatBedrock(
            model_id=self.settings.agent_model,
            region_name=self.settings.aws_region,
            model_kwargs={"temperature": self.config.temperature},
        )

    async def __call__(
        self, state: OverallState, config: RunnableConfig
    ) -> Dict:
        """Execute web researcher agent.

        Args:
            state: Current workflow state
            config: Runnable configuration

        Returns:
            Updated state dict
        """
        logger.info("Web researcher agent executing")

        try:
            # Get location history from user context
            location_history = (
                state.get("user_context", {}).get("location_history", [])
            )

            if not location_history:
                logger.warning("No location history provided")
                return {
                    "environmental_data": {},
                    "current_agent": "web_researcher",
                }

            # Analyze location history
            environmental_data = self.web_service.analyze_location_history(
                location_history
            )

            logger.info(
                f"Environmental data collected for {len(environmental_data.get('exposures', []))} locations"
            )

            # Use LLM to generate environmental summary
            query_text = state.get("query", {}).get("text", "")
            environmental_summary = await self._generate_environmental_summary(
                query_text, location_history, environmental_data
            )

            # Add summary to environmental data
            environmental_data["summary"] = environmental_summary

            return {
                "environmental_data": environmental_data,
                "current_agent": "web_researcher",
            }

        except Exception as e:
            logger.error(f"Web researcher error: {e}", exc_info=True)
            return {
                "environmental_data": {},
                "current_agent": "web_researcher",
                "metadata": {"error": str(e)},
            }

    async def _generate_environmental_summary(
        self, query_text: str, location_history: list, environmental_data: dict
    ) -> str:
        """Generate environmental summary using LLM.

        Args:
            query_text: Original query
            location_history: User's location history
            environmental_data: Collected environmental data

        Returns:
            Environmental summary string
        """
        exposures = environmental_data.get("exposures", [])
        exposure_summary = "\n".join([
            f"- {exp.get('city', 'Unknown')}: PM2.5={exp.get('pm25', 'N/A')} µg/m³ "
            f"({exp.get('start_date', 'unknown')} to {exp.get('end_date', 'present')})"
            for exp in exposures
        ])

        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""Analyze this environmental exposure data and generate a concise summary (<150 chars).

Query: {query_text}

Location History:
{exposure_summary}

Environmental Deltas: {environmental_data.get('delta_summary', 'None')}

Focus on:
1. Significant changes in exposure levels
2. Health-relevant pollution thresholds
3. Duration of exposures
4. Comparative analysis between locations

Generate a concise summary in <150 characters."""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            summary = response.content.strip()
            logger.info(f"LLM generated environmental summary: {summary}")
            return summary
        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}, using fallback")
            # Fallback
            if exposures:
                latest = exposures[-1]
                return f"{latest.get('city', 'Current location')}: PM2.5 {latest.get('pm25', 'unknown')} µg/m³"
            return "Environmental data collected"

    async def cleanup(self):
        """Cleanup resources."""
        await self.web_service.close()


# Factory function for agent
async def create_web_researcher_agent(handoff_tools=None) -> WebResearcherAgent:
    """Create web researcher agent instance.

    Args:
        handoff_tools: Optional handoff tools for delegation (unused in legacy agent)

    Returns:
        WebResearcherAgent instance
    """
    # TODO: Convert to ReAct pattern with tools
    return WebResearcherAgent()
