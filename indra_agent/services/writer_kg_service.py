"""Writer Knowledge Graph service for MeSH ontology queries.

⚠️  DEPRECATED: This service is deprecated and will be removed in a future release.
Use LocalOntologyAdapter instead for MeSH resolution (local Memgraph ontology).

This service integrates with Writer's KG API to query the MeSH ontology
for semantic enrichment, synonym resolution, and hierarchical term expansion.

DEPRECATION RATIONALE:
- Writer KG trial ended (no budget)
- Local ontology provides equivalent functionality
- 30,924 MeSH entities available in Memgraph (local, <100ms queries)
- See LocalOntologyAdapter for drop-in replacement
"""

import logging
import warnings
from typing import Dict, List, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from indra_agent.config.settings import get_settings

logger = logging.getLogger(__name__)


class WriterKGService:
    """Service for querying Writer Knowledge Graph with MeSH ontology.

    ⚠️  DEPRECATED: Use LocalOntologyAdapter instead.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        graph_id: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None
    ):
        """Initialize Writer KG service.

        ⚠️  DEPRECATED: This service will be removed in a future release.
        Use LocalOntologyAdapter from indra_agent.services.local_ontology_adapter instead.

        Args:
            api_key: Writer API key (defaults to settings)
            graph_id: Writer Graph ID for MeSH ontology (defaults to settings)
            client: Optional shared HTTP client. If not provided, creates a new one.
        """
        warnings.warn(
            "WriterKGService is deprecated. Use LocalOntologyAdapter instead. "
            "Writer KG trial ended and local ontology provides equivalent functionality.",
            DeprecationWarning,
            stacklevel=2
        )

        settings = get_settings()
        self.api_key = api_key or settings.writer_api_key
        self.graph_id = graph_id or settings.writer_graph_id
        self.base_url = "https://api.writer.com/v1"

        # HTTP client for async requests
        self._owns_client = client is None  # Track if we own the client
        if client is not None:
            self.client = client
        else:
            self.client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        # Cache for MeSH lookups (in-memory for now)
        self._cache: Dict[str, Dict] = {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def _fetch_with_retry(self, url: str, **kwargs):
        """Fetch with automatic retry on transient errors.

        Args:
            url: URL to fetch
            **kwargs: Additional arguments for the request

        Returns:
            HTTP response

        Raises:
            httpx.HTTPError: On non-retryable errors or after max retries
        """
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response

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
            # Use retry wrapper for reliable network call
            response = await self._fetch_with_retry(
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
            Dict with mesh_id, mesh_label, definition, synonyms, or None if not found
        """
        question = f"What is the MeSH ID and definition for the biomedical term '{term_name}'? Include synonyms if available."

        result = await self.query_mesh_terms(question, max_snippets=10, grounding_level=0.9)

        if not result.get("sources"):
            logger.warning(f"No MeSH term found for: {term_name}")
            return None

        # Extract MeSH ID from LLM answer first (most reliable)
        answer = result.get("answer", "")
        mesh_id = self._extract_mesh_id_from_answer(answer)

        # Find matching entry in sources
        mesh_label = None
        definition = None

        if mesh_id:
            # Search all sources for the specific MeSH ID
            for source in result.get("sources", []):
                snippet = source.get("snippet", "")
                for line in snippet.split('\n'):
                    if mesh_id in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            mesh_label = parts[1].strip()
                        if len(parts) >= 3:
                            definition = parts[2].strip()
                        break
                if mesh_label:
                    break

        # Fallback to answer for definition
        if not definition:
            definition = answer

        # CRITICAL: If mesh_label is still None, extract from LLM answer
        # The LLM answer usually contains the label right after mentioning the MESH ID
        if not mesh_label and mesh_id and answer:
            # Look for patterns like "D052638 is Particulate Matter" or "The term is Particulate Matter"
            import re
            # Pattern 1: "D052638 is/refers to/means <label>"
            pattern1 = rf'{mesh_id}\s+(?:is|refers to|means|corresponds to)\s+([^,.]+)'
            match = re.search(pattern1, answer, re.IGNORECASE)
            if match:
                mesh_label = match.group(1).strip()
            else:
                # Pattern 2: "The term is <label>" or "It is <label>"
                pattern2 = r'(?:the term|it)\s+is\s+([A-Z][^,.]+)'
                match = re.search(pattern2, answer)
                if match:
                    mesh_label = match.group(1).strip()

            if mesh_label:
                logger.info(f"Extracted label from LLM answer: {mesh_label}")

        return {
            "term": term_name,
            "mesh_id": mesh_id,
            "mesh_label": mesh_label,
            "definition": definition,
            "synonyms": self._extract_synonyms(answer),
        }

    async def find_ontology_term(
        self,
        term_name: str,
        ontology: str = "auto",
        prefer_id_type: Optional[str] = None
    ) -> Optional[Dict]:
        """Find term across ALL ontologies with unified response.

        This is the NEW primary method that replaces find_mesh_term() for
        multi-ontology support. It queries Writer KG for MeSH, CHEBI, and GO
        identifiers simultaneously.

        Args:
            term_name: Term to search (e.g., "lead", "oxidative stress", "CRP")
            ontology: Which ontology to search:
                - "auto": Search all, return all matches (default)
                - "mesh": MeSH only
                - "chebi": CHEBI only
                - "go": GO only
            prefer_id_type: If multiple IDs found, prefer this type
                ("chebi", "mesh", "go"). Useful for ranking results.

        Returns:
            Dict with all found ontology IDs and INDRA query formats:
            {
                "term": "lead",
                "mesh_id": "D007854",
                "chebi_id": "CHEBI:25016",
                "go_id": None,
                "labels": {
                    "mesh": "Lead",
                    "chebi": "lead atom"
                },
                "definitions": {
                    "mesh": "A heavy metal...",
                    "chebi": "An element..."
                },
                "indra_query_formats": {
                    "mesh": "MESH:D007854",
                    "chebi": "CHEBI:25016@CHEBI"
                },
                "raw_ids": {
                    "mesh_ids": ["D007854"],
                    "chebi_ids": ["CHEBI:25016"],
                    "go_ids": [],
                    "hgnc_symbols": []
                }
            }

        Example:
            # Get all IDs for a chemical
            result = await service.find_ontology_term("lead")
            chebi_id = result["chebi_id"]  # Use for INDRA DB REST
            mesh_id = result["mesh_id"]    # Use for PathwayCommons (if needed)

            # Get only CHEBI ID
            result = await service.find_ontology_term("benzene", ontology="chebi")

            # Auto-detect with preference
            result = await service.find_ontology_term("oxidative stress", prefer_id_type="go")
        """
        # Build ontology-aware question
        if ontology == "auto":
            question = (
                f"What are the MeSH ID, CHEBI ID, and GO ID for '{term_name}'? "
                f"Include all available database identifiers and labels."
            )
        elif ontology == "chebi":
            question = (
                f"What is the CHEBI ID for the chemical '{term_name}'? "
                f"Include chemical formula and exact CHEBI identifier."
            )
        elif ontology == "mesh":
            question = (
                f"What is the MeSH ID for '{term_name}'? "
                f"Include the MeSH descriptor number."
            )
        elif ontology == "go":
            question = (
                f"What is the Gene Ontology (GO) ID for the biological process '{term_name}'? "
                f"Include the exact GO identifier."
            )
        else:
            raise ValueError(f"Unknown ontology: {ontology}")

        # Query Writer KG
        result = await self.query_mesh_terms(
            question,
            max_snippets=15,
            grounding_level=0.9
        )

        # Extract ALL IDs from answer + sources
        full_text = result.get("answer", "") + "\n" + "\n".join([
            s.get("snippet", "") for s in result.get("sources", [])
        ])

        ids = self._extract_all_ontology_ids(full_text)

        # Build response
        return {
            "term": term_name,
            "mesh_id": ids["mesh_ids"][0] if ids["mesh_ids"] else None,
            "chebi_id": ids["chebi_ids"][0] if ids["chebi_ids"] else None,
            "go_id": ids["go_ids"][0] if ids["go_ids"] else None,
            "labels": self._extract_labels_from_result(result, ids),
            "definitions": self._extract_definitions_from_result(result, ids),
            "indra_query_formats": self._build_indra_formats(ids),
            "raw_ids": ids,  # All found IDs for advanced usage
        }

    def _extract_labels_from_result(self, result: Dict, ids: Dict) -> Dict[str, str]:
        """Extract labels for each ontology from Writer KG result.

        Args:
            result: Writer KG query result
            ids: Extracted IDs dict from _extract_all_ontology_ids()

        Returns:
            Dict mapping ontology to label:
            {
                "mesh": "Particulate Matter",
                "chebi": "lead atom"
            }
        """
        labels = {}
        answer = result.get("answer", "")

        # Extract labels from answer text (LLM usually provides them)
        if ids["mesh_ids"]:
            # Look for patterns like "D052638 is Particulate Matter"
            import re
            for mesh_id in ids["mesh_ids"]:
                pattern = rf'{mesh_id}\s+(?:is|refers to|means)\s+([^,.]+)'
                match = re.search(pattern, answer, re.IGNORECASE)
                if match:
                    labels["mesh"] = match.group(1).strip()
                    break

        if ids["chebi_ids"]:
            # Look for "CHEBI:25016 (lead atom)" or "lead atom (CHEBI:25016)"
            for chebi_id in ids["chebi_ids"]:
                pattern = rf'{chebi_id}\s*\(([^)]+)\)|([^(]+)\s*\({chebi_id}\)'
                match = re.search(pattern, answer, re.IGNORECASE)
                if match:
                    labels["chebi"] = (match.group(1) or match.group(2)).strip()
                    break

        return labels

    def _extract_definitions_from_result(self, result: Dict, ids: Dict) -> Dict[str, str]:
        """Extract definitions for each ontology from Writer KG result.

        Args:
            result: Writer KG query result
            ids: Extracted IDs dict

        Returns:
            Dict mapping ontology to definition
        """
        definitions = {}
        answer = result.get("answer", "")

        # Use LLM answer as primary definition source
        if answer:
            # Split answer by ontology mentions
            if ids["mesh_ids"]:
                definitions["mesh"] = answer  # Simplified for now
            if ids["chebi_ids"]:
                definitions["chebi"] = answer
            if ids["go_ids"]:
                definitions["go"] = answer

        return definitions

    def _build_indra_formats(self, ids: Dict[str, List[str]]) -> Dict[str, str]:
        """Build INDRA-compatible query formats from ontology IDs.

        This converts raw IDs into the exact format INDRA DB REST expects.

        Args:
            ids: Dict from _extract_all_ontology_ids()

        Returns:
            Dict mapping ontology to INDRA query string:
            {
                "mesh": "MESH:D052638",
                "chebi": "CHEBI:25016@CHEBI",
                "go": "GO:0006979",
                "fplx": "FPLX:JNK"
            }

        Example:
            >>> ids = {"chebi_ids": ["CHEBI:25016"], "mesh_ids": ["D052638"], "fplx_ids": ["FPLX:JNK"]}
            >>> formats = service._build_indra_formats(ids)
            >>> formats["chebi"]
            "CHEBI:25016@CHEBI"  # Ready for INDRA DB REST query
            >>> formats["fplx"]
            "FPLX:JNK"  # Protein family queries
        """
        formats = {}

        if ids.get("mesh_ids"):
            formats["mesh"] = f"MESH:{ids['mesh_ids'][0]}"

        if ids.get("chebi_ids"):
            # CRITICAL: INDRA DB REST requires @CHEBI suffix
            formats["chebi"] = f"{ids['chebi_ids'][0]}@CHEBI"

        if ids.get("go_ids"):
            formats["go"] = ids["go_ids"][0]

        if ids.get("fplx_ids"):
            # FPLX protein family format for INDRA queries
            formats["fplx"] = ids["fplx_ids"][0]

        return formats

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

    def _extract_mesh_id_from_answer(self, answer: str) -> Optional[str]:
        """Extract MeSH ID from LLM answer text.

        Args:
            answer: LLM-generated answer text

        Returns:
            MeSH ID string (e.g., "D052638") or None
        """
        import re
        # Look for patterns like "D052638", "MeSH ID D052638", "ID: D052638"
        match = re.search(r'\b([DCA]\d{6})\b', answer)
        if match:
            return match.group(1)
        return None

    def _extract_chebi_id_from_answer(self, answer: str) -> Optional[str]:
        """Extract CHEBI ID from LLM answer text.

        Args:
            answer: LLM-generated answer text

        Returns:
            CHEBI ID string (e.g., "CHEBI:25016") or None

        Patterns supported:
            - CHEBI:25016
            - chebi:25016 (case insensitive)
            - CHEBI 25016 (with space)
        """
        import re
        match = re.search(r'\bCHEBI[:\s]?(\d+)\b', answer, re.IGNORECASE)
        return f"CHEBI:{match.group(1)}" if match else None

    def _extract_go_id_from_answer(self, answer: str) -> Optional[str]:
        """Extract GO (Gene Ontology) ID from LLM answer text.

        Args:
            answer: LLM-generated answer text

        Returns:
            GO ID string (e.g., "GO:0006979") or None

        Patterns supported:
            - GO:0006979
            - go:0006979 (case insensitive)
            - GO 0006979 (with space)
        """
        import re
        match = re.search(r'\bGO[:\s]?(\d{7})\b', answer, re.IGNORECASE)
        return f"GO:{match.group(1)}" if match else None

    def _extract_fplx_id_from_answer(self, answer: str) -> Optional[str]:
        """Extract FPLX (FamPlex protein family) ID from LLM answer text.

        Args:
            answer: LLM-generated answer text

        Returns:
            FPLX ID string (e.g., "FPLX:JNK") or None

        Patterns supported:
            - FPLX:JNK
            - fplx:ERK (case insensitive)
            - FPLX NFkappaB_1 (with space)
        """
        import re
        match = re.search(r'\bFPLX[:\s]?([A-Za-z0-9_]+)\b', answer, re.IGNORECASE)
        return f"FPLX:{match.group(1)}" if match else None

    def _extract_all_ontology_ids(self, text: str) -> Dict[str, List[str]]:
        """Extract ALL ontology IDs from text (answer + sources).

        This is the unified multi-ontology extractor that searches for
        MeSH, CHEBI, GO, FPLX, and HGNC identifiers in combined text.

        Args:
            text: Combined text from LLM answer and source snippets

        Returns:
            Dict with lists of found IDs by type:
            {
                "mesh_ids": ["D052638", "D001554"],
                "chebi_ids": ["CHEBI:25016", "CHEBI:16716"],
                "go_ids": ["GO:0006979", "GO:0045454"],
                "fplx_ids": ["FPLX:JNK", "FPLX:ERK"],
                "hgnc_symbols": ["NFKB1", "JUN", "FOS"]
            }

        Example:
            >>> text = "Lead (CHEBI:25016) activates NF-κB (FPLX:NFkappaB_1) and affects GO:0006979"
            >>> ids = service._extract_all_ontology_ids(text)
            >>> ids["chebi_ids"]
            ["CHEBI:25016"]
            >>> ids["fplx_ids"]
            ["FPLX:NFkappaB_1"]
            >>> ids["go_ids"]
            ["GO:0006979"]
        """
        import re
        return {
            "mesh_ids": re.findall(r'\b([DCA]\d{6})\b', text),
            "chebi_ids": [f"CHEBI:{m}" for m in re.findall(r'\bCHEBI[:\s]?(\d+)\b', text, re.IGNORECASE)],
            "go_ids": [f"GO:{m}" for m in re.findall(r'\bGO[:\s]?(\d{7})\b', text, re.IGNORECASE)],
            "fplx_ids": [f"FPLX:{m}" for m in re.findall(r'\bFPLX[:\s]?([A-Za-z0-9_]+)\b', text, re.IGNORECASE)],
            "hgnc_symbols": re.findall(r'\b([A-Z][A-Z0-9]{2,10})\b', text),  # Gene symbols
        }

    def _extract_mesh_id(self, source: Dict) -> Optional[str]:
        """Extract MeSH ID from source metadata or TSV snippet.

        Args:
            source: Source dict from Writer KG

        Returns:
            MeSH ID string (e.g., "D052638") or None
        """
        snippet = source.get("snippet", "")

        # Parse TSV format: mesh_id\tlabel\tdefinition\turi
        # Skip header lines
        lines = [line.strip() for line in snippet.split('\n') if line.strip()]

        for line in lines:
            # Skip CSV/TSV header
            if line.startswith("mesh_id"):
                continue

            # Parse tab-separated values
            parts = line.split('\t')
            if len(parts) >= 1:
                mesh_id = parts[0].strip()
                # Validate MeSH ID pattern: D######, C######, A######
                import re
                if re.match(r'^[DCA]\d{6}$', mesh_id):
                    return mesh_id

        # Fallback: try metadata field
        return source.get("metadata", {}).get("mesh_id")

    def _extract_label(self, source: Dict) -> Optional[str]:
        """Extract term label from source or TSV snippet.

        Args:
            source: Source dict from Writer KG

        Returns:
            Label string or None
        """
        # Try title first
        if source.get("title"):
            return source["title"]

        snippet = source.get("snippet", "")

        # Parse TSV format: mesh_id\tlabel\tdefinition\turi
        lines = [line.strip() for line in snippet.split('\n') if line.strip()]

        for line in lines:
            # Skip CSV/TSV header
            if line.startswith("mesh_id"):
                continue

            # Parse tab-separated values
            parts = line.split('\t')
            if len(parts) >= 2:
                mesh_id = parts[0].strip()
                label = parts[1].strip()

                # Validate this is a data row (not header or junk)
                import re
                if re.match(r'^[DCA]\d{6}$', mesh_id) and label:
                    return label

        # Fallback: return first line if no TSV structure found
        return lines[0] if lines else None

    def _extract_definition(self, source: Dict) -> Optional[str]:
        """Extract definition from source or TSV snippet.

        Args:
            source: Source dict from Writer KG

        Returns:
            Definition string or None
        """
        snippet = source.get("snippet", "")

        # Parse TSV format: mesh_id\tlabel\tdefinition\turi
        lines = [line.strip() for line in snippet.split('\n') if line.strip()]

        for line in lines:
            # Skip CSV/TSV header
            if line.startswith("mesh_id"):
                continue

            # Parse tab-separated values
            parts = line.split('\t')
            if len(parts) >= 3:
                mesh_id = parts[0].strip()
                definition = parts[2].strip()

                # Validate this is a data row (not header or junk)
                import re
                if re.match(r'^[DCA]\d{6}$', mesh_id) and definition:
                    return definition

        # No definition found in TSV
        return None

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
        """Clean up HTTP client resources if we own it."""
        if self._owns_client:
            await self.client.aclose()


# Factory function for agent usage
async def create_writer_kg_service() -> WriterKGService:
    """Create Writer KG service instance.

    Returns:
        WriterKGService instance
    """
    return WriterKGService()
