#!/usr/bin/env python3
"""Convert MeSH RDF N-Triples to CSV format for Writer Knowledge Graph.

Extracts MeSH descriptors, relationships, and hierarchies from RDF format
and creates structured CSV files suitable for Writer KG upload.

Output files:
- mesh_terms.csv: Core MeSH descriptors with labels and definitions
- mesh_relationships.csv: Hierarchical relationships (broader/narrower)
- mesh_synonyms.csv: Alternative terms and synonyms

Usage:
    python 02_convert_to_csv.py [--full | --curated]

Options:
    --full      Convert all 30K+ MeSH terms (slower, larger output)
    --curated   Convert curated subset of ~1000 metabolic/environmental terms (default)
"""

import argparse
import csv
import gzip
import logging
import sys
from pathlib import Path
from typing import Dict, List, Set

import rdflib
from rdflib import Namespace, URIRef

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
INPUT_FILE = DATA_DIR / "mesh2025.nt.gz"
OUTPUT_DIR = DATA_DIR / "csv"

# RDF Namespaces
MESH = Namespace("http://id.nlm.nih.gov/mesh/")
MESHV = Namespace("http://id.nlm.nih.gov/mesh/vocab#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

# Curated MeSH term prefixes (for --curated mode)
# Focus on metabolic, inflammatory, environmental health terms
CURATED_CATEGORIES = {
    # Environmental exposures
    "D052638",  # Particulate Matter
    "D000393",  # Air Pollutants
    "D010126",  # Ozone
    "D009585",  # Nitrogen Dioxide
    "D013458",  # Sulfur Dioxide
    "D002244",  # Carbon Monoxide
    # Biomarkers - Inflammatory
    "D002097",  # C-Reactive Protein
    "D015850",  # Interleukin-6
    "D014409",  # Tumor Necrosis Factor-alpha
    "D015847",  # Interleukin-4
    "D016753",  # Interleukin-10
    # Biomarkers - Metabolic
    "D005947",  # Glucose
    "D007328",  # Insulin
    "D006442",  # Glycated Hemoglobin A
    "D054795",  # Incretins
    "D052242",  # Adiponectin
    # Oxidative stress
    "D017382",  # Reactive Oxygen Species
    "D005978",  # Glutathione
    "D018698",  # Glutathione S-Transferase
    "D013481",  # Superoxide Dismutase
    # Diabetes/Metabolic
    "D003924",  # Diabetes Mellitus, Type 2
    "D011236",  # Prediabetic State
    "D007333",  # Insulin Resistance
    "D024821",  # Metabolic Syndrome
    "D009765",  # Obesity
    # Cardiovascular
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


def extract_mesh_id(uri: URIRef) -> str:
    """Extract MeSH ID from URI.

    Args:
        uri: RDF URI reference

    Returns:
        MeSH ID (e.g., "D052638")
    """
    return str(uri).split("/")[-1]


def load_rdf_graph(input_file: Path) -> rdflib.Graph:
    """Load MeSH RDF graph from N-Triples file.

    Args:
        input_file: Path to mesh2025.nt.gz

    Returns:
        Loaded RDF graph
    """
    logger.info(f"Loading RDF graph from {input_file}")
    logger.info("This may take 5-15 minutes for full MeSH...")

    g = rdflib.Graph()

    try:
        # Parse gzipped N-Triples
        with gzip.open(input_file, "rb") as f:
            g.parse(f, format="nt")

        logger.info(f"✓ Loaded {len(g)} triples")
        return g

    except FileNotFoundError:
        logger.error(f"✗ Input file not found: {input_file}")
        logger.error("Run 01_download_mesh.py first")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Error loading RDF: {e}")
        sys.exit(1)


def extract_terms(g: rdflib.Graph, curated_only: bool = True) -> List[Dict]:
    """Extract MeSH terms (descriptors) from graph.

    Args:
        g: RDF graph
        curated_only: If True, only extract curated subset

    Returns:
        List of term dictionaries
    """
    logger.info("Extracting MeSH terms...")

    terms = []
    term_count = 0

    # Query for MeSH descriptors with labels
    for subject in g.subjects(predicate=rdflib.RDF.type, object=MESHV.Descriptor):
        mesh_id = extract_mesh_id(subject)

        # Filter to curated terms if requested
        if curated_only and mesh_id not in CURATED_CATEGORIES:
            continue

        # Get preferred label
        label = None
        for label_obj in g.objects(subject, RDFS.label):
            label = str(label_obj)
            break

        if not label:
            continue

        # Get scope note (definition)
        definition = None
        for def_obj in g.objects(subject, MESHV.scopeNote):
            definition = str(def_obj)
            break

        terms.append({
            "mesh_id": mesh_id,
            "label": label,
            "definition": definition or "",
            "uri": str(subject)
        })

        term_count += 1
        if term_count % 1000 == 0:
            logger.info(f"  Processed {term_count} terms...")

    logger.info(f"✓ Extracted {len(terms)} terms")
    return terms


def extract_relationships(g: rdflib.Graph, term_ids: Set[str]) -> List[Dict]:
    """Extract hierarchical relationships between terms.

    Args:
        g: RDF graph
        term_ids: Set of MeSH IDs to include

    Returns:
        List of relationship dictionaries
    """
    logger.info("Extracting relationships...")

    relationships = []

    # Query for broader/narrower relationships
    for subject, predicate, obj in g.triples((None, MESHV.broaderDescriptor, None)):
        source_id = extract_mesh_id(subject)
        target_id = extract_mesh_id(obj)

        # Only include if both terms are in our set
        if source_id in term_ids and target_id in term_ids:
            relationships.append({
                "source": source_id,
                "target": target_id,
                "relationship": "broader_than",
                "description": f"{target_id} is broader than {source_id}"
            })

    logger.info(f"✓ Extracted {len(relationships)} relationships")
    return relationships


def extract_synonyms(g: rdflib.Graph, term_ids: Set[str]) -> List[Dict]:
    """Extract alternative terms and synonyms.

    Args:
        g: RDF graph
        term_ids: Set of MeSH IDs to include

    Returns:
        List of synonym dictionaries
    """
    logger.info("Extracting synonyms...")

    synonyms = []

    for subject in g.subjects(predicate=rdflib.RDF.type, object=MESHV.Descriptor):
        mesh_id = extract_mesh_id(subject)

        if mesh_id not in term_ids:
            continue

        # Get alternative labels
        for alt_label in g.objects(subject, SKOS.altLabel):
            synonyms.append({
                "mesh_id": mesh_id,
                "synonym": str(alt_label),
                "type": "alternative"
            })

    logger.info(f"✓ Extracted {len(synonyms)} synonyms")
    return synonyms


def write_csv_files(terms: List[Dict], relationships: List[Dict], synonyms: List[Dict]):
    """Write extracted data to CSV files.

    Args:
        terms: MeSH terms
        relationships: Hierarchical relationships
        synonyms: Alternative terms
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write terms
    terms_file = OUTPUT_DIR / "mesh_terms.csv"
    logger.info(f"Writing {terms_file}")
    with open(terms_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mesh_id", "label", "definition", "uri"])
        writer.writeheader()
        writer.writerows(terms)

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

    # Calculate file sizes
    terms_size = terms_file.stat().st_size / 1024
    rels_size = rels_file.stat().st_size / 1024
    syns_size = syns_file.stat().st_size / 1024
    total_size = terms_size + rels_size + syns_size

    logger.info("")
    logger.info("✓ CSV files created:")
    logger.info(f"  - {terms_file.name}: {terms_size:.1f} KB")
    logger.info(f"  - {rels_file.name}: {rels_size:.1f} KB")
    logger.info(f"  - {syns_file.name}: {syns_size:.1f} KB")
    logger.info(f"  Total: {total_size:.1f} KB ({total_size/1024:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Convert MeSH RDF to CSV")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Convert all MeSH terms (30K+, slower)",
    )
    parser.add_argument(
        "--curated",
        action="store_true",
        default=True,
        help="Convert curated subset (~1000 terms, default)",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("MeSH RDF to CSV Converter")
    logger.info("=" * 70)

    if args.full:
        logger.info("Mode: FULL (all MeSH terms)")
        curated_only = False
    else:
        logger.info("Mode: CURATED (metabolic/environmental subset)")
        curated_only = True

    # Load RDF graph
    graph = load_rdf_graph(INPUT_FILE)

    # Extract data
    terms = extract_terms(graph, curated_only=curated_only)
    term_ids = {t["mesh_id"] for t in terms}
    relationships = extract_relationships(graph, term_ids)
    synonyms = extract_synonyms(graph, term_ids)

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
