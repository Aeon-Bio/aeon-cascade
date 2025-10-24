#!/usr/bin/env python3
"""Upload new MeSH CSV and replace existing Knowledge Graph."""

import logging
import os
import re
import sys
import time
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
CSV_FILE = SCRIPT_DIR / "data" / "mesh_for_writer.csv"
ENV_FILE = SCRIPT_DIR.parent.parent / ".env"
WRITER_BASE_URL = "https://api.writer.com/v1"
WRITER_API_KEY = os.getenv("WRITER_API_KEY")


def upload_file(api_key, filepath):
    logger.info(f"Uploading {filepath.name}...")
    client = httpx.Client(base_url=WRITER_BASE_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=60.0)
    try:
        with open(filepath, "rb") as f:
            response = client.post("/files", headers={"Content-Disposition": f'attachment; filename="{filepath.name}"', "Content-Type": "text/csv"}, content=f.read())
            response.raise_for_status()
        file_id = response.json()["id"]
        logger.info(f"✓ Uploaded: {file_id}")
        return file_id
    except httpx.HTTPError as e:
        logger.error(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        client.close()


def create_graph(api_key, name, description):
    logger.info(f"Creating Knowledge Graph: {name}")
    client = httpx.Client(base_url=WRITER_BASE_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=60.0)
    try:
        response = client.post("/graphs", json={"name": name, "description": description})
        response.raise_for_status()
        graph_id = response.json()["id"]
        logger.info(f"✓ Created: {graph_id}")
        return graph_id
    except httpx.HTTPError as e:
        logger.error(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        client.close()


def add_file_to_graph(api_key, graph_id, file_id):
    logger.info(f"Adding file to graph...")
    client = httpx.Client(base_url=WRITER_BASE_URL, headers={"Authorization": f"Bearer {api_key}"}, timeout=60.0)
    try:
        for attempt in range(10):
            try:
                response = client.post(f"/graphs/{graph_id}/file", json={"file_id": file_id})
                response.raise_for_status()
                logger.info("✓ File added")
                return
            except httpx.HTTPError as e:
                if hasattr(e, "response") and "still processing" in e.response.text.lower() and attempt < 9:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
    except httpx.HTTPError as e:
        logger.error(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        client.close()


def update_env(env_file, new_graph_id):
    logger.info(f"Updating .env...")
    with open(env_file, "r") as f:
        content = f.read()
    pattern = r'WRITER_GRAPH_ID="[^"]*"'
    replacement = f'WRITER_GRAPH_ID="{new_graph_id}"'
    new_content = re.sub(pattern, replacement, content) if re.search(pattern, content) else content + f'\nWRITER_GRAPH_ID="{new_graph_id}"\n'
    with open(env_file, "w") as f:
        f.write(new_content)
    logger.info(f"✓ Updated WRITER_GRAPH_ID = {new_graph_id}")


def main():
    logger.info("=" * 70)
    logger.info("Upload MeSH CSV → Replace Writer KG")
    logger.info("=" * 70)
    
    if not WRITER_API_KEY:
        logger.error("✗ WRITER_API_KEY not set")
        sys.exit(1)
    
    file_id = upload_file(WRITER_API_KEY, CSV_FILE)
    graph_id = create_graph(WRITER_API_KEY, "mesh-2025-biomedical-ontology", "MeSH 2025 - 34 curated biomarkers")
    add_file_to_graph(WRITER_API_KEY, graph_id, file_id)
    update_env(ENV_FILE, graph_id)
    
    logger.info("")
    logger.info("✓ SUCCESS! New Graph ID: " + graph_id)
    logger.info("Wait 2-3 minutes for indexing, then:")
    logger.info("  uv run python scripts/mesh/verify_new_kg.py")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
