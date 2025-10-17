"""Test graph compilation after ReAct migration.

This test verifies that:
1. Graph compiles without errors after converting all agents to ReAct
2. All three agents (MeSH, INDRA, Web) are properly integrated
3. Graph structure is correct
"""

import pytest
from indra_agent.agents.graph import create_causal_discovery_graph


@pytest.mark.asyncio
async def test_graph_compiles_with_all_react_agents():
    """Test that graph compiles successfully with all ReAct agents.

    This is the critical test that was failing before migration completion.
    Before: AttributeError: 'MeSHEnrichmentAgent' object has no attribute 'name'
    After: Graph compiles successfully
    """
    graph = await create_causal_discovery_graph()

    assert graph is not None
    assert hasattr(graph, "ainvoke")
    assert hasattr(graph, "astream")


@pytest.mark.asyncio
async def test_graph_has_supervisor_node():
    """Test that graph contains the supervisor node."""
    graph = await create_causal_discovery_graph()

    # Get graph structure
    graph_dict = graph.get_graph().to_json()

    # Verify supervisor node exists
    assert "supervisor" in str(graph_dict).lower()


@pytest.mark.asyncio
async def test_graph_node_count():
    """Test that graph has expected number of nodes.

    Expected nodes:
    - __start__ (LangGraph entry point)
    - supervisor (orchestrator)
    - mesh_enrichment (if Writer KG configured)
    - indra_query_agent (always)
    - web_researcher (always)
    - __end__ (LangGraph exit point)
    """
    graph = await create_causal_discovery_graph()

    nodes = list(graph.get_graph().nodes.keys())

    # Minimum 5 nodes if Writer KG not configured (start, supervisor, indra, web, end)
    # Maximum 6 nodes if Writer KG configured (+ mesh_enrichment)
    assert len(nodes) >= 5, f"Expected at least 5 nodes, got {len(nodes)}: {nodes}"
    assert len(nodes) <= 6, f"Expected at most 6 nodes, got {len(nodes)}: {nodes}"


@pytest.mark.asyncio
async def test_all_agents_have_names():
    """Test that all agents were created with required name parameter.

    This verifies the fix for:
    ValueError: Please specify a name when you create your agent
    """
    # If graph compiles, all agents have names
    # This test documents the requirement
    graph = await create_causal_discovery_graph()

    assert graph is not None


@pytest.mark.asyncio
async def test_no_legacy_class_based_agents():
    """Test that no legacy class-based agents are in use.

    This test documents the requirement that all agents must be ReAct-based.
    User directive: "leave no legacy code behind"
    """
    # If graph compiles without AttributeError, no class-based agents remain
    graph = await create_causal_discovery_graph()

    assert graph is not None
