"""Unit tests for biological prior knowledge system.

Tests the prior knowledge data structures and utility functions used
by the SCM graph builder for causal discovery fallback.
"""

import pytest
from indra_agent.config.biological_priors import (
    ENVIRONMENTAL_TO_MOLECULAR,
    KNOWN_MEDIATORS,
    MOLECULAR_CASCADES,
    get_all_prior_edges,
    get_mediators_between,
    get_prior_edge,
    is_known_mediator,
    normalize_entity_name,
)


class TestEntityNormalization:
    """Test entity name normalization for INDRA queries."""

    def test_normalize_environmental_entities(self):
        """Test normalization of environmental exposure terms."""
        assert normalize_entity_name("PM2.5") == "Particulate Matter"
        assert normalize_entity_name("PM10") == "Particulate Matter"
        assert normalize_entity_name("O3") == "Ozone"
        assert normalize_entity_name("NO2") == "Nitrogen Dioxide"

    def test_normalize_molecular_entities(self):
        """Test normalization of molecular entity names."""
        assert normalize_entity_name("ROS") == "reactive oxygen species"
        assert normalize_entity_name("NF-κB") == "NFKB1"
        assert normalize_entity_name("NFκB") == "NFKB1"
        assert normalize_entity_name("NF-kappaB") == "NFKB1"

    def test_normalize_cytokines(self):
        """Test normalization of cytokine names."""
        assert normalize_entity_name("TNF-α") == "TNF"
        assert normalize_entity_name("TNF-alpha") == "TNF"
        assert normalize_entity_name("IL-1β") == "IL1B"
        assert normalize_entity_name("IL-1beta") == "IL1B"
        assert normalize_entity_name("IL-6") == "IL6"
        assert normalize_entity_name("IL-8") == "IL8"

    def test_normalize_acute_phase_proteins(self):
        """Test normalization of acute phase protein names."""
        assert normalize_entity_name("C-reactive protein") == "CRP"
        assert normalize_entity_name("C-Reactive Protein") == "CRP"

    def test_normalize_unknown_entity(self):
        """Test that unknown entities pass through unchanged."""
        assert normalize_entity_name("UNKNOWN_ENTITY") == "UNKNOWN_ENTITY"
        assert normalize_entity_name("Some Random Term") == "Some Random Term"


class TestPriorEdgeRetrieval:
    """Test retrieval of prior knowledge edges."""

    def test_get_environmental_to_molecular_edge(self):
        """Test retrieval of environmental → molecular edges."""
        prior = get_prior_edge("Particulate Matter", "reactive oxygen species")
        assert prior is not None
        assert prior["belief"] == 0.92
        assert prior["mechanism"] == "mitochondrial_dysfunction"
        assert prior["evidence_count"] == 150

    def test_get_environmental_to_molecular_with_normalization(self):
        """Test retrieval with entity name normalization."""
        # Test with synonym that needs normalization
        prior = get_prior_edge("PM2.5", "ROS")
        assert prior is not None
        assert prior["belief"] == 0.92  # Same as Particulate Matter → ROS

    def test_get_molecular_cascade_edge(self):
        """Test retrieval of molecular cascade edges."""
        prior = get_prior_edge("NFKB1", "IL6")
        assert prior is not None
        assert prior["belief"] == 0.96
        assert prior["mechanism"] == "transcription_factor"
        assert prior["evidence_count"] == 500

    def test_get_il6_to_crp_edge(self):
        """Test the canonical IL-6 → CRP edge."""
        prior = get_prior_edge("IL6", "CRP")
        assert prior is not None
        assert prior["belief"] == 0.98  # Highest belief score
        assert prior["mechanism"] == "hepatic_acute_phase_response"
        assert prior["evidence_count"] == 600  # Highest evidence count

    def test_get_nonexistent_edge(self):
        """Test retrieval of non-existent edge."""
        prior = get_prior_edge("PM2.5", "NOTAREALENTITY")
        assert prior is None

        prior = get_prior_edge("ENTITY1", "ENTITY2")
        assert prior is None


