"""Test clinical report generator.

This module tests the clinical report generation functionality,
ensuring reports are generated correctly from intervention discovery results.
"""

import pytest
from indra_agent.services.clinical_report_generator import (
    generate_intervention_clinical_report,
    generate_validation_report,
    _generate_clinical_significance,
)
from indra_agent.core.intervention_models import (
    ConsensusTarget,
    InterventionHub,
    SharedRegulator,
    MinimalNetworkResult,
    PathwayMechanism,
    PredictedEffect,
)


def test_generate_intervention_report_full():
    """Test full intervention report generation with all components."""

    # Sample data matching real intervention discovery results
    consensus_targets = [
        ConsensusTarget(
            node="IL6",
            found_in_methods=["shared_regulators", "intervention_hubs", "minimal_network"],
            max_coverage=2,
            max_score=0.87,
            recommendation="IL6 found by 3 methods (shared_regulators, intervention_hubs, minimal_network), affects 2/3 biomarkers",
        ),
        ConsensusTarget(
            node="TNF",
            found_in_methods=["shared_regulators", "intervention_hubs"],
            max_coverage=2,
            max_score=0.87,
            recommendation="TNF found by 2 methods (shared_regulators, intervention_hubs), affects 2/3 biomarkers",
        ),
    ]

    intervention_hubs = [
        InterventionHub(
            node="SRC",
            namespace="HGNC",
            identifier="11283",
            affected_biomarkers=["CRP", "IL6", "Glucose"],
            coverage=3,
            coverage_ratio=1.0,
            intervention_type="signaling",
            actionability="high",
            druggable=True,
            betweenness_count=22,
            intervention_score=1.0,
            upstream_exposures=["PM2.5"],
            avg_belief=0.85,
            total_evidence=67,
            reasoning="Regulates all 3 biomarkers. High betweenness (appears in 22 paths). Druggable target (dasatinib).",
        ),
        InterventionHub(
            node="STAT3",
            namespace="HGNC",
            identifier="11364",
            affected_biomarkers=["CRP", "IL6", "Glucose"],
            coverage=3,
            coverage_ratio=1.0,
            intervention_type="signaling",
            actionability="high",
            druggable=True,
            betweenness_count=18,
            intervention_score=0.95,
            upstream_exposures=[],
            avg_belief=0.82,
            total_evidence=54,
            reasoning="Regulates all 3 biomarkers. High betweenness (appears in 18 paths). Druggable target.",
        ),
        InterventionHub(
            node="HK1",
            namespace="HGNC",
            identifier="4922",
            affected_biomarkers=["CRP", "IL6", "Glucose"],
            coverage=3,
            coverage_ratio=1.0,
            intervention_type="metabolic",
            actionability="medium",
            druggable=False,
            betweenness_count=12,
            intervention_score=0.88,
            upstream_exposures=[],
            avg_belief=0.75,
            total_evidence=28,
            reasoning="Regulates all 3 biomarkers via metabolic pathways. Appears in 12 paths.",
        ),
    ]

    shared_regulators = [
        SharedRegulator(
            node="TNF",
            namespace="HGNC",
            identifier="11892",
            affected_biomarkers=["CRP", "IL6"],
            coverage=2,
            coverage_ratio=0.67,
            total_evidence=433,
            avg_belief=1.0,
            intervention_score=0.87,
        ),
        SharedRegulator(
            node="IL6",
            namespace="HGNC",
            identifier="6018",
            affected_biomarkers=["CRP", "IL6"],
            coverage=2,
            coverage_ratio=0.67,
            total_evidence=312,
            avg_belief=1.0,
            intervention_score=0.83,
        ),
    ]

    minimal_network = MinimalNetworkResult(
        total_nodes=8,
        total_edges=10,
        paths_used=3,
        avg_path_length=3.3,
        network_diameter=4,
        connected_biomarkers=["CRP", "IL6", "Glucose"],
        disconnected_biomarkers=[],
        intervention_points=[
            {
                "node": "NF-κB",
                "coverage": 2,
                "affected_biomarkers": ["CRP", "IL6"],
            }
        ],
        nodes=[],
        edges=[],
    )

    user_context = {
        "biomarkers": ["CRP", "IL6", "Glucose"],
        "current_biomarker_values": {
            "CRP": 5.2,
            "IL6": 3.8,
            "Glucose": 110.0,
        },
        "genetics": {
            "GSTM1": "null",
        },
    }

    # Generate report
    report = generate_intervention_clinical_report(
        consensus_targets=consensus_targets,
        intervention_hubs=intervention_hubs,
        shared_regulators=shared_regulators,
        minimal_network=minimal_network,
        user_context=user_context,
        format="markdown",
    )

    # Validate report structure
    assert "# INTERVENTION DISCOVERY REPORT" in report
    assert "## Patient Context" in report
    assert "## Top Intervention Targets" in report
    assert "## Consensus Recommendations" in report
    assert "## Literature-Based Regulators" in report
    assert "## Minimal Causal Network" in report
    assert "## Next Steps" in report
    assert "## Important Disclaimers" in report

    # Validate content
    assert "SRC" in report
    assert "STAT3" in report
    assert "HK1" in report
    assert "CRP: 5.2" in report
    assert "IL6: 3.8" in report
    assert "Glucose: 110.0" in report
    assert "GSTM1: null" in report
    assert "dasatinib" in report
    assert "TNF" in report

    # Validate synergy language
    assert "synergistic" in report.lower() or "Multi-Target Synergy" in report

    # Validate disclaimers
    assert "FOR RESEARCH AND INFORMATIONAL PURPOSES ONLY" in report
    assert "healthcare provider" in report

    print("\n" + "=" * 80)
    print("INTERVENTION DISCOVERY REPORT")
    print("=" * 80)
    print(report)
    print("=" * 80)

    return report


