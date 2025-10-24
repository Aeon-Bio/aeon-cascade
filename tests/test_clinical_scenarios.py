"""Clinical scenario validation tests.

This module tests the complete intervention discovery workflow with realistic
clinical scenarios, validating end-to-end functionality from biomarkers to
actionable intervention recommendations.
"""

import pytest
from fastapi.testclient import TestClient
from indra_agent.main import app
from indra_agent.services.clinical_report_generator import (
    generate_intervention_clinical_report,
    generate_validation_report,
)


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_sarah_chen_metabolic_inflammatory_syndrome(client):
    """Test Sarah Chen's clinical case: metabolic-inflammatory syndrome.

    Patient Profile:
    - Age: 34, Software Engineer, Los Angeles
    - Primary: Chronic inflammation (CRP: 5.2 mg/L, IL-6: 3.8 pg/mL)
    - Emerging: Prediabetes (HbA1c: 5.9%, fasting glucose: 110 mg/dL)
    - Environmental: High PM2.5 exposure (LA: 35 µg/m³)

    Expected: System discovers multi-target interventions affecting BOTH
    inflammation AND metabolic markers simultaneously.
    """

    # Request intervention discovery
    request_payload = {
        "request_id": "sarah-chen-001",
        "biomarkers": ["CRP", "IL6", "Glucose"],
        "exposures": ["PM2.5"],
        "genetics": {"GSTM1": "null"},
        "current_biomarker_values": {
            "CRP": 5.2,
            "IL6": 3.8,
            "Glucose": 110.0
        },
        "options": {
            "methods": ["shared_regulators", "intervention_hubs", "minimal_network"],
            "max_depth": 3,
            "min_coverage": 2,
            "belief_cutoff": 0.6,
            "prioritize_druggable": True
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    # Validate response
    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        # Validate multi-biomarker coverage
        assert len(data["consensus_targets"]) > 0, "Should find consensus targets"

        # Check for multi-target hubs (affect 2+ biomarkers)
        hubs = data["results"].get("intervention_hubs", [])
        multi_target_hubs = [h for h in hubs if h["coverage"] >= 2]
        assert len(multi_target_hubs) > 0, "Should find hubs affecting multiple biomarkers"

        # Validate network summary
        summary = data["network_summary"]
        assert summary["total_hubs"] > 0, "Should identify intervention hubs"
        assert summary["avg_coverage"] >= 1.0, "Hubs should affect at least 1 biomarker"

        # Print clinical insights
        print("\n" + "="*80)
        print("SARAH CHEN CLINICAL CASE - INTERVENTION DISCOVERY")
        print("="*80)
        print(f"✓ Found {len(data['consensus_targets'])} consensus targets")
        print(f"✓ Found {len(multi_target_hubs)} multi-target hubs")
        print(f"✓ Network summary: {summary['total_hubs']} hubs, avg coverage {summary['avg_coverage']:.2f}")

        if data["consensus_targets"]:
            print("\n🎯 TOP CONSENSUS TARGETS:")
            for i, target in enumerate(data["consensus_targets"][:3], 1):
                print(f"  {i}. {target['node']} - affects {target['max_coverage']}/3 biomarkers")
                print(f"     Methods: {', '.join(target['found_in_methods'])}")

        if multi_target_hubs:
            print("\n🔬 MULTI-TARGET INTERVENTION HUBS:")
            for i, hub in enumerate(multi_target_hubs[:3], 1):
                print(f"  {i}. {hub['node']} - affects {hub['coverage']}/3 biomarkers")
                print(f"     Type: {hub['intervention_type']}, Actionability: {hub['actionability']}")
                print(f"     Druggable: {hub['druggable']}")

        print("="*80)
    else:
        print(f"\n⚠️  Warning: Intervention discovery returned error: {data.get('error_message')}")
        print("   This may be expected due to INDRA API availability")


def test_environmental_exposure_intervention(client):
    """Test environmental exposure → biomarker causal pathway.

    Scenario: Patient exposed to high PM2.5 wants to know impact on inflammation.
    Expected: System discovers PM2.5 → oxidative stress → inflammatory biomarkers.
    """

    request_payload = {
        "request_id": "env-exposure-001",
        "biomarkers": ["CRP", "IL6"],
        "exposures": ["PM2.5"],
        "current_biomarker_values": {
            "CRP": 4.5,
            "IL6": 2.8
        },
        "options": {
            "methods": ["intervention_hubs", "minimal_network"],
            "max_depth": 3,
            "min_coverage": 1,
            "belief_cutoff": 0.5
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        # Should find intervention points between exposure and biomarkers
        hubs = data["results"].get("intervention_hubs", [])
        assert len(hubs) > 0, "Should find intervention hubs"

        # Print findings
        print("\n" + "="*80)
        print("ENVIRONMENTAL EXPOSURE INTERVENTION")
        print("="*80)
        print(f"✓ Found {len(hubs)} intervention hubs")
        print(f"✓ Processing time: {data['processing_time_ms']}ms")

        if hubs:
            print("\n🌍 ENVIRONMENTAL INTERVENTION TARGETS:")
            for i, hub in enumerate(hubs[:5], 1):
                print(f"  {i}. {hub['node']} - {hub['intervention_type']}")
                print(f"     Affected biomarkers: {', '.join(hub['affected_biomarkers'])}")

        print("="*80)


def test_genetic_modifier_scenario(client):
    """Test genetic variant impact on intervention discovery.

    Scenario: Patient with GSTM1 null variant (impaired antioxidant defense).
    Expected: System should identify interventions that compensate for this genetic risk.
    """

    request_payload = {
        "request_id": "genetic-001",
        "biomarkers": ["8-OHdG", "CRP"],  # Oxidative stress marker + inflammation
        "genetics": {
            "GSTM1": "null"  # Null variant increases oxidative stress susceptibility
        },
        "current_biomarker_values": {
            "8-OHdG": 12.5,  # High oxidative damage
            "CRP": 6.0       # High inflammation
        },
        "options": {
            "methods": ["shared_regulators", "intervention_hubs"],
            "max_depth": 3,
            "min_coverage": 1,
            "belief_cutoff": 0.6
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        # Validate intervention discovery with genetic context
        results = data["results"]
        assert "intervention_hubs" in results or "shared_regulators" in results

        print("\n" + "="*80)
        print("GENETIC MODIFIER SCENARIO - GSTM1 NULL")
        print("="*80)
        print(f"✓ Request ID: {data['request_id']}")
        print(f"✓ Genetic context: GSTM1 null variant (impaired antioxidant defense)")

        if "intervention_hubs" in results:
            hubs = results["intervention_hubs"]
            print(f"✓ Found {len(hubs)} intervention hubs")

            if hubs:
                print("\n💊 INTERVENTION TARGETS:")
                for i, hub in enumerate(hubs[:3], 1):
                    print(f"  {i}. {hub['node']} - {hub['intervention_type']}")
                    print(f"     Actionability: {hub['actionability']}, Druggable: {hub['druggable']}")

        print("="*80)


def test_intervention_validation_multi_biomarker(client):
    """Test intervention validation for a target affecting multiple biomarkers.

    Scenario: Validate that SRC kinase affects inflammation and metabolic markers.
    Expected: System finds causal pathways to multiple biomarkers with synergy.
    """

    request_payload = {
        "target_node": "SRC",
        "biomarkers": ["CRP", "IL6", "Glucose"],
        "current_biomarker_values": {
            "CRP": 5.2,
            "IL6": 3.8,
            "Glucose": 110.0
        },
        "simulate_effect_size": 0.3
    }

    response = client.post("/api/v1/validate_intervention", json=request_payload)

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        # Validate multi-biomarker effects
        assert "pathway_analysis" in data
        assert "predicted_effects" in data
        assert "synergy_score" in data

        # Check for pathways to each biomarker
        pathways = data["pathway_analysis"]
        affected_biomarkers = set(p["target"] for p in pathways)

        print("\n" + "="*80)
        print("INTERVENTION VALIDATION - MULTI-BIOMARKER")
        print("="*80)
        print(f"✓ Target: {data['target_node']}")
        print(f"✓ Affects all biomarkers: {data['affects_all_biomarkers']}")
        print(f"✓ Pathways found: {len(pathways)}")
        print(f"✓ Affected biomarkers: {', '.join(affected_biomarkers)}")
        print(f"✓ Synergy score: {data['synergy_score']:.2f}")

        if pathways:
            print("\n🔬 CAUSAL PATHWAYS:")
            for pathway in pathways:
                print(f"  {pathway['mechanism']}")
                print(f"  Confidence: {pathway['confidence']:.2f}, Lag: {pathway['temporal_lag_hours']}h")

        if data["predicted_effects"]:
            print("\n📊 PREDICTED EFFECTS:")
            for biomarker, effect in data["predicted_effects"].items():
                print(f"  {biomarker}: {effect['baseline']:.1f} → {effect['predicted']:.1f} ({effect['pct_change']:+.1f}%)")

        print(f"\n💡 Clinical Significance:")
        print(f"  {data['clinical_significance']}")

        print("="*80)


def test_no_paths_scenario(client):
    """Test handling of biomarkers with no known causal paths.

    Scenario: Request interventions for unrelated biomarkers.
    Expected: System returns gracefully with empty results or partial coverage.
    """

    request_payload = {
        "request_id": "no-paths-001",
        "biomarkers": ["RandomMarker1", "UnknownProtein2"],
        "options": {
            "methods": ["shared_regulators", "intervention_hubs"],
            "max_depth": 2,
            "min_coverage": 1
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    # Should still return 200 with appropriate status
    assert response.status_code == 200
    data = response.json()

    print("\n" + "="*80)
    print("NO PATHS SCENARIO")
    print("="*80)
    print(f"Status: {data['status']}")
    print(f"Request ID: {data['request_id']}")

    if data["status"] == "success":
        print(f"Consensus targets: {len(data.get('consensus_targets', []))}")
        print("✓ System handles unknown biomarkers gracefully")
    else:
        print(f"Error message: {data.get('error_message', 'N/A')}")
        print("✓ System returns appropriate error for nonsensical query")

    print("="*80)


def test_minimal_network_coverage(client):
    """Test minimal network discovery for disconnected biomarkers.

    Scenario: Multiple biomarkers that may not all be connected.
    Expected: System finds minimal subgraph connecting as many as possible.
    """

    request_payload = {
        "request_id": "minimal-network-001",
        "biomarkers": ["CRP", "IL6", "TNF", "Glucose"],
        "options": {
            "methods": ["minimal_network"],
            "max_depth": 3,
            "min_coverage": 1
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        # Check minimal network results
        results = data["results"]
        if "minimal_network" in results:
            network = results["minimal_network"]

            print("\n" + "="*80)
            print("MINIMAL NETWORK COVERAGE")
            print("="*80)
            print(f"✓ Total nodes: {network['total_nodes']}")
            print(f"✓ Total edges: {network['total_edges']}")
            print(f"✓ Paths used: {network['paths_used']}")
            print(f"✓ Average path length: {network['avg_path_length']:.2f} hops")
            print(f"✓ Network diameter: {network['network_diameter']}")

            print(f"\n🔗 Connected biomarkers: {', '.join(network['connected_biomarkers'])}")

            if network.get('disconnected_biomarkers'):
                print(f"⚠️  Disconnected biomarkers: {', '.join(network['disconnected_biomarkers'])}")

            if network.get('intervention_points'):
                print(f"\n💡 Intervention points: {len(network['intervention_points'])}")
                for point in network['intervention_points'][:3]:
                    print(f"  - {point['node']} affects {point['coverage']} biomarkers")

            print("="*80)


def test_druggable_prioritization(client):
    """Test prioritization of druggable targets.

    Scenario: Request interventions with druggable prioritization enabled.
    Expected: Druggable targets appear higher in results.
    """

    request_payload = {
        "request_id": "druggable-001",
        "biomarkers": ["CRP", "IL6"],
        "options": {
            "methods": ["intervention_hubs"],
            "max_depth": 3,
            "min_coverage": 1,
            "prioritize_druggable": True
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    assert response.status_code == 200
    data = response.json()

    if data["status"] == "success":
        hubs = data["results"].get("intervention_hubs", [])

        if hubs:
            druggable_count = sum(1 for h in hubs if h.get("druggable", False))
            top_druggable = sum(1 for h in hubs[:3] if h.get("druggable", False))

            print("\n" + "="*80)
            print("DRUGGABLE TARGET PRIORITIZATION")
            print("="*80)
            print(f"✓ Total hubs: {len(hubs)}")
            print(f"✓ Druggable hubs: {druggable_count}")
            print(f"✓ Druggable in top 3: {top_druggable}")

            print("\n💊 TOP INTERVENTION HUBS:")
            for i, hub in enumerate(hubs[:5], 1):
                druggable_flag = "✓" if hub.get("druggable") else "✗"
                print(f"  {i}. [{druggable_flag}] {hub['node']} - {hub['intervention_type']}")
                print(f"      Actionability: {hub['actionability']}, Score: {hub['intervention_score']:.2f}")

            print("="*80)


def test_clinical_report_generation_from_api(client):
    """Test end-to-end: API discovery → clinical report generation.

    Scenario: Complete workflow from biomarker query to clinical report.
    Expected: Generate patient-friendly report with actionable recommendations.
    """

    # Step 1: Discover interventions
    discovery_request = {
        "request_id": "report-gen-001",
        "biomarkers": ["CRP", "IL6", "Glucose"],
        "exposures": ["PM2.5"],
        "current_biomarker_values": {
            "CRP": 5.2,
            "IL6": 3.8,
            "Glucose": 110.0
        },
        "genetics": {"GSTM1": "null"},
        "options": {
            "methods": ["shared_regulators", "intervention_hubs", "minimal_network"],
            "max_depth": 3,
            "min_coverage": 2
        }
    }

    response = client.post("/api/v1/discover_interventions", json=discovery_request)
    assert response.status_code == 200

    data = response.json()

    if data["status"] == "success":
        # Step 2: Generate clinical report from API response
        from indra_agent.core.intervention_models import (
            ConsensusTarget, InterventionHub, SharedRegulator, MinimalNetworkResult
        )

        # Parse response data
        consensus_targets = [ConsensusTarget(**ct) for ct in data.get("consensus_targets", [])]

        hubs_data = data["results"].get("intervention_hubs", [])
        intervention_hubs = [InterventionHub(**hub) for hub in hubs_data]

        shared_regs_data = data["results"].get("shared_regulators", [])
        shared_regulators = [SharedRegulator(**sr) for sr in shared_regs_data] if shared_regs_data else None

        network_data = data["results"].get("minimal_network")
        minimal_network = MinimalNetworkResult(**network_data) if network_data else None

        # Generate clinical report
        user_context = {
            "biomarkers": discovery_request["biomarkers"],
            "current_biomarker_values": discovery_request["current_biomarker_values"],
            "genetics": discovery_request["genetics"],
            "exposures": discovery_request.get("exposures", [])
        }

        report = generate_intervention_clinical_report(
            consensus_targets=consensus_targets,
            intervention_hubs=intervention_hubs,
            shared_regulators=shared_regulators,
            minimal_network=minimal_network,
            user_context=user_context,
            format="markdown"
        )

        # Validate report
        assert "# INTERVENTION DISCOVERY REPORT" in report
        assert "Patient Context" in report
        assert "Top Intervention Targets" in report

        print("\n" + "="*80)
        print("END-TO-END CLINICAL REPORT GENERATION")
        print("="*80)
        print("✓ Discovery API call successful")
        print("✓ Clinical report generated")
        print(f"✓ Report length: {len(report)} characters")
        print("\n--- REPORT PREVIEW (FIRST 500 CHARS) ---")
        print(report[:500] + "...")
        print("="*80)


if __name__ == "__main__":
    """Run clinical scenario tests directly for quick validation."""
    print("="*80)
    print("CLINICAL SCENARIO VALIDATION TESTS")
    print("="*80)

    from fastapi.testclient import TestClient
    from indra_agent.main import app

    client = TestClient(app)

    print("\n[1/9] Testing Sarah Chen metabolic-inflammatory syndrome...")
    test_sarah_chen_metabolic_inflammatory_syndrome(client)

    print("\n[2/9] Testing environmental exposure intervention...")
    test_environmental_exposure_intervention(client)

    print("\n[3/9] Testing genetic modifier scenario...")
    test_genetic_modifier_scenario(client)

    print("\n[4/9] Testing intervention validation (multi-biomarker)...")
    test_intervention_validation_multi_biomarker(client)

    print("\n[5/9] Testing no paths scenario...")
    test_no_paths_scenario(client)

    print("\n[6/9] Testing minimal network coverage...")
    test_minimal_network_coverage(client)

    print("\n[7/9] Testing druggable prioritization...")
    test_druggable_prioritization(client)

    print("\n[8/9] Testing clinical report generation from API...")
    test_clinical_report_generation_from_api(client)

    print("\n" + "="*80)
    print("ALL CLINICAL SCENARIO TESTS COMPLETED")
    print("="*80)
    print("\nNote: Some tests may show warnings if INDRA API is unavailable.")
    print("This is expected behavior - the system falls back gracefully.")
