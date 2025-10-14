"""INDRA query agent for causal path discovery."""

import logging
from typing import Dict

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import INDRA_QUERY_AGENT_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.graph_builder import GraphBuilderService
from indra_agent.services.grounding_service import GroundingService
from indra_agent.services.indra_service import INDRAService

logger = logging.getLogger(__name__)


class INDRAQueryAgent:
    """Agent for querying INDRA and constructing causal graphs."""

    def __init__(self):
        """Initialize INDRA query agent."""
        self.settings = get_settings()
        self.config = INDRA_QUERY_AGENT_CONFIG

        # Initialize services
        self.grounding_service = GroundingService()
        self.indra_service = INDRAService()
        self.graph_builder = GraphBuilderService()

        # Initialize LLM (AWS Bedrock)
        self.llm = ChatBedrock(
            model_id=self.settings.agent_model,
            region_name=self.settings.aws_region,
            model_kwargs={"temperature": self.config.temperature},
        )

    async def __call__(
        self, state: OverallState, config: RunnableConfig
    ) -> Dict:
        """Execute INDRA query agent.

        Args:
            state: Current workflow state
            config: Runnable configuration

        Returns:
            Updated state dict
        """
        logger.info("INDRA query agent executing")

        try:
            # Extract entities from query
            entities = self._extract_entities(state)

            # Ground entities
            grounded = self.grounding_service.ground_entities(entities)

            # Identify sources (exposures) and targets (biomarkers)
            sources = self._identify_sources(grounded)
            targets = self._identify_targets(grounded, state)

            logger.info(f"Sources: {sources}, Targets: {targets}")

            # Query INDRA for paths
            all_paths = []
            for source in sources:
                for target in targets:
                    paths = await self.indra_service.find_causal_paths(
                        source=source,
                        target=target,
                        max_depth=state.get("options", {}).get("max_graph_depth", 4),
                    )
                    all_paths.extend(paths)

            # Rank paths
            ranked_paths = self.indra_service.rank_paths(all_paths)

            logger.info(f"Found {len(ranked_paths)} causal paths")

            # Build causal graph
            causal_graph = self.graph_builder.build_causal_graph(
                paths=ranked_paths[:3],  # Use top 3 paths
                genetics=state.get("user_context", {}).get("genetics", {}),
            )

            # Update state
            return {
                "entities": entities,
                "source_entities": sources,
                "target_entities": targets,
                "indra_paths": ranked_paths,
                "causal_graph": causal_graph.model_dump(),
                "current_agent": "indra_query_agent",
            }

        except Exception as e:
            logger.error(f"INDRA query agent error: {e}", exc_info=True)
            return {
                "current_agent": "indra_query_agent",
                "metadata": {"error": str(e)},
            }

    def _extract_entities(self, state: OverallState) -> list:
        """Extract entities from query text.

        Args:
            state: Current state

        Returns:
            List of entity names
        """
        query_text = state.get("query", {}).get("text", "")
        entities = self.grounding_service.extract_entities_from_query(query_text)

        # Add focus biomarkers
        focus_biomarkers = state.get("query", {}).get("focus_biomarkers", [])
        entities.extend(focus_biomarkers)

        # Deduplicate
        return list(set(entities))

    def _identify_sources(self, grounded: Dict) -> list:
        """Identify source entities (environmental exposures).

        Args:
            grounded: Grounded entities dict

        Returns:
            List of source entity IDs in INDRA format
        """
        sources = []
        for entity_name, entity_data in grounded.items():
            if entity_data and entity_data.get("type") == "environmental":
                indra_id = self.grounding_service.format_for_indra(entity_data)
                sources.append(entity_data["id"])  # Use simple ID for caching

        return sources if sources else ["PM2.5"]  # Default to PM2.5

    def _identify_targets(self, grounded: Dict, state: OverallState) -> list:
        """Identify target entities (biomarkers).

        Args:
            grounded: Grounded entities dict
            state: Current state

        Returns:
            List of target entity IDs in INDRA format
        """
        targets = []

        # First try focus biomarkers
        focus_biomarkers = state.get("query", {}).get("focus_biomarkers", [])
        for biomarker in focus_biomarkers:
            if biomarker in grounded and grounded[biomarker]:
                targets.append(grounded[biomarker]["id"])

        # Then try current biomarkers
        if not targets:
            current_biomarkers = (
                state.get("user_context", {}).get("current_biomarkers", {}).keys()
            )
            for biomarker in current_biomarkers:
                if biomarker in grounded and grounded[biomarker]:
                    targets.append(grounded[biomarker]["id"])

        # Try entities marked as biomarkers
        if not targets:
            for entity_name, entity_data in grounded.items():
                if entity_data and entity_data.get("type") == "biomarker":
                    targets.append(entity_data["id"])

        return targets if targets else ["IL6", "CRP"]  # Defaults

    async def cleanup(self):
        """Cleanup resources."""
        await self.indra_service.close()


# Factory function for agent
async def create_indra_query_agent() -> INDRAQueryAgent:
    """Create INDRA query agent instance.

    Returns:
        INDRAQueryAgent instance
    """
    return INDRAQueryAgent()
