"""MCP server for causal inference tools.

Exposes three tools for agent-to-agent communication:
1. discover_causal_pathways: Query INDRA + build causal graph
2. predict_intervention: Perform do-calculus intervention
3. explain_mechanism: Generate natural language explanation

Usage:
    python -m indra_agent.mcp_server
"""

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    UserContext,
    Query,
    RequestOptions,
    InterventionRequest,
    Intervention,
)
from indra_agent.services.graph_store import get_graph_store
from indra_agent.services.scm_inference import SCMInferenceEngine

logger = logging.getLogger(__name__)

# Initialize INDRA client
indra_client = INDRAAgentClient()
scm_engine = SCMInferenceEngine()

# Create MCP server
server = Server("causal-inference-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="discover_causal_pathways",
            description=(
                "Discover causal pathways between biomarkers, exposures, and health outcomes "
                "using literature-backed evidence from INDRA bio-ontology. "
                "Returns a causal graph with effect sizes, confidence intervals, and evidence counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g., 'How does PM2.5 affect CRP?')",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID for context (optional)",
                        "default": "anonymous",
                    },
                    "genetics": {
                        "type": "object",
                        "description": "User genetics (e.g., {'GSTM1': 'null'})",
                        "additionalProperties": {"type": "string"},
                        "default": {},
                    },
                    "current_biomarkers": {
                        "type": "object",
                        "description": "Current biomarker values (e.g., {'CRP': 5.2})",
                        "additionalProperties": {"type": "number"},
                        "default": {},
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="predict_intervention",
            description=(
                "Perform causal intervention to answer 'What if?' questions using do-calculus. "
                "Computes counterfactual predictions: what would happen if we intervene on a specific node. "
                "Requires a graph_id from a previous discover_causal_pathways call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_id": {
                        "type": "string",
                        "description": "Graph ID from discover_causal_pathways",
                    },
                    "intervention_node": {
                        "type": "string",
                        "description": "Node to intervene on (e.g., 'PM2.5')",
                    },
                    "intervention_value": {
                        "type": "number",
                        "description": "Intervention value (e.g., 10.0 for 10 µg/m³ PM2.5)",
                    },
                    "target_biomarkers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Biomarkers to predict (e.g., ['CRP', 'IL-6'])",
                    },
                    "horizon_days": {
                        "type": "integer",
                        "description": "Prediction horizon in days (default: 90)",
                        "default": 90,
                    },
                },
                "required": ["graph_id", "intervention_node", "intervention_value", "target_biomarkers"],
            },
        ),
        Tool(
            name="explain_mechanism",
            description=(
                "Generate natural language explanation of causal mechanisms. "
                "Explains pathways, mediators, and evidence for a causal relationship. "
                "Requires a graph_id from discover_causal_pathways."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_id": {
                        "type": "string",
                        "description": "Graph ID from discover_causal_pathways",
                    },
                    "source": {
                        "type": "string",
                        "description": "Source node (e.g., 'PM2.5')",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target node (e.g., 'CRP')",
                    },
                },
                "required": ["graph_id", "source", "target"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    logger.info(f"MCP tool call: {name} with args: {arguments}")

    if name == "discover_causal_pathways":
        # Extract arguments
        query_text = arguments.get("query")
        user_id = arguments.get("user_id", "anonymous")
        genetics = arguments.get("genetics", {})
        current_biomarkers = arguments.get("current_biomarkers", {})

        # Build request
        request = CausalDiscoveryRequest(
            request_id=f"mcp-{user_id}-{hash(query_text)}",
            user_context=UserContext(
                user_id=user_id,
                genetics=genetics,
                current_biomarkers=current_biomarkers,
                location_history=[],
            ),
            query=Query(text=query_text),
            options=RequestOptions(),
        )

        try:
            # Process request
            response = await indra_client.process_request(request)

            # Extract graph_id for later use
            graph_id = f"graph-{request.request_id}"

            # Add graph_id to response
            result = response.model_dump()
            result["graph_id"] = graph_id

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        except Exception as e:
            logger.error(f"Error in discover_causal_pathways: {e}", exc_info=True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "status": "error"}, indent=2),
                )
            ]

    elif name == "predict_intervention":
        # Extract arguments
        graph_id = arguments.get("graph_id")
        intervention_node = arguments.get("intervention_node")
        intervention_value = arguments.get("intervention_value")
        target_biomarkers = arguments.get("target_biomarkers")
        horizon_days = arguments.get("horizon_days", 90)

        try:
            # Retrieve graph from store
            graph_store = get_graph_store()
            stored_data = graph_store.retrieve(graph_id)
            graph = stored_data["graph"]
            baseline_values = stored_data["baseline_values"]

            # Build SCM
            scm = scm_engine.build_scm(graph, baseline_values)

            # Compute baseline predictions
            baseline_predictions = scm_engine.predict(
                scm,
                target_biomarkers=target_biomarkers,
                horizon_days=horizon_days,
            )

            # Compute interventional predictions
            interventions = {intervention_node: intervention_value}
            interventional_predictions = scm_engine.intervene(
                scm,
                interventions=interventions,
                target_biomarkers=target_biomarkers,
                horizon_days=horizon_days,
            )

            # Build response with deltas
            predictions = {}
            for biomarker_id in target_biomarkers:
                if biomarker_id not in interventional_predictions:
                    continue

                baseline_pred = baseline_predictions.get(biomarker_id)
                int_pred = interventional_predictions[biomarker_id]

                baseline_mean = baseline_pred.timeline[-1]["mean"] if baseline_pred else 0.0
                int_mean = int_pred.timeline[-1]["mean"]

                delta_absolute = int_mean - baseline_mean
                delta_percent = (
                    100 * delta_absolute / baseline_mean if baseline_mean != 0 else 0.0
                )

                predictions[biomarker_id] = {
                    "baseline": baseline_mean,
                    "post_intervention": int_mean,
                    "delta_absolute": round(delta_absolute, 2),
                    "delta_percent": round(delta_percent, 1),
                    "timeline": int_pred.timeline,
                }

            result = {
                "status": "success",
                "intervention": {
                    "node": intervention_node,
                    "value": intervention_value,
                },
                "predictions": predictions,
            }

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        except ValueError as e:
            # Graph not found or expired
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "status": "error"}, indent=2),
                )
            ]
        except Exception as e:
            logger.error(f"Error in predict_intervention: {e}", exc_info=True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "status": "error"}, indent=2),
                )
            ]

    elif name == "explain_mechanism":
        # Extract arguments
        graph_id = arguments.get("graph_id")
        source = arguments.get("source")
        target = arguments.get("target")

        try:
            # Retrieve graph from store
            graph_store = get_graph_store()
            stored_data = graph_store.retrieve(graph_id)
            graph = stored_data["graph"]

            # Build SCM for causal effect computation
            scm = scm_engine.build_scm(graph)

            # Compute total causal effect
            effect_result = scm_engine.compute_causal_effect(scm, source, target)

            # Find pathways using NetworkX
            import networkx as nx

            G = nx.DiGraph()
            for edge in graph.edges:
                G.add_edge(edge.source, edge.target, edge_data=edge)

            pathways = []
            if source in G and target in G:
                try:
                    all_paths = list(nx.all_simple_paths(G, source, target, cutoff=5))
                    for path in all_paths[:3]:  # Top 3 pathways
                        # Build pathway description
                        pathway_desc = " → ".join(path)

                        # Get relationships
                        relationships = []
                        for i in range(len(path) - 1):
                            edge_data = G[path[i]][path[i + 1]]["edge_data"]
                            relationships.append(
                                {
                                    "from": path[i],
                                    "to": path[i + 1],
                                    "relationship": edge_data.relationship,
                                    "effect_size": edge_data.effect_size,
                                    "evidence_count": edge_data.evidence.count,
                                }
                            )

                        pathways.append(
                            {
                                "pathway": pathway_desc,
                                "nodes": path,
                                "relationships": relationships,
                            }
                        )
                except nx.NetworkXNoPath:
                    pass

            result = {
                "status": "success",
                "source": source,
                "target": target,
                "total_causal_effect": effect_result.get("total_effect", 0.0),
                "pathways": pathways,
                "explanation": (
                    f"{source} affects {target} through {len(pathways)} causal pathway(s). "
                    f"Total causal effect: {effect_result.get('total_effect', 0.0):.3f}"
                ),
            }

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )
            ]

        except ValueError as e:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "status": "error"}, indent=2),
                )
            ]
        except Exception as e:
            logger.error(f"Error in explain_mechanism: {e}", exc_info=True)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": str(e), "status": "error"}, indent=2),
                )
            ]

    else:
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}", "status": "error"}, indent=2),
            )
        ]


async def main():
    """Run MCP server."""
    logger.info("Starting MCP server for causal inference...")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(main())
