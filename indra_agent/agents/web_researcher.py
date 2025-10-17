"""Web researcher agent for environmental data fetching.

This agent fetches real-time environmental data (air quality, pollution metrics)
based on user location history and calculates exposure changes.
"""

import json
import logging
from typing import Annotated, List, Dict

from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import WEB_RESEARCHER_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.web_data_service import WebDataService

logger = logging.getLogger(__name__)


def create_web_researcher_tools():
    """Create tools for web researcher agent.

    Returns:
        List of LangChain tools for web research operations
    """
    # Initialize web service (shared across tool calls)
    web_service = WebDataService()

    @tool
    async def fetch_pollution_data(
        locations: Annotated[List[Dict], "List of location dicts with city/state/country keys"]
    ) -> str:
        """Fetch real-time air quality and pollution data for locations.

        Args:
            locations: List of location dicts, e.g., [{"city": "San Francisco", "state": "CA", "country": "USA"}]

        Returns:
            JSON string with pollution data (PM2.5, ozone, AQI) for each location
        """
        try:
            all_data = []

            for loc in locations[:5]:  # Limit to 5 locations
                logger.info(f"Fetching pollution data for: {loc}")

                data = await web_service.get_air_quality(
                    city=loc.get("city"),
                    state=loc.get("state"),
                    country=loc.get("country")
                )

                if data:
                    all_data.append({
                        "location": loc,
                        "aqi": data.get("aqi"),
                        "pm25": data.get("pm25"),
                        "ozone": data.get("ozone"),
                        "timestamp": data.get("timestamp")
                    })

            return json.dumps({
                "status": "success",
                "pollution_data": all_data,
                "count": len(all_data)
            })

        except Exception as e:
            logger.error(f"Pollution data fetch failed: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "pollution_data": []
            })

    @tool
    async def calculate_exposure_changes(
        pollution_data_json: Annotated[str, "JSON string of pollution data from fetch_pollution_data"]
    ) -> str:
        """Calculate changes in pollution exposure across locations.

        Args:
            pollution_data_json: JSON string from fetch_pollution_data

        Returns:
            JSON string with exposure deltas (PM2.5 changes, AQI changes, etc.)
        """
        try:
            data = json.loads(pollution_data_json)
            pollution_data = data.get("pollution_data", [])

            if len(pollution_data) < 2:
                return json.dumps({
                    "status": "insufficient_data",
                    "message": "Need at least 2 locations to calculate changes",
                    "exposure_deltas": []
                })

            # Calculate deltas between consecutive locations
            deltas = []
            for i in range(len(pollution_data) - 1):
                prev = pollution_data[i]
                curr = pollution_data[i + 1]

                delta = {
                    "from_location": prev["location"],
                    "to_location": curr["location"],
                    "pm25_change": curr["pm25"] - prev["pm25"] if curr.get("pm25") and prev.get("pm25") else None,
                    "aqi_change": curr["aqi"] - prev["aqi"] if curr.get("aqi") and prev.get("aqi") else None,
                }
                deltas.append(delta)

            return json.dumps({
                "status": "success",
                "exposure_deltas": deltas,
                "count": len(deltas)
            })

        except Exception as e:
            logger.error(f"Exposure calculation failed: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "exposure_deltas": []
            })

    return [fetch_pollution_data, calculate_exposure_changes]


async def create_web_researcher_agent(handoff_tools=None):
    """Create web researcher agent using ReAct pattern.

    Args:
        handoff_tools: Optional handoff tools for delegation

    Returns:
        LangGraph ReAct agent configured for web research
    """
    settings = get_settings()

    # Initialize LLM
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        model_kwargs={"temperature": WEB_RESEARCHER_CONFIG.temperature},
    )

    # Get web researcher tools
    web_tools = create_web_researcher_tools()

    # Combine with handoff tools if provided
    all_tools = web_tools + (handoff_tools or [])

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=WEB_RESEARCHER_CONFIG.system_prompt,
        name="web_researcher",  # Required by langgraph_supervisor
    )

    logger.info("Web researcher ReAct agent created successfully")
    return agent