def test_generate_intervention_report_minimal():
    """Test report generation with minimal data (no user context)."""

    intervention_hubs = [
        InterventionHub(
            node="TNF",
            namespace="HGNC",
            identifier="11892",
            affected_biomarkers=["CRP", "IL6"],
            coverage=2,
            coverage_ratio=1.0,
            intervention_type="signaling",
            actionability="high",
            druggable=True,
            betweenness_count=8,
            intervention_score=0.9,
            upstream_exposures=[],
            avg_belief=0.95,
            total_evidence=433,
            reasoning="Regulates CRP and IL6 via inflammatory signaling.",
        )
    ]

    report = generate_intervention_clinical_report(
        consensus_targets=[],
        intervention_hubs=intervention_hubs,
        format="markdown",
    )

    # Should still generate valid report
    assert "# INTERVENTION DISCOVERY REPORT" in report
    assert "TNF" in report
    assert "FOR RESEARCH" in report


def test_generate_validation_report():
    """Test validation report generation."""

    pathway_analysis = [
        PathwayMechanism(
            source="SRC",
            target="CRP",
            mechanism="SRC → NF-κB → IL6 → CRP",
            confidence=0.95,
            temporal_lag_hours=18,
            evidence_count=67,
        ),
        PathwayMechanism(
            source="SRC",
            target="IL6",
            mechanism="SRC → NF-κB → IL6",
            confidence=0.87,
            temporal_lag_hours=12,
            evidence_count=47,
        ),
        PathwayMechanism(
            source="SRC",
            target="Glucose",
            mechanism="SRC → IRS1 → Glucose metabolism",
            confidence=0.72,
            temporal_lag_hours=24,
            evidence_count=28,
        ),
    ]

    predicted_effects = {
        "CRP": PredictedEffect(
            baseline=5.2,
            predicted=4.36,
            delta=-0.84,
            pct_change=-16.2,
            confidence="high",
        ),
        "IL6": PredictedEffect(
            baseline=3.8,
            predicted=3.2,
            delta=-0.6,
            pct_change=-15.8,
            confidence="high",
        ),
        "Glucose": PredictedEffect(
            baseline=110.0,
            predicted=98.0,
            delta=-12.0,
            pct_change=-10.9,
            confidence="medium",
        ),
    }

    synergy_score = 1.34
    clinical_significance = (
        "Moderate reduction across all biomarkers. CRP enters low-risk range. "
        "Expected timeframe: 18-24 hours for initial effects."
    )

    # Generate report
    report = generate_validation_report(
        target_node="SRC",
        pathway_analysis=pathway_analysis,
        predicted_effects=predicted_effects,
        synergy_score=synergy_score,
        clinical_significance=clinical_significance,
        format="markdown",
    )

    # Validate structure
    assert "# INTERVENTION VALIDATION REPORT" in report
    assert "## Synergy Assessment" in report
    assert "## Causal Pathways" in report
    assert "## Predicted Biomarker Changes" in report
    assert "## Clinical Significance" in report
    assert "## Important Disclaimers" in report

    # Validate content
    assert "SRC" in report
    assert "1.34" in report
    assert "STRONG SYNERGY" in report  # Score 1.34 >= 1.3
    assert "super-additive" in report
    assert "NF-κB → IL6 → CRP" in report
    assert "CRP" in report
    assert "5.2" in report
    assert "4.36" in report
    assert "-16.2%" in report

    print("\n" + "=" * 80)
    print("INTERVENTION VALIDATION REPORT")
    print("=" * 80)
    print(report)
    print("=" * 80)

    return report


