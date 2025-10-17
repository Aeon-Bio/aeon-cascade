#!/usr/bin/env python3
"""Ultra-fast parallel MeSH to CSV converter.

Single-pass extraction with concurrent processing.

Usage:
    python 02_convert_to_csv_parallel.py --curated
"""

import argparse
import csv
import logging
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
INPUT_FILE = DATA_DIR / "mesh.nt"
OUTPUT_DIR = DATA_DIR / "csv"

# Curated MeSH term IDs
CURATED_IDS = {
    "D052638", "D000393", "D010126", "D009585", "D013458", "D002244",
    "D002097", "D015850", "D014409", "D015847", "D016753",
    "D005947", "D007328", "D006442", "D054795", "D052242",
    "D017382", "D005978", "D018698", "D013481",
    "D003924", "D011236", "D007333", "D024821", "D009765",
    "D002318", "D004730", "D050197",
    "D016328", "D016899", "D053829",
    "D020641", "D005819", "D005838",
}


def process_chunk(args):
    """Process a chunk of the file (for parallel processing)."""
    chunk_data, term_ids = args

    terms = {}
    relationships = []
    synonyms = []

    for line in chunk_data.split('\n'):
        if not line.strip():
            continue

        # Check if line contains any of our target term IDs
        relevant = False
        for term_id in term_ids:
            if f"/{term_id}>" in line:
                relevant = True
                mesh_id = term_id
                break

        if not relevant:
            continue

        # Parse label
        if "rdfs#label" in line and "@en" in line:
            match = re.search(r'"([^"]+)"@en', line)
            if match:
                if mesh_id not in terms:
                    terms[mesh_id] = {"mesh_id": mesh_id, "label": "", "definition": "", "uri": f"http://id.nlm.nih.gov/mesh/{mesh_id}"}
                terms[mesh_id]["label"] = match.group(1)

        # Parse scope note
        elif "scopeNote" in line:
            match = re.search(r'"([^"]+)"', line)
            if match:
                if mesh_id not in terms:
                    terms[mesh_id] = {"mesh_id": mesh_id, "label": "", "definition": "", "uri": f"http://id.nlm.nih.gov/mesh/{mesh_id}"}
                terms[mesh_id]["definition"] = match.group(1)

        # Parse broader relationship
        elif "broaderDescriptor" in line:
            match = re.search(r'mesh/(\w+)>\s*\.\s*$', line)
            if match:
                target_id = match.group(1)
                if target_id in term_ids:
                    relationships.append({
                        "source": mesh_id,
                        "target": target_id,
                        "relationship": "broader_than",
                        "description": f"{target_id} is broader than {mesh_id}"
                    })

        # Parse synonyms
        elif "altLabel" in line:
            match = re.search(r'"([^"]+)"', line)
            if match:
                synonyms.append({
                    "mesh_id": mesh_id,
                    "synonym": match.group(1),
                    "type": "alternative"
                })

    return terms, relationships, synonyms


