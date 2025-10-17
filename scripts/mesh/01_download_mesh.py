#!/usr/bin/env python3
"""Download MeSH 2025 RDF data from NLM.

Downloads the complete MeSH ontology in N-Triples format from the National Library of Medicine.
File size: ~500-800MB compressed, ~2-3GB uncompressed.

Usage:
    python 01_download_mesh.py
"""

import hashlib
import logging
import sys
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MeSH Download Configuration
MESH_URL = "https://nlmpubs.nlm.nih.gov/projects/mesh/rdf/2025/mesh2025.nt.gz"
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "mesh2025.nt.gz"
CHUNK_SIZE = 1024 * 1024  # 1MB chunks


def download_mesh_rdf() -> Path:
    """Download MeSH RDF N-Triples file.

    Returns:
        Path to downloaded file
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUTPUT_FILE.exists():
        logger.info(f"MeSH file already exists at {OUTPUT_FILE}")
        logger.info("Delete the file to re-download")
        return OUTPUT_FILE

    logger.info(f"Downloading MeSH 2025 from {MESH_URL}")
    logger.info(f"Output: {OUTPUT_FILE}")
    logger.info("This may take 10-30 minutes depending on connection speed...")

    try:
        with httpx.stream("GET", MESH_URL, timeout=300.0, follow_redirects=True) as response:
            response.raise_for_status()

            # Get total file size if available
            total_size = int(response.headers.get("content-length", 0))
            total_mb = total_size / (1024 * 1024) if total_size > 0 else "unknown"
            logger.info(f"File size: {total_mb:.1f} MB")

            downloaded_bytes = 0
            with open(OUTPUT_FILE, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
                    downloaded_bytes += len(chunk)

                    # Progress update every 10MB
                    if downloaded_bytes % (10 * 1024 * 1024) < CHUNK_SIZE:
                        mb_downloaded = downloaded_bytes / (1024 * 1024)
                        if total_size > 0:
                            progress = (downloaded_bytes / total_size) * 100
                            logger.info(f"Downloaded: {mb_downloaded:.1f} MB ({progress:.1f}%)")
                        else:
                            logger.info(f"Downloaded: {mb_downloaded:.1f} MB")

        file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Download complete: {OUTPUT_FILE} ({file_size_mb:.1f} MB)")
        return OUTPUT_FILE

    except httpx.HTTPError as e:
        logger.error(f"✗ HTTP error downloading MeSH: {e}")
        if OUTPUT_FILE.exists():
            OUTPUT_FILE.unlink()  # Clean up partial download
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        if OUTPUT_FILE.exists():
            OUTPUT_FILE.unlink()
        sys.exit(1)


def verify_download(filepath: Path) -> bool:
    """Verify the downloaded file is valid gzip.

    Args:
        filepath: Path to downloaded file

    Returns:
        True if file appears valid
    """
    logger.info("Verifying download...")

    try:
        import gzip

        # Try to open and read first few bytes
        with gzip.open(filepath, "rb") as f:
            header = f.read(1024)
            if len(header) == 0:
                logger.error("✗ File is empty or corrupted")
                return False

        logger.info("✓ File appears to be valid gzip")
        return True

    except Exception as e:
        logger.error(f"✗ Verification failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("MeSH 2025 Download Script")
    logger.info("=" * 70)

    filepath = download_mesh_rdf()

    if verify_download(filepath):
        logger.info("")
        logger.info("✓ SUCCESS: MeSH RDF downloaded and verified")
        logger.info(f"Location: {filepath}")
        logger.info("")
        logger.info("Next step:")
        logger.info("  python 02_convert_to_csv.py")
    else:
        logger.error("✗ FAILED: Download verification failed")
        sys.exit(1)
