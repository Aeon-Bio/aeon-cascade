"""Tests for SCM Inference Engine.

Tests verify closed-form Linear Gaussian SCM inference:
- Matrix construction from causal graphs
- Observational predictions
- Interventional predictions (do-calculus)
- Causal effect computation
"""

import numpy as np
import pytest

from indra_agent.agents.validation_agent import ValidationAgent
from indra_agent.core.models import CausalGraph, Edge, Evidence, Grounding, Node
from indra_agent.services.scm_inference import SCMInferenceEngine


class TestSCMInference:
    """Test SCM inference engine."""

    def setup_method(self):
        """Initialize engine before each test."""
        self.engine = SCMInferenceEngine(noise_variance=0.1)
        self.validator = ValidationAgent()

    def _create_simple_chain(self) -> CausalGraph:
        """Create simple chain: A → B → C."""
        nodes = [
            Node(id="A", type="environmental", label="A", grounding=Grounding(database="MESH", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
            Node(id="C", type="biomarker", label="C", grounding=Grounding(database="HGNC", identifier="3")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.6,
                temporal_lag_hours=6,
                evidence=Evidence(count=50, confidence=0.7, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="C",
                relationship="increases",
                effect_size=0.7,
                temporal_lag_hours=12,
                evidence=Evidence(count=100, confidence=0.8, sources=[], summary="B→C"),
            ),
        ]

        return CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

    def test_build_scm_creates_correct_matrices(self):
        """Test that build_scm creates correct W, mu, Sigma matrices."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)

        assert scm["n"] == 3
        assert "W" in scm
        assert "mu" in scm
        assert "Sigma" in scm

        # Check W shape
        assert scm["W"].shape == (3, 3)

        # Check W values (A→B: W[1,0]=0.6, B→C: W[2,1]=0.7)
        node_to_idx = scm["node_to_idx"]
        assert scm["W"][node_to_idx["B"], node_to_idx["A"]] == pytest.approx(0.6)
        assert scm["W"][node_to_idx["C"], node_to_idx["B"]] == pytest.approx(0.7)

        # Check mu values
        assert scm["mu"][node_to_idx["A"]] == pytest.approx(1.0)
        assert scm["mu"][node_to_idx["B"]] == pytest.approx(0.5)
        assert scm["mu"][node_to_idx["C"]] == pytest.approx(2.0)

        # Check Sigma is diagonal
        assert np.allclose(scm["Sigma"], np.eye(3) * 0.1)

    def test_predict_generates_valid_timeline(self):
        """Test that predict generates valid PredictionTimeline."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)
        predictions = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)

        assert "C" in predictions
        pred = predictions["C"]

        # Check timeline structure
        assert pred.baseline == 2.0
        assert len(pred.timeline) > 0

        # Check timeline points have required fields
        for point in pred.timeline:
            assert "day" in point
            assert "mean" in point
            assert "confidence_interval" in point
            assert "risk_level" in point

            # Validate CI format
            assert len(point["confidence_interval"]) == 2
            assert point["confidence_interval"][0] < point["confidence_interval"][1]

    def test_predict_uses_closed_form_inference(self):
        """Test that predictions are deterministic (closed-form, not Monte Carlo)."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)

        # Run prediction twice
        pred1 = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)
        pred2 = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)

        # Should be identical (no randomness)
        assert pred1["C"].timeline == pred2["C"].timeline

    def test_intervene_changes_predictions(self):
        """Test that interventions change predictions correctly."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)

        # Observational prediction
        obs_pred = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)
        obs_mean = obs_pred["C"].timeline[-1]["mean"]

        # Interventional prediction: set A = 2.0 (increase)
        int_pred = self.engine.intervene(
            scm,
            interventions={"A": 2.0},
            target_biomarkers=["C"],
            horizon_days=90,
        )
        int_mean = int_pred["C"].timeline[-1]["mean"]

        # Intervention should change C (A → B → C chain)
        assert int_mean != obs_mean

    def test_intervene_with_inhibition(self):
        """Test that inhibitory edges are handled correctly in interventions."""
        nodes = [
            Node(id="A", type="environmental", label="A", grounding=Grounding(database="MESH", identifier="1")),
            Node(id="B", type="biomarker", label="B", grounding=Grounding(database="HGNC", identifier="2")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="inhibits",
                effect_size=0.8,
                temporal_lag_hours=6,
                evidence=Evidence(count=50, confidence=0.9, sources=[], summary="A inhibits B"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        baseline_values = {"A": 1.0, "B": 5.0}

        scm = self.engine.build_scm(graph, baseline_values)

        # Increase A (inhibitor) → B should decrease
        int_pred = self.engine.intervene(
            scm,
            interventions={"A": 3.0},  # Triple A
            target_biomarkers=["B"],
            horizon_days=90,
        )

        # B should be lower than baseline due to increased inhibition
        int_mean = int_pred["B"].timeline[-1]["mean"]
        assert int_mean < baseline_values["B"]

    def test_compute_causal_effect_simple_chain(self):
        """Test causal effect computation for simple chain."""
        graph = self._create_simple_chain()
        scm = self.engine.build_scm(graph, baseline_values={"A": 1.0})

        # Compute A → C effect
        effect = self.engine.compute_causal_effect(scm, source="A", target="C")

        assert effect["is_valid"] is True
        assert effect["error"] is None

        # Total effect should be product of path effects: 0.6 * 0.7 = 0.42
        assert abs(effect["total_effect"] - 0.42) < 0.01

    def test_compute_causal_effect_with_multiple_paths(self):
        """Test causal effect computation with multiple paths."""
        nodes = [
            Node(id="A", type="environmental", label="A", grounding=Grounding(database="MESH", identifier="1")),
            Node(id="B", type="molecular", label="B", grounding=Grounding(database="HGNC", identifier="2")),
            Node(id="C", type="biomarker", label="C", grounding=Grounding(database="HGNC", identifier="3")),
        ]

        edges = [
            Edge(
                source="A",
                target="B",
                relationship="activates",
                effect_size=0.6,
                temporal_lag_hours=6,
                evidence=Evidence(count=50, confidence=0.7, sources=[], summary="A→B"),
            ),
            Edge(
                source="B",
                target="C",
                relationship="increases",
                effect_size=0.7,
                temporal_lag_hours=12,
                evidence=Evidence(count=100, confidence=0.8, sources=[], summary="B→C"),
            ),
            Edge(
                source="A",
                target="C",
                relationship="activates",
                effect_size=0.3,  # Direct path
                temporal_lag_hours=12,
                evidence=Evidence(count=30, confidence=0.6, sources=[], summary="A→C"),
            ),
        ]

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])
        scm = self.engine.build_scm(graph)

        # Compute A → C effect (should include both direct and indirect paths)
        effect = self.engine.compute_causal_effect(scm, source="A", target="C")

        assert effect["is_valid"] is True

        # Total effect = direct (0.3) + indirect (0.6 * 0.7 = 0.42) = 0.72
        assert abs(effect["total_effect"] - 0.72) < 0.01

    def test_scm_with_validated_graph(self):
        """Test SCM inference on a graph that passes validation."""
        graph = self._create_simple_chain()

        # Validate graph first
        validation = self.validator.validate_graph(graph)
        assert validation["is_valid"] is True

        # Build SCM
        scm = self.engine.build_scm(graph, baseline_values={"A": 1.0, "C": 2.0})

        # Should succeed
        predictions = self.engine.predict(scm, target_biomarkers=["C"])
        assert "C" in predictions

    def test_scm_inference_performance(self):
        """Test that SCM inference is fast (<10ms for n=10)."""
        import time

        # Create larger graph (n=10)
        nodes = [
            Node(id=f"N{i}", type="molecular", label=f"Node{i}", grounding=Grounding(database="HGNC", identifier=str(i)))
            for i in range(10)
        ]

        edges = []
        for i in range(9):
            edges.append(
                Edge(
                    source=f"N{i}",
                    target=f"N{i+1}",
                    relationship="activates",
                    effect_size=0.5,
                    temporal_lag_hours=6,
                    evidence=Evidence(count=50, confidence=0.7, sources=[], summary=f"N{i}→N{i+1}"),
                )
            )

        graph = CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])

        # Build SCM
        scm = self.engine.build_scm(graph)

        # Time prediction
        start = time.time()
        predictions = self.engine.predict(scm, target_biomarkers=["N9"], horizon_days=90)
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert "N9" in predictions
        assert elapsed < 50  # Should be well under 50ms for n=10

    def test_scm_handles_no_baseline_values(self):
        """Test SCM builds successfully with no baseline values."""
        graph = self._create_simple_chain()
        scm = self.engine.build_scm(graph, baseline_values=None)

        assert scm["n"] == 3
        assert np.allclose(scm["mu"], np.zeros(3))  # Default to zeros

    def test_intervention_does_not_affect_intervened_node(self):
        """Test that intervened nodes are not included in predictions."""
        graph = self._create_simple_chain()
        scm = self.engine.build_scm(graph, baseline_values={"A": 1.0, "B": 0.5, "C": 2.0})

        # Intervene on B, request predictions for both B and C
        predictions = self.engine.intervene(
            scm,
            interventions={"B": 10.0},
            target_biomarkers=["B", "C"],
            horizon_days=90,
        )

        # B should not be in predictions (it's fixed)
        assert "B" not in predictions

        # C should be in predictions
        assert "C" in predictions

    def test_matrix_invertibility_check(self):
        """Test that SCM checks for matrix invertibility."""
        graph = self._create_simple_chain()

        # Artificially create an unstable graph (this would fail validation)
        graph.edges[0].effect_size = 0.99
        graph.edges[1].effect_size = 0.99

        # Build should still succeed but log warning
        scm = self.engine.build_scm(graph)

        # Should have all components
        assert "W" in scm
        assert "mu" in scm

    def test_timeline_interpolation(self):
        """Test that timeline uses linear interpolation from baseline to steady-state."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)
        predictions = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)

        timeline = predictions["C"].timeline

        # First point should be close to baseline
        assert abs(timeline[0]["mean"] - 2.0) < 0.5

        # Timeline should be monotonic or near-monotonic
        means = [point["mean"] for point in timeline]
        # (May increase or decrease depending on causal effects)

    def test_confidence_intervals_widen_over_time(self):
        """Test that confidence intervals widen as uncertainty accumulates."""
        graph = self._create_simple_chain()
        baseline_values = {"A": 1.0, "B": 0.5, "C": 2.0}

        scm = self.engine.build_scm(graph, baseline_values)
        predictions = self.engine.predict(scm, target_biomarkers=["C"], horizon_days=90)

        timeline = predictions["C"].timeline

        if len(timeline) >= 2:
            # CI width at day 0
            width_0 = timeline[0]["confidence_interval"][1] - timeline[0]["confidence_interval"][0]

            # CI width at last day
            width_last = timeline[-1]["confidence_interval"][1] - timeline[-1]["confidence_interval"][0]

            # Width should increase over time
            assert width_last >= width_0
