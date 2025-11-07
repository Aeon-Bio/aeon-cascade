#!/usr/bin/env python3
"""Ingest ontology CSVs into local hybrid system (Memgraph + LightRAG).

Reads MESH, GO, CHEBI, FPLX CSVs and populates both:
- Memgraph (property graph for path queries)
- LightRAG (semantic search with PubMedBERT embeddings)

Usage:
    python ingest_to_local_ontology.py --data-dir ./data --memgraph bolt://localhost:7687 --lightrag ./lightrag_cache
"""

import argparse
import asyncio
import logging
from pathlib import Path
import pandas as pd
from typing import Dict, List

# Import local ontology clients
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from indra_agent.services.local_ontology import MemgraphClient, LightRAGClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OntologyIngester:
    """Ingest ontology data into Memgraph + LightRAG."""

    def __init__(
        self,
        memgraph: MemgraphClient,
        lightrag: LightRAGClient
    ):
        self.memgraph = memgraph
        self.lightrag = lightrag
        self.stats = {
            "entities_created": 0,
            "relationships_created": 0,
            "lightrag_documents": 0
        }

    async def initialize(self):
        """Initialize both backends."""
        await self.memgraph.connect()
        await self.memgraph.create_indexes()
        await self.lightrag.initialize()
        logger.info("Backends initialized")

    async def ingest_csv(
        self,
        csv_path: Path,
        namespace: str,
        has_relationships: bool = True
    ):
        """Ingest a single CSV file.

        Args:
            csv_path: Path to CSV file
            namespace: Ontology namespace (MESH, HGNC, GO, CHEBI, FPLX)
            has_relationships: Whether CSV contains relationship data
        """
        logger.info(f"Ingesting {csv_path.name} (namespace: {namespace})")

        df = pd.read_csv(csv_path)
        logger.info(f"  Loaded {len(df)} rows")

        # Process entities
        entity_count = 0
        lightrag_docs = []

        for _, row in df.iterrows():
            # Extract entity fields
            entity_id = f"{namespace.lower()}:{row['id']}"
            name = row.get('name', '')
            definition = row.get('definition', '')
            synonyms = row.get('synonyms', '')

            # Parse synonyms (usually pipe-separated)
            # Handle NaN values (pandas converts empty cells to float NaN)
            synonym_list = [s.strip() for s in str(synonyms).split('|')] if synonyms and str(synonyms) != 'nan' else []

            # Create entity in Memgraph
            await self.memgraph.create_entity(
                entity_id=entity_id,
                name=name,
                namespace=namespace.upper(),
                definition=definition,
                synonyms=synonym_list
            )
            entity_count += 1

            # Prepare LightRAG document
            lightrag_docs.append({
                "id": entity_id,
                "name": name,
                "definition": definition,
                "synonyms": synonym_list
            })

            if entity_count % 1000 == 0:
                logger.info(f"  Processed {entity_count} entities...")

        self.stats["entities_created"] += entity_count
        logger.info(f"  Created {entity_count} entities in Memgraph")

        # Ingest into LightRAG (batch operation)
        await self.lightrag.insert(lightrag_docs)
        self.stats["lightrag_documents"] += len(lightrag_docs)
        logger.info(f"  Inserted {len(lightrag_docs)} documents into LightRAG")

        # Process relationships (if present)
        if has_relationships and 'relationships' in df.columns:
            relationship_count = await self._ingest_relationships(df, namespace)
            self.stats["relationships_created"] += relationship_count
            logger.info(f"  Created {relationship_count} relationships in Memgraph")

    async def _ingest_relationships(
        self,
        df: pd.DataFrame,
        namespace: str
    ) -> int:
        """Ingest relationships from CSV.

        Assumes 'relationships' column contains JSON: [{target_id, type, belief, evidence_count}]
        """
        count = 0

        for _, row in df.iterrows():
            source_id = f"{namespace.lower()}:{row['id']}"
            relationships_str = row.get('relationships', '')

            # Handle NaN values (pandas converts empty cells to float NaN)
            if not relationships_str or str(relationships_str) == 'nan':
                continue

            # Parse relationships (format depends on CSV structure)
            # Example: "target_id:type:belief:evidence_count|..."
            # Note: target_id may contain colons (e.g., "HGNC:APLF")
            for rel in str(relationships_str).split('|'):
                if not rel.strip():
                    continue

                parts = rel.split(':')
                if len(parts) < 4:  # Need at least namespace:id:type:belief
                    continue

                # Split from right: last 3 parts are type, belief, evidence
                # Everything before that is the target_id
                evidence_count = int(parts[-1]) if len(parts) > 3 else 1
                belief = float(parts[-2]) if len(parts) > 2 else 0.5
                stmt_type = parts[-3] if len(parts) > 1 else "unknown"
                target_id = ':'.join(parts[:-3])  # Rejoin all parts except last 3

                await self.memgraph.create_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    stmt_type=stmt_type,
                    belief=belief,
                    evidence_count=evidence_count
                )
                count += 1

        return count

    async def ingest_directory(
        self,
        data_dir: Path,
        namespaces: List[str] = None
    ):
        """Ingest all CSVs from data directory.

        Args:
            data_dir: Directory containing ontology CSV files
            namespaces: Optional list of namespaces to ingest
        """
        all_namespaces = ["MESH", "GO", "CHEBI", "FPLX"]
        if namespaces:
            all_namespaces = [ns.upper() for ns in namespaces]

        for namespace in all_namespaces:
            namespace_dir = data_dir / namespace.lower()
            if not namespace_dir.exists():
                logger.warning(f"Namespace directory not found: {namespace_dir}")
                continue

            # Find all CSV files
            csv_files = sorted(namespace_dir.glob("*.csv"))
            logger.info(f"Found {len(csv_files)} CSV files for {namespace}")

            for csv_file in csv_files:
                try:
                    await self.ingest_csv(csv_file, namespace)
                except Exception as e:
                    logger.error(f"Error ingesting {csv_file}: {e}")
                    continue

        logger.info(f"Ingestion complete: {self.stats}")

    async def close(self):
        """Close backend connections."""
        await self.memgraph.close()