def test_generate_clinical_significance():
    """Test clinical significance generation for different hub types."""

    # Multi-target, high actionability hub
    hub1 = InterventionHub(
        node="SRC",
        namespace="HGNC",
        identifier="11283",
        affected_biomarkers=["CRP", "IL6", "Glucose"],
        coverage=3,
        coverage_ratio=1.0,
        intervention_type="signaling",
        actionability="high",
        druggable=True,
        betweenness_count=22,
        intervention_score=1.0,
        upstream_exposures=[],
        avg_belief=0.85,
        total_evidence=67,
        reasoning="Test reasoning",
    )

    significance1 = _generate_clinical_significance(hub1, {})
    assert "Multi-Target Synergy" in significance1
    assert "High Actionability" in significance1
    assert "druggable target" in significance1
    assert "Critical Bottleneck" in significance1
    assert "Signaling Pathway" in significance1
    assert "22 causal pathways" in significance1

    # Single target, low actionability hub
    hub2 = InterventionHub(
        node="ProcessX",
        namespace="GO",
        identifier="12345",
        affected_biomarkers=["CRP"],
        coverage=1,
        coverage_ratio=0.33,
        intervention_type="environmental",
        actionability="low",
        druggable=False,
        betweenness_count=2,
        intervention_score=0.3,
        upstream_exposures=[],
        avg_belief=0.6,
        total_evidence=5,
        reasoning="Test reasoning",
    )

    significance2 = _generate_clinical_significance(hub2, {})
    assert "Single-Target" in significance2
    assert "Low Actionability" in significance2
    assert "Environmental Factor" in significance2


def test_html_generation():
    """Test HTML report generation."""

    intervention_hubs = [
        InterventionHub(
            node="TNF",
            namespace="HGNC",
            identifier="11892",
            affected_biomarkers=["CRP", "IL6"],
            coverage=2,
            coverage_ratio=1.0,
            intervention_type="signaling",
            actionability="high",
            druggable=True,
            betweenness_count=8,
            intervention_score=0.9,
            upstream_exposures=[],
            avg_belief=0.95,
            total_evidence=433,
            reasoning="Test",
        )
    ]

    # Generate HTML report
    html_report = generate_intervention_clinical_report(
        consensus_targets=[],
        intervention_hubs=intervention_hubs,
        format="html",
    )

    # Validate HTML structure
    assert "<html>" in html_report
    assert "<head>" in html_report
    assert "<body>" in html_report
    assert "</html>" in html_report
    assert "<h1>" in html_report
    assert "<h2>" in html_report
    assert "TNF" in html_report

    # Should have CSS styling
    assert "<style>" in html_report
    assert "font-family" in html_report


if __name__ == "__main__":
    """Run tests directly for quick validation."""
    print("=" * 80)
    print("CLINICAL REPORT GENERATOR TESTS")
    print("=" * 80)

    print("\n[1/5] Testing full intervention report...")
    test_generate_intervention_report_full()

    print("\n[2/5] Testing minimal intervention report...")
    test_generate_intervention_report_minimal()

    print("\n[3/5] Testing validation report...")
    test_generate_validation_report()

    print("\n[4/5] Testing clinical significance...")
    test_generate_clinical_significance()
    print("✅ Clinical significance generation working correctly")

    print("\n[5/5] Testing HTML generation...")
    test_html_generation()
    print("✅ HTML generation working correctly")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)
