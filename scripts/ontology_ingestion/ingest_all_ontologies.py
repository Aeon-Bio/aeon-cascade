#!/usr/bin/env python3
"""Unified multi-ontology ingestion pipeline.

Downloads and converts multiple biomedical ontologies into a unified KG:
1. MeSH (medical terms, diseases, chemicals)
2. CTD (environmental exposures → gene interactions) ← CRITICAL FOR US
3. CHEBI (chemical entities)
4. GO (biological processes)

All ontologies are converted to Writer KG CSV format and can be uploaded
as a single unified knowledge graph.

Usage:
    python ingest_all_ontologies.py [--ontologies mesh,ctd,chebi,go] [--download]

Design:
    Uses Abstract Factory pattern for ontology-agnostic ingestion.
    Each ontology provides: Downloader, Parser, Converter
    All flow through same pipeline: Download → Parse → Convert → Upload
"""

import argparse
import logging
from pathlib import Path
from typing import List, Set

from converters import WriterCSVConverter
from ontology_base import (
    CHEBIDownloader,
    CTDDownloader,
    GODownloader,
    MeSHDownloader,
    OntologyIngestionPipeline,
)
from parsers import CTDParser, MeSHParser

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "output"

# Curated term sets for each ontology
MESH_ENVIRONMENTAL_HEALTH = {
    # Environmental exposures
    "D052638",  # Particulate Matter
    "D000393",  # Air Pollutants
    "D010126",  # Ozone
    "D009585",  # Nitrogen Dioxide
    # Inflammatory biomarkers
    "D002097",  # C-Reactive Protein
    "D015850",  # Interleukin-6
    "D014409",  # Tumor Necrosis Factor-alpha
    # Metabolic biomarkers
    "D005947",  # Glucose
    "D007328",  # Insulin
    "D006442",  # Glycated Hemoglobin A (HbA1c)
    # Oxidative stress
    "D017382",  # Reactive Oxygen Species
    "D005978",  # Glutathione
    # Diseases
    "D003924",  # Diabetes Mellitus, Type 2
    "D007333",  # Insulin Resistance
    "D024821",  # Metabolic Syndrome
    # Molecular mechanisms
    "D016328",  # NF-kappa B
}

CTD_ENVIRONMENTAL_CHEMICALS = {
    # Air pollutants (CRITICAL - fills INDRA gap)
    "Particulate Matter",
    "Ozone",
    "Nitrogen Dioxide",
    "Sulfur Dioxide",
    "Carbon Monoxide",
    # Heavy metals
    "Lead",
    "Cadmium",
    "Arsenic",
    "Mercury",
    # Organic pollutants
    "Benzene",
    "Formaldehyde",
    "Benzo(a)pyrene",
    # Reactive species
    "Hydrogen Peroxide",
    "Superoxide",
    # Smoking
    "Cigarette Smoke",
    "Nicotine",
}


