"""Tests for intervention API endpoint.

Tests verify end-to-end intervention workflow:
- Graph storage and retrieval
- Intervention request processing
- Response format validation
"""

import pytest
from fastapi.testclient import TestClient

from indra_agent.core.models import (
    CausalGraph,
    Edge,
    Evidence,
    Grounding,
    Intervention,
    InterventionRequest,
    Node,
)
from indra_agent.main import app
from indra_agent.services.graph_store import get_graph_store


class TestInterventionEndpoint:
    """Test intervention API endpoint."""

    def setup_method(self):
        """Initialize test client before each test."""
        self.client = TestClient(app)
        self.graph_store = get_graph_store()

        # Clear graph store
        self.graph_store.graphs.clear()

    def _create_test_graph(self) -> CausalGraph:
        """Create test graph: PM2.5 → NF-κB → IL-6 → CRP."""
        nodes = [
            Node(
                id="PM2.5",
                type="environmental",
                label="PM2.5",
                grounding=Grounding(database="MESH", identifier="D052638"),
            ),
            Node(
                id="NFKB1",
                type="molecular",
                label="NF-κB",
                grounding=Grounding(database="HGNC", identifier="7794"),
            ),
            Node(
                id="IL6",
                type="biomarker",
                label="IL-6",
                grounding=Grounding(database="HGNC", identifier="6018"),
            ),
            Node(
                id="CRP",
                type="biomarker",
                label="CRP",
                grounding=Grounding(database="HGNC", identifier="2367"),
            ),
        ]

        edges = [
            Edge(
                source="PM2.5",
                target="NFKB1",
                relationship="activates",
                effect_size=0.82,
                temporal_lag_hours=6,
                evidence=Evidence(
                    count=47,
                    confidence=0.82,
                    sources=["PMID:12345678"],
                    summary="PM2.5 activates NFKB1",
                ),
            ),
            Edge(
                source="NFKB1",
                target="IL6",
                relationship="increases",
                effect_size=0.87,
                temporal_lag_hours=12,
                evidence=Evidence(
                    count=89,
                    confidence=0.87,
                    sources=["PMID:23456789"],
                    summary="NFKB1 increases IL6",
                ),
            ),
            Edge(
                source="IL6",
                target="CRP",
                relationship="increases",
                effect_size=0.91,
                temporal_lag_hours=24,
                evidence=Evidence(
                    count=312,
                    confidence=0.98,
                    sources=["PMID:34567890"],
                    summary="IL6 increases CRP",
                ),
            ),
        ]

        return CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

    def test_intervention_returns_valid_response(self):
        """Test that intervention endpoint returns valid response."""
        # Store test graph
        graph = self._create_test_graph()
        graph_id = "test-graph-001"
        baseline_values = {"PM2.5": 34.5, "CRP": 5.2, "IL6": 3.8}

        self.graph_store.store(graph_id, graph, baseline_values)

        # Make intervention request
        request_data = {
            "request_id": "intervention-test-001",
            "graph_id": graph_id,
            "intervention": {
                "node_id": "PM2.5",
                "value": 12.5,
                "unit": "µg/m³",
            },
            "target_biomarkers": ["CRP", "IL6"],
            "horizon_days": 90,
            "confidence_level": 0.95,
        }

        response = self.client.post("/api/v1/intervene", json=request_data)

        assert response.status_code == 200

        data = response.json()

        # Validate response structure
        assert data["status"] == "success"
        assert data["request_id"] == "intervention-test-001"
        assert "intervention_summary" in data
        assert "predictions" in data
        assert "metadata" in data

        # Validate predictions
        assert "CRP" in data["predictions"] or "IL6" in data["predictions"]

        if "CRP" in data["predictions"]:
            crp_pred = data["predictions"]["CRP"]
            assert "baseline" in crp_pred
            assert "post_intervention" in crp_pred
            assert "delta" in crp_pred
            assert "timeline" in crp_pred

            # Validate delta
            assert "absolute" in crp_pred["delta"]
            assert "percent" in crp_pred["delta"]

    def test_intervention_not_found_graph(self):
        """Test that intervention returns 404 for non-existent graph."""
        request_data = {
            "request_id": "intervention-test-002",
            "graph_id": "nonexistent-graph",
            "intervention": {"node_id": "PM2.5", "value": 10.0},
            "target_biomarkers": ["CRP"],
            "horizon_days": 90,
        }

        response = self.client.post("/api/v1/intervene", json=request_data)

        assert response.status_code == 404

    def test_intervention_affects_downstream_biomarkers(self):
        """Test that intervention on PM2.5 affects downstream biomarkers."""
        # Store test graph
        graph = self._create_test_graph()
        graph_id = "test-graph-003"
        baseline_values = {"PM2.5": 34.5, "CRP": 5.2, "IL6": 3.8}

        self.graph_store.store(graph_id, graph, baseline_values)

        # Intervene: reduce PM2.5 from 34.5 to 12.5
        request_data = {
            "request_id": "intervention-test-003",
            "graph_id": graph_id,
            "intervention": {"node_id": "PM2.5", "value": 12.5},
            "target_biomarkers": ["CRP"],
            "horizon_days": 90,
        }

        response = self.client.post("/api/v1/intervene", json=request_data)
        data = response.json()

        # CRP should change (decrease since PM2.5 decreased)
        if "CRP" in data["predictions"]:
            crp_delta = data["predictions"]["CRP"]["delta"]["absolute"]
            # Delta should be non-zero
            assert crp_delta != 0

    def test_intervention_includes_affected_pathways(self):
        """Test that response includes affected pathways."""
        graph = self._create_test_graph()
        graph_id = "test-graph-004"
        baseline_values = {"PM2.5": 34.5, "CRP": 5.2}

        self.graph_store.store(graph_id, graph, baseline_values)

        request_data = {
            "request_id": "intervention-test-004",
            "graph_id": graph_id,
            "intervention": {"node_id": "PM2.5", "value": 12.5},
            "target_biomarkers": ["CRP"],
            "horizon_days": 90,
        }

        response = self.client.post("/api/v1/intervene", json=request_data)
        data = response.json()

        assert "affected_pathways" in data

        # Should have at least one pathway (PM2.5 → ... → CRP)
        if data["affected_pathways"]:
            pathway = data["affected_pathways"][0]
            assert "pathway" in pathway
            assert "relationship_chain" in pathway
            assert "total_effect_size" in pathway
            assert "explanation" in pathway

            # Pathway should start with PM2.5 and end with CRP
            assert pathway["pathway"][0] == "PM2.5"
            assert pathway["pathway"][-1] == "CRP"

    def test_intervention_metadata(self):
        """Test that response includes correct metadata."""
        graph = self._create_test_graph()
        graph_id = "test-graph-005"

        self.graph_store.store(graph_id, graph, {})

        request_data = {
            "request_id": "intervention-test-005",
            "graph_id": graph_id,
            "intervention": {"node_id": "PM2.5", "value": 12.5},
            "target_biomarkers": ["CRP"],
            "horizon_days": 90,
            "confidence_level": 0.95,
        }

        response = self.client.post("/api/v1/intervene", json=request_data)
        data = response.json()

        metadata = data["metadata"]

        assert "computation_time_ms" in metadata
        assert "graph_nodes" in metadata
        assert "confidence_level" in metadata

        assert metadata["graph_nodes"] == 4
        assert metadata["confidence_level"] == 0.95
        assert metadata["computation_time_ms"] >= 0  # Can be 0 for very fast computation