class TestKnownMediators:
    """Test known mediator identification and retrieval."""

    def test_is_known_mediator_oxidative_stress(self):
        """Test identification of oxidative stress mediators."""
        assert is_known_mediator("reactive oxygen species")
        assert is_known_mediator("oxidative stress")
        assert is_known_mediator("superoxide")

    def test_is_known_mediator_transcription_factors(self):
        """Test identification of transcription factor mediators."""
        assert is_known_mediator("NFKB1")
        assert is_known_mediator("RELA")
        assert is_known_mediator("STAT3")
        assert is_known_mediator("AP1")

    def test_is_known_mediator_cytokines(self):
        """Test identification of cytokine mediators."""
        assert is_known_mediator("TNF")
        assert is_known_mediator("IL1B")
        assert is_known_mediator("IL6")
        assert is_known_mediator("IL8")

    def test_is_known_mediator_with_normalization(self):
        """Test mediator identification with name normalization."""
        assert is_known_mediator("NF-κB")  # Normalizes to NFKB1
        assert is_known_mediator("IL-6")  # Normalizes to IL6

    def test_is_not_known_mediator(self):
        """Test that non-mediators return False."""
        assert not is_known_mediator("UNKNOWN_ENTITY")
        assert not is_known_mediator("PM2.5")  # Environmental, not mediator


class TestMediatorDiscovery:
    """Test discovery of mediators between source and target."""

    def test_get_mediators_pm25_to_crp(self):
        """Test mediator discovery for PM2.5 → CRP pathway."""
        mediators = get_mediators_between("Particulate Matter", "CRP")

        # Should include key inflammatory mediators
        mediator_set = set(mediators)
        expected_mediators = {"reactive oxygen species", "oxidative stress", "IL6"}

        # At least some of the expected mediators should be present
        assert len(mediator_set & expected_mediators) > 0, \
            f"Should find inflammatory mediators. Found: {mediators}"

    def test_get_mediators_with_normalization(self):
        """Test mediator discovery with entity name normalization."""
        mediators = get_mediators_between("PM2.5", "C-reactive protein")

        # Should normalize and find mediators
        assert len(mediators) > 0

    def test_get_mediators_ros_to_cytokines(self):
        """Test mediator discovery for oxidative stress → cytokines."""
        mediators = get_mediators_between("reactive oxygen species", "IL6")

        # Should include NF-κB (key transcription factor)
        assert "NFKB1" in mediators or "RELA" in mediators

    def test_get_mediators_no_connection(self):
        """Test mediator discovery when no clear path exists."""
        mediators = get_mediators_between("UNKNOWN1", "UNKNOWN2")

        # May return empty list or some default mediators
        # This is acceptable - the function is best-effort
        assert isinstance(mediators, list)


class TestPriorEdgeStructure:
    """Test structure and validity of prior knowledge edges."""

    def test_all_edges_have_required_fields(self):
        """Test that all prior edges have required metadata fields."""
        all_edges = get_all_prior_edges()

        for source, target, metadata in all_edges:
            # Check required fields exist
            assert "belief" in metadata
            assert "mechanism" in metadata
            assert "evidence_count" in metadata
            assert "rationale" in metadata

            # Check field types and ranges
            assert isinstance(metadata["belief"], float)
            assert 0 <= metadata["belief"] <= 1
            assert isinstance(metadata["evidence_count"], int)
            assert metadata["evidence_count"] > 0
            assert isinstance(metadata["mechanism"], str)
            assert len(metadata["mechanism"]) > 0
            assert isinstance(metadata["rationale"], str)
            assert len(metadata["rationale"]) > 0

    def test_edge_count(self):
        """Test that we have a reasonable number of prior edges."""
        all_edges = get_all_prior_edges()

        # Should have edges from both dictionaries
        assert len(all_edges) >= 10, "Should have at least 10 prior edges"

        # Count by type
        env_to_mol = len(ENVIRONMENTAL_TO_MOLECULAR)
        mol_cascades = len(MOLECULAR_CASCADES)

        assert env_to_mol > 0, "Should have environmental → molecular edges"
        assert mol_cascades > 0, "Should have molecular cascade edges"
        assert len(all_edges) == env_to_mol + mol_cascades

    def test_belief_scores_reasonable(self):
        """Test that belief scores are in reasonable ranges."""
        all_edges = get_all_prior_edges()

        for _, _, metadata in all_edges:
            belief = metadata["belief"]

            # Priors should have high belief (>= 0.8) since they're well-established
            assert belief >= 0.8, \
                f"Prior edges should have high belief (>= 0.8), got {belief}"

    def test_evidence_counts_reasonable(self):
        """Test that evidence counts are substantial."""
        all_edges = get_all_prior_edges()

        for _, _, metadata in all_edges:
            evidence_count = metadata["evidence_count"]

            # Priors should have substantial evidence (>= 50 papers)
            assert evidence_count >= 50, \
                f"Prior edges should have >= 50 papers, got {evidence_count}"


