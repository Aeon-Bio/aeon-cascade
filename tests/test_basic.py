"""Basic tests for INDRA agent system."""

import pytest

from indra_agent.config.genetic_modifiers import get_genetic_modifier
from tests.fixtures.cached_indra_paths import get_cached_path
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    LocationHistory,
    Query,
    UserContext,
)
from indra_agent.services.grounding_service import GroundingService
from indra_agent.services.graph_builder import GraphBuilderService


def test_grounding_service():
    """Test entity grounding service."""
    service = GroundingService()

    # Test biomarker grounding
    crp = service.ground_entity("CRP")
    assert crp is not None
    assert crp["type"] == "biomarker"
    assert crp["database"] == "HGNC"

    # Test environmental grounding
    pm25 = service.ground_entity("PM2.5")
    assert pm25 is not None
    assert pm25["type"] == "environmental"
    assert pm25["database"] == "MESH"

    # Test INDRA formatting
    indra_id = service.format_for_indra(crp)
    assert indra_id == "HGNC:2367"


def test_cached_responses():
    """Test cached INDRA responses."""
    # Test PM2.5 to IL6 path
    paths = get_cached_path("PM2.5", "IL6")
    assert len(paths) > 0
    assert len(paths[0]["nodes"]) >= 3

    # Test IL6 to CRP path
    paths = get_cached_path("IL6", "CRP")
    assert len(paths) > 0
    assert len(paths[0]["edges"]) >= 1

    # Verify evidence count
    edge = paths[0]["edges"][0]
    assert edge["evidence_count"] > 100  # Well-studied relationship


def test_genetic_modifiers():
    """Test genetic modifier retrieval with literature-derived effect sizes."""
    modifier = get_genetic_modifier("GSTM1_null")
    assert modifier["effect_type"] == "amplifies"
    assert modifier["magnitude"] == 2.34  # OR from PMID:18053222 (meta-analysis)
    assert "oxidative_stress" in modifier["affected_nodes"]
    assert modifier["pmid"] == "18053222"  # Must have citation
    assert modifier["confidence"] == "Level 2A"  # PharmGKB confidence level


def test_request_model_validation():
    """Test Pydantic request model validation."""
    request = CausalDiscoveryRequest(
        request_id="test-001",
        user_context=UserContext(
            user_id="test_user",
            genetics={"GSTM1": "null"},
            current_biomarkers={"CRP": 0.7},
            location_history=[
                LocationHistory(
                    city="Los Angeles",
                    start_date="2025-01-01",
                    end_date=None,
                    avg_pm25=34.5,
                )
            ],
        ),
        query=Query(text="How does air quality affect inflammation?"),
    )

    assert request.request_id == "test-001"
    assert request.user_context.genetics["GSTM1"] == "null"
    assert request.user_context.current_biomarkers["CRP"] == 0.7


def test_graph_builder_effect_size():
    """Test effect size calculation."""
    builder = GraphBuilderService()

    # Test with high belief and high evidence
    effect_size = builder._calculate_effect_size(belief=0.9, evidence_count=150)
    assert 0 <= effect_size <= 1
    assert effect_size > 0.8  # Should be high

    # Test with low belief
    effect_size = builder._calculate_effect_size(belief=0.5, evidence_count=5)
    assert 0 <= effect_size <= 1
    assert effect_size < 0.6  # Should be moderate


def test_graph_builder_temporal_lag():
    """Test temporal lag estimation."""
    builder = GraphBuilderService()

    # Fast signaling
    assert builder.TEMPORAL_LAG_MAP["Phosphorylation"] == 1

    # Gene expression
    assert builder.TEMPORAL_LAG_MAP["IncreaseAmount"] == 12

    # Default
    assert builder.TEMPORAL_LAG_MAP["default"] == 6
