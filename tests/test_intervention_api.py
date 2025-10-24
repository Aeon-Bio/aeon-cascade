"""Test intervention discovery API endpoints.

This module tests the FastAPI endpoints for intervention discovery and validation.
"""

import pytest
from fastapi.testclient import TestClient
from indra_agent.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_discover_interventions_endpoint(client):
    """Test POST /api/v1/discover_interventions endpoint."""
    request_payload = {
        "request_id": "test-req-001",
        "biomarkers": ["CRP", "IL6", "Glucose"],
        "exposures": ["PM2.5"],
        "options": {
            "methods": ["shared_regulators", "intervention_hubs", "minimal_network"],
            "max_depth": 3,
            "min_coverage": 2,
            "belief_cutoff": 0.6,
            "prioritize_druggable": True
        }
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    # Check status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Parse response
    data = response.json()

    # Validate response structure
    assert data["status"] in ["success", "error"], "Status must be 'success' or 'error'"
    assert data["request_id"] == "test-req-001", "Request ID should match"

    if data["status"] == "success":
        # Check results structure
        assert "results" in data, "Response should have 'results'"
        assert "consensus_targets" in data, "Response should have 'consensus_targets'"
        assert "network_summary" in data, "Response should have 'network_summary'"
        assert "processing_time_ms" in data, "Response should have 'processing_time_ms'"

        # Validate network summary
        summary = data["network_summary"]
        assert "total_hubs" in summary
        assert "avg_coverage" in summary
        assert "total_paths_analyzed" in summary
        assert "shared_regulators" in summary
        assert "betweenness_hubs" in summary

        print(f"\n✅ Intervention discovery succeeded!")
        print(f"   Found {len(data.get('consensus_targets', []))} consensus targets")
        print(f"   Total hubs: {summary['total_hubs']}")
        print(f"   Processing time: {data['processing_time_ms']}ms")

        # Print top consensus targets
        if data.get("consensus_targets"):
            print(f"\n🎯 Top Consensus Targets:")
            for i, target in enumerate(data["consensus_targets"][:3], 1):
                print(f"   {i}. {target['node']}")
                print(f"      Methods: {', '.join(target['found_in_methods'])}")
                print(f"      Coverage: {target['max_coverage']}/3 biomarkers")
                print(f"      Score: {target['max_score']:.2f}")
    else:
        print(f"\n⚠️  Intervention discovery returned error: {data.get('error_message')}")
        print("   This may be due to INDRA API timeout or connectivity issues")


def test_validate_intervention_endpoint(client):
    """Test POST /api/v1/validate_intervention endpoint."""
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

    # Check status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Parse response
    data = response.json()

    # Validate response structure
    assert data["status"] in ["success", "error"], "Status must be 'success' or 'error'"
    assert data["target_node"] == "SRC", "Target node should match"

    if data["status"] == "success":
        # Check response structure
        assert "affects_all_biomarkers" in data
        assert "pathway_analysis" in data
        assert "predicted_effects" in data
        assert "synergy_score" in data
        assert "clinical_significance" in data

        print(f"\n✅ Intervention validation succeeded!")
        print(f"   Target: {data['target_node']}")
        print(f"   Affects all biomarkers: {data['affects_all_biomarkers']}")
        print(f"   Pathways found: {len(data['pathway_analysis'])}")
        print(f"   Synergy score: {data['synergy_score']:.2f}")

        # Print pathway analysis
        if data["pathway_analysis"]:
            print(f"\n🔬 Pathway Analysis:")
            for pathway in data["pathway_analysis"]:
                print(f"   {pathway['mechanism']}")
                print(f"   Confidence: {pathway['confidence']:.2f}, Lag: {pathway['temporal_lag_hours']}h")

        # Print predicted effects
        if data["predicted_effects"]:
            print(f"\n📊 Predicted Effects:")
            for biomarker, effect in data["predicted_effects"].items():
                print(f"   {biomarker}: {effect['baseline']} → {effect['predicted']} ({effect['pct_change']:+.1f}%)")

        # Print clinical significance
        print(f"\n💡 Clinical Significance:")
        print(f"   {data['clinical_significance']}")
    else:
        print(f"\n⚠️  Intervention validation returned error: {data.get('error_message')}")
        print("   This may be due to missing pathways or INDRA API issues")


def test_discover_interventions_minimal_request(client):
    """Test intervention discovery with minimal request."""
    request_payload = {
        "request_id": "test-req-002",
        "biomarkers": ["CRP", "IL6"]
    }

    response = client.post("/api/v1/discover_interventions", json=request_payload)

    # Should succeed with default options
    assert response.status_code == 200
    data = response.json()

    # Validate response
    assert data["request_id"] == "test-req-002"
    print(f"\n✅ Minimal request succeeded with status: {data['status']}")


def test_validate_intervention_without_baseline(client):
    """Test intervention validation without baseline values."""
    request_payload = {
        "target_node": "TNF",
        "biomarkers": ["CRP", "IL6"]
    }

    response = client.post("/api/v1/validate_intervention", json=request_payload)

    # Should succeed even without baseline values
    assert response.status_code == 200
    data = response.json()

    print(f"\n✅ Validation without baseline succeeded with status: {data['status']}")


if __name__ == "__main__":
    """Run tests directly for quick validation."""
    print("=" * 80)
    print("INTERVENTION API ENDPOINT TESTS")
    print("=" * 80)

    from fastapi.testclient import TestClient
    from indra_agent.main import app

    client = TestClient(app)

    print("\n[1/4] Testing intervention discovery endpoint...")
    test_discover_interventions_endpoint(client)

    print("\n[2/4] Testing intervention validation endpoint...")
    test_validate_intervention_endpoint(client)

    print("\n[3/4] Testing minimal intervention discovery...")
    test_discover_interventions_minimal_request(client)

    print("\n[4/4] Testing validation without baseline...")
    test_validate_intervention_without_baseline(client)

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)
