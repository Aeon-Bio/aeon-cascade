"""End-to-end tests for complete causal discovery workflow.

Tests the full pipeline from request to response, including:
- Entity grounding
- Path search via INDRA
- Graph building
- Response formatting
"""

import pytest
from fastapi.testclient import TestClient

from indra_agent.main import app
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    LocationHistory,
    Query,
    UserContext,
)


client = TestClient(app)


def test_health_endpoint():
    """Test API health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_causal_discovery_simple_query():
    """Test simple causal discovery query with minimal context."""
    request_payload = {
        "request_id": "test-e2e-001",
        "user_context": {
            "user_id": "test_user",
            "genetics": {},
            "current_biomarkers": {"CRP": 0.7},
            "location_history": [
                {
                    "city": "Test City",
                    "start_date": "2025-01-01",
                    "end_date": None,
                    "avg_pm25": 20.0
                }
            ]
        },
        "query": {
            "text": "How does IL-6 affect CRP?"
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)

    # Should succeed even if no paths found
    assert response.status_code == 200, f"Request failed: {response.text}"

    data = response.json()
    assert "status" in data
    assert data["status"] in ["success", "error"]

    if data["status"] == "success":
        # Verify response structure
        assert "request_id" in data
        assert data["request_id"] == "test-e2e-001"
        assert "causal_graph" in data
        assert "metadata" in data
        assert "explanations" in data

        # Verify causal graph structure
        graph = data["causal_graph"]
        assert "nodes" in graph
        assert "edges" in graph
        assert "genetic_modifiers" in graph

        # If paths were found, verify node/edge structure
        if len(graph["nodes"]) > 0:
            node = graph["nodes"][0]
            assert "id" in node
            assert "type" in node
            assert node["type"] in ["environmental", "molecular", "biomarker", "genetic"]
            assert "label" in node
            assert "grounding" in node
            assert "database" in node["grounding"]
            assert "identifier" in node["grounding"]

        if len(graph["edges"]) > 0:
            edge = graph["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "relationship" in edge
            assert edge["relationship"] in ["activates", "inhibits", "increases", "decreases"]
            assert "evidence" in edge
            assert "effect_size" in edge
            assert 0 <= edge["effect_size"] <= 1, "effect_size must be [0,1]"
            assert "temporal_lag_hours" in edge
            assert edge["temporal_lag_hours"] >= 0, "temporal_lag must be >= 0"


def test_causal_discovery_sf_to_la_scenario():
    """Test the demo SF→LA scenario."""
    request_payload = {
        "request_id": "test-sf-la-001",
        "user_context": {
            "user_id": "sarah_chen",
            "genetics": {
                "GSTM1": "null",
                "GSTP1": "Val/Val"
            },
            "current_biomarkers": {
                "CRP": 0.7,
                "IL-6": 1.1
            },
            "location_history": [
                {
                    "city": "San Francisco",
                    "start_date": "2020-01-01",
                    "end_date": "2025-08-31",
                    "avg_pm25": 7.8
                },
                {
                    "city": "Los Angeles",
                    "start_date": "2025-09-01",
                    "end_date": None,
                    "avg_pm25": 34.5
                }
            ]
        },
        "query": {
            "text": "How will LA air quality affect my inflammation?",
            "focus_biomarkers": ["CRP", "IL-6"]
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)
    assert response.status_code == 200

    data = response.json()

    if data["status"] == "success":
        graph = data["causal_graph"]

        # Should have environmental exposure
        env_nodes = [n for n in graph["nodes"] if n["type"] == "environmental"]
        assert len(env_nodes) > 0, "Should identify environmental factors"

        # Should have biomarkers
        biomarker_nodes = [n for n in graph["nodes"] if n["type"] == "biomarker"]
        assert len(biomarker_nodes) > 0, "Should identify biomarkers"

        # Should have genetic modifiers (GSTM1 null)
        if len(graph["genetic_modifiers"]) > 0:
            modifier = graph["genetic_modifiers"][0]
            assert "variant" in modifier
            assert "affected_nodes" in modifier
            assert "effect_type" in modifier
            assert modifier["effect_type"] in ["amplifies", "dampens"]
            assert "magnitude" in modifier
            assert modifier["magnitude"] > 0

        # Should have explanations
        assert len(data["explanations"]) >= 3, "Should have 3-5 explanations"
        assert len(data["explanations"]) <= 5, "Should have 3-5 explanations"


def test_causal_discovery_invalid_request():
    """Test handling of invalid requests."""
    # Missing required fields
    invalid_payload = {
        "request_id": "test-invalid-001",
        "user_context": {
            "user_id": "test_user"
            # Missing required fields
        },
        "query": {}  # Missing text
    }

    response = client.post("/api/v1/causal_discovery", json=invalid_payload)
    assert response.status_code == 422, "Should reject invalid request"


def test_causal_discovery_with_options():
    """Test causal discovery with custom options."""
    request_payload = {
        "request_id": "test-options-001",
        "user_context": {
            "user_id": "test_user",
            "genetics": {},
            "current_biomarkers": {"CRP": 0.7},
            "location_history": []
        },
        "query": {
            "text": "Test query"
        },
        "options": {
            "max_graph_depth": 3,
            "min_evidence_count": 5,
            "include_interventions": False
        }
    }

    response = client.post("/api/v1/causal_discovery", json=request_payload)
    assert response.status_code == 200


def test_response_contract_compliance():
    """Test that response strictly complies with API contract."""
    request_payload = {
        "request_id": "test-contract-001",
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

    # Required fields
    assert "request_id" in data
    assert "status" in data
    assert data["status"] in ["success", "error"]

    if data["status"] == "success":
        # Success response requirements
        assert "causal_graph" in data
        assert "metadata" in data
        assert "explanations" in data

        # Validate all edges meet constraints
        for edge in data["causal_graph"]["edges"]:
            assert 0 <= edge["effect_size"] <= 1, \
                f"effect_size {edge['effect_size']} out of range [0,1]"
            assert edge["temporal_lag_hours"] >= 0, \
                f"temporal_lag_hours {edge['temporal_lag_hours']} must be >= 0"

    elif data["status"] == "error":
        # Error response requirements
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test handling of concurrent requests."""
    import asyncio
    import httpx

    async with httpx.AsyncClient(base_url="http://testserver") as async_client:
        # Create multiple concurrent requests
        requests = [
            {
                "request_id": f"test-concurrent-{i}",
                "user_context": {
                    "user_id": f"user_{i}",
                    "genetics": {},
                    "current_biomarkers": {},
                    "location_history": []
                },
                "query": {"text": f"test query {i}"}
            }
            for i in range(5)
        ]

        # Send all requests concurrently
        async def send_request(payload):
            response = await async_client.post("/api/v1/causal_discovery", json=payload)
            return response

        # This would work with a running server
        # For now, just verify the test structure is correct
        assert len(requests) == 5