class OntologyRegistry:
    """Registry of available ontologies with their ingestion configs.

    This is the Abstract Factory - it knows how to create complete
    pipelines for each ontology type.
    """

    @staticmethod
    def get_mesh_pipeline() -> OntologyIngestionPipeline:
        """Create MeSH ingestion pipeline."""
        return OntologyIngestionPipeline(
            downloader=MeSHDownloader(DATA_DIR, year=2025),
            parser=MeSHParser(),
            converter=WriterCSVConverter(),
            target_ids=MESH_ENVIRONMENTAL_HEALTH,
        )

    @staticmethod
    def get_ctd_pipeline() -> OntologyIngestionPipeline:
        """Create CTD ingestion pipeline.

        THIS IS CRITICAL - CTD fills the environmental → molecular gap.
        """
        return OntologyIngestionPipeline(
            downloader=CTDDownloader(DATA_DIR),
            parser=CTDParser(),
            converter=WriterCSVConverter(),
            target_ids=CTD_ENVIRONMENTAL_CHEMICALS,
        )

    @staticmethod
    def get_chebi_pipeline() -> OntologyIngestionPipeline:
        """Create CHEBI ingestion pipeline.

        Note: CHEBI parser not yet implemented (requires owlready2).
        """
        from parsers import CHEBIParser

        return OntologyIngestionPipeline(
            downloader=CHEBIDownloader(DATA_DIR),
            parser=CHEBIParser(),
            converter=WriterCSVConverter(),
            target_ids=None,  # Extract all chemical entities
        )

    @staticmethod
    def get_go_pipeline() -> OntologyIngestionPipeline:
        """Create GO (Gene Ontology) ingestion pipeline.

        Note: GO parser not yet implemented (requires owlready2).
        """
        from parsers import GOParser

        return OntologyIngestionPipeline(
            downloader=GODownloader(DATA_DIR),
            parser=GOParser(),
            converter=WriterCSVConverter(),
            target_ids=None,  # Extract all biological processes
        )

    @staticmethod
    def get_available_ontologies() -> List[str]:
        """List available ontology names."""
        return ["mesh", "ctd", "chebi", "go"]

    @staticmethod
    def create_pipeline(ontology_name: str) -> OntologyIngestionPipeline:
        """Factory method to create pipeline for ontology.

        Args:
            ontology_name: One of: mesh, ctd, chebi, go

        Returns:
            Configured pipeline

        Raises:
            ValueError: If ontology name unknown
        """
        factories = {
            "mesh": OntologyRegistry.get_mesh_pipeline,
            "ctd": OntologyRegistry.get_ctd_pipeline,
            "chebi": OntologyRegistry.get_chebi_pipeline,
            "go": OntologyRegistry.get_go_pipeline,
        }

        factory = factories.get(ontology_name.lower())
        if not factory:
            raise ValueError(
                f"Unknown ontology: {ontology_name}. "
                f"Available: {OntologyRegistry.get_available_ontologies()}"
            )

        return factory()


def ingest_ontologies(ontology_names: List[str]) -> None:
    """Ingest multiple ontologies into unified KG.

    Args:
        ontology_names: List of ontology names to ingest
    """
    logger.info("=" * 70)
    logger.info("Multi-Ontology Ingestion Pipeline")
    logger.info("=" * 70)
    logger.info(f"Target ontologies: {', '.join(ontology_names)}")
    logger.info("")

    total_terms = 0
    output_files = []

    for ontology_name in ontology_names:
        logger.info(f"Processing: {ontology_name.upper()}")
        logger.info("-" * 70)

        try:
            # Create pipeline for this ontology
            pipeline = OntologyRegistry.create_pipeline(ontology_name)

            # Run ingestion
            output_path = OUTPUT_DIR / f"{ontology_name}_terms.csv"
            num_terms = pipeline.run(download_dir=DATA_DIR, output_path=output_path)

            logger.info(f"✓ {ontology_name.upper()}: {num_terms} terms extracted")
            logger.info(f"  Output: {output_path}")
            logger.info("")

            total_terms += num_terms
            output_files.append(output_path)

        except Exception as e:
            logger.error(f"✗ {ontology_name.upper()} failed: {e}")
            logger.info("")
            continue

    # Summary
    logger.info("=" * 70)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total terms: {total_terms}")
    logger.info(f"Output files: {len(output_files)}")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Review extracted terms in output/*.csv")
    logger.info("2. Merge CSVs (optional): cat output/*.csv > merged_kg.csv")
    logger.info("3. Upload to Writer KG: https://dev.writer.com/home/knowledge-graph")
    logger.info("4. Update WRITER_GRAPH_ID in .env")
    logger.info("")
    logger.info("🔗 CRITICAL: CTD provides environmental → molecular pathways")
    logger.info("   This fills the gap INDRA doesn't have!")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest multiple biomedical ontologies into unified KG"
    )
    parser.add_argument(
        "--ontologies",
        type=str,
        default="mesh,ctd",
        help="Comma-separated list of ontologies (default: mesh,ctd)",
    )
    parser.add_argument(
        "--download", action="store_true", help="Download ontology files first"
    )
    args = parser.parse_args()

    # Parse ontology names
    ontology_names = [name.strip() for name in args.ontologies.split(",")]

    # Validate ontology names
    available = OntologyRegistry.get_available_ontologies()
    for name in ontology_names:
        if name.lower() not in available:
            logger.error(f"Unknown ontology: {name}")
            logger.error(f"Available: {', '.join(available)}")
            return

    # Run ingestion
    try:
        ingest_ontologies(ontology_names)
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise


if __name__ == "__main__":
    main()
