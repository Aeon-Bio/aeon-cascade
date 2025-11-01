"""Base classes for ontology ingestion using Abstract Factory pattern.

This provides a unified interface for downloading, parsing, and converting
different biomedical ontologies (MeSH, CHEBI, GO, CTD, etc.) into a common
knowledge graph format.

Design Pattern: Abstract Factory + Template Method
- OntologyDownloader: Downloads ontology files from various sources
- OntologyParser: Parses different formats (RDF, OWL, OBO, TSV)
- OntologyConverter: Converts to Writer KG CSV format

All ontologies flow through the same pipeline:
  Download → Parse → Convert → Upload to KG
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set


class OntologyFormat(Enum):
    """Supported ontology formats."""

    RDF_NTRIPLES = "nt"  # MeSH, some CHEBI
    RDF_TURTLE = "ttl"  # CHEBI, GO
    OWL = "owl"  # GO, many bio-ontologies
    OBO = "obo"  # GO, legacy format
    TSV = "tsv"  # CTD (Comparative Toxicogenomics Database)
    CSV = "csv"  # Custom formats


@dataclass
class OntologyTerm:
    """Unified representation of an ontology term.

    All parsers convert their native format to this common structure.
    """

    term_id: str  # Ontology-specific ID (e.g., "MESH:D052638", "CHEBI:29678")
    label: str  # Human-readable name
    definition: str  # Full definition/description
    synonyms: List[str]  # Alternative names
    relationships: Dict[str, List[str]]  # {relation_type: [target_ids]}
    xrefs: Dict[str, str]  # Cross-references to other ontologies


class OntologyDownloader(ABC):
    """Abstract base class for downloading ontology files.

    Each ontology source (NLM, EBI, OBO Foundry, etc.) has its own downloader.
    """

    def __init__(self, output_dir: Path):
        """Initialize downloader.

        Args:
            output_dir: Directory to save downloaded files
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def download(self) -> Path:
        """Download ontology file.

        Returns:
            Path to downloaded file

        Raises:
            DownloadError: If download fails
        """
        pass

    @abstractmethod
    def get_url(self) -> str:
        """Get download URL for this ontology."""
        pass

    @abstractmethod
    def get_expected_format(self) -> OntologyFormat:
        """Get expected file format."""
        pass


class OntologyParser(ABC):
    """Abstract base class for parsing ontology files.

    Each format (RDF, OWL, OBO, TSV) has its own parser.
    Parsers are stateless - they take a file path and yield terms.
    """

    @abstractmethod
    def parse(
        self, file_path: Path, target_ids: Optional[Set[str]] = None
    ) -> Iterator[OntologyTerm]:
        """Parse ontology file and yield terms.

        Args:
            file_path: Path to ontology file
            target_ids: Optional set of IDs to extract (for efficiency)
                       If None, extract all terms

        Yields:
            OntologyTerm objects
        """
        pass

    @abstractmethod
    def supports_format(self, format: OntologyFormat) -> bool:
        """Check if this parser supports the given format."""
        pass


class OntologyConverter(ABC):
    """Abstract base class for converting terms to KG format.

    Converts from unified OntologyTerm representation to target KG format
    (Writer CSV, Neo4j Cypher, RDF triples, etc.)
    """

    @abstractmethod
    def convert(
        self, terms: Iterator[OntologyTerm], output_path: Path
    ) -> int:
        """Convert terms to target format.

        Args:
            terms: Iterator of OntologyTerm objects
            output_path: Where to write converted data

        Returns:
            Number of terms converted
        """
        pass


class OntologyIngestionPipeline:
    """Template method pattern for ontology ingestion.

    This orchestrates the download → parse → convert → upload workflow.
    Concrete implementations provide specific downloader/parser/converter.
    """

    def __init__(
        self,
        downloader: OntologyDownloader,
        parser: OntologyParser,
        converter: OntologyConverter,
        target_ids: Optional[Set[str]] = None,
    ):
        """Initialize pipeline.

        Args:
            downloader: Ontology downloader
            parser: Ontology parser
            converter: Format converter
            target_ids: Optional set of IDs to extract (None = all)
        """
        self.downloader = downloader
        self.parser = parser
        self.converter = converter
        self.target_ids = target_ids

    def run(self, download_dir: Path, output_path: Path) -> int:
        """Run complete ingestion pipeline.

        Template method that orchestrates the workflow:
        1. Download ontology file
        2. Parse to OntologyTerm objects
        3. Convert to target KG format
        4. (Upload handled separately)

        Args:
            download_dir: Directory for downloaded files
            output_path: Where to write converted output

        Returns:
            Number of terms processed

        Raises:
            PipelineError: If any step fails
        """
        # Step 1: Download
        file_path = self.downloader.download()

        # Step 2: Parse
        terms = self.parser.parse(file_path, target_ids=self.target_ids)

        # Step 3: Convert
        num_terms = self.converter.convert(terms, output_path)

        return num_terms


