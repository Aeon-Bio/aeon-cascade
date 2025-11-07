"""MeSH enrichment agent for semantic entity expansion using Writer KG.

This agent queries the Writer Knowledge Graph containing MeSH ontology
to enrich user queries with synonyms, hierarchical relationships, and
related biomedical terms before passing to INDRA query agent.
"""

import asyncio
import json
import logging
from typing import Annotated, Dict, List

from langchain_aws import ChatBedrock
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.settings import get_settings
from indra_agent.services.local_ontology_adapter import LocalOntologyAdapter

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


def create_mesh_tools(progress_emitter=None):
    """Create tools for MeSH enrichment agent.

    Args:
        progress_emitter: Optional ProgressEmitter for real-time updates

    Returns:
        List of LangChain tools for MeSH operations
    """
    # Initialize local ontology (shared across tool calls)
    settings = get_settings()
    local_ontology = LocalOntologyAdapter()

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
        # Initialize local ontology if not already done
        if not hasattr(local_ontology, '_initialized') or not local_ontology._initialized:
            await local_ontology.initialize()

        try:
            # Emit initial progress: Step 4 - MeSH enrichment (18%)
            if progress_emitter:
                async with progress_emitter.step(
                    agent="mesh_enrichment",
                    action=f"Enriching {len(terms[:10])} terms in parallel with MeSH ontology",
                    progress_percent=18,
                    phase="initialization",
                    metadata={"term_count": len(terms[:10])}
                ):
                    pass

            enriched_entities = []
            limited_terms = terms[:10]  # Limit to 10 terms

            # Create async tasks for all terms at once (parallel execution)
            async def enrich_single_term(term: str):
                """Enrich a single term and return (term, result) tuple."""
                logger.info(f"Enriching term: {term}")
                result = await local_ontology.find_mesh_term(term)
                return (term, result)

            tasks = [enrich_single_term(term) for term in limited_terms]

            # Process results as they complete (streaming progress)
            for i, completed_task in enumerate(asyncio.as_completed(tasks)):
                term, result = await completed_task

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

                # Emit micro-progress every 2 terms (every ~2-3 seconds since parallel)
                if (i + 1) % 2 == 0 and progress_emitter:
                    async with progress_emitter.step(
                        agent="mesh_enrichment",
                        action=f"Enriched {i+1}/{len(limited_terms)} terms with MeSH ontology",
                        progress_percent=18 + int((i + 1) * 10 / len(limited_terms)),  # 18% → 28%
                        phase="initialization",
                        metadata={
                            "completed": i + 1,
                            "total": len(limited_terms),
                            "latest_term": term,
                            "latest_mesh_id": enriched_entities[-1].get("mesh_id") if enriched_entities else None
                        }
                    ):
                        pass

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


async def _mesh_agent_node(state: OverallState, config: RunnableConfig) -> Dict:
    """MeSH agent node that extracts tool results to state.

    This wrapper runs the ReAct agent and then extracts mesh_enriched_entities
    from the agent's own ToolMessages, updating the shared state.

    Args:
        state: Current state
        config: Runnable configuration

    Returns:
        State updates with messages and mesh_enriched_entities
    """
    from langchain_core.messages import ToolMessage

    settings = get_settings()

    # Initialize LLM
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        model_kwargs={"temperature": MESH_ENRICHMENT_CONFIG["temperature"]},
    )

    # Get progress emitter from config (not state - causes pickle errors)
    progress_emitter = config.get("configurable", {}).get("progress_emitter")

    # Get MeSH tools with progress emitter
    mesh_tools = create_mesh_tools(progress_emitter=progress_emitter)

    # Get handoff tools from config if available
    handoff_tools = config.get("configurable", {}).get("handoff_tools", [])
    all_tools = mesh_tools + handoff_tools

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=MESH_ENRICHMENT_CONFIG["system_prompt"],
    )

    # Run the agent
    result = await agent.ainvoke(state, config)

    # Extract tool results from the agent's messages
    mesh_enriched_entities = []

    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, ToolMessage):
            # Skip handoff messages
            if "transfer" in msg.content.lower():
                continue

            try:
                parsed = json.loads(msg.content)

                if parsed.get("status") == "success" and "enriched_entities" in parsed and not mesh_enriched_entities:
                    mesh_enriched_entities = parsed["enriched_entities"]
                    logger.info(f"✅ Extracted {len(mesh_enriched_entities)} MeSH-enriched entities")

            except (json.JSONDecodeError, AttributeError, KeyError):
                continue

    # Build return dict with messages and extracted state
    updates = {"messages": result.get("messages", [])}
    if mesh_enriched_entities:
        updates["mesh_enriched_entities"] = mesh_enriched_entities

    return updates


async def create_mesh_enrichment_agent(handoff_tools=None):
    """Create MeSH enrichment agent with state extraction.

    Args:
        handoff_tools: Optional list of handoff tools for delegation

    Returns:
        RunnableLambda wrapping agent node that returns extracted state
    """
    # Store handoff tools in a closure
    async def mesh_agent_with_handoffs(state: OverallState, config: RunnableConfig) -> Dict:
        # Inject handoff tools into config
        if handoff_tools:
            config = config or {}
            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["handoff_tools"] = handoff_tools

        return await _mesh_agent_node(state, config)

    # Wrap in RunnableLambda for .ainvoke() compatibility with langgraph_supervisor
    runnable = RunnableLambda(mesh_agent_with_handoffs)
    # Set name attribute for langgraph_supervisor
    runnable.name = "mesh_enrichment"

    logger.info("MeSH enrichment agent created with state extraction")
    return runnable
