"""Unit tests for WriterKGService ontology ID extraction methods.

These tests validate the extraction methods work correctly with synthetic data,
without requiring Writer KG to be indexed yet.

Run with: pytest tests/test_writer_kg_service_extraction.py -v -s
"""

import pytest
from indra_agent.services.writer_kg_service import WriterKGService


class TestOntologyIDExtraction:
    """Test ontology ID extraction methods."""

    def setup_method(self):
        """Create service instance for each test."""
        self.service = WriterKGService()

    @pytest.mark.asyncio
    async def teardown_method(self):
        """Clean up service after each test."""
        await self.service.cleanup()

    def test_extract_mesh_id(self):
        """Test MeSH ID extraction from text."""
        answer = "The MeSH ID for particulate matter is D052638."
        mesh_id = self.service._extract_mesh_id_from_answer(answer)

        assert mesh_id == "D052638"
        print(f"✅ Extracted MeSH ID: {mesh_id}")

    def test_extract_chebi_id(self):
        """Test CHEBI ID extraction from text."""
        test_cases = [
            ("Lead has CHEBI:25016 identifier", "CHEBI:25016"),
            ("The CHEBI ID is chebi:16716", "CHEBI:16716"),  # Case insensitive
            ("Chemical CHEBI 16842 is formaldehyde", "CHEBI:16842"),  # Space separator
        ]

        for text, expected in test_cases:
            chebi_id = self.service._extract_chebi_id_from_answer(text)
            assert chebi_id == expected
            print(f"✅ Extracted CHEBI ID from '{text[:40]}...': {chebi_id}")

    def test_extract_go_id(self):
        """Test GO ID extraction from text."""
        test_cases = [
            ("Oxidative stress is GO:0006979", "GO:0006979"),
            ("The process go:0045454 involves...", "GO:0045454"),  # Case insensitive
            ("GO 0006915 is apoptosis", "GO:0006915"),  # Space separator
        ]

        for text, expected in test_cases:
            go_id = self.service._extract_go_id_from_answer(text)
            assert go_id == expected
            print(f"✅ Extracted GO ID from '{text[:40]}...': {go_id}")

    def test_extract_all_ontology_ids(self):
        """Test unified extraction of all ontology IDs."""
        text = """
        Lead (CHEBI:25016) is a heavy metal (D007854 in MeSH).
        It causes oxidative stress (GO:0006979) by activating NFKB1.
        Benzene (CHEBI:16716) also affects inflammatory pathways.
        Particulate matter D052638 increases CRP levels.
        """

        ids = self.service._extract_all_ontology_ids(text)

        # Check MeSH IDs
        assert "D007854" in ids["mesh_ids"]
        assert "D052638" in ids["mesh_ids"]
        print(f"✅ MeSH IDs: {ids['mesh_ids']}")

        # Check CHEBI IDs
        assert "CHEBI:25016" in ids["chebi_ids"]
        assert "CHEBI:16716" in ids["chebi_ids"]
        print(f"✅ CHEBI IDs: {ids['chebi_ids']}")

        # Check GO IDs
        assert "GO:0006979" in ids["go_ids"]
        print(f"✅ GO IDs: {ids['go_ids']}")

        # Check gene symbols (NFKB1 should be detected)
        assert "NFKB1" in ids["hgnc_symbols"]
        print(f"✅ Gene symbols: {ids['hgnc_symbols']}")

    def test_build_indra_formats(self):
        """Test INDRA query format building."""
        ids = {
            "mesh_ids": ["D052638"],
            "chebi_ids": ["CHEBI:25016"],
            "go_ids": ["GO:0006979"],
            "hgnc_symbols": ["NFKB1"],
        }

        formats = self.service._build_indra_formats(ids)

        # Check MeSH format
        assert formats["mesh"] == "MESH:D052638"
        print(f"✅ MeSH INDRA format: {formats['mesh']}")

        # Check CHEBI format (CRITICAL: must have @CHEBI suffix)
        assert formats["chebi"] == "CHEBI:25016@CHEBI"
        print(f"✅ CHEBI INDRA format: {formats['chebi']}")

        # Check GO format
        assert formats["go"] == "GO:0006979"
        print(f"✅ GO INDRA format: {formats['go']}")

    def test_build_indra_formats_empty(self):
        """Test INDRA format building with no IDs."""
        ids = {
            "mesh_ids": [],
            "chebi_ids": [],
            "go_ids": [],
            "hgnc_symbols": [],
        }

        formats = self.service._build_indra_formats(ids)

        assert formats == {}
        print(f"✅ Empty IDs produce empty formats: {formats}")

    def test_build_indra_formats_partial(self):
        """Test INDRA format building with only CHEBI ID."""
        ids = {
            "mesh_ids": [],
            "chebi_ids": ["CHEBI:16716"],
            "go_ids": [],
            "hgnc_symbols": [],
        }

        formats = self.service._build_indra_formats(ids)

        assert "chebi" in formats
        assert formats["chebi"] == "CHEBI:16716@CHEBI"
        assert "mesh" not in formats
        assert "go" not in formats
        print(f"✅ Partial IDs (CHEBI only): {formats}")

    def test_extract_multiple_mesh_ids(self):
        """Test extraction of multiple MeSH IDs."""
        text = """
        Air pollution contains D052638 (PM2.5), D001554 (Benzene),
        and C029424 (formaldehyde).
        """

        ids = self.service._extract_all_ontology_ids(text)

        assert len(ids["mesh_ids"]) >= 2
        assert "D052638" in ids["mesh_ids"]
        assert "D001554" in ids["mesh_ids"]
        print(f"✅ Multiple MeSH IDs: {ids['mesh_ids']}")

    def test_extract_labels_from_result(self):
        """Test label extraction from Writer KG result."""
        result = {
            "answer": "D052638 is Particulate Matter, a component of air pollution. CHEBI:25016 (lead atom) is a heavy metal."
        }

        ids = {
            "mesh_ids": ["D052638"],
            "chebi_ids": ["CHEBI:25016"],
            "go_ids": [],
            "hgnc_symbols": []
        }

        labels = self.service._extract_labels_from_result(result, ids)

        # Check MeSH label
        assert "mesh" in labels
        assert "Particulate Matter" in labels["mesh"]
        print(f"✅ MeSH label: {labels['mesh']}")

        # Check CHEBI label
        assert "chebi" in labels
        assert "lead atom" in labels["chebi"]
        print(f"✅ CHEBI label: {labels['chebi']}")


