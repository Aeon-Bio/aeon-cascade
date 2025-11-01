"""Multi-ontology ingestion framework using Abstract Factory pattern.

Provides unified interface for downloading, parsing, and converting
biomedical ontologies (MeSH, CTD, CHEBI, GO) into knowledge graphs.

Key classes:
- OntologyDownloader: Downloads ontology files
- OntologyParser: Parses different formats (RDF, OWL, TSV)
- OntologyConverter: Converts to target KG format
- OntologyIngestionPipeline: Orchestrates download → parse → convert workflow

Example usage:
    from ontology_ingestion import OntologyRegistry

    # Create CTD pipeline (environmental exposures)
    pipeline = OntologyRegistry.create_pipeline("ctd")
    pipeline.run(download_dir="data", output_path="output/ctd.csv")

See README.md for full documentation.
"""

from ontology_base import (
    OntologyDownloader,
    OntologyParser,
    OntologyConverter,
    OntologyIngestionPipeline,
    OntologyTerm,
    OntologyFormat,
)

from parsers import (
    MeSHParser,
    CTDParser,
    CHEBIParser,
    GOParser,
    get_parser,
)

from converters import (
    WriterCSVConverter,
    ExtendedCSVConverter,
    Neo4jCypherConverter,
    get_converter,
)

__all__ = [
    # Base classes
    "OntologyDownloader",
    "OntologyParser",
    "OntologyConverter",
    "OntologyIngestionPipeline",
    "OntologyTerm",
    "OntologyFormat",
    # Parsers
    "MeSHParser",
    "CTDParser",
    "CHEBIParser",
    "GOParser",
    "get_parser",
    # Converters
    "WriterCSVConverter",
    "ExtendedCSVConverter",
    "Neo4jCypherConverter",
    "get_converter",
]

__version__ = "1.0.0"
