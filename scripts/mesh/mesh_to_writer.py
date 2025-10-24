#!/usr/bin/env python3
"""Complete MeSH → Writer KG pipeline with parallel processing.

Downloads MeSH 2025, extracts curated terms with parallel processing,
and creates a single CSV file ready for Writer KG upload.

Usage:
    python mesh_to_writer.py [--download] [--all]

Options:
    --download  Download latest MeSH 2025 first
    --all       Process all 30K+ terms (default: curated ~100 terms)
"""

import argparse
import csv
import gzip
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
INPUT_FILE = DATA_DIR / "mesh2025.nt.gz"
OUTPUT_FILE = DATA_DIR / "mesh_for_writer.csv"

# MeSH curated terms (environmental health + metabolic)
CURATED_IDS = {
    # Environmental exposures
    "D052638",  # Particulate Matter
    "D000393",  # Air Pollutants
    "D010126",  # Ozone
    "D009585",  # Nitrogen Dioxide
    "D013458",  # Sulfur Dioxide
    "D002244",  # Carbon Monoxide
    # Inflammatory biomarkers
    "D002097",  # C-Reactive Protein
    "D015850",  # Interleukin-6
    "D014409",  # Tumor Necrosis Factor-alpha
    "D015847",  # Interleukin-4
    "D016753",  # Interleukin-10
    # Metabolic biomarkers
    "D005947",  # Glucose
    "D007328",  # Insulin
    "D006442",  # Glycated Hemoglobin A (HbA1c)
    "D054795",  # Incretins
    "D052242",  # Adiponectin
    # Oxidative stress
    "D017382",  # Reactive Oxygen Species
    "D005978",  # Glutathione
    "D018698",  # Glutathione S-Transferase
    "D013481",  # Superoxide Dismutase
    # Diseases
    "D003924",  # Diabetes Mellitus, Type 2
    "D011236",  # Prediabetic State
    "D007333",  # Insulin Resistance
    "D024821",  # Metabolic Syndrome
    "D009765",  # Obesity
    "D002318",  # Cardiovascular Diseases
    "D004730",  # Endothelial Dysfunction
    "D050197",  # Atherosclerosis
    # Molecular mechanisms
    "D016328",  # NF-kappa B
    "D016899",  # Interferon-gamma
    "D053829",  # Amyloid beta-Peptides
    # Genetics
    "D020641",  # Polymorphism, Single Nucleotide
    "D005819",  # Genetic Markers
    "D005838",  # Genotype
}


