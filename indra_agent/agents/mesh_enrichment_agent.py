"""MeSH enrichment agent for semantic entity expansion using Writer KG.

This agent queries the Writer Knowledge Graph containing MeSH ontology
to enrich user queries with synonyms, hierarchical relationships, and
related biomedical terms before passing to INDRA query agent.
"""

import json
import logging
from typing import Annotated, List

from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.settings import get_settings
from indra_agent.services.writer_kg_service import WriterKGService

logger = logging.getLogger(__name__)


# Agent configuration
MESH_ENRICHMENT_CONFIG = {
    "name": "mesh_enrichment",
    "display_name": "MeSH Semantic Enrichment Specialist",
    "description": "Specialist in expanding biomedical queries using MeSH ontology",
    "system_prompt": """You are a biomedical ontology specialist that enriches user queries with MeSH semantic knowledge.

Your role is to use the enrich_biomedical_terms tool to expand user queries with MeSH ontology knowledge.

When given a biomedical query:
1. Identify key biomedical terms (diseases, biomarkers, exposures, processes)
2. Call enrich_biomedical_terms with those terms
3. Return the enriched entities for use by downstream agents

The enriched entities will include:
- Official MeSH IDs and labels
- Synonyms and alternative terms
- Related concepts and hierarchical relationships

Always pass the enriched results through - do not summarize or filter them.""",
    "temperature": 0.0,
}


def create_mesh_tools():
    """Create tools for MeSH enrichment agent.

    Returns:
        List of LangChain tools for MeSH operations
    """
    # Initialize Writer KG service (shared across tool calls)
    settings = get_settings()
    writer_service = WriterKGService() if settings.is_writer_configured else None

    @tool
    async def enrich_biomedical_terms(
        terms: Annotated[List[str], "List of biomedical terms to enrich with MeSH ontology"]
    ) -> str:
        """Enrich biomedical terms with MeSH ontology knowledge from Writer KG.

        This tool queries the Writer Knowledge Graph to find:
        - Official MeSH IDs and labels
        - Synonyms and alternative names
        - Related concepts and hierarchical relationships (broader/narrower)

        Args:
            terms: List of biomedical term strings (e.g., ["PM2.5", "CRP", "inflammation"])

        Returns:
            JSON string with enriched entities containing MeSH metadata
        """
        if writer_service is None:
            logger.warning("Writer KG not configured - skipping MeSH enrichment")
            return json.dumps({
                "status": "skipped",
                "message": "Writer KG not configured",
                "enriched_entities": []
            })

        try:
            enriched_entities = []

            for term in terms[:10]:  # Limit to 10 terms
                logger.info(f"Enriching term: {term}")

                # Query Writer KG for MeSH information
                result = await writer_service.find_mesh_term(term)

                if result:
                    enriched = {
                        "original_term": term,
                        "mesh_id": result.get("mesh_id"),
                        "mesh_label": result.get("mesh_label"),
                        "definition": result.get("definition", ""),
                        "synonyms": result.get("synonyms", []),
                        "related_terms": result.get("related_terms", [])
                    }
                    enriched_entities.append(enriched)
                    logger.info(f"Enriched '{term}' -> {enriched['mesh_id']}")
                else:
                    logger.warning(f"No MeSH entry found for: {term}")

            return json.dumps({
                "status": "success",
                "enriched_entities": enriched_entities,
                "count": len(enriched_entities)
            })

        except Exception as e:
            logger.error(f"MeSH enrichment failed: {e}")
            return json.dumps({
                "status": "error",
                "error": str(e),
                "enriched_entities": []
            })

    return [enrich_biomedical_terms]


async def create_mesh_enrichment_agent(handoff_tools=None):
    """Create MeSH enrichment agent using ReAct pattern.

    Args:
        handoff_tools: Optional handoff tools for delegation

    Returns:
        LangGraph ReAct agent configured for MeSH enrichment
    """
    settings = get_settings()

    # Initialize LLM
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        model_kwargs={"temperature": MESH_ENRICHMENT_CONFIG["temperature"]},
    )

    # Get MeSH-specific tools
    mesh_tools = create_mesh_tools()

    # Combine with handoff tools if provided
    all_tools = mesh_tools + (handoff_tools or [])

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=MESH_ENRICHMENT_CONFIG["system_prompt"],
        name="mesh_enrichment",  # Required by langgraph_supervisor
    )

    logger.info("MeSH enrichment ReAct agent created successfully")
    return agent
