#!/usr/bin/env python3
"""Upload MeSH CSV files to Writer Knowledge Graph.

Creates a Writer Knowledge Graph and uploads the MeSH terms, relationships,
and synonyms for semantic search and entity grounding.

Requires:
- WRITER_API_KEY environment variable
- CSV files from 02_convert_to_csv.py

Usage:
    python 03_upload_to_writer.py [--graph-id EXISTING_ID]

Options:
    --graph-id ID   Use existing Knowledge Graph ID (skips creation)
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data" / "csv"
TERMS_FILE = DATA_DIR / "mesh_terms.csv"
RELATIONSHIPS_FILE = DATA_DIR / "mesh_relationships.csv"
SYNONYMS_FILE = DATA_DIR / "mesh_synonyms.csv"

# Writer API Configuration
WRITER_BASE_URL = "https://api.writer.com/v1"
WRITER_API_KEY = os.getenv("WRITER_API_KEY")


class WriterKGUploader:
    """Handler for Writer Knowledge Graph API operations."""

    def __init__(self, api_key: str):
        if not api_key:
            logger.error("✗ WRITER_API_KEY environment variable not set")
            logger.error("Set it in .env or export WRITER_API_KEY=your_key")
            sys.exit(1)

        self.api_key = api_key
        self.client = httpx.Client(
            base_url=WRITER_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def create_knowledge_graph(self, name: str, description: str) -> str:
        """Create a new Knowledge Graph.

        Args:
            name: Knowledge Graph name
            description: Description of the graph

        Returns:
            Knowledge Graph ID
        """
        logger.info(f"Creating Knowledge Graph: {name}")

        try:
            response = self.client.post(
                "/graphs",
                json={"name": name, "description": description},
            )
            response.raise_for_status()

            graph_id = response.json()["id"]
            logger.info(f"✓ Created Knowledge Graph: {graph_id}")
            return graph_id

        except httpx.HTTPError as e:
            logger.error(f"✗ Error creating Knowledge Graph: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response: {e.response.text}")
            sys.exit(1)

    def upload_file(self, filepath: Path) -> str:
        """Upload a file to Writer.

        Args:
            filepath: Path to CSV file

        Returns:
            File ID
        """
        logger.info(f"Uploading {filepath.name}...")

        if not filepath.exists():
            logger.error(f"✗ File not found: {filepath}")
            sys.exit(1)

        file_size = filepath.stat().st_size / 1024
        logger.info(f"  File size: {file_size:.1f} KB")

        try:
            with open(filepath, "rb") as f:
                response = self.client.post(
                    "/files",
                    headers={
                        "Content-Disposition": f'attachment; filename="{filepath.name}"',
                        "Content-Type": "text/csv",
                    },
                    content=f.read(),
                )
                response.raise_for_status()

            file_id = response.json()["id"]
            logger.info(f"✓ Uploaded: {file_id}")
            return file_id

        except httpx.HTTPError as e:
            logger.error(f"✗ Error uploading file: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response: {e.response.text}")
            sys.exit(1)

    def add_file_to_graph(self, graph_id: str, file_id: str, max_retries: int = 10):
        """Add uploaded file to Knowledge Graph (with retry for processing delay).

        Args:
            graph_id: Knowledge Graph ID
            file_id: Uploaded file ID
            max_retries: Maximum number of retries if file is still processing
        """
        logger.info(f"Adding file {file_id} to graph {graph_id}")

        for attempt in range(max_retries):
            try:
                response = self.client.post(
                    f"/graphs/{graph_id}/file",
                    json={"file_id": file_id},
                )
                response.raise_for_status()

                logger.info("✓ File added to Knowledge Graph")
                return

            except httpx.HTTPError as e:
                if hasattr(e, "response") and e.response:
                    response_text = e.response.text
                    # Check if file is still processing
                    if "still processing" in response_text.lower() and attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)  # Exponential backoff
                        logger.info(f"  File still processing, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue

                logger.error(f"✗ Error adding file to graph: {e}")
                if hasattr(e, "response") and e.response:
                    logger.error(f"Response: {e.response.text}")
                sys.exit(1)

    def close(self):
        """Close HTTP client."""
        self.client.close()


def main():
    parser = argparse.ArgumentParser(description="Upload MeSH to Writer KG")
    parser.add_argument(
        "--graph-id",
        type=str,
        help="Use existing Knowledge Graph ID (skips creation)",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("MeSH → Writer Knowledge Graph Uploader")
    logger.info("=" * 70)

    # Verify CSV files exist
    required_files = [TERMS_FILE, RELATIONSHIPS_FILE, SYNONYMS_FILE]
    for filepath in required_files:
        if not filepath.exists():
            logger.error(f"✗ Required file not found: {filepath}")
            logger.error("Run 02_convert_to_csv.py first")
            sys.exit(1)

    # Initialize uploader
    uploader = WriterKGUploader(WRITER_API_KEY)

    try:
        # Create or use existing Knowledge Graph
        if args.graph_id:
            logger.info(f"Using existing Knowledge Graph: {args.graph_id}")
            graph_id = args.graph_id
        else:
            graph_id = uploader.create_knowledge_graph(
                name="mesh-ontology-2025",
                description="Medical Subject Headings (MeSH) 2025 - Curated subset for metabolic, inflammatory, and environmental health terms. Enables semantic biomedical entity grounding.",
            )

        # Upload files
        logger.info("")
        logger.info("Uploading CSV files...")

        terms_id = uploader.upload_file(TERMS_FILE)
        uploader.add_file_to_graph(graph_id, terms_id)

        relationships_id = uploader.upload_file(RELATIONSHIPS_FILE)
        uploader.add_file_to_graph(graph_id, relationships_id)

        synonyms_id = uploader.upload_file(SYNONYMS_FILE)
        uploader.add_file_to_graph(graph_id, synonyms_id)

        # Success
        logger.info("")
        logger.info("=" * 70)
        logger.info("✓ SUCCESS: MeSH Knowledge Graph created")
        logger.info(f"Graph ID: {graph_id}")
        logger.info("")
        logger.info("Save this ID for querying:")
        logger.info(f'  export WRITER_GRAPH_ID="{graph_id}"')
        logger.info("")
        logger.info("Test query (once indexing completes, ~5-10 minutes):")
        logger.info("  python test_writer_query.py")
        logger.info("=" * 70)

    finally:
        uploader.close()


if __name__ == "__main__":
    main()
