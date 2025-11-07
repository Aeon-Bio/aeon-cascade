#!/usr/bin/env python3
"""Transform MeSH RDF N-Triples to local_ontology_format CSV.

Parses MeSH 2025 RDF data and outputs CSV files compatible with ingest_to_local_ontology.py.

Input:
    data/mesh/mesh.nt (2.1GB N-Triples file)

Output:
    output/local_ontology_format/mesh/mesh.csv

CSV Schema (compatible with ingest_to_local_ontology.py):
    id,name,definition,synonyms

Usage:
    python transform_mesh.py
"""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Set

import rdflib
from rdflib import Namespace

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
INPUT_FILE = SCRIPT_DIR / "data" / "mesh" / "mesh.nt"
OUTPUT_DIR = SCRIPT_DIR / "output" / "local_ontology_format" / "mesh"
OUTPUT_FILE = OUTPUT_DIR / "mesh.csv"

# RDF Namespaces
MESH = Namespace("http://id.nlm.nih.gov/mesh/")
MESHV = Namespace("http://id.nlm.nih.gov/mesh/vocab#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")


def extract_mesh_id(uri: rdflib.URIRef) -> str:
    """Extract MeSH ID from URI (e.g., D052638)."""
    return str(uri).split("/")[-1]


def load_rdf_graph(input_file: Path) -> rdflib.Graph:
    """Load MeSH RDF graph from N-Triples file.

    This takes 5-15 minutes for the full 2.1GB file.
    """
    logger.info(f"Loading RDF graph from {input_file}")
    logger.info("This will take 5-15 minutes for full MeSH...")

    g = rdflib.Graph()

    try:
        with open(input_file, "rb") as f:
            g.parse(f, format="nt")

        logger.info(f"✓ Loaded {len(g):,} triples")
        return g

    except FileNotFoundError:
        logger.error(f"✗ Input file not found: {input_file}")
        logger.error("Expected location: data/mesh/mesh.nt")
        raise
    except Exception as e:
        logger.error(f"✗ Error loading RDF: {e}")
        raise


def extract_mesh_terms(g: rdflib.Graph) -> List[Dict]:
    """Extract all MeSH descriptors with labels, definitions, and synonyms.

    Returns list of dicts with schema: {id, name, definition, synonyms}
    """
    logger.info("Extracting MeSH descriptors...")

    terms = []
    term_count = 0
    seen_ids = set()

    # Query for all MeSH descriptor types (TopicalDescriptor, GeographicalDescriptor, etc.)
    descriptor_types = [
        MESHV.TopicalDescriptor,
        MESHV.GeographicalDescriptor,
        MESHV.PublicationType,
        MESHV.CheckTag,
        MESHV.Qualifier
    ]

    for descriptor_type in descriptor_types:
        for subject in g.subjects(predicate=rdflib.RDF.type, object=descriptor_type):
            mesh_id = extract_mesh_id(subject)

            # Skip if already processed
            if mesh_id in seen_ids:
                continue
            seen_ids.add(mesh_id)

            # Get preferred label (required)
            label = None
            for label_obj in g.objects(subject, RDFS.label):
                label = str(label_obj)
                break

            if not label:
                continue  # Skip descriptors without labels

            # Get scope note (definition) - optional
            definition = None
            for def_obj in g.objects(subject, MESHV.scopeNote):
                definition = str(def_obj)
                break

            # Get all synonyms (alternative labels)
            synonyms = []
            for alt_label in g.objects(subject, SKOS.altLabel):
                synonyms.append(str(alt_label))

            # Also include concept preferred terms as synonyms
            for concept in g.objects(subject, MESHV.concept):
                for concept_label in g.objects(concept, MESHV.prefLabel):
                    concept_label_str = str(concept_label)
                    if concept_label_str != label and concept_label_str not in synonyms:
                        synonyms.append(concept_label_str)

            terms.append({
                "id": mesh_id,
                "name": label,
                "definition": definition or "",
                "synonyms": "|".join(synonyms) if synonyms else ""
            })

            term_count += 1
            if term_count % 1000 == 0:
                logger.info(f"  Processed {term_count:,} descriptors...")

    logger.info(f"✓ Extracted {len(terms):,} MeSH descriptors")
    return terms


def write_csv(terms: List[Dict]):
    """Write terms to CSV file in local_ontology_format."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing {OUTPUT_FILE}")

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "definition", "synonyms"])
        writer.writeheader()
        writer.writerows(terms)

    file_size = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    logger.info(f"✓ Wrote {len(terms):,} terms ({file_size:.1f} MB)")


def main():
    logger.info("=" * 70)
    logger.info("MeSH RDF → local_ontology_format CSV Transformer")
    logger.info("=" * 70)
    logger.info("")

    # Load RDF graph (this is the slow part: 5-15 minutes)
    graph = load_rdf_graph(INPUT_FILE)

    # Extract terms (fast: ~1 minute)
    terms = extract_mesh_terms(graph)

    # Write CSV
    write_csv(terms)

    logger.info("")
    logger.info("✓ SUCCESS: Transformation complete")
    logger.info(f"Output file: {OUTPUT_FILE}")
    logger.info("")
    logger.info("Next step:")
    logger.info("  python ingest_to_local_ontology.py --namespaces MESH")


if __name__ == "__main__":
    main()
