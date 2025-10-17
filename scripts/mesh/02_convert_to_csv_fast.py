#!/usr/bin/env python3
"""Fast MeSH to CSV converter using grep/awk instead of full RDF parsing.

For curated mode, extracts only the target terms without loading entire graph.
This is 10-100x faster than rdflib parsing for curated subsets.

Usage:
    python 02_convert_to_csv_fast.py --curated
"""

import argparse
import csv
import logging
import subprocess
import sys
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


def extract_curated_terms_fast(input_file: Path, term_ids: Set[str]) -> Dict[str, Dict]:
    """Extract curated terms using grep (much faster than RDF parsing).

    Args:
        input_file: Path to mesh.nt file
        term_ids: Set of MeSH IDs to extract

    Returns:
        Dictionary mapping mesh_id to term data
    """
    logger.info(f"Extracting {len(term_ids)} curated terms from {input_file}")

    terms = {}

    for mesh_id in term_ids:
        uri = f"http://id.nlm.nih.gov/mesh/{mesh_id}"

        # Extract label
        label_cmd = f'grep "{uri}" "{input_file}" | grep "rdfs#label" | head -1'
        try:
            result = subprocess.run(label_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.stdout:
                # Parse: <uri> <predicate> "Label"@en .
                parts = result.stdout.split('"')
                if len(parts) >= 2:
                    label = parts[1]
                else:
                    label = mesh_id
            else:
                label = mesh_id
        except:
            label = mesh_id

        # Extract scope note (definition)
        scope_cmd = f'grep "{uri}" "{input_file}" | grep "scopeNote" | head -1'
        try:
            result = subprocess.run(scope_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.stdout:
                parts = result.stdout.split('"')
                definition = parts[1] if len(parts) >= 2 else ""
            else:
                definition = ""
        except:
            definition = ""

        terms[mesh_id] = {
            "mesh_id": mesh_id,
            "label": label,
            "definition": definition,
            "uri": uri
        }

        if len(terms) % 10 == 0:
            logger.info(f"  Extracted {len(terms)}/{len(term_ids)} terms...")

    logger.info(f"✓ Extracted {len(terms)} terms")
    return terms


def extract_relationships_fast(input_file: Path, term_ids: Set[str]) -> List[Dict]:
    """Extract relationships using grep.

    Args:
        input_file: Path to mesh.nt file
        term_ids: Set of MeSH IDs to include

    Returns:
        List of relationship dictionaries
    """
    logger.info("Extracting relationships...")

    relationships = []

    for mesh_id in term_ids:
        uri = f"http://id.nlm.nih.gov/mesh/{mesh_id}"

        # Find broader terms
        broader_cmd = f'grep "{uri}" "{input_file}" | grep "broaderDescriptor"'
        try:
            result = subprocess.run(broader_cmd, shell=True, capture_output=True, text=True, timeout=30)
            for line in result.stdout.split('\n'):
                if not line:
                    continue
                # Parse: <source_uri> <predicate> <target_uri> .
                parts = line.split()
                if len(parts) >= 3:
                    target_uri = parts[2].strip('<>.')
                    target_id = target_uri.split('/')[-1]

                    if target_id in term_ids:
                        relationships.append({
                            "source": mesh_id,
                            "target": target_id,
                            "relationship": "broader_than",
                            "description": f"{target_id} is broader than {mesh_id}"
                        })
        except:
            pass

    logger.info(f"✓ Extracted {len(relationships)} relationships")
    return relationships


def extract_synonyms_fast(input_file: Path, term_ids: Set[str]) -> List[Dict]:
    """Extract synonyms using grep.

    Args:
        input_file: Path to mesh.nt file
        term_ids: Set of MeSH IDs to include

    Returns:
        List of synonym dictionaries
    """
    logger.info("Extracting synonyms...")

    synonyms = []

    for mesh_id in term_ids:
        uri = f"http://id.nlm.nih.gov/mesh/{mesh_id}"

        # Find alternative labels
        alt_cmd = f'grep "{uri}" "{input_file}" | grep "altLabel"'
        try:
            result = subprocess.run(alt_cmd, shell=True, capture_output=True, text=True, timeout=30)
            for line in result.stdout.split('\n'):
                if not line:
                    continue
                parts = line.split('"')
                if len(parts) >= 2:
                    synonym = parts[1]
                    synonyms.append({
                        "mesh_id": mesh_id,
                        "synonym": synonym,
                        "type": "alternative"
                    })
        except:
            pass

    logger.info(f"✓ Extracted {len(synonyms)} synonyms")
    return synonyms


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
    parser = argparse.ArgumentParser(description="Fast MeSH to CSV converter")
    parser.add_argument("--curated", action="store_true", default=True, help="Extract curated subset")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Fast MeSH to CSV Converter (grep-based)")
    logger.info("=" * 70)
    logger.info(f"Mode: CURATED ({len(CURATED_IDS)} terms)")

    if not INPUT_FILE.exists():
        logger.error(f"✗ Input file not found: {INPUT_FILE}")
        logger.error("Run 01_download_mesh.py first")
        sys.exit(1)

    # Extract data using grep (fast, parallel-friendly)
    terms = extract_curated_terms_fast(INPUT_FILE, CURATED_IDS)
    relationships = extract_relationships_fast(INPUT_FILE, CURATED_IDS)
    synonyms = extract_synonyms_fast(INPUT_FILE, CURATED_IDS)

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
