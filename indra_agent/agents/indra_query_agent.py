"""INDRA query agent for causal path discovery."""

import json
import logging
from typing import Annotated, Any, Dict, List

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import INDRA_QUERY_AGENT_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.graph_builder import GraphBuilderService
from indra_agent.services.grounding_service import GroundingService
from indra_agent.services.indra_service import INDRAService

logger = logging.getLogger(__name__)


def create_indra_tools():
    """Create tools for INDRA query agent.

    Returns:
        List of LangChain tools for INDRA operations
    """
    # Initialize services (shared across tool calls)
    grounding_service = GroundingService()
    indra_service = INDRAService()
    graph_builder = GraphBuilderService()

    @tool
    async def ground_biological_entities(
        entities: Annotated[List[str], "List of biological entity names to ground to database IDs"]
    ) -> str:
        """Ground biological entities to standardized database identifiers.

        This tool maps entity names (like 'PM2.5', 'IL-6', 'CRP') to database IDs
        (MESH, HGNC, GO, CHEBI) that can be used to query INDRA.

        Args:
            entities: List of biological entity names

        Returns:
            JSON string with grounded entities mapping
        """
        try:
            grounded = grounding_service.ground_entities(entities)
            return json.dumps({
                "status": "success",
                "grounded_entities": grounded,
                "count": len([e for e in grounded.values() if e])
            })
        except Exception as e:
            logger.error(f"Entity grounding failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def find_causal_paths(
        source_entity: Annotated[str, "Source entity ID (e.g., 'MESH:D052638' for PM2.5)"],
        target_entity: Annotated[str, "Target entity ID (e.g., 'HGNC:5992' for IL-6)"],
        max_depth: Annotated[int, "Maximum path depth to search"] = 4
    ) -> str:
        """Find causal paths between two biological entities using INDRA.

        This queries the INDRA database for mechanistic pathways connecting
        a source (like an environmental exposure) to a target (like a biomarker).

        Args:
            source_entity: Database ID of source entity
            target_entity: Database ID of target entity
            max_depth: Maximum number of steps in the pathway

        Returns:
            JSON string with discovered causal paths
        """
        try:
            paths = await indra_service.find_causal_paths(
                source=source_entity,
                target=target_entity,
                max_depth=max_depth
            )
            ranked = indra_service.rank_paths(paths)

            return json.dumps({
                "status": "success",
                "num_paths": len(ranked),
                "paths": ranked[:10],  # Return top 10
                "total_evidence": sum(
                    sum(e.get("evidence_count", 0) for e in p.get("edges", []))
                    for p in ranked
                )
            })
        except Exception as e:
            logger.error(f"Path finding failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def build_causal_graph(
        paths_json: Annotated[str, "JSON string of ranked paths from find_causal_paths"],
        genetics_json: Annotated[str, "JSON string of genetic context"] = "{}"
    ) -> str:
        """Build a structured causal graph from INDRA paths.

        This constructs a graph representation with nodes, edges, effect sizes,
        temporal lags, and genetic modifiers.

        Args:
            paths_json: JSON string containing paths from find_causal_paths
            genetics_json: JSON string with genetic variants

        Returns:
            JSON string with causal graph structure
        """
        try:
            paths = json.loads(paths_json).get("paths", [])
            genetics = json.loads(genetics_json)

            # Build top 3 paths
            causal_graph = graph_builder.build_causal_graph(
                paths=paths[:3],
                genetics=genetics
            )

            return json.dumps({
                "status": "success",
                "causal_graph": causal_graph.model_dump(),
                "num_nodes": len(causal_graph.nodes),
                "num_edges": len(causal_graph.edges)
            })
        except Exception as e:
            logger.error(f"Graph building failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    return [ground_biological_entities, find_causal_paths, build_causal_graph]


async def create_indra_query_agent(handoff_tools=None):
    """Create INDRA query agent using ReAct pattern.

    Args:
        handoff_tools: Optional list of handoff tools for delegation

    Returns:
        LangGraph ReAct agent configured for INDRA querying
    """
    settings = get_settings()
    config = INDRA_QUERY_AGENT_CONFIG

    # Initialize LLM
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        model_kwargs={"temperature": config.temperature},
    )

    # Get INDRA-specific tools
    indra_tools = create_indra_tools()

    # Combine with handoff tools if provided
    all_tools = indra_tools + (handoff_tools or [])

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=config.system_prompt,
        name="indra_query_agent",  # Required by langgraph_supervisor
    )

    logger.info("INDRA query ReAct agent created successfully")
    return agent
