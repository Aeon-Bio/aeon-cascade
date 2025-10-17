"""Writer Knowledge Graph service for MeSH ontology queries.

This service integrates with Writer's KG API to query the MeSH ontology
for semantic enrichment, synonym resolution, and hierarchical term expansion.
"""

import logging
from typing import Dict, List, Optional

import httpx

from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class WriterKGService:
    """Service for querying Writer Knowledge Graph with MeSH ontology."""

    def __init__(self, api_key: Optional[str] = None, graph_id: Optional[str] = None):
        """Initialize Writer KG service.

        Args:
            api_key: Writer API key (defaults to settings)
            graph_id: Writer Graph ID for MeSH ontology (defaults to settings)
        """
        settings = get_settings()
        self.api_key = api_key or settings.writer_api_key
        self.graph_id = graph_id or settings.writer_graph_id
        self.base_url = "https://api.writer.com/v1"

        # HTTP client for async requests
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        # Cache for MeSH lookups (in-memory for now)
        self._cache: Dict[str, Dict] = {}

    async def query_mesh_terms(
        self,
        question: str,
        max_snippets: int = 10,
        grounding_level: float = 0.8,
    ) -> Dict:
        """Query Writer KG for MeSH terms.

        Args:
            question: Natural language question about MeSH terms
            max_snippets: Maximum number of result snippets
            grounding_level: Grounding precision (0.0-1.0, higher = more precise)

        Returns:
            Dict with answer and sources from Writer KG
        """
        # Check cache
        cache_key = f"{question}:{max_snippets}:{grounding_level}"
        if cache_key in self._cache:
            logger.info(f"Cache hit for MeSH query: {question[:50]}...")
            return self._cache[cache_key]

        logger.info(f"Querying Writer KG: {question}")

        try:
            response = await self.client.post(
                f"{self.base_url}/graphs/question",
                json={
                    "graph_ids": [self.graph_id],
                    "question": question,
                    "query_config": {
                        "max_snippets": max_snippets,
                        "grounding_level": grounding_level,
                        "max_tokens": 2000,
                    },
                },
            )
            response.raise_for_status()

            result = response.json()

            # Cache result
            self._cache[cache_key] = result

            logger.info(f"Writer KG returned answer with {len(result.get('sources', []))} sources")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"Writer KG API error: {e.response.status_code} - {e.response.text}")
            return {"answer": "", "sources": []}
        except Exception as e:
            logger.error(f"Error querying Writer KG: {e}")
            return {"answer": "", "sources": []}

    async def find_mesh_term(self, term_name: str) -> Optional[Dict]:
        """Find a specific MeSH term by name.

        Args:
            term_name: Term name to search for (e.g., "particulate matter", "CRP")

        Returns:
            Dict with mesh_id, label, definition, synonyms, or None if not found
        """
        question = f"What is the MeSH ID and definition for the biomedical term '{term_name}'? Include synonyms if available."

        result = await self.query_mesh_terms(question, max_snippets=5, grounding_level=0.9)

        if not result.get("sources"):
            logger.warning(f"No MeSH term found for: {term_name}")
            return None

        # Parse first source
        source = result["sources"][0]

        return {
            "term": term_name,
            "mesh_id": self._extract_mesh_id(source),
            "label": self._extract_label(source),
            "definition": source.get("snippet", ""),
            "synonyms": self._extract_synonyms(result["answer"]),
        }

    async def expand_with_hierarchy(self, mesh_id: str) -> Dict:
        """Get broader and narrower MeSH terms for hierarchical expansion.

        Args:
            mesh_id: MeSH ID (e.g., "D052638")

        Returns:
            Dict with broader_terms and narrower_terms lists
        """
        question = f"What are the broader parent terms and narrower child terms for MeSH ID {mesh_id} in the MeSH hierarchy?"

        result = await self.query_mesh_terms(question, max_snippets=15)

        return {
            "mesh_id": mesh_id,
            "broader_terms": self._extract_related_terms(result["answer"], "broader"),
            "narrower_terms": self._extract_related_terms(result["answer"], "narrower"),
        }

    async def find_related_terms(self, term_name: str) -> List[Dict]:
        """Find semantically related MeSH terms.

        Args:
            term_name: Term to find relations for

        Returns:
            List of related term dicts with mesh_id and relationship type
        """
        question = f"What MeSH terms are semantically related to '{term_name}'? Include synonyms, broader terms, and narrower terms."

        result = await self.query_mesh_terms(question, max_snippets=20)

        related = []

        # Parse sources for related terms
        for source in result.get("sources", []):
            mesh_id = self._extract_mesh_id(source)
            label = self._extract_label(source)

            if mesh_id and label:
                related.append({
                    "mesh_id": mesh_id,
                    "label": label,
                    "relationship": self._infer_relationship(term_name, label),
                })

        logger.info(f"Found {len(related)} related terms for: {term_name}")
        return related

    def _extract_mesh_id(self, source: Dict) -> Optional[str]:
        """Extract MeSH ID from source metadata.

        Args:
            source: Source dict from Writer KG

        Returns:
            MeSH ID string (e.g., "D052638") or None
        """
        # Try to extract from metadata or snippet
        snippet = source.get("snippet", "")

        # Look for MeSH ID patterns: D######, C######, etc.
        import re
        match = re.search(r'\b([DCA]\d{6})\b', snippet)
        if match:
            return match.group(1)

        # Try metadata field
        return source.get("metadata", {}).get("mesh_id")

    def _extract_label(self, source: Dict) -> Optional[str]:
        """Extract term label from source.

        Args:
            source: Source dict from Writer KG

        Returns:
            Label string or None
        """
        # Try title first
        if source.get("title"):
            return source["title"]

        # Extract from snippet - look for pattern "Label (ID)" or just "Label"
        snippet = source.get("snippet", "")

        import re
        # Pattern: "Label (MeSH:ID)" or "Label (ID)"
        match = re.match(r'^([^(]+)\s*\([A-Z]?\d+\)', snippet)
        if match:
            return match.group(1).strip()

        # Fallback: first sentence
        return snippet.split(".")[0]

    def _extract_synonyms(self, answer_text: str) -> List[str]:
        """Extract synonyms from answer text.

        Args:
            answer_text: Answer text from Writer KG

        Returns:
            List of synonym strings
        """
        # Simple extraction - look for "synonym", "also known as", etc.
        synonyms = []

        import re
        # Pattern: "synonyms: A, B, C" or "also known as X"
        synonym_patterns = [
            r'synonyms?:\s*([^.]+)',
            r'also known as\s+([^,.]+)',
            r'alternative terms?:\s*([^.]+)',
        ]

        for pattern in synonym_patterns:
            matches = re.findall(pattern, answer_text, re.IGNORECASE)
            for match in matches:
                # Split on commas/ands
                terms = re.split(r',|\sand\s', match)
                synonyms.extend([t.strip() for t in terms if t.strip()])

        return list(set(synonyms))[:5]  # Dedupe and limit

    def _extract_related_terms(self, answer_text: str, relationship: str) -> List[str]:
        """Extract related terms by relationship type.

        Args:
            answer_text: Answer text from Writer KG
            relationship: "broader" or "narrower"

        Returns:
            List of related term names
        """
        terms = []

        import re
        pattern = rf'{relationship}\s+terms?:\s*([^.]+)'
        matches = re.findall(pattern, answer_text, re.IGNORECASE)

        for match in matches:
            # Split on commas/ands
            term_list = re.split(r',|\sand\s', match)
            terms.extend([t.strip() for t in term_list if t.strip()])

        return list(set(terms))[:5]  # Dedupe and limit

    def _infer_relationship(self, source_term: str, target_term: str) -> str:
        """Infer relationship type between terms.

        Args:
            source_term: Source term name
            target_term: Target term name

        Returns:
            Relationship type: "synonym", "broader", "narrower", or "related"
        """
        source_lower = source_term.lower()
        target_lower = target_term.lower()

        # Check for synonym indicators
        if source_lower in target_lower or target_lower in source_lower:
            return "synonym"

        # Default to generic "related"
        return "related"

    async def cleanup(self):
        """Clean up HTTP client resources."""
        await self.client.aclose()


# Factory function for agent usage
async def create_writer_kg_service() -> WriterKGService:
    """Create Writer KG service instance.

    Returns:
        WriterKGService instance
    """
    return WriterKGService()