# Concrete implementations follow below for each ontology


class MeSHDownloader(OntologyDownloader):
    """Download MeSH from NLM."""

    def __init__(self, output_dir: Path, year: int = 2025):
        super().__init__(output_dir)
        self.year = year

    def get_url(self) -> str:
        return f"https://nlmpubs.nlm.nih.gov/projects/mesh/rdf/{self.year}/mesh{self.year}.nt.gz"

    def get_expected_format(self) -> OntologyFormat:
        return OntologyFormat.RDF_NTRIPLES

    def download(self) -> Path:
        """Download MeSH N-Triples file."""
        import httpx

        output_file = self.output_dir / f"mesh{self.year}.nt.gz"

        if output_file.exists():
            return output_file

        url = self.get_url()

        with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as response:
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        return output_file


class CHEBIDownloader(OntologyDownloader):
    """Download CHEBI from EBI."""

    def get_url(self) -> str:
        return "https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi.owl.gz"

    def get_expected_format(self) -> OntologyFormat:
        return OntologyFormat.OWL

    def download(self) -> Path:
        """Download CHEBI OWL file."""
        import httpx

        output_file = self.output_dir / "chebi.owl.gz"

        if output_file.exists():
            return output_file

        url = self.get_url()

        with httpx.stream("GET", url, timeout=600.0, follow_redirects=True) as response:
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        return output_file


class CTDDownloader(OntologyDownloader):
    """Download CTD (Comparative Toxicogenomics Database) chemical-gene associations."""

    def get_url(self) -> str:
        # CTD provides TSV files
        return "http://ctdbase.org/reports/CTD_chem_gene_ixns.tsv.gz"

    def get_expected_format(self) -> OntologyFormat:
        return OntologyFormat.TSV

    def download(self) -> Path:
        """Download CTD chemical-gene interactions."""
        import httpx

        output_file = self.output_dir / "ctd_chem_gene_ixns.tsv.gz"

        if output_file.exists():
            return output_file

        url = self.get_url()

        with httpx.stream("GET", url, timeout=600.0, follow_redirects=True) as response:
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        return output_file


class GODownloader(OntologyDownloader):
    """Download Gene Ontology from OBO Foundry."""

    def get_url(self) -> str:
        return "http://purl.obolibrary.org/obo/go.owl"

    def get_expected_format(self) -> OntologyFormat:
        return OntologyFormat.OWL

    def download(self) -> Path:
        """Download GO OWL file."""
        import httpx

        output_file = self.output_dir / "go.owl"

        if output_file.exists():
            return output_file

        url = self.get_url()

        with httpx.stream("GET", url, timeout=600.0, follow_redirects=True) as response:
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)

        return output_file


# Example usage pattern:
"""
# For MeSH
mesh_pipeline = OntologyIngestionPipeline(
    downloader=MeSHDownloader(Path("data")),
    parser=MeSHParser(),
    converter=WriterCSVConverter(),
    target_ids=ENVIRONMENTAL_HEALTH_MESH_IDS
)

mesh_pipeline.run(
    download_dir=Path("data"),
    output_path=Path("output/mesh_environmental.csv")
)

# For CHEBI (same interface!)
chebi_pipeline = OntologyIngestionPipeline(
    downloader=CHEBIDownloader(Path("data")),
    parser=CHEBIParser(),
    converter=WriterCSVConverter(),
    target_ids=POLLUTION_CHEMICAL_IDS
)

chebi_pipeline.run(
    download_dir=Path("data"),
    output_path=Path("output/chebi_chemicals.csv")
)

# For CTD (environmental → gene associations)
ctd_pipeline = OntologyIngestionPipeline(
    downloader=CTDDownloader(Path("data")),
    parser=CTDParser(),
    converter=WriterCSVConverter(),
    target_ids=None  # Extract all environmental exposures
)

ctd_pipeline.run(
    download_dir=Path("data"),
    output_path=Path("output/ctd_exposures.csv")
)
"""
