"""Concrete parser implementations for different ontology formats.

Implements parsers for:
- RDF N-Triples (MeSH)
- OWL (CHEBI, GO)
- TSV (CTD)

All parsers yield OntologyTerm objects for unified downstream processing.
"""

import csv
import gzip
import re
from pathlib import Path
from typing import Dict, Iterator, Optional, Set

from ontology_base import (
    OntologyFormat,
    OntologyParser,
    OntologyTerm,
)


class MeSHParser(OntologyParser):
    """Parse MeSH RDF N-Triples format.

    MeSH uses RDF with specific vocabularies:
    - rdf-schema#label → term label
    - meshv:scopeNote → definition
    - meshv:preferredConcept → cross-references
    """

    def supports_format(self, format: OntologyFormat) -> bool:
        return format == OntologyFormat.RDF_NTRIPLES

    def parse(
        self, file_path: Path, target_ids: Optional[Set[str]] = None
    ) -> Iterator[OntologyTerm]:
        """Parse MeSH N-Triples file.

        Args:
            file_path: Path to mesh2025.nt.gz or .nt file
            target_ids: Optional set of MeSH IDs (e.g., {"D052638", "D000393"})

        Yields:
            OntologyTerm objects
        """
        # Accumulate term data across multiple triples
        terms_data: Dict[str, Dict] = {}

        # Open file (auto-detect gzip)
        if file_path.suffix == ".gz":
            f = gzip.open(file_path, "rt", encoding="utf-8", errors="ignore")
        else:
            f = open(file_path, "r", encoding="utf-8", errors="ignore")

        try:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extract MeSH ID from subject URI
                # Format: <http://id.nlm.nih.gov/mesh/2025/D052638>
                mesh_id_match = re.search(r"mesh/\d+/([DCA]\d{6})>", line)
                if not mesh_id_match:
                    continue

                mesh_id = mesh_id_match.group(1)

                # Filter by target IDs if specified
                if target_ids and mesh_id not in target_ids:
                    continue

                # Initialize term data
                if mesh_id not in terms_data:
                    terms_data[mesh_id] = {
                        "term_id": f"MESH:{mesh_id}",
                        "label": "",
                        "definition": "",
                        "synonyms": [],
                        "relationships": {},
                        "xrefs": {},
                    }

                # Parse predicate-object pairs
                if "rdf-schema#label" in line:
                    # Extract label
                    label_match = re.search(r'"([^"]+)"', line)
                    if label_match:
                        label = label_match.group(1).split("@")[0]
                        # Skip qualifier labels (e.g., "Term/adverse effects")
                        if "/" not in label or label.split("/")[0].strip() == label:
                            terms_data[mesh_id]["label"] = label

                elif "vocab#scopeNote" in line:
                    # Extract definition
                    def_match = re.search(r'"([^"]+)"', line)
                    if def_match:
                        terms_data[mesh_id]["definition"] = def_match.group(1)

                elif "vocab#altLabel" in line:
                    # Extract synonym
                    syn_match = re.search(r'"([^"]+)"', line)
                    if syn_match:
                        synonym = syn_match.group(1).split("@")[0]
                        terms_data[mesh_id]["synonyms"].append(synonym)

        finally:
            f.close()

        # Yield complete terms
        for term_data in terms_data.values():
            # Use ID as label if missing
            if not term_data["label"]:
                term_data["label"] = term_data["term_id"].split(":")[-1]

            yield OntologyTerm(**term_data)


class CHEBIParser(OntologyParser):
    """Parse CHEBI OWL format.

    CHEBI uses OWL ontology format with chemistry-specific annotations.
    For now, this is a placeholder - full OWL parsing requires owlready2.
    """

    def supports_format(self, format: OntologyFormat) -> bool:
        return format == OntologyFormat.OWL

    def parse(
        self, file_path: Path, target_ids: Optional[Set[str]] = None
    ) -> Iterator[OntologyTerm]:
        """Parse CHEBI OWL file.

        TODO: Implement full OWL parsing with owlready2.
        For now, returns empty iterator.

        Args:
            file_path: Path to chebi.owl.gz
            target_ids: Optional set of CHEBI IDs

        Yields:
            OntologyTerm objects
        """
        # Placeholder - requires owlready2 library
        # from owlready2 import get_ontology
        #
        # onto = get_ontology(str(file_path)).load()
        # for entity in onto.individuals():
        #     if target_ids and entity.name not in target_ids:
        #         continue
        #
        #     yield OntologyTerm(
        #         term_id=f"CHEBI:{entity.name}",
        #         label=entity.label.first() if entity.label else entity.name,
        #         definition=entity.IAO_0000115.first() if hasattr(entity, 'IAO_0000115') else "",
        #         synonyms=[],
        #         relationships={},
        #         xrefs={}
        #     )

        return iter([])  # Placeholder


