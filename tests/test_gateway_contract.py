"""Contract tests for aeon-gateway integration.

Validates that indra_agent responses match the contract expected by aeon-gateway.
Tests the interface boundary between the two systems.
"""

import pytest
from fastapi.testclient import TestClient

from indra_agent.main import app
from indra_agent.core.models import CausalDiscoveryResponse
from indra_agent.services.graph_builder import GraphBuilderService


client = TestClient(app)


def test_response_matches_aeon_gateway_contract():
    """Test that our response structure matches what aeon-gateway expects."""
    request_payload = {
        "request_id": "contract-test-001",
        "user_context": {
            "user_id": "test_user",
            "genetics": {},
            "current_biomarkers": {"CRP": 0.7},
            "location_history": []
        },
        "query": {
            "text": "test query"
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)
    assert response.status_code == 200

    data = response.json()

    # Verify top-level structure matches AgenticSystemResponse
    assert "request_id" in data
    assert "status" in data
    assert data["status"] in ["success", "error"]

    if data["status"] == "success":
        # Required by aeon-gateway
        assert "causal_graph" in data
        assert "metadata" in data
        assert "explanations" in data

        # Verify CausalGraph structure
        graph = data["causal_graph"]
        assert "nodes" in graph
        assert "edges" in graph
        assert "genetic_modifiers" in graph

        # Verify CausalNode structure (aeon-gateway expects these fields)
        for node in graph["nodes"]:
            assert "id" in node, "aeon-gateway expects node.id"
            assert "type" in node, "aeon-gateway expects node.type"
            assert node["type"] in ["environmental", "molecular", "biomarker", "genetic"]
            assert "label" in node, "aeon-gateway expects node.label"
            assert "grounding" in node, "aeon-gateway expects node.grounding"
            assert "database" in node["grounding"]
            assert "identifier" in node["grounding"]

        # Verify CausalEdge structure (aeon-gateway has strict validators)
        for edge in graph["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relationship" in edge
            assert edge["relationship"] in ["activates", "inhibits", "increases", "decreases"], \
                "aeon-gateway validates relationship values"
            assert "evidence" in edge
            assert "count" in edge["evidence"]
            assert "confidence" in edge["evidence"]
            assert "sources" in edge["evidence"]
            assert "summary" in edge["evidence"]
            assert "effect_size" in edge
            assert isinstance(edge["effect_size"], (int, float))
            assert 0 <= edge["effect_size"] <= 1, \
                "aeon-gateway requires effect_size in [0,1]"
            assert "temporal_lag_hours" in edge
            assert isinstance(edge["temporal_lag_hours"], int)
            assert edge["temporal_lag_hours"] >= 0, \
                "aeon-gateway requires temporal_lag_hours >= 0"

        # Verify genetic_modifiers structure
        for modifier in graph["genetic_modifiers"]:
            assert "variant" in modifier
            assert "affected_nodes" in modifier
            assert isinstance(modifier["affected_nodes"], list)
            assert "effect_type" in modifier
            assert modifier["effect_type"] in ["amplifies", "dampens"]
            assert "magnitude" in modifier
            assert modifier["magnitude"] > 0


def test_pydantic_model_serialization():
    """Test that Pydantic models serialize correctly for aeon-gateway."""
    from indra_agent.core.models import (
        CausalGraph,
        Node,
        Edge,
        Evidence,
        Grounding,
        GeneticModifier
    )

    # Create sample graph
    node1 = Node(
        id="PM2.5",
        type="environmental",
        label="Particulate Matter",
        grounding=Grounding(database="MESH", identifier="D052638")
    )

    node2 = Node(
        id="CRP",
        type="biomarker",
        label="C-Reactive Protein",
        grounding=Grounding(database="HGNC", identifier="2367")
    )

    edge = Edge(
        source="PM2.5",
        target="CRP",
        relationship="increases",
        evidence=Evidence(
            count=50,
            confidence=0.8,
            sources=["PMID:12345"],
            summary="PM2.5 increases CRP levels"
        ),
        effect_size=0.65,
        temporal_lag_hours=24
    )

    modifier = GeneticModifier(
        variant="GSTM1_null",
        affected_nodes=["oxidative_stress"],
        effect_type="amplifies",
        magnitude=1.3
    )

    graph = CausalGraph(
        nodes=[node1, node2],
        edges=[edge],
        genetic_modifiers=[modifier]
    )

    # Serialize to dict (what aeon-gateway receives)
    graph_dict = graph.model_dump()

    # Verify structure
    assert len(graph_dict["nodes"]) == 2
    assert len(graph_dict["edges"]) == 1
    assert len(graph_dict["genetic_modifiers"]) == 1

    # Verify node serialization
    assert graph_dict["nodes"][0]["id"] == "PM2.5"
    assert graph_dict["nodes"][0]["grounding"]["database"] == "MESH"

    # Verify edge serialization
    assert graph_dict["edges"][0]["effect_size"] == 0.65
    assert graph_dict["edges"][0]["temporal_lag_hours"] == 24


def test_edge_constraint_validation():
    """Test that edge constraints are enforced (critical for aeon-gateway)."""
    from indra_agent.core.models import Edge, Evidence
    import pytest as pyt

    # Valid edge
    valid_edge = Edge(
        source="A",
        target="B",
        relationship="activates",
        evidence=Evidence(
            count=10,
            confidence=0.7,
            sources=[],
            summary="test"
        ),
        effect_size=0.5,
        temporal_lag_hours=6
    )
    assert valid_edge.effect_size == 0.5

    # Invalid effect_size (>1) - should raise ValidationError
    with pyt.raises(Exception):  # Pydantic ValidationError
        Edge(
            source="A",
            target="B",
            relationship="activates",
            evidence=Evidence(count=10, confidence=0.7, sources=[], summary="test"),
            effect_size=1.5,  # Invalid!
            temporal_lag_hours=6
        )

    # Invalid temporal_lag (negative) - should raise ValidationError
    with pyt.raises(Exception):  # Pydantic ValidationError
        Edge(
            source="A",
            target="B",
            relationship="activates",
            evidence=Evidence(count=10, confidence=0.7, sources=[], summary="test"),
            effect_size=0.5,
            temporal_lag_hours=-1  # Invalid!
        )


def test_graph_builder_produces_valid_contract():
    """Test that GraphBuilderService produces aeon-gateway-compatible output."""
    builder = GraphBuilderService()

    # Create sample INDRA paths
    paths = [
        {
            "nodes": [
                {
                    "id": "IL6",
                    "name": "IL-6",
                    "grounding": {"db": "HGNC", "id": "6018"}
                },
                {
                    "id": "CRP",
                    "name": "CRP",
                    "grounding": {"db": "HGNC", "id": "2367"}
                }
            ],
            "edges": [
                {
                    "source": "IL6",
                    "target": "CRP",
                    "relationship": "increases",
                    "evidence_count": 150,
                    "belief": 0.95,
                    "statement_type": "IncreaseAmount",
                    "pmids": ["PMID:12345"]
                }
            ],
            "path_belief": 0.95
        }
    ]

    # Build graph
    graph = builder.build_causal_graph(
        paths=paths,
        genetics={"GSTM1": "null"}
    )

    # Verify it can be serialized for aeon-gateway
    graph_dict = graph.model_dump()

    # Verify structure
    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    assert "genetic_modifiers" in graph_dict

    # Verify constraints
    for edge in graph_dict["edges"]:
        assert 0 <= edge["effect_size"] <= 1
        assert edge["temporal_lag_hours"] >= 0


def test_error_response_contract():
    """Test error responses match aeon-gateway expectations."""
    # Force an error by sending completely invalid data
    request_payload = {
        "request_id": "error-test-001",
        "user_context": {
            "user_id": "test_user",
            "genetics": {},
            "current_biomarkers": {},
            "location_history": []
        },
        "query": {
            "text": ""  # Empty query
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)

    # Should still return 200 (error in response body)
    assert response.status_code == 200

    data = response.json()

    # Could be success (empty graph) or error
    assert data["status"] in ["success", "error"]

    if data["status"] == "error":
        # Verify error structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


def test_metadata_structure():
    """Test that metadata matches aeon-gateway expectations."""
    request_payload = {
        "request_id": "metadata-test-001",
        "user_context": {
            "user_id": "test_user",
            "genetics": {},
            "current_biomarkers": {},
            "location_history": []
        },
        "query": {
            "text": "test"
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)
    assert response.status_code == 200

    data = response.json()

    if data["status"] == "success":
        metadata = data["metadata"]
        assert "query_time_ms" in metadata
        assert isinstance(metadata["query_time_ms"], int)
        assert metadata["query_time_ms"] >= 0
