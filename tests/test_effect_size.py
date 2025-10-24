"""Tests for effect size calculation in GraphBuilderService.

These tests verify the formula matches the specification:
    W_ij = min(0.6·belief + 0.1·log(1+n), 0.95)
"""

import math
import pytest

from indra_agent.services.graph_builder import GraphBuilderService


class TestEffectSizeCalculation:
    """Test effect size calculation formula."""

    def setup_method(self):
        """Initialize service before each test."""
        self.service = GraphBuilderService()

    def test_effect_size_formula_matches_spec(self):
        """Test that formula matches specification exactly."""
        # Example from docs: belief=0.82, evidence=47
        # Expected: min(0.6×0.82 + 0.1×log(48), 0.95)
        #         = min(0.492 + 0.1×3.871, 0.95)
        #         = min(0.492 + 0.387, 0.95)
        #         = min(0.879, 0.95) = 0.879

        effect = self.service._calculate_effect_size(belief=0.82, evidence_count=47)
        expected = min(0.6 * 0.82 + 0.1 * math.log(1 + 47), 0.95)

        assert abs(effect - expected) < 0.001, f"Expected {expected:.3f}, got {effect:.3f}"
        assert abs(effect - 0.879) < 0.01, f"Expected ~0.88, got {effect:.3f}"

    def test_high_evidence_caps_at_max(self):
        """Test that high evidence count is capped at 0.95."""
        # belief=0.91, evidence=312
        # Expected: min(0.6×0.91 + 0.1×log(313), 0.95) = 0.95 (capped)

        effect = self.service._calculate_effect_size(belief=0.91, evidence_count=312)

        assert effect == 0.95, f"Expected 0.95 (capped), got {effect}"

    def test_low_evidence_returns_reasonable_value(self):
        """Test low evidence count gives reasonable effect size."""
        # belief=0.65, evidence=12
        # Expected: min(0.6×0.65 + 0.1×log(13), 0.95)
        #         = min(0.39 + 0.1×2.565, 0.95)
        #         = min(0.39 + 0.257, 0.95) = 0.647

        effect = self.service._calculate_effect_size(belief=0.65, evidence_count=12)
        expected = min(0.6 * 0.65 + 0.1 * math.log(1 + 12), 0.95)

        assert abs(effect - expected) < 0.001
        assert 0.6 < effect < 0.7, f"Expected ~0.65, got {effect:.3f}"

    def test_zero_evidence_uses_only_belief(self):
        """Test that zero evidence uses only belief score."""
        # belief=0.7, evidence=0
        # Expected: min(0.6×0.7 + 0.1×log(1), 0.95)
        #         = min(0.42 + 0, 0.95) = 0.42

        effect = self.service._calculate_effect_size(belief=0.7, evidence_count=0)
        expected = 0.6 * 0.7  # log(1) = 0

        assert abs(effect - expected) < 0.001
        assert abs(effect - 0.42) < 0.01

    def test_perfect_belief_high_evidence(self):
        """Test perfect belief with high evidence."""
        # belief=1.0, evidence=100
        # Expected: min(0.6×1.0 + 0.1×log(101), 0.95)
        #         = min(0.6 + 0.1×4.615, 0.95)
        #         = min(0.6 + 0.462, 0.95) = 0.95 (capped)

        effect = self.service._calculate_effect_size(belief=1.0, evidence_count=100)

        assert effect == 0.95

    def test_low_belief_high_evidence(self):
        """Test low belief with high evidence."""
        # belief=0.3, evidence=200
        # Expected: min(0.6×0.3 + 0.1×log(201), 0.95)
        #         = min(0.18 + 0.1×5.303, 0.95)
        #         = min(0.18 + 0.530, 0.95) = 0.71

        effect = self.service._calculate_effect_size(belief=0.3, evidence_count=200)
        expected = min(0.6 * 0.3 + 0.1 * math.log(1 + 200), 0.95)

        assert abs(effect - expected) < 0.001
        assert 0.7 < effect < 0.75

    def test_effect_size_always_in_valid_range(self):
        """Test that effect size is always in [0, 1]."""
        test_cases = [
            (0.0, 0),
            (0.5, 10),
            (0.8, 50),
            (1.0, 100),
            (0.9, 500),
        ]

        for belief, evidence in test_cases:
            effect = self.service._calculate_effect_size(belief, evidence)
            assert 0 <= effect <= 1, f"Effect {effect} out of range for belief={belief}, evidence={evidence}"

    def test_effect_size_never_exceeds_max(self):
        """Test that effect size never exceeds MAX_EFFECT."""
        # Try extreme cases
        extreme_cases = [
            (1.0, 1000),
            (0.95, 500),
            (1.0, 10000),
        ]

        for belief, evidence in extreme_cases:
            effect = self.service._calculate_effect_size(belief, evidence)
            assert effect <= self.service.MAX_EFFECT, f"Effect {effect} exceeds MAX_EFFECT for belief={belief}, evidence={evidence}"

    def test_invalid_belief_raises_error(self):
        """Test that invalid belief values raise ValueError."""
        with pytest.raises(ValueError, match="Belief must be"):
            self.service._calculate_effect_size(belief=1.5, evidence_count=10)

        with pytest.raises(ValueError, match="Belief must be"):
            self.service._calculate_effect_size(belief=-0.1, evidence_count=10)

    def test_effect_size_monotonic_in_belief(self):
        """Test that effect size increases with belief (fixed evidence)."""
        evidence = 50

        effect_1 = self.service._calculate_effect_size(0.3, evidence)
        effect_2 = self.service._calculate_effect_size(0.5, evidence)
        effect_3 = self.service._calculate_effect_size(0.7, evidence)
        effect_4 = self.service._calculate_effect_size(0.9, evidence)

        assert effect_1 < effect_2 < effect_3 < effect_4

    def test_effect_size_monotonic_in_evidence(self):
        """Test that effect size increases with evidence (fixed belief)."""
        belief = 0.7

        effect_1 = self.service._calculate_effect_size(belief, 0)
        effect_2 = self.service._calculate_effect_size(belief, 10)
        effect_3 = self.service._calculate_effect_size(belief, 50)
        effect_4 = self.service._calculate_effect_size(belief, 200)

        # Should increase (until capped)
        assert effect_1 < effect_2 < effect_3 < effect_4

    def test_logarithmic_diminishing_returns(self):
        """Test that evidence shows logarithmic diminishing returns."""
        belief = 0.5

        # Calculate marginal benefit from adding 50 papers
        effect_50 = self.service._calculate_effect_size(belief, 50)
        effect_100 = self.service._calculate_effect_size(belief, 100)
        benefit_1 = effect_100 - effect_50

        # Calculate marginal benefit from adding next 50 papers
        effect_150 = self.service._calculate_effect_size(belief, 150)
        benefit_2 = effect_150 - effect_100

        # Diminishing returns: benefit_2 < benefit_1
        assert benefit_2 < benefit_1, "Evidence should show diminishing returns"

    def test_real_world_examples(self):
        """Test with real-world INDRA data examples."""
        # Example 1: PM2.5 → NF-κB (47 papers, belief 0.82)
        effect_1 = self.service._calculate_effect_size(0.82, 47)
        assert 0.85 < effect_1 < 0.90, f"Expected ~0.88, got {effect_1:.3f}"

        # Example 2: IL-6 → CRP (312 papers, belief 0.98)
        effect_2 = self.service._calculate_effect_size(0.98, 312)
        assert effect_2 == 0.95, "Should be capped at 0.95"

        # Example 3: Low confidence edge (belief 0.4, 5 papers)
        effect_3 = self.service._calculate_effect_size(0.4, 5)
        assert 0.40 < effect_3 < 0.50, f"Expected ~0.42, got {effect_3:.3f}"

    def test_parameters_match_spec(self):
        """Test that class parameters match specification."""
        assert self.service.ALPHA == 0.6
        assert self.service.BETA == 0.1
        assert self.service.MAX_EFFECT == 0.95