async def main():
    parser = argparse.ArgumentParser(description="Ingest ontologies into local hybrid system")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Directory containing ontology CSV files"
    )
    parser.add_argument(
        "--memgraph",
        type=str,
        default="bolt://localhost:7687",
        help="Memgraph Bolt URI"
    )
    parser.add_argument(
        "--lightrag",
        type=str,
        default="./lightrag_cache",
        help="LightRAG working directory"
    )
    parser.add_argument(
        "--namespaces",
        type=str,
        nargs="+",
        help="Optional: specific namespaces to ingest (MESH, GO, CHEBI, FPLX)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before ingestion (DANGEROUS!)"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return

    # Initialize clients
    memgraph = MemgraphClient(uri=args.memgraph)
    lightrag = LightRAGClient(working_dir=args.lightrag)

    ingester = OntologyIngester(memgraph, lightrag)
    await ingester.initialize()

    # Clear existing data if requested
    if args.clear:
        logger.warning("Clearing existing data...")
        await memgraph.clear_database()
        await lightrag.clear_index()

    # Ingest data
    try:
        await ingester.ingest_directory(data_dir, args.namespaces)

        # Print statistics
        logger.info("=" * 70)
        logger.info("Ingestion Statistics")
        logger.info("=" * 70)
        for key, value in ingester.stats.items():
            logger.info(f"{key}: {value:,}")

        # Get backend stats
        memgraph_stats = await memgraph.get_stats()
        logger.info(f"Memgraph entities: {memgraph_stats['total_entities']:,}")
        logger.info(f"Memgraph relationships: {memgraph_stats['total_relationships']:,}")

        lightrag_stats = await lightrag.get_stats()
        logger.info(f"LightRAG cache size: {lightrag_stats.get('cache_size_mb', 0)} MB")

    finally:
        await ingester.close()


if __name__ == "__main__":
    asyncio.run(main())