class TestKnownMediatorList:
    """Test the KNOWN_MEDIATORS list structure."""

    def test_mediators_list_not_empty(self):
        """Test that mediators list is populated."""
        assert len(KNOWN_MEDIATORS) > 0
        assert len(KNOWN_MEDIATORS) >= 10, "Should have at least 10 known mediators"

    def test_mediators_include_key_mechanisms(self):
        """Test that key biological mechanisms are included."""
        mediator_set = set(KNOWN_MEDIATORS)

        # Key oxidative stress mediators
        assert "reactive oxygen species" in mediator_set
        assert "oxidative stress" in mediator_set

        # Key transcription factors
        assert "NFKB1" in mediator_set or "RELA" in mediator_set

        # Key cytokines
        assert "IL6" in mediator_set
        assert "TNF" in mediator_set

        # Key acute phase protein
        assert "CRP" in mediator_set

    def test_mediators_are_unique(self):
        """Test that mediator list has no duplicates."""
        assert len(KNOWN_MEDIATORS) == len(set(KNOWN_MEDIATORS)), \
            "KNOWN_MEDIATORS should not contain duplicates"


class TestBiologicalPlausibility:
    """Test biological plausibility of prior knowledge."""

    def test_pm25_to_ros_pathway_exists(self):
        """Test that PM2.5 → ROS pathway is encoded."""
        prior = get_prior_edge("Particulate Matter", "reactive oxygen species")
        assert prior is not None
        assert prior["belief"] >= 0.9  # Should be very confident

    def test_ros_to_nfkb_pathway_exists(self):
        """Test that ROS → NF-κB pathway is encoded."""
        prior = get_prior_edge("reactive oxygen species", "NFKB1")
        assert prior is not None
        assert prior["belief"] >= 0.9  # Should be very confident

    def test_nfkb_to_cytokine_pathways_exist(self):
        """Test that NF-κB → cytokine pathways are encoded."""
        il6_prior = get_prior_edge("NFKB1", "IL6")
        tnf_prior = get_prior_edge("NFKB1", "TNF")

        assert il6_prior is not None
        assert tnf_prior is not None
        assert il6_prior["belief"] >= 0.9
        assert tnf_prior["belief"] >= 0.9

    def test_il6_to_crp_pathway_exists(self):
        """Test the canonical IL-6 → CRP acute phase response."""
        prior = get_prior_edge("IL6", "CRP")
        assert prior is not None
        assert prior["belief"] >= 0.95  # Should be extremely confident
        assert prior["evidence_count"] >= 500  # Should have extensive literature

    def test_full_pm25_to_crp_cascade(self):
        """Test that complete PM2.5 → CRP pathway can be constructed from priors."""
        # PM2.5 → ROS
        edge1 = get_prior_edge("Particulate Matter", "reactive oxygen species")
        assert edge1 is not None

        # ROS → NF-κB
        edge2 = get_prior_edge("reactive oxygen species", "NFKB1")
        assert edge2 is not None

        # NF-κB → IL-6
        edge3 = get_prior_edge("NFKB1", "IL6")
        assert edge3 is not None

        # IL-6 → CRP
        edge4 = get_prior_edge("IL6", "CRP")
        assert edge4 is not None

        # All edges should have high confidence
        for edge in [edge1, edge2, edge3, edge4]:
            assert edge["belief"] >= 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
