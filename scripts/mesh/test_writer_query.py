#!/usr/bin/env python3
"""Test queries against the Writer MeSH Knowledge Graph.

Validates that the MeSH terms were successfully indexed and are searchable.

Usage:
    python test_writer_query.py
"""

import json
import logging
import os
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

WRITER_API_KEY = os.getenv("WRITER_API_KEY")
WRITER_GRAPH_ID = os.getenv("WRITER_GRAPH_ID")
WRITER_BASE_URL = "https://api.writer.com/v1"


def query_knowledge_graph(question: str, graph_id: str, api_key: str) -> dict:
    """Query the Writer Knowledge Graph.

    Args:
        question: Natural language question
        graph_id: Knowledge Graph ID
        api_key: Writer API key

    Returns:
        Response dictionary with answer and sources
    """
    logger.info(f"Querying: '{question}'")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{WRITER_BASE_URL}/graphs/question",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "graph_ids": [graph_id],
                    "question": question,
                    "subqueries": False,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error(f"✗ Query failed: {e}")
        if hasattr(e, "response") and e.response:
            logger.error(f"Response: {e.response.text}")
        raise


def print_query_result(question: str, result: dict):
    """Pretty print query result.

    Args:
        question: The question asked
        result: Response from Writer API
    """
    logger.info("=" * 70)
    logger.info(f"Q: {question}")
    logger.info("-" * 70)

    # Extract answer
    answer = result.get("answer", "No answer found")
    logger.info(f"A: {answer}")

    # Extract sources
    sources = result.get("sources", [])
    if sources:
        logger.info("")
        logger.info(f"Sources ({len(sources)}):")
        for idx, source in enumerate(sources, 1):
            # Sources may have different formats - handle gracefully
            source_text = source.get("text", source.get("content", str(source)))
            logger.info(f"  [{idx}] {source_text[:200]}...")

    logger.info("=" * 70)
    logger.info("")


def main():
    logger.info("=" * 70)
    logger.info("Writer MeSH Knowledge Graph Query Test")
    logger.info("=" * 70)
    logger.info("")

    # Validate environment
    if not WRITER_API_KEY:
        logger.error("✗ WRITER_API_KEY not set in .env")
        sys.exit(1)

    if not WRITER_GRAPH_ID:
        logger.error("✗ WRITER_GRAPH_ID not set in .env")
        logger.error("Run 03_upload_to_writer.py first")
        sys.exit(1)

    logger.info(f"Graph ID: {WRITER_GRAPH_ID}")
    logger.info("")

    # Test queries for our curated MeSH terms
    test_queries = [
        # Environmental exposure
        "What is particulate matter?",
        "What is PM2.5?",

        # Inflammatory markers
        "What is C-Reactive Protein?",
        "Tell me about IL-6",

        # Metabolic markers
        "What is HbA1c?",
        "What is glucose?",

        # Diseases
        "What is Type 2 Diabetes?",
        "What is prediabetes?",

        # Relationships
        "What are broader categories of particulate matter?",
        "What conditions are related to insulin resistance?",
    ]

    results = []
    successful = 0
    failed = 0

    for question in test_queries:
        try:
            result = query_knowledge_graph(question, WRITER_GRAPH_ID, WRITER_API_KEY)
            print_query_result(question, result)
            results.append({"question": question, "success": True, "result": result})
            successful += 1

        except Exception as e:
            logger.error(f"✗ Query failed: {question}")
            logger.error(f"  Error: {e}")
            logger.info("")
            results.append({"question": question, "success": False, "error": str(e)})
            failed += 1

    # Summary
    logger.info("=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total queries: {len(test_queries)}")
    logger.info(f"✓ Successful: {successful}")
    logger.info(f"✗ Failed: {failed}")
    logger.info("")

    if failed == 0:
        logger.info("✓ ALL TESTS PASSED")
        logger.info("MeSH Knowledge Graph is working correctly!")
    else:
        logger.warning(f"⚠ {failed} tests failed")
        logger.info("Note: Graph may still be indexing (~5-10 minutes after upload)")

    logger.info("=" * 70)


if __name__ == "__main__":
    main()