def extract_parallel(input_file: Path, term_ids: Set[str], chunk_size_mb: int = 200) -> tuple:
    """Extract data using parallel chunk processing.

    Args:
        input_file: Path to mesh.nt file
        term_ids: Set of MeSH IDs to extract
        chunk_size_mb: Chunk size in MB for parallel processing

    Returns:
        Tuple of (terms_dict, relationships_list, synonyms_list)
    """
    logger.info(f"Extracting {len(term_ids)} curated terms using parallel processing...")
    logger.info(f"Reading {input_file.stat().st_size / (1024**3):.2f} GB file...")

    # Read file in chunks
    chunk_size = chunk_size_mb * 1024 * 1024
    chunks = []

    with open(input_file, 'r', encoding='utf-8') as f:
        current_chunk = []
        current_size = 0

        for line in f:
            current_chunk.append(line)
            current_size += len(line)

            if current_size >= chunk_size:
                chunks.append((''.join(current_chunk), term_ids))
                current_chunk = []
                current_size = 0

                if len(chunks) % 5 == 0:
                    logger.info(f"  Prepared {len(chunks)} chunks for processing...")

        # Add final chunk
        if current_chunk:
            chunks.append((''.join(current_chunk), term_ids))

    logger.info(f"✓ Prepared {len(chunks)} chunks ({chunk_size_mb}MB each)")
    logger.info(f"Processing in parallel with {min(8, len(chunks))} workers...")

    # Process chunks in parallel
    all_terms = {}
    all_relationships = []
    all_synonyms = []

    with ProcessPoolExecutor(max_workers=min(8, len(chunks))) as executor:
        results = executor.map(process_chunk, chunks)

        for idx, (terms, relationships, synonyms) in enumerate(results, 1):
            all_terms.update(terms)
            all_relationships.extend(relationships)
            all_synonyms.extend(synonyms)

            if idx % 2 == 0:
                logger.info(f"  Processed {idx}/{len(chunks)} chunks... ({len(all_terms)} terms found)")

    # Fill in missing terms with basic data
    for term_id in term_ids:
        if term_id not in all_terms:
            all_terms[term_id] = {
                "mesh_id": term_id,
                "label": term_id,  # Fallback to ID
                "definition": "",
                "uri": f"http://id.nlm.nih.gov/mesh/{term_id}"
            }

    logger.info(f"✓ Extracted {len(all_terms)} terms")
    logger.info(f"✓ Extracted {len(all_relationships)} relationships")
    logger.info(f"✓ Extracted {len(all_synonyms)} synonyms")

    return all_terms, all_relationships, all_synonyms


def write_csv_files(terms: Dict[str, Dict], relationships: List[Dict], synonyms: List[Dict]):
    """Write extracted data to CSV files."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write terms
    terms_file = OUTPUT_DIR / "mesh_terms.csv"
    logger.info(f"Writing {terms_file}")
    with open(terms_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mesh_id", "label", "definition", "uri"])
        writer.writeheader()
        writer.writerows(terms.values())

    # Write relationships
    rels_file = OUTPUT_DIR / "mesh_relationships.csv"
    logger.info(f"Writing {rels_file}")
    with open(rels_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "target", "relationship", "description"])
        writer.writeheader()
        writer.writerows(relationships)

    # Write synonyms
    syns_file = OUTPUT_DIR / "mesh_synonyms.csv"
    logger.info(f"Writing {syns_file}")
    with open(syns_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mesh_id", "synonym", "type"])
        writer.writeheader()
        writer.writerows(synonyms)

    # Stats
    terms_size = terms_file.stat().st_size / 1024
    rels_size = rels_file.stat().st_size / 1024
    syns_size = syns_file.stat().st_size / 1024
    total_size = terms_size + rels_size + syns_size

    logger.info("")
    logger.info("✓ CSV files created:")
    logger.info(f"  - {terms_file.name}: {terms_size:.1f} KB")
    logger.info(f"  - {rels_file.name}: {rels_size:.1f} KB")
    logger.info(f"  - {syns_file.name}: {syns_size:.1f} KB")
    logger.info(f"  Total: {total_size:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description="Parallel MeSH to CSV converter")
    parser.add_argument("--curated", action="store_true", default=True, help="Extract curated subset")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Parallel MeSH to CSV Converter")
    logger.info("=" * 70)
    logger.info(f"Mode: CURATED ({len(CURATED_IDS)} terms)")

    if not INPUT_FILE.exists():
        logger.error(f"✗ Input file not found: {INPUT_FILE}")
        logger.error("Run 01_download_mesh.py first")
        sys.exit(1)

    # Extract data in parallel
    terms, relationships, synonyms = extract_parallel(INPUT_FILE, CURATED_IDS)

    # Write CSV files
    write_csv_files(terms, relationships, synonyms)

    logger.info("")
    logger.info("✓ SUCCESS: Conversion complete")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info("")
    logger.info("Next step:")
    logger.info("  python 03_upload_to_writer.py")


if __name__ == "__main__":
    main()
