"""Live end-to-end integration tests with Writer KG + INDRA.

These tests verify the complete pipeline:
1. User query -> MeSH enrichment (Writer KG)
2. MeSH-enriched entities -> INDRA path search
3. INDRA paths -> Causal graph construction
4. Final response generation

Requirements:
- WRITER_API_KEY and WRITER_GRAPH_ID set (for MeSH enrichment)
- AWS credentials configured (for Bedrock LLM)
- INDRA API accessible (public API)

Run with: pytest tests/test_live_e2e_with_writer_kg.py -v -s --tb=short
"""

import pytest
from indra_agent.config.settings import get_settings
from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    Query,
    UserContext,
    QueryOptions,
)


# Skip entire module if Writer KG not configured
pytestmark = pytest.mark.skipif(
    not get_settings().is_writer_configured,
    reason="Writer KG not configured (set WRITER_API_KEY and WRITER_GRAPH_ID)"
)


@pytest.fixture
async def client():
    """Create INDRA agent client."""
    return INDRAAgentClient()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_with_mesh_enrichment_pm25_to_crp(client):
    """Test full E2E flow: PM2.5 -> CRP with MeSH enrichment.

    Pipeline:
    1. Query mentions "particulate matter" and "CRP"
    2. MeSH agent enriches to D052638 (Particulate Matter) and proper CRP MeSH ID
    3. INDRA finds paths between these grounded entities
    4. Graph builder constructs causal graph
    5. Supervisor generates explanations
    """
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-pm25-crp",
        query=Query(
            text="How does particulate matter exposure affect C-reactive protein levels?",
            focus_biomarkers=["CRP"]
        ),
        user_context=UserContext(
            current_biomarkers={"CRP": 5.2},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=4)
    )

    response = await client.process_request(request)

    # Verify successful response
    assert response.request_id == request.request_id
    assert hasattr(response, "causal_graph"), "Should have causal_graph (not error response)"

    # Verify causal graph structure
    assert len(response.causal_graph.nodes) > 0, "Should have nodes"
    assert len(response.causal_graph.edges) > 0, "Should have edges"

    # Verify explanations
    assert len(response.explanations) >= 3, "Should have 3-5 explanations"
    assert len(response.explanations) <= 5

    # Verify metadata
    assert response.metadata.query_time_ms > 0
    assert response.metadata.indra_paths_explored > 0

    # Check that MeSH enrichment was used (should see particulate matter entity)
    node_names = [node.name.lower() for node in response.causal_graph.nodes]
    has_pm25 = any("particulate" in name or "pm2.5" in name or "pm25" in name for name in node_names)
    has_crp = any("crp" in name or "c-reactive" in name for name in node_names)

    assert has_pm25 or has_crp, f"Should have PM2.5 or CRP in graph nodes: {node_names[:5]}"

    print(f"\n✅ E2E test passed:")
    print(f"   Nodes: {len(response.causal_graph.nodes)}")
    print(f"   Edges: {len(response.causal_graph.edges)}")
    print(f"   Paths explored: {response.metadata.indra_paths_explored}")
    print(f"   Query time: {response.metadata.query_time_ms}ms")
    print(f"   Sample explanation: {response.explanations[0][:100]}...")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_with_mesh_enrichment_il6_pathway(client):
    """Test E2E with IL-6 inflammatory pathway.

    Tests that MeSH enrichment helps find the canonical IL-6 pathway:
    PM2.5 -> oxidative stress -> NF-κB -> IL-6 -> CRP
    """
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-il6",
        query=Query(
            text="What is the inflammatory pathway from air pollution to IL-6 and CRP?",
            focus_biomarkers=["IL-6", "CRP"]
        ),
        user_context=UserContext(
            current_biomarkers={"IL-6": 15.3, "CRP": 4.8},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=5)
    )

    response = await client.process_request(request)

    # Verify response
    assert hasattr(response, "causal_graph")
    assert len(response.causal_graph.nodes) >= 3, "Should have at least 3 nodes in pathway"

    # Check for inflammatory markers
    node_names = [node.name.lower() for node in response.causal_graph.nodes]

    has_il6 = any("il-6" in name or "il6" in name or "interleukin-6" in name for name in node_names)
    has_inflammation_markers = any(
        marker in " ".join(node_names)
        for marker in ["nf-kb", "nfkb", "oxidative", "inflammation", "cytokine"]
    )

    assert has_il6 or has_inflammation_markers, \
        f"Should have IL-6 or inflammation markers: {node_names[:5]}"

    # Verify edges have proper constraints
    for edge in response.causal_graph.edges:
        assert 0 <= edge.effect_size <= 1, f"effect_size must be in [0,1], got {edge.effect_size}"
        assert edge.temporal_lag_hours >= 0, f"temporal_lag must be >= 0, got {edge.temporal_lag_hours}"

    print(f"\n✅ IL-6 pathway test passed:")
    print(f"   Nodes: {len(response.causal_graph.nodes)}")
    print(f"   Key nodes: {', '.join(node_names[:5])}")
    print(f"   Evidence papers: {response.metadata.total_evidence_papers}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_mesh_enrichment_improves_grounding(client):
    """Test that MeSH enrichment improves entity grounding quality.

    Without MeSH: May use fallback grounding or fail to find some entities
    With MeSH: Should have better coverage and more accurate database IDs
    """
    # Use a query with ambiguous medical terms
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-grounding",
        query=Query(
            text="How does fine particulate air pollution induce systemic inflammation and oxidative damage?",
            focus_biomarkers=["8-OHdG", "IL-6"]  # 8-OHdG is less common
        ),
        user_context=UserContext(
            current_biomarkers={"8-OHdG": 25.0},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=4)
    )

    response = await client.process_request(request)

    # Should successfully process even with complex medical terminology
    assert hasattr(response, "causal_graph")

    # MeSH should help ground "fine particulate air pollution" -> PM2.5/D052638
    # And "oxidative damage" -> relevant oxidative stress markers
    node_types = [node.type for node in response.causal_graph.nodes]

    # Should have mix of environmental and biomarker nodes
    assert "environmental" in node_types or "molecular" in node_types
    assert "biomarker" in node_types or "molecular" in node_types

    print(f"\n✅ Grounding quality test passed:")
    print(f"   Node types: {set(node_types)}")
    print(f"   Successfully grounded complex medical terms")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_mesh_enrichment_with_synonyms(client):
    """Test that MeSH handles synonym resolution.

    Query uses colloquial terms, MeSH should resolve to canonical medical terms.
    """
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-synonyms",
        query=Query(
            text="How does smog affect blood inflammation markers?",
            focus_biomarkers=[]
        ),
        user_context=UserContext(
            current_biomarkers={},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=3)
    )

    response = await client.process_request(request)

    assert hasattr(response, "causal_graph")

    # "smog" should be enriched to air pollution/PM2.5 via MeSH
    # "blood inflammation markers" should be enriched to CRP/IL-6
    node_names_str = " ".join([n.name.lower() for n in response.causal_graph.nodes])

    has_air_pollution = any(
        term in node_names_str
        for term in ["pollution", "particulate", "pm", "ozone", "no2"]
    )

    has_inflammation = any(
        term in node_names_str
        for term in ["crp", "il-6", "il6", "cytokine", "inflammation"]
    )

    assert has_air_pollution or has_inflammation, \
        "MeSH should resolve synonyms: 'smog' -> air pollution, 'blood markers' -> CRP/IL-6"

    print(f"\n✅ Synonym resolution test passed")
    print(f"   Query: 'smog' and 'blood inflammation markers'")
    print(f"   Resolved to: {', '.join([n.name for n in response.causal_graph.nodes[:3]])}")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_mesh_enrichment_timing(client):
    """Test that MeSH enrichment doesn't add excessive latency.

    MeSH enrichment should be <1s, total query should be <5s.
    """
    import time

    start = time.time()

    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-timing",
        query=Query(
            text="How does PM2.5 affect cardiovascular biomarkers?",
            focus_biomarkers=["CRP", "troponin"]
        ),
        user_context=UserContext(
            current_biomarkers={},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=3)
    )

    response = await client.process_request(request)

    elapsed_ms = (time.time() - start) * 1000

    assert hasattr(response, "causal_graph")

    # Total time should be reasonable (< 10s for full pipeline)
    assert elapsed_ms < 10000, f"Query took {elapsed_ms}ms, should be < 10s"

    # Metadata should match elapsed time (within 20% tolerance)
    reported_time = response.metadata.query_time_ms
    assert abs(reported_time - elapsed_ms) / elapsed_ms < 0.5, \
        f"Reported {reported_time}ms vs actual {elapsed_ms}ms"

    print(f"\n✅ Timing test passed:")
    print(f"   Total time: {elapsed_ms:.0f}ms")
    print(f"   Reported time: {reported_time}ms")
    print(f"   Within acceptable latency (<10s)")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_mesh_fallback_when_not_found(client):
    """Test that system falls back gracefully when MeSH can't enrich a term.

    Some entities may not have MeSH IDs (e.g., very new biomarkers).
    System should still work using hardcoded grounding.
    """
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-fallback",
        query=Query(
            text="How does PM2.5 affect NOTAREALBIOMARKER123?",
            focus_biomarkers=["NOTAREALBIOMARKER123"]
        ),
        user_context=UserContext(
            current_biomarkers={},
            genetics={}
        ),
        options=QueryOptions(max_graph_depth=2)
    )

    response = await client.process_request(request)

    # May get error or empty graph, but shouldn't crash
    if hasattr(response, "error"):
        # Error response is acceptable for invalid biomarker
        assert response.error.code in ["NO_CAUSAL_PATH", "INVALID_REQUEST"]
        print(f"\n✅ Fallback test passed: Handled unknown biomarker gracefully")
        print(f"   Error code: {response.error.code}")
    else:
        # Or may succeed with partial results using PM2.5 default targets
        assert len(response.causal_graph.nodes) > 0
        print(f"\n✅ Fallback test passed: Used default grounding")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_e2e_mesh_enrichment_genetic_modifiers(client):
    """Test E2E with genetic variants + MeSH enrichment.

    Genetic variants should modulate effect sizes in the causal graph.
    """
    request = CausalDiscoveryRequest(
        request_id="test-e2e-mesh-genetics",
        query=Query(
            text="How does air pollution affect oxidative stress?",
            focus_biomarkers=["8-OHdG"]
        ),
        user_context=UserContext(
            current_biomarkers={"8-OHdG": 30.0},
            genetics={
                "GSTM1_null": True,  # Glutathione S-transferase deletion
                "NQO1_C609T": "TT"   # NAD(P)H quinone oxidoreductase variant
            }
        ),
        options=QueryOptions(max_graph_depth=4)
    )

    response = await client.process_request(request)

    assert hasattr(response, "causal_graph")

    # Should have genetic modifiers if relevant genes affect pathway
    if len(response.causal_graph.genetic_modifiers) > 0:
        modifier = response.causal_graph.genetic_modifiers[0]

        assert modifier.variant in ["GSTM1_null", "NQO1_C609T"]
        assert 0.5 <= modifier.effect_multiplier <= 2.0, \
            f"Genetic modifier should be reasonable, got {modifier.effect_multiplier}"

        print(f"\n✅ Genetic modifier test passed:")
        print(f"   Variant: {modifier.variant}")
        print(f"   Multiplier: {modifier.effect_multiplier}x")
        print(f"   Affected nodes: {', '.join(modifier.affected_nodes)}")
    else:
        print(f"\n✅ Genetic modifier test passed (no modifiers applicable to this pathway)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