class TestEdgeCases:
    """Test edge cases and error handling."""

    def setup_method(self):
        """Create service instance for each test."""
        self.service = WriterKGService()

    @pytest.mark.asyncio
    async def teardown_method(self):
        """Clean up service after each test."""
        await self.service.cleanup()

    def test_extract_mesh_id_no_match(self):
        """Test MeSH extraction when no ID present."""
        answer = "This text contains no MeSH IDs."
        mesh_id = self.service._extract_mesh_id_from_answer(answer)

        assert mesh_id is None
        print(f"✅ No MeSH ID found (expected): {mesh_id}")

    def test_extract_chebi_id_no_match(self):
        """Test CHEBI extraction when no ID present."""
        answer = "This text contains no CHEBI IDs."
        chebi_id = self.service._extract_chebi_id_from_answer(answer)

        assert chebi_id is None
        print(f"✅ No CHEBI ID found (expected): {chebi_id}")

    def test_extract_go_id_no_match(self):
        """Test GO extraction when no ID present."""
        answer = "This text contains no GO IDs."
        go_id = self.service._extract_go_id_from_answer(answer)

        assert go_id is None
        print(f"✅ No GO ID found (expected): {go_id}")

    def test_extract_all_ontology_ids_empty(self):
        """Test extraction from empty text."""
        ids = self.service._extract_all_ontology_ids("")

        assert len(ids["mesh_ids"]) == 0
        assert len(ids["chebi_ids"]) == 0
        assert len(ids["go_ids"]) == 0
        print(f"✅ Empty text produces empty results: {ids}")

    def test_extract_chebi_id_case_insensitive(self):
        """Test CHEBI extraction is case insensitive."""
        test_cases = [
            "CHEBI:25016",
            "chebi:25016",
            "ChEbI:25016",
            "Chebi:25016",
        ]

        for text in test_cases:
            chebi_id = self.service._extract_chebi_id_from_answer(text)
            assert chebi_id == "CHEBI:25016"
            print(f"✅ Case insensitive CHEBI extraction: '{text}' → {chebi_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
