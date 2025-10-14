"""Web researcher agent for environmental data collection."""

import logging
from typing import Dict

from langchain_aws import ChatBedrock
from langchain_core.runnables import RunnableConfig

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import WEB_RESEARCHER_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.web_data_service import WebDataService

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

    async def cleanup(self):
        """Cleanup resources."""
        await self.web_service.close()


# Factory function for agent
async def create_web_researcher_agent() -> WebResearcherAgent:
    """Create web researcher agent instance.

    Returns:
        WebResearcherAgent instance
    """
    return WebResearcherAgent()
