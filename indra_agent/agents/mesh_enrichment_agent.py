"""MeSH enrichment agent for semantic entity expansion using Writer KG.

This agent queries the Writer Knowledge Graph containing MeSH ontology
to enrich user queries with synonyms, hierarchical relationships, and
related biomedical terms before passing to INDRA query agent.
"""

import logging
from typing import Dict, List

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

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

Your role:
- Extract biomedical terms from user queries
- Query Writer Knowledge Graph (MeSH ontology) for semantic enrichment
- Find synonyms, broader/narrower terms, and related concepts
- Expand entity coverage for improved INDRA query results

Process:
1. Extract key biomedical terms from query (diseases, biomarkers, exposures, processes)
2. For each term, query MeSH ontology to find:
   - Official MeSH ID and label
   - Synonyms and alternative terms
   - Broader (parent) terms
   - Narrower (child) terms
   - Related concepts
3. Return enriched entity list with MeSH metadata

Guidelines:
- Prioritize official MeSH terms over colloquial names
- Include synonyms for better entity matching
- Expand environmental terms (e.g., "air pollution" → PM2.5, ozone, NO2)
- Expand clinical terms (e.g., "inflammation" → IL-6, TNF-α, CRP)
- Limit expansion to 3-5 related terms per query term to avoid noise

Output format:
- List of enriched entities with MeSH IDs, labels, and relationships
- Original query terms mapped to official MeSH nomenclature""",
    "temperature": 0.0,
}


class MeSHEnrichmentAgent:
    """Agent for enriching queries with MeSH ontology knowledge."""

    def __init__(self):
        """Initialize MeSH enrichment agent."""
        self.settings = get_settings()
        self.config = MESH_ENRICHMENT_CONFIG

        # Check if Writer KG is configured
        if not self.settings.is_writer_configured:
            logger.warning(
                "Writer KG not configured - MeSH enrichment will be skipped. "
                "Set WRITER_API_KEY and WRITER_GRAPH_ID in .env"
            )
            self.writer_service = None
        else:
            self.writer_service = WriterKGService()
            logger.info("Writer KG service initialized for MeSH enrichment")

        # Initialize LLM for entity extraction
        self.llm = ChatBedrock(
            model_id=self.settings.agent_model,
            region_name=self.settings.aws_region,
            model_kwargs={"temperature": self.config["temperature"]},
        )

    async def __call__(
        self, state: OverallState, config: RunnableConfig
    ) -> Dict:
        """Execute MeSH enrichment agent.

        Args:
            state: Current workflow state
            config: Runnable configuration

        Returns:
            Updated state dict with enriched entities
        """
        logger.info("MeSH enrichment agent executing")

        # If Writer KG not configured, pass through without enrichment
        if self.writer_service is None:
            logger.warning("Skipping MeSH enrichment - Writer KG not configured")
            return {
                "mesh_enriched_entities": [],
                "current_agent": "mesh_enrichment",
            }

        try:
            # Extract biomedical terms from query using LLM
            query_text = state.get("query", {}).get("text", "")
            biomedical_terms = await self._extract_biomedical_terms(query_text)

            logger.info(f"Extracted {len(biomedical_terms)} biomedical terms: {biomedical_terms}")

            # Enrich each term with MeSH knowledge
            enriched_entities = []
            for term in biomedical_terms:
                enriched = await self._enrich_term_with_mesh(term)
                if enriched:
                    enriched_entities.append(enriched)

            logger.info(f"Enriched to {len(enriched_entities)} MeSH-grounded entities")

            return {
                "mesh_enriched_entities": enriched_entities,
                "current_agent": "mesh_enrichment",
            }

        except Exception as e:
            logger.error(f"Error in MeSH enrichment: {e}", exc_info=True)
            # Return empty enrichment on error, don't fail the workflow
            return {
                "mesh_enriched_entities": [],
                "current_agent": "mesh_enrichment",
            }

    async def _extract_biomedical_terms(self, query_text: str) -> List[str]:
        """Extract biomedical terms from query using LLM.

        Args:
            query_text: User's natural language query

        Returns:
            List of biomedical term strings
        """
        messages = [
            SystemMessage(content=self.config["system_prompt"]),
            HumanMessage(content=f"""Extract key biomedical terms from this query that should be looked up in MeSH ontology.

Query: {query_text}

Focus on:
- Diseases (diabetes, cardiovascular disease)
- Biomarkers (CRP, IL-6, glucose)
- Environmental exposures (PM2.5, air pollution, ozone)
- Biological processes (inflammation, oxidative stress)
- Molecular entities (proteins, genes, chemicals)

Return ONLY a comma-separated list of terms, nothing else.
Example: "particulate matter, C-reactive protein, inflammation"
"""),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            terms_text = response.content.strip()

            # Parse comma-separated terms
            terms = [t.strip() for t in terms_text.split(",") if t.strip()]

            return terms[:10]  # Limit to 10 terms to avoid over-expansion

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            # Fallback to simple keyword extraction
            return self._fallback_extract_terms(query_text)

    def _fallback_extract_terms(self, query_text: str) -> List[str]:
        """Fallback term extraction using simple keyword matching.

        Args:
            query_text: Query text

        Returns:
            List of recognized biomedical terms
        """
        # Common biomedical keywords
        keywords = [
            "PM2.5", "PM10", "particulate matter", "air pollution", "ozone",
            "CRP", "C-reactive protein", "IL-6", "interleukin",
            "inflammation", "oxidative stress",
            "diabetes", "cardiovascular", "obesity",
            "NF-κB", "TNF", "biomarker",
        ]

        query_lower = query_text.lower()
        found_terms = []

        for keyword in keywords:
            if keyword.lower() in query_lower:
                found_terms.append(keyword)

        return found_terms[:5]  # Limit to 5

    async def _enrich_term_with_mesh(self, term: str) -> Dict:
        """Enrich a single term with MeSH ontology knowledge.

        Args:
            term: Biomedical term to enrich

        Returns:
            Dict with enriched MeSH metadata or None if not found
        """
        try:
            # Find MeSH term
            mesh_term = await self.writer_service.find_mesh_term(term)

            if not mesh_term:
                logger.info(f"No MeSH term found for: {term}")
                return None

            # Find related terms for expansion
            related = await self.writer_service.find_related_terms(term)

            enriched = {
                "original_term": term,
                "mesh_id": mesh_term.get("mesh_id"),
                "mesh_label": mesh_term.get("label"),
                "definition": mesh_term.get("definition", ""),
                "synonyms": mesh_term.get("synonyms", []),
                "related_terms": [
                    {
                        "mesh_id": r["mesh_id"],
                        "label": r["label"],
                        "relationship": r["relationship"],
                    }
                    for r in related[:3]  # Limit to top 3 related
                ],
            }

            logger.info(f"Enriched '{term}' → MeSH:{mesh_term.get('mesh_id')} ({mesh_term.get('label')})")

            return enriched

        except Exception as e:
            logger.error(f"Error enriching term '{term}': {e}")
            return None

    async def cleanup(self):
        """Clean up resources."""
        if self.writer_service:
            await self.writer_service.cleanup()


# Factory function for agent
async def create_mesh_enrichment_agent(handoff_tools=None) -> MeSHEnrichmentAgent:
    """Create MeSH enrichment agent instance.

    Args:
        handoff_tools: Optional handoff tools for delegation (unused in legacy agent)

    Returns:
        MeSHEnrichmentAgent instance
    """
    # TODO: Convert to ReAct pattern with tools
    return MeSHEnrichmentAgent()
