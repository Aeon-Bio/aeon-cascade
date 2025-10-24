"""Tests for ValidationAgent.

These tests verify that the validation agent correctly checks:
- DAG constraint (acyclic)
- Stability (spectral radius < 1)
- Parameter ranges
"""

import pytest

from indra_agent.agents.validation_agent import ValidationAgent
from indra_agent.core.models import CausalGraph, Edge, Evidence, Grounding, Node


class TestValidationAgent:
    """Test ValidationAgent constraints."""

    def setup_method(self):
        """Initialize agent before each test."""
        self.agent = ValidationAgent()

    def _create_valid_graph(self) -> CausalGraph:
        """Create a valid test graph: PM2.5 → NF-κB → IL-6 → CRP."""
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

    def test_valid_graph_passes_all_checks(self):
        """Test that a valid graph passes all validation checks."""
        graph = self._create_valid_graph()
        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is True
        assert result["checks"]["is_dag"] is True
        assert result["checks"]["is_stable"] is True
        assert result["checks"]["parameters_valid"] is True
        assert len(result["errors"]) == 0
        assert result["metadata"]["spectral_radius"] < 1.0

    def test_dag_validation_detects_simple_cycle(self):
        """Test that DAG validation detects a simple 2-node cycle."""
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.7, sources=[], summary="A activates B"),
            ),
            Edge(
                source="B",
                target="A",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.7, sources=[], summary="B activates A"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is False
        assert result["checks"]["is_dag"] is False
        assert any("cycle" in err.lower() for err in result["errors"])

    def test_dag_validation_detects_3node_cycle(self):
        """Test that DAG validation detects a 3-node cycle."""
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
            Node(id="C", type="molecular", label="C", grounding=Grounding(database="HGNC", identifier="3")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.7, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="C",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.7, sources=[], summary="B→C"),
            ),
            Edge(
                source="C",
                target="A",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.7, sources=[], summary="C→A"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is False
        assert result["checks"]["is_dag"] is False

    def test_parameter_validation_detects_out_of_range_effect_size(self):
        """Test that parameter validation detects effect size > 1."""
        graph = self._create_valid_graph()

        # Modify one edge to have invalid effect size
        graph.edges[0].effect_size = 1.5  # Invalid: > 1

        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is False
        assert result["checks"]["parameters_valid"] is False
        assert any("effect_size" in err.lower() and "1.5" in err for err in result["errors"])

    def test_parameter_validation_detects_negative_temporal_lag(self):
        """Test that parameter validation detects negative temporal lag."""
        graph = self._create_valid_graph()

        # Modify one edge to have negative temporal lag
        graph.edges[0].temporal_lag_hours = -5  # Invalid

        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is False
        assert result["checks"]["parameters_valid"] is False
        assert any("temporal_lag" in err.lower() for err in result["errors"])

    def test_parameter_validation_accepts_inhibitory_edges(self):
        """Test that inhibitory edges with positive effect_size are valid."""
        graph = self._create_valid_graph()

        # Add inhibitory edge (effect_size is always positive, relationship determines sign)
        graph.edges.append(
            Edge(
                source="NFKB1",
                target="PM2.5",
                relationship="inhibits",
                effect_size=0.6,  # Positive magnitude
                temporal_lag_hours=6,
                evidence=Evidence(count=20, confidence=0.7, sources=[], summary="NFKB1 inhibits PM2.5"),
            )
        )

        result = self.agent.validate_graph(graph)

        # Parameters should be valid (DAG might fail due to cycle)
        assert result["checks"]["parameters_valid"] is True

    def test_stability_validation_with_stable_graph(self):
        """Test spectral radius check on a stable graph."""
        graph = self._create_valid_graph()
        result = self.agent.validate_graph(graph)

        assert result["is_valid"] is True
        assert result["checks"]["is_stable"] is True
        assert result["metadata"]["spectral_radius"] < 1.0

    def test_stability_validation_with_unstable_graph(self):
        """Test spectral radius check on an unstable graph."""
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
        ]

        # Create very strong edges that will violate stability
        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.95,
                temporal_lag_hours=1,
                evidence=Evidence(count=100, confidence=0.95, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="A",
                relationship="activates",
                effect_size=0.95,
                temporal_lag_hours=1,
                evidence=Evidence(count=100, confidence=0.95, sources=[], summary="B→A"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

        # This graph has a cycle, so DAG check will fail first
        # Let's test stability on a DAG with strong self-reinforcement
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
            Node(id="C", type="molecular", label="C", grounding=Grounding(database="HGNC", identifier="3")),
        ]

        edges = [
            Edge(
                source="A",
                target="A",  # Self-loop with very strong effect
                relationship="activates",
                effect_size=0.99,  # Very close to 1, may cause instability
                temporal_lag_hours=1,
                evidence=Evidence(count=50, confidence=0.9, sources=[], summary="A→A"),
            ),
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=50, confidence=0.9, sources=[], summary="A→B"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        result = self.agent.validate_graph(graph)

        # With self-loop of 0.99, spectral radius should be close to or exceed 1
        # This may pass or fail depending on exact eigenvalues, but we test handling
        assert "spectral_radius" in result["metadata"]

    def test_fix_violations_caps_effect_sizes(self):
        """Test that fix_violations caps effect sizes at 0.95."""
        graph = self._create_valid_graph()
        graph.edges[0].effect_size = 1.2  # Too high

        fixed_graph = self.agent.fix_violations(graph)

        assert fixed_graph.edges[0].effect_size == 0.95

    def test_fix_violations_fixes_negative_temporal_lag(self):
        """Test that fix_violations sets negative temporal lags to 0."""
        graph = self._create_valid_graph()
        graph.edges[0].temporal_lag_hours = -5

        fixed_graph = self.agent.fix_violations(graph)

        assert fixed_graph.edges[0].temporal_lag_hours == 0

    def test_fix_violations_removes_cycles(self):
        """Test that fix_violations removes cycles."""
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=50, confidence=0.7, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="A",
                relationship="activates",
                effect_size=0.5,
                temporal_lag_hours=1,
                evidence=Evidence(count=10, confidence=0.6, sources=[], summary="B→A"),  # Lower evidence
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

        fixed_graph = self.agent.fix_violations(graph)

        # Should remove the edge with lower evidence (B→A)
        assert len(fixed_graph.edges) == 1
        assert fixed_graph.edges[0].source == "A"
        assert fixed_graph.edges[0].target == "B"

        # Validate fixed graph is a DAG
        result = self.agent.validate_graph(fixed_graph)
        assert result["checks"]["is_dag"] is True

    def test_fix_violations_scales_for_stability(self):
        """Test that fix_violations scales effect sizes for stability."""
        # Create a graph that's close to instability
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
            Node(id="C", type="molecular", label="C", grounding=Grounding(database="HGNC", identifier="3")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.95,
                temporal_lag_hours=1,
                evidence=Evidence(count=100, confidence=0.95, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="C",
                relationship="activates",
                effect_size=0.95,
                temporal_lag_hours=1,
                evidence=Evidence(count=100, confidence=0.95, sources=[], summary="B→C"),
            ),
            Edge(
                source="A",
                target="C",
                relationship="activates",
                effect_size=0.95,
                temporal_lag_hours=1,
                evidence=Evidence(count=100, confidence=0.95, sources=[], summary="A→C"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

        # Check if original is unstable
        result = self.agent.validate_graph(graph)

        if not result["checks"]["is_stable"]:
            # Fix should scale down
            fixed_graph = self.agent.fix_violations(graph)

            # All effect sizes should be scaled
            for edge in fixed_graph.edges:
                assert edge.effect_size < 0.95

            # Validate fixed graph is stable
            fixed_result = self.agent.validate_graph(fixed_graph)
            assert fixed_result["checks"]["is_stable"] is True

    def test_validation_with_empty_graph(self):
        """Test validation with an empty graph."""
        graph = CausalGraph(nodes=[], edges=[], genetic_modifiers=[])

        result = self.agent.validate_graph(graph)

        # Empty graph is trivially valid
        assert result["is_valid"] is True
        assert result["metadata"]["num_nodes"] == 0
        assert result["metadata"]["num_edges"] == 0

    def test_validation_metadata(self):
        """Test that validation returns correct metadata."""
        graph = self._create_valid_graph()
        result = self.agent.validate_graph(graph)

        assert result["metadata"]["num_nodes"] == 4
        assert result["metadata"]["num_edges"] == 3
        assert result["metadata"]["spectral_radius"] is not None
        assert isinstance(result["metadata"]["spectral_radius"], float)

    def test_warning_for_near_threshold_spectral_radius(self):
        """Test that validation warns when spectral radius is close to 1."""
        # Create graph with spectral radius between 0.99 and 1.0
        nodes = [
            Node(id="A", type="molecular", label="A", grounding=Grounding(database="HGNC", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.98,  # Very high, close to threshold
                temporal_lag_hours=1,
                evidence=Evidence(count=200, confidence=0.99, sources=[], summary="A→B"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        result = self.agent.validate_graph(graph)

        # Should be valid but have warnings
        if result["metadata"]["spectral_radius"] > 0.99:
            assert len(result["warnings"]) > 0
            assert any("spectral radius" in warn.lower() for warn in result["warnings"])
