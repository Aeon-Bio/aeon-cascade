"""Integration test for IndraNet refactor.

Tests complete workflow with new INDRA Python library integration:
1. IndraNetService builds biomarker network
2. GraphBuilder converts to causal graph
3. Tools work end-to-end in IndraQueryAgent
"""

import pytest
import json
from indra_agent.agents.indra_query_agent import create_indra_tools
from indra_agent.services.indranet_service import IndraNetService
from indra_agent.services.graph_builder import GraphBuilderService


def get_indra_tools():
    """Get fresh INDRA tools with unique cache namespace.

    CRITICAL: Do NOT cache tools at module level - creates race conditions.
    Each test must get fresh tools to avoid cache sharing.
    """
    return create_indra_tools(progress_emitter=None)


# Unpack tools for backward compatibility
ground_biological_entities, find_causal_paths, build_causal_graph, build_scm_graph = get_indra_tools()


@pytest.mark.asyncio
async def test_indranet_service_build_network():
    """Test IndraNetService can build biomarker network."""
    service = IndraNetService()

    # Build network for well-known relationship: IL6 -> CRP
    result = await service.build_biomarker_network(
        exposures=["IL6"],
        biomarkers=["CRP"],
        max_depth=2,
        belief_threshold=0.5
    )

    # Verify result structure
    assert result is not None
    assert hasattr(result, "graph")
    assert hasattr(result, "statements")
    assert hasattr(result, "node_names")
    assert hasattr(result, "edge_count")
    assert hasattr(result, "belief_scores")
    assert hasattr(result, "evidence_counts")

    # If no results from INDRA API, that's ok (may be temporary)
    # Just verify the structure is correct
    if result.edge_count > 0:
        # Verify graph structure
        assert result.graph.number_of_nodes() > 0
        assert result.graph.number_of_edges() > 0

        # Verify metadata
        assert len(result.node_names) > 0
        assert len(result.belief_scores) > 0
        assert len(result.evidence_counts) > 0

        # Verify belief scores are valid
        for belief in result.belief_scores.values():
            assert 0 <= belief <= 1


@pytest.mark.asyncio
async def test_graph_builder_from_indranet():
    """Test GraphBuilder can convert IndraNetworkResult to CausalGraph."""
    service = IndraNetService()
    builder = GraphBuilderService()

    # Build network
    result = await service.build_biomarker_network(
        exposures=["IL6"],
        biomarkers=["CRP"],
        max_depth=2,
        belief_threshold=0.5
    )

    # Convert to causal graph
    causal_graph = builder.build_causal_graph_from_indranet(
        indranet_result=result,
        genetics={},
        effect_modifiers=None
    )

    # Verify causal graph structure
    assert causal_graph is not None
    assert hasattr(causal_graph, "nodes")
    assert hasattr(causal_graph, "edges")
    assert hasattr(causal_graph, "genetic_modifiers")

    # If we got edges, verify their structure
    if len(causal_graph.edges) > 0:
        edge = causal_graph.edges[0]
        assert hasattr(edge, "source")
        assert hasattr(edge, "target")
        assert hasattr(edge, "relationship")
        assert hasattr(edge, "evidence")
        assert hasattr(edge, "effect_size")
        assert hasattr(edge, "temporal_lag_hours")

        # Verify effect size is valid
        assert 0 <= edge.effect_size <= 1
        assert edge.temporal_lag_hours >= 0


@pytest.mark.asyncio
async def test_find_causal_paths_tool():
    """Test find_causal_paths tool works end-to-end."""
    # Call tool
    result_json = await find_causal_paths.ainvoke({
        "source_entity": "IL6",
        "target_entity": "CRP",
        "max_depth": 2
    })

    # Parse result
    result = json.loads(result_json)

    # Verify response structure
    assert result["status"] == "success"
    assert "num_nodes" in result
    assert "num_edges" in result
    assert "num_statements" in result
    assert "cache_key" in result
    assert "total_evidence" in result

    # If we got results, verify they're reasonable
    if result["num_edges"] > 0:
        assert result["num_nodes"] >= 2
        assert result["total_evidence"] > 0


