"""LightRAG Client Wrapper.

Provides async interface to LightRAG for semantic search and entity grounding.
Uses PubMedBERT embeddings for biomedical domain understanding.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

try:
    from lightrag import LightRAG, QueryParam
    LIGHTRAG_AVAILABLE = True
except ImportError:
    LIGHTRAG_AVAILABLE = False
    LightRAG = None
    QueryParam = None

logger = logging.getLogger(__name__)


class LightRAGClient:
    """Async client for LightRAG semantic search.

    Uses PubMedBERT for biomedical embeddings and supports hybrid search modes.
    """

    def __init__(
        self,
        working_dir: str = "./lightrag_cache",
        embedding_model: str = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract",
        embedding_dim: int = 768,
        max_tokens: int = 4096,
        max_embed_tokens: int = 8192
    ):
        """Initialize LightRAG client.

        Args:
            working_dir: Directory for LightRAG cache and index
            embedding_model: HuggingFace model ID for embeddings
            embedding_dim: Embedding dimensionality
            max_tokens: Max tokens for LLM completion
            max_embed_tokens: Max tokens for embeddings
        """
        if not LIGHTRAG_AVAILABLE:
            raise ImportError("LightRAG not installed. Run: pip install lightrag-hku")

        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.max_tokens = max_tokens
        self.max_embed_tokens = max_embed_tokens

        self.rag = None

    async def initialize(self):
        """Initialize LightRAG instance."""
        if self.rag:
            return

        logger.warning("LightRAG initialization not yet fully implemented for latest API version")
        logger.warning("Semantic search features will be unavailable")
        logger.warning("Memgraph-only mode will be used")

        # TODO: Update to latest LightRAG API
        # For now, we skip LightRAG initialization and rely on Memgraph only
        # self.rag = LightRAG(working_dir=str(self.working_dir), ...)

        logger.info("LightRAG client initialized (semantic features disabled)")

    def _create_embedding_func(self):
        """Create embedding function using PubMedBERT.

        Returns:
            Async function for computing embeddings
        """
        async def pubmedbert_embedding(texts: List[str]) -> List[List[float]]:
            """Compute PubMedBERT embeddings for texts."""
            # Use HuggingFace transformers to compute embeddings
            try:
                from transformers import AutoTokenizer, AutoModel
                import torch

                # Load model and tokenizer (cached after first load)
                tokenizer = AutoTokenizer.from_pretrained(self.embedding_model)
                model = AutoModel.from_pretrained(self.embedding_model)
                model.eval()

                # Tokenize and compute embeddings
                inputs = tokenizer(
                    texts,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt"
                )

                with torch.no_grad():
                    outputs = model(**inputs)
                    # Use [CLS] token embedding (first token)
                    embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()

                return embeddings.tolist()

            except ImportError:
                logger.warning("transformers not installed, falling back to OpenAI embeddings")
                # Fallback to OpenAI embeddings
                return await openai_embedding(texts)

        return pubmedbert_embedding

    async def insert(self, documents: List[Dict[str, str]]):
        """Insert documents into LightRAG index.

        Args:
            documents: List of dicts with keys: id, text, metadata
        """
        if not self.rag:
            await self.initialize()

        if not self.rag:
            logger.warning(f"Skipping insertion of {len(documents)} documents (LightRAG not available)")
            return

        # Convert documents to LightRAG format
        texts = []
        for doc in documents:
            # Combine entity metadata into searchable text
            text = f"ID: {doc['id']}\n"
            text += f"Name: {doc.get('name', '')}\n"
            if doc.get('definition'):
                text += f"Definition: {doc['definition']}\n"
            if doc.get('synonyms'):
                text += f"Synonyms: {', '.join(doc['synonyms'])}\n"
            texts.append(text)

        # Batch insert
        await self.rag.ainsert(texts)
        logger.info(f"Inserted {len(documents)} documents into LightRAG")

    async def search(
        self,
        query: str,
        mode: str = "hybrid",
        top_k: int = 10,
        only_need_context: bool = True
    ) -> List[Dict]:
        """Semantic search for entities.

        Args:
            query: Search query text
            mode: Search mode ("naive", "local", "global", "hybrid")
            top_k: Maximum results
            only_need_context: If True, return only context chunks

        Returns:
            List of search results with scores
        """
        if not self.rag:
            await self.initialize()

        # Execute query
        result = await self.rag.aquery(
            query,
            param=QueryParam(
                mode=mode,
                top_k=top_k,
                only_need_context=only_need_context
            )
        )

        # Parse results
        if only_need_context:
            # Extract entity IDs and metadata from context chunks
            entities = self._parse_context_chunks(result, top_k)
        else:
            # Full LLM-generated response
            entities = [{"text": result, "score": 1.0}]

        return entities

    def _parse_context_chunks(self, context: str, limit: int) -> List[Dict]:
        """Parse context chunks into entity results.

        Args:
            context: Context string from LightRAG
            limit: Maximum entities to return

        Returns:
            List of entity dicts with id, name, score
        """
        entities = []
        chunks = context.split("\n\n")

        for chunk in chunks[:limit]:
            # Extract entity ID and name from chunk
            lines = chunk.strip().split("\n")
            entity = {}

            for line in lines:
                if line.startswith("ID:"):
                    entity["id"] = line.replace("ID:", "").strip()
                elif line.startswith("Name:"):
                    entity["name"] = line.replace("Name:", "").strip()
                elif line.startswith("Definition:"):
                    entity["definition"] = line.replace("Definition:", "").strip()

            if "id" in entity and "name" in entity:
                # Assign default score (LightRAG doesn't provide explicit scores)
                entity["score"] = 1.0 - (len(entities) * 0.05)  # Decreasing score by rank
                entities.append(entity)

            if len(entities) >= limit:
                break

        return entities

    async def ground_text(
        self,
        text: str,
        top_k: int = 5,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Ground text to ontology entities using semantic similarity.

        Args:
            text: Text to ground (e.g., "particulate matter", "CRP")
            top_k: Maximum results
            namespaces: Optional namespace filter (applied post-search)

        Returns:
            List of grounded entities with scores
        """
        # Search for similar entities
        results = await self.search(text, mode="hybrid", top_k=top_k * 2)

        # Filter by namespace if specified
        if namespaces:
            results = [
                r for r in results
                if any(r["id"].startswith(f"{ns.lower()}:") for ns in namespaces)
            ]

        return results[:top_k]

    async def clear_index(self):
        """Clear LightRAG index. USE WITH CAUTION."""
        if self.rag:
            # Delete index files
            import shutil
            if self.working_dir.exists():
                shutil.rmtree(self.working_dir)
                self.working_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("LightRAG index cleared!")
            self.rag = None

    async def get_stats(self) -> Dict:
        """Get index statistics.

        Returns:
            Dict with index size, document count, etc.
        """
        if not self.rag:
            return {"status": "not_initialized", "documents": 0}

        # Check index files
        stats = {
            "working_dir": str(self.working_dir),
            "exists": self.working_dir.exists(),
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim
        }

        # Count cached files
        if self.working_dir.exists():
            cache_files = list(self.working_dir.glob("**/*"))
            stats["cache_files"] = len(cache_files)
            total_size = sum(f.stat().st_size for f in cache_files if f.is_file())
            stats["cache_size_mb"] = round(total_size / (1024 * 1024), 2)

        return stats
