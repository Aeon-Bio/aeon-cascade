"""Converters for transforming ontology terms to target KG formats.

Implements converters for:
- Writer KG CSV format (3-column: id, label, definition)
- Extended CSV with relationships and synonyms
- Future: Neo4j Cypher, RDF triples, etc.
"""

import csv
from pathlib import Path
from typing import Iterator

from ontology_base import OntologyConverter, OntologyTerm


class WriterCSVConverter(OntologyConverter):
    """Convert to Writer KG CSV format (3 columns: id, label, definition).

    Writer KG expects simple CSV with:
    - Column 1: Unique ID (e.g., "MESH:D052638")
    - Column 2: Label (human-readable name)
    - Column 3: Definition (optional description)

    Relationships and synonyms are discarded in this format.
    For full data, use ExtendedCSVConverter.
    """

    def convert(self, terms: Iterator[OntologyTerm], output_path: Path) -> int:
        """Convert terms to Writer CSV format.

        Args:
            terms: Iterator of OntologyTerm objects
            output_path: Where to write CSV file

        Returns:
            Number of terms written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["term_id", "label", "definition"]
            )
            writer.writeheader()

            for term in terms:
                writer.writerow(
                    {
                        "term_id": term.term_id,
                        "label": term.label,
                        "definition": term.definition,
                    }
                )
                count += 1

        return count


class ExtendedCSVConverter(OntologyConverter):
    """Convert to extended CSV format with all metadata.

    Creates TWO CSV files:
    1. {output}_terms.csv: id, label, definition, synonyms
    2. {output}_relationships.csv: source_id, relation, target_id

    This preserves all ontology data for advanced KG construction.
    """

    def convert(self, terms: Iterator[OntologyTerm], output_path: Path) -> int:
        """Convert terms to extended CSV format.

        Args:
            terms: Iterator of OntologyTerm objects
            output_path: Base path (will create _terms.csv and _relationships.csv)

        Returns:
            Number of terms written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create output paths
        terms_path = output_path.parent / f"{output_path.stem}_terms.csv"
        rels_path = output_path.parent / f"{output_path.stem}_relationships.csv"

        term_count = 0

        # Write terms file
        with open(terms_path, "w", newline="", encoding="utf-8") as terms_file:
            terms_writer = csv.DictWriter(
                terms_file,
                fieldnames=["term_id", "label", "definition", "synonyms", "xrefs"],
            )
            terms_writer.writeheader()

            # Write relationships file
            with open(rels_path, "w", newline="", encoding="utf-8") as rels_file:
                rels_writer = csv.DictWriter(
                    rels_file, fieldnames=["source_id", "relation", "target_id"]
                )
                rels_writer.writeheader()

                for term in terms:
                    # Write term
                    terms_writer.writerow(
                        {
                            "term_id": term.term_id,
                            "label": term.label,
                            "definition": term.definition,
                            "synonyms": "|".join(term.synonyms),
                            "xrefs": "|".join(
                                f"{k}:{v}" for k, v in term.xrefs.items()
                            ),
                        }
                    )

                    # Write relationships
                    for relation_type, targets in term.relationships.items():
                        for target in targets:
                            rels_writer.writerow(
                                {
                                    "source_id": term.term_id,
                                    "relation": relation_type,
                                    "target_id": target,
                                }
                            )

                    term_count += 1

        return term_count


class Neo4jCypherConverter(OntologyConverter):
    """Convert to Neo4j Cypher statements.

    Generates .cypher file with CREATE statements for nodes and relationships.
    Can be imported directly into Neo4j.

    Example output:
        CREATE (n:Term {id: 'MESH:D052638', label: 'Particulate Matter', ...})
        CREATE (n1:Term {id: 'MESH:D000393'})-[:RELATED_TO]->(n2:Term {id: 'MESH:D052638'})
    """

    def convert(self, terms: Iterator[OntologyTerm], output_path: Path) -> int:
        """Convert terms to Neo4j Cypher format.

        Args:
            terms: Iterator of OntologyTerm objects
            output_path: Where to write .cypher file

        Returns:
            Number of terms written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for term in terms:
                # Escape quotes in strings
                label_escaped = term.label.replace("'", "\\'")
                def_escaped = term.definition.replace("'", "\\'")

                # Create node
                f.write(
                    f"CREATE (n{count}:Term {{\n"
                    f"  id: '{term.term_id}',\n"
                    f"  label: '{label_escaped}',\n"
                    f"  definition: '{def_escaped}'\n"
                    f"}});\n"
                )

                # Create relationship edges
                for relation_type, targets in term.relationships.items():
                    for target in targets:
                        # This creates dangling references - targets must exist
                        # Real implementation would batch-create all nodes first
                        f.write(
                            f"MATCH (source:Term {{id: '{term.term_id}'}}), "
                            f"(target:Term {{id: '{target}'}})\n"
                            f"CREATE (source)-[:{relation_type}]->(target);\n"
                        )

                count += 1

        return count


# Converter factory
def get_converter(format: str) -> OntologyConverter:
    """Get appropriate converter for target format.

    Args:
        format: Target format ("writer_csv", "extended_csv", "neo4j")

    Returns:
        Converter instance

    Raises:
        ValueError: If format not supported
    """
    converters = {
        "writer_csv": WriterCSVConverter(),
        "extended_csv": ExtendedCSVConverter(),
        "neo4j": Neo4jCypherConverter(),
    }

    converter = converters.get(format)
    if not converter:
        raise ValueError(f"No converter available for format: {format}")

    return converter