class CTDParser(OntologyParser):
    """Parse CTD TSV format.

    CTD provides chemical-gene interaction data in TSV format.
    This is CRITICAL for environmental exposures → molecular targets.

    Columns:
    - ChemicalName, ChemicalID (MESH ID)
    - GeneSymbol, GeneID
    - InteractionActions (increases^decreases^affects...)
    - PubMedIDs (evidence)
    """

    def supports_format(self, format: OntologyFormat) -> bool:
        return format == OntologyFormat.TSV

    def parse(
        self, file_path: Path, target_ids: Optional[Set[str]] = None
    ) -> Iterator[OntologyTerm]:
        """Parse CTD chemical-gene interactions.

        Args:
            file_path: Path to CTD_chem_gene_ixns.tsv.gz
            target_ids: Optional set of chemical names or MESH IDs

        Yields:
            OntologyTerm objects representing chemical → gene relationships
        """
        # Open file (auto-detect gzip)
        if file_path.suffix == ".gz":
            f = gzip.open(file_path, "rt", encoding="utf-8", errors="ignore")
        else:
            f = open(file_path, "r", encoding="utf-8", errors="ignore")

        try:
            # CTD TSV has header lines starting with #
            # Skip until we find column headers
            for line in f:
                if line.startswith("# Fields:"):
                    # Next line is column headers
                    break

            # Read TSV with csv.DictReader
            reader = csv.DictReader(
                f, delimiter="\t", quoting=csv.QUOTE_NONE
            )

            # Accumulate interactions by chemical
            chemical_data: Dict[str, Dict] = {}

            for row in reader:
                try:
                    chem_name = row.get("ChemicalName", "")
                    chem_id = row.get("ChemicalID", "")  # Format: "MESH:D052638"
                    gene_symbol = row.get("GeneSymbol", "")
                    gene_id = row.get("GeneID", "")
                    interaction = row.get("InteractionActions", "")
                    pubmed_ids = row.get("PubMedIDs", "")

                    if not chem_name or not gene_symbol:
                        continue

                    # Filter by target IDs if specified
                    if target_ids and (
                        chem_name not in target_ids and chem_id not in target_ids
                    ):
                        continue

                    # Initialize chemical term
                    if chem_id not in chemical_data:
                        chemical_data[chem_id] = {
                            "term_id": chem_id,
                            "label": chem_name,
                            "definition": f"Environmental chemical with molecular interactions (from CTD)",
                            "synonyms": [],
                            "relationships": {},
                            "xrefs": {},
                        }

                    # Add gene interaction as relationship
                    if "affects" not in chemical_data[chem_id]["relationships"]:
                        chemical_data[chem_id]["relationships"]["affects"] = []

                    # Store interaction: gene + action + evidence
                    interaction_str = (
                        f"{gene_symbol} ({interaction}; PMID:{pubmed_ids})"
                    )
                    chemical_data[chem_id]["relationships"]["affects"].append(
                        interaction_str
                    )

                except (KeyError, ValueError):
                    continue

        finally:
            f.close()

        # Yield complete chemical terms with all interactions
        for term_data in chemical_data.values():
            yield OntologyTerm(**term_data)


class GOParser(OntologyParser):
    """Parse Gene Ontology OWL format.

    GO uses OWL with specific biological process annotations.
    This is a placeholder - requires owlready2 for full implementation.
    """

    def supports_format(self, format: OntologyFormat) -> bool:
        return format == OntologyFormat.OWL

    def parse(
        self, file_path: Path, target_ids: Optional[Set[str]] = None
    ) -> Iterator[OntologyTerm]:
        """Parse GO OWL file.

        TODO: Implement with owlready2.
        """
        return iter([])  # Placeholder


# Parser factory (simple factory pattern)
def get_parser(format: OntologyFormat) -> OntologyParser:
    """Get appropriate parser for ontology format.

    Args:
        format: OntologyFormat enum

    Returns:
        Parser instance

    Raises:
        ValueError: If format not supported
    """
    parsers = {
        OntologyFormat.RDF_NTRIPLES: MeSHParser(),
        OntologyFormat.OWL: CHEBIParser(),  # Placeholder
        OntologyFormat.TSV: CTDParser(),
    }

    parser = parsers.get(format)
    if not parser:
        raise ValueError(f"No parser available for format: {format}")

    return parser
