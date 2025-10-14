"""Basic tests for INDRA agent system."""

import pytest

from indra_agent.config.cached_responses import get_cached_path, get_genetic_modifier
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
    """Test genetic modifier retrieval."""
    modifier = get_genetic_modifier("GSTM1_null")
    assert modifier["effect_type"] == "amplifies"
    assert modifier["magnitude"] == 1.3
    assert "oxidative_stress" in modifier["affected_nodes"]


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