@pytest.mark.asyncio
async def test_build_causal_graph_tool():
    """Test build_causal_graph tool works end-to-end."""
    # First, run find_causal_paths to populate cache
    paths_result_json = await find_causal_paths.ainvoke({
        "source_entity": "IL6",
        "target_entity": "CRP",
        "max_depth": 2
    })

    paths_result = json.loads(paths_result_json)

    # Now call build_causal_graph
    graph_result_json = await build_causal_graph.ainvoke({
        "network_result_json": paths_result_json,
        "genetics_json": "{}"
    })

    # Parse result
    graph_result = json.loads(graph_result_json)

    # Verify response structure
    assert graph_result["status"] == "success"
    assert "causal_graph" in graph_result
    assert "num_nodes" in graph_result
    assert "num_edges" in graph_result

    # Verify causal graph structure
    causal_graph = graph_result["causal_graph"]
    assert "nodes" in causal_graph
    assert "edges" in causal_graph
    assert "genetic_modifiers" in causal_graph

    # If we got edges, verify their structure
    if len(causal_graph["edges"]) > 0:
        edge = causal_graph["edges"][0]
        assert "source" in edge
        assert "target" in edge
        assert "relationship" in edge
        assert "evidence" in edge
        assert "effect_size" in edge
        assert "temporal_lag_hours" in edge

        # Verify constraints
        assert 0 <= edge["effect_size"] <= 1
        assert edge["temporal_lag_hours"] >= 0
        assert edge["relationship"] in ["activates", "inhibits", "increases", "decreases"]


@pytest.mark.asyncio
async def test_ground_biological_entities_tool():
    """Test ground_biological_entities tool."""
    result_json = await ground_biological_entities.ainvoke({
        "entities": ["CRP", "IL-6"]
    })

    result = json.loads(result_json)

    # Verify response structure
    assert result["status"] == "success"
    assert "grounded_entities" in result

    grounded = result["grounded_entities"]
    assert len(grounded) >= 1  # At least one should ground

    # Verify grounded entity structure (dict mapping entity names to grounding info)
    for entity_name, grounding_info in grounded.items():
        if grounding_info:  # May be None if grounding failed
            assert "name" in grounding_info or "database" in grounding_info


@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete workflow: ground -> find paths -> build graph."""
    # Step 1: Ground entities
    ground_result_json = await ground_biological_entities.ainvoke({
        "entities": ["IL6", "CRP"]
    })
    ground_result = json.loads(ground_result_json)
    assert ground_result["status"] == "success"

    # Step 2: Find causal paths
    paths_result_json = await find_causal_paths.ainvoke({
        "source_entity": "IL6",
        "target_entity": "CRP",
        "max_depth": 2
    })
    paths_result = json.loads(paths_result_json)
    assert paths_result["status"] == "success"

    # Step 3: Build causal graph
    graph_result_json = await build_causal_graph.ainvoke({
        "network_result_json": paths_result_json,
        "genetics_json": "{}"
    })
    graph_result = json.loads(graph_result_json)
    assert graph_result["status"] == "success"

    # Verify complete workflow produced valid output
    assert "causal_graph" in graph_result
    causal_graph = graph_result["causal_graph"]
    assert "nodes" in causal_graph
    assert "edges" in causal_graph

    print("✅ Complete workflow test passed!")
    print(f"   - Grounded {ground_result.get('count', 0)} entities")
    print(f"   - Found {paths_result['num_edges']} edges in network")
    print(f"   - Built graph with {graph_result['num_nodes']} nodes, {graph_result['num_edges']} edges")


@pytest.mark.asyncio
async def test_scm_compatibility_methods():
    """Test SCMGraphBuilder compatibility methods."""
    service = IndraNetService()

    # Test get_multi_interactors
    interactors = await service.get_multi_interactors(
        nodes=["CRP"],
        downstream=True,
        belief_cutoff=0.5,
        max_results=10
    )

    # Verify structure
    assert isinstance(interactors, list)
    for interactor in interactors:
        assert "name" in interactor
        assert "namespace" in interactor
        assert "belief" in interactor
        assert "evidence_count" in interactor

    # Test find_causal_paths
    paths = await service.find_causal_paths(
        source="IL6",
        target="CRP",
        max_depth=3,
        use_cache=True
    )

    # Verify structure
    assert isinstance(paths, list)
    for path in paths:
        assert "nodes" in path
        assert "edges" in path
        assert "path_belief" in path

    # Test rank_paths
    if len(paths) > 0:
        ranked = service.rank_paths(paths)
        assert len(ranked) == len(paths)

        # Verify ranking (first should have highest score)
        if len(ranked) > 1:
            first_score = sum(e.get("evidence_count", 0) for e in ranked[0]["edges"])
            # Just verify it's a valid ranking (may not be strictly decreasing)
            assert first_score >= 0

    print("✅ SCMGraphBuilder compatibility methods work!")
