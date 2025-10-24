"""Tests for MCP server.

Tests verify:
- Tool listing
- discover_causal_pathways tool
- predict_intervention tool
- explain_mechanism tool
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from indra_agent.mcp_server import list_tools, call_tool
from indra_agent.core.models import (
    CausalDiscoveryResponse,
    CausalGraph,
    Node,
    Edge,
    Evidence,
    Grounding,
    Metadata,
)


class TestMCPServer:
    """Test MCP server tools."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_three_tools(self):
        """Test that list_tools returns all three tools."""
        tools = await list_tools()

        assert len(tools) == 3

        tool_names = {tool.name for tool in tools}
        assert "discover_causal_pathways" in tool_names
        assert "predict_intervention" in tool_names
        assert "explain_mechanism" in tool_names

    @pytest.mark.asyncio
    async def test_discover_causal_pathways_tool_schema(self):
        """Test that discover_causal_pathways has correct schema."""
        tools = await list_tools()
        discover_tool = next(t for t in tools if t.name == "discover_causal_pathways")

        assert "query" in discover_tool.inputSchema["properties"]
        assert "user_id" in discover_tool.inputSchema["properties"]
        assert "genetics" in discover_tool.inputSchema["properties"]
        assert "current_biomarkers" in discover_tool.inputSchema["properties"]

        # Required field
        assert "query" in discover_tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_discover_causal_pathways_returns_graph(self):
        """Test that discover_causal_pathways returns a causal graph."""
        # Mock INDRA client
        mock_graph = CausalGraph(
            nodes=[
                Node(
                    id="PM2.5",
                    type="environmental",
                    label="PM2.5",
                    grounding=Grounding(database="MESH", identifier="D052638"),
                ),
                Node(
                    id="CRP",
                    type="biomarker",
                    label="CRP",
                    grounding=Grounding(database="HGNC", identifier="2367"),
                ),
            ],
            edges=[
                Edge(
                    source="PM2.5",
                    target="CRP",
                    relationship="increases",
                    effect_size=0.75,
                    temporal_lag_hours=24,
                    evidence=Evidence(
                        count=100,
                        confidence=0.85,
                        sources=["PMID:12345"],
                        summary="PM2.5 increases CRP",
                    ),
                )
            ],
            genetic_modifiers=[],
        )

        mock_response = CausalDiscoveryResponse(
            request_id="test-request",
            status="success",
            causal_graph=mock_graph,
            metadata=Metadata(
                query_time_ms=100,
                indra_paths_explored=5,
                total_evidence_papers=100,
            ),
            explanations=["PM2.5 increases CRP through inflammatory pathways"],
        )

        with patch("indra_agent.mcp_server.indra_client") as mock_client:
            mock_client.process_request = AsyncMock(return_value=mock_response)

            result = await call_tool(
                name="discover_causal_pathways",
                arguments={"query": "How does PM2.5 affect CRP?"},
            )

            assert len(result) == 1
            text_content = result[0]
            assert text_content.type == "text"

            # Parse JSON response
            response_data = json.loads(text_content.text)
            assert response_data["status"] == "success"
            assert "graph_id" in response_data
            assert "causal_graph" in response_data
            assert len(response_data["causal_graph"]["nodes"]) == 2
            assert len(response_data["causal_graph"]["edges"]) == 1

    @pytest.mark.asyncio
    async def test_predict_intervention_tool_schema(self):
        """Test that predict_intervention has correct schema."""
        tools = await list_tools()
        intervention_tool = next(t for t in tools if t.name == "predict_intervention")

        assert "graph_id" in intervention_tool.inputSchema["properties"]
        assert "intervention_node" in intervention_tool.inputSchema["properties"]
        assert "intervention_value" in intervention_tool.inputSchema["properties"]
        assert "target_biomarkers" in intervention_tool.inputSchema["properties"]

        # Required fields
        required = intervention_tool.inputSchema["required"]
        assert "graph_id" in required
        assert "intervention_node" in required
        assert "intervention_value" in required
        assert "target_biomarkers" in required

    @pytest.mark.asyncio
    async def test_predict_intervention_returns_predictions(self):
        """Test that predict_intervention returns predictions."""
        # Mock graph store
        mock_graph = CausalGraph(
            nodes=[
                Node(
                    id="PM2.5",
                    type="environmental",
                    label="PM2.5",
                    grounding=Grounding(database="MESH", identifier="D052638"),
                ),
                Node(
                    id="CRP",
                    type="biomarker",
                    label="CRP",
                    grounding=Grounding(database="HGNC", identifier="2367"),
                ),
            ],
            edges=[
                Edge(
                    source="PM2.5",
                    target="CRP",
                    relationship="increases",
                    effect_size=0.75,
                    temporal_lag_hours=24,
                    evidence=Evidence(
                        count=100,
                        confidence=0.85,
                        sources=["PMID:12345"],
                        summary="PM2.5 increases CRP",
                    ),
                )
            ],
            genetic_modifiers=[],
        )

        mock_stored_data = {
            "graph": mock_graph,
            "baseline_values": {"PM2.5": 30.0, "CRP": 5.0},
        }

        with patch("indra_agent.mcp_server.get_graph_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.retrieve.return_value = mock_stored_data
            mock_get_store.return_value = mock_store

            result = await call_tool(
                name="predict_intervention",
                arguments={
                    "graph_id": "test-graph-id",
                    "intervention_node": "PM2.5",
                    "intervention_value": 10.0,
                    "target_biomarkers": ["CRP"],
                    "horizon_days": 90,
                },
            )

            assert len(result) == 1
            text_content = result[0]
            assert text_content.type == "text"

            # Parse JSON response
            response_data = json.loads(text_content.text)
            assert response_data["status"] == "success"
            assert "intervention" in response_data
            assert "predictions" in response_data
            assert "CRP" in response_data["predictions"]

            crp_pred = response_data["predictions"]["CRP"]
            assert "baseline" in crp_pred
            assert "post_intervention" in crp_pred
            assert "delta_absolute" in crp_pred
            assert "delta_percent" in crp_pred

    @pytest.mark.asyncio
    async def test_explain_mechanism_tool_schema(self):
        """Test that explain_mechanism has correct schema."""
        tools = await list_tools()
        explain_tool = next(t for t in tools if t.name == "explain_mechanism")

        assert "graph_id" in explain_tool.inputSchema["properties"]
        assert "source" in explain_tool.inputSchema["properties"]
        assert "target" in explain_tool.inputSchema["properties"]

        # Required fields
        required = explain_tool.inputSchema["required"]
        assert "graph_id" in required
        assert "source" in required
        assert "target" in required

    @pytest.mark.asyncio
    async def test_explain_mechanism_returns_explanation(self):
        """Test that explain_mechanism returns pathway explanation."""
        # Mock graph store
        mock_graph = CausalGraph(
            nodes=[
                Node(
                    id="PM2.5",
                    type="environmental",
                    label="PM2.5",
                    grounding=Grounding(database="MESH", identifier="D052638"),
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
            ],
            edges=[
                Edge(
                    source="PM2.5",
                    target="IL6",
                    relationship="increases",
                    effect_size=0.70,
                    temporal_lag_hours=12,
                    evidence=Evidence(
                        count=80,
                        confidence=0.80,
                        sources=["PMID:11111"],
                        summary="PM2.5 increases IL6",
                    ),
                ),
                Edge(
                    source="IL6",
                    target="CRP",
                    relationship="increases",
                    effect_size=0.85,
                    temporal_lag_hours=24,
                    evidence=Evidence(
                        count=150,
                        confidence=0.90,
                        sources=["PMID:22222"],
                        summary="IL6 increases CRP",
                    ),
                ),
            ],
            genetic_modifiers=[],
        )

        mock_stored_data = {"graph": mock_graph, "baseline_values": {}}

        with patch("indra_agent.mcp_server.get_graph_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.retrieve.return_value = mock_stored_data
            mock_get_store.return_value = mock_store

            result = await call_tool(
                name="explain_mechanism",
                arguments={
                    "graph_id": "test-graph-id",
                    "source": "PM2.5",
                    "target": "CRP",
                },
            )

            assert len(result) == 1
            text_content = result[0]
            assert text_content.type == "text"

            # Parse JSON response
            response_data = json.loads(text_content.text)
            assert response_data["status"] == "success"
            assert response_data["source"] == "PM2.5"
            assert response_data["target"] == "CRP"
            assert "total_causal_effect" in response_data
            assert "pathways" in response_data
            assert "explanation" in response_data

            # Should find pathway: PM2.5 → IL6 → CRP
            assert len(response_data["pathways"]) > 0
            pathway = response_data["pathways"][0]
            assert "PM2.5" in pathway["nodes"]
            assert "CRP" in pathway["nodes"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Test that unknown tool name returns error."""
        result = await call_tool(name="unknown_tool", arguments={})

        assert len(result) == 1
        text_content = result[0]
        response_data = json.loads(text_content.text)

        assert response_data["status"] == "error"
        assert "Unknown tool" in response_data["error"]

    @pytest.mark.asyncio
    async def test_predict_intervention_graph_not_found(self):
        """Test that predict_intervention returns error for missing graph."""
        with patch("indra_agent.mcp_server.get_graph_store") as mock_get_store:
            mock_store = MagicMock()
            mock_store.retrieve.side_effect = ValueError("Graph not found")
            mock_get_store.return_value = mock_store

            result = await call_tool(
                name="predict_intervention",
                arguments={
                    "graph_id": "nonexistent-graph",
                    "intervention_node": "PM2.5",
                    "intervention_value": 10.0,
                    "target_biomarkers": ["CRP"],
                },
            )

            assert len(result) == 1
            text_content = result[0]
            response_data = json.loads(text_content.text)

            assert response_data["status"] == "error"
            assert "Graph not found" in response_data["error"]