def download_mesh():
    """Download MeSH 2025 if not present."""
    if INPUT_FILE.exists():
        logger.info(f"✓ MeSH file exists: {INPUT_FILE}")
        return

    logger.info("Downloading MeSH 2025...")
    import httpx

    url = "https://nlmpubs.nlm.nih.gov/projects/mesh/rdf/2025/mesh2025.nt.gz"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as response:
            response.raise_for_status()
            total_mb = int(response.headers.get("content-length", 0)) / (1024 * 1024)
            logger.info(f"Downloading {total_mb:.1f} MB...")

            with open(INPUT_FILE, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        logger.info(f"✓ Download complete: {INPUT_FILE}")
    except Exception as e:
        logger.error(f"✗ Download failed: {e}")
        sys.exit(1)


def parse_mesh_chunk(lines: List[bytes], target_ids: Set[str]) -> Dict[str, Dict]:
    """Parse a chunk of MeSH N-Triples lines (worker function for parallel processing).

    Args:
        lines: List of N-Triples lines as bytes
        target_ids: Set of MeSH IDs to extract

    Returns:
        Dictionary mapping mesh_id to term data
    """
    import re

    terms = {}

    for line in lines:
        try:
            line_str = line.decode('utf-8', errors='ignore').strip()
            if not line_str or line_str.startswith('#'):
                continue

            # Parse N-Triple: <subject> <predicate> <object> .
            # Extract MeSH ID from subject URI (format: mesh/2025/D052638)
            mesh_id_match = re.search(r'mesh/\d+/([DCA]\d{6})>', line_str)
            if not mesh_id_match:
                continue

            mesh_id = mesh_id_match.group(1)

            # Only process target IDs
            if mesh_id not in target_ids:
                continue

            # Initialize term if not exists
            if mesh_id not in terms:
                terms[mesh_id] = {
                    "mesh_id": mesh_id,
                    "mesh_label": "",
                    "definition": "",
                }

            # Extract label (rdf-schema#label)
            if 'rdf-schema#label' in line_str:
                label_match = re.search(r'"([^"]+)"', line_str)
                if label_match:
                    # Only extract simple label (without qualifiers like "/adverse effects")
                    label = label_match.group(1)
                    if '/' not in label or label.split('/')[0].strip() == label:
                        terms[mesh_id]["mesh_label"] = label.split('@')[0].strip('"')

            # Extract definition (meshv:scopeNote)
            elif 'vocab#scopeNote' in line_str:
                def_match = re.search(r'"([^"]+)"', line_str)
                if def_match:
                    terms[mesh_id]["definition"] = def_match.group(1)

        except Exception:
            continue

    return terms


def extract_mesh_terms_parallel(input_file: Path, target_ids: Set[str], workers: int = 8) -> Dict[str, Dict]:
    """Extract MeSH terms using parallel processing.

    Args:
        input_file: Path to mesh2025.nt.gz
        target_ids: Set of MeSH IDs to extract
        workers: Number of parallel workers

    Returns:
        Dictionary mapping mesh_id to term data
    """
    logger.info(f"Extracting {len(target_ids)} MeSH terms using {workers} parallel workers...")

    # Read file in chunks
    chunk_size = 100000  # Lines per chunk
    chunks = []
    current_chunk = []

    # Auto-detect if file is gzipped or plain text
    try:
        with gzip.open(input_file, 'rb') as f:
            # Try reading first line to see if it's valid gzip
            first_line = f.readline()
            if first_line:
                # Valid gzip, reopen and read all
                logger.info("Detected gzipped file format")
            else:
                raise gzip.BadGzipFile("Empty file")
    except gzip.BadGzipFile:
        # Not gzipped, read as plain text
        logger.info("Detected plain text file format")
        with open(input_file, 'rb') as f:
            for line in f:
                current_chunk.append(line)
                if len(current_chunk) >= chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = []

            if current_chunk:
                chunks.append(current_chunk)
    else:
        # Is gzipped, read normally
        with gzip.open(input_file, 'rb') as f:
            for line in f:
                current_chunk.append(line)
                if len(current_chunk) >= chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = []

            if current_chunk:
                chunks.append(current_chunk)

    logger.info(f"Processing {len(chunks)} chunks in parallel...")

    # Process chunks in parallel
    all_terms = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(parse_mesh_chunk, chunk, target_ids): i
                   for i, chunk in enumerate(chunks)}

        completed = 0
        for future in as_completed(futures):
            chunk_terms = future.result()
            all_terms.update(chunk_terms)
            completed += 1
            if completed % 10 == 0:
                logger.info(f"  Processed {completed}/{len(chunks)} chunks, found {len(all_terms)} terms so far...")

    logger.info(f"✓ Extracted {len(all_terms)}/{len(target_ids)} terms")

    # Fill in missing terms with ID as label (fallback)
    for mesh_id in target_ids:
        if mesh_id not in all_terms:
            logger.warning(f"  Missing: {mesh_id}, using ID as label")
            all_terms[mesh_id] = {
                "mesh_id": mesh_id,
                "mesh_label": mesh_id,
                "definition": "",
            }
        elif not all_terms[mesh_id]["mesh_label"]:
            # If label is empty, use ID as fallback
            all_terms[mesh_id]["mesh_label"] = mesh_id

    return all_terms


def write_writer_csv(terms: Dict[str, Dict], output_file: Path):
    """Write terms to CSV format for Writer KG upload.

    Writer expects: mesh_id, mesh_label, definition (3 columns, no extra fields)
    """
    logger.info(f"Writing Writer KG CSV: {output_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mesh_id", "mesh_label", "definition"])
        writer.writeheader()

        # Sort by mesh_id for consistency
        sorted_terms = sorted(terms.values(), key=lambda x: x["mesh_id"])
        writer.writerows(sorted_terms)

    file_size_kb = output_file.stat().st_size / 1024
    logger.info(f"✓ Wrote {len(terms)} terms ({file_size_kb:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="MeSH → Writer KG pipeline")
    parser.add_argument("--download", action="store_true", help="Download MeSH 2025 first")
    parser.add_argument("--all", action="store_true", help="Process all terms (not just curated)")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers (default: 8)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("MeSH → Writer KG Pipeline (Parallel Processing)")
    logger.info("=" * 70)

    # Step 1: Download if requested
    if args.download:
        download_mesh()
    elif not INPUT_FILE.exists():
        logger.error(f"✗ Input file not found: {INPUT_FILE}")
        logger.error("Run with --download flag")
        sys.exit(1)

    # Step 2: Determine target IDs
    if args.all:
        logger.info("Mode: ALL (30K+ terms, slower)")
        # For --all, we'd need to extract all IDs first (not implemented here)
        logger.error("--all mode not yet implemented, use curated mode")
        sys.exit(1)
    else:
        logger.info(f"Mode: CURATED ({len(CURATED_IDS)} terms)")
        target_ids = CURATED_IDS

    # Step 3: Extract terms with parallel processing
    terms = extract_mesh_terms_parallel(INPUT_FILE, target_ids, workers=args.workers)

    # Step 4: Write CSV for Writer upload
    write_writer_csv(terms, OUTPUT_FILE)

    logger.info("")
    logger.info("✓ SUCCESS: CSV ready for Writer KG upload")
    logger.info(f"Output: {OUTPUT_FILE}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Go to https://dev.writer.com/home/files")
    logger.info(f"2. Upload {OUTPUT_FILE.name}")
    logger.info("3. Go to https://dev.writer.com/home/knowledge-graph")
    logger.info("4. Create new KG with the uploaded file")
    logger.info("5. Save the Graph ID to .env as WRITER_GRAPH_ID")
    logger.info("")


if __name__ == "__main__":
    main()
