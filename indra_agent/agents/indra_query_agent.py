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
            # Extract entities from query using LLM
            entities = await self._extract_entities(state)

            # Ground entities
            grounded = self.grounding_service.ground_entities(entities)

            # Identify sources (exposures) and targets (biomarkers) using LLM
            query_text = state.get("query", {}).get("text", "")
            sources = await self._identify_sources(grounded, query_text)
            targets = await self._identify_targets(grounded, state)

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
            # Return empty but valid causal graph to prevent downstream validation errors
            return {
                "current_agent": "indra_query_agent",
                "causal_graph": {"nodes": [], "edges": [], "genetic_modifiers": []},
                "metadata": {"error": str(e)},
            }

    async def _extract_entities(self, state: OverallState) -> list:
        """Extract entities from query text using LLM.

        Args:
            state: Current state

        Returns:
            List of entity names
        """
        query_text = state.get("query", {}).get("text", "")
        focus_biomarkers = state.get("query", {}).get("focus_biomarkers", [])

        # Use LLM to extract entities
        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""Extract biological entities from this query for causal path discovery.

Query: {query_text}
Focus Biomarkers: {focus_biomarkers}

Identify:
1. Environmental exposures (PM2.5, ozone, air pollution, chemicals)
2. Biomarkers (CRP, IL-6, 8-OHdG, proteins, metabolites)
3. Molecular mechanisms (oxidative stress, inflammation, NF-κB)
4. Clinical outcomes (cardiovascular disease, cancer, etc.)

Return ONLY a JSON list of entity names: ["entity1", "entity2", ...]"""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            import json
            entities = json.loads(response.content.strip())
            logger.info(f"LLM extracted {len(entities)} entities: {entities}")

            # Add focus biomarkers
            entities.extend(focus_biomarkers)

            # Deduplicate
            return list(set(entities))
        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}, using fallback")
            # Fallback to service-based extraction
            entities = self.grounding_service.extract_entities_from_query(query_text)
            entities.extend(focus_biomarkers)
            return list(set(entities))

    async def _identify_sources(self, grounded: Dict, query_text: str) -> list:
        """Identify source entities (environmental exposures) using LLM.

        Args:
            grounded: Grounded entities dict
            query_text: Original query text

        Returns:
            List of source entity IDs in INDRA format
        """
        # Use LLM to identify sources
        entity_list = "\n".join([f"- {name}: {data}" for name, data in grounded.items() if data])

        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""From these grounded entities, identify which are SOURCES (environmental exposures or upstream causes).

Query: {query_text}

Grounded Entities:
{entity_list}

Sources are typically:
- Environmental exposures (PM2.5, ozone, pollution)
- Chemicals or toxins
- Lifestyle factors
- Upstream causes

Return ONLY a JSON list of entity IDs: ["entity_id1", "entity_id2", ...]
If none found, return ["PM2.5"] as default."""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            import json
            sources = json.loads(response.content.strip())
            logger.info(f"LLM identified sources: {sources}")
            return sources if sources else ["PM2.5"]
        except Exception as e:
            logger.warning(f"LLM source identification failed: {e}, using fallback")
            # Fallback
            sources = []
            for entity_name, entity_data in grounded.items():
                if entity_data and entity_data.get("type") == "environmental":
                    sources.append(entity_data["id"])
            return sources if sources else ["PM2.5"]

    async def _identify_targets(self, grounded: Dict, state: OverallState) -> list:
        """Identify target entities (biomarkers) using LLM.

        Args:
            grounded: Grounded entities dict
            state: Current state

        Returns:
            List of target entity IDs in INDRA format
        """
        query_text = state.get("query", {}).get("text", "")
        focus_biomarkers = state.get("query", {}).get("focus_biomarkers", [])
        entity_list = "\n".join([f"- {name}: {data}" for name, data in grounded.items() if data])

        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=f"""From these grounded entities, identify which are TARGETS (biomarkers or health outcomes).

Query: {query_text}
Focus Biomarkers: {focus_biomarkers}

Grounded Entities:
{entity_list}

Targets are typically:
- Clinical biomarkers (CRP, IL-6, 8-OHdG)
- Health outcomes or diseases
- Downstream effects
- Measurable health indicators

Return ONLY a JSON list of entity IDs: ["entity_id1", "entity_id2", ...]
If none found, return ["IL6", "CRP"] as default."""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            import json
            targets = json.loads(response.content.strip())
            logger.info(f"LLM identified targets: {targets}")
            return targets if targets else ["IL6", "CRP"]
        except Exception as e:
            logger.warning(f"LLM target identification failed: {e}, using fallback")
            # Fallback
            targets = []
            for biomarker in focus_biomarkers:
                if biomarker in grounded and grounded[biomarker]:
                    targets.append(grounded[biomarker]["id"])

            if not targets:
                current_biomarkers = state.get("user_context", {}).get("current_biomarkers", {}).keys()
                for biomarker in current_biomarkers:
                    if biomarker in grounded and grounded[biomarker]:
                        targets.append(grounded[biomarker]["id"])

            if not targets:
                for entity_name, entity_data in grounded.items():
                    if entity_data and entity_data.get("type") == "biomarker":
                        targets.append(entity_data["id"])

            return targets if targets else ["IL6", "CRP"]

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
