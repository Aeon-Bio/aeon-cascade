"""Intervention planner agent for analyzing causal graphs and proposing interventions.

This agent analyzes causal graph structure to identify optimal intervention points,
detect synergies from multi-target interventions, and find feedback loops.
"""

import json
import logging
from typing import Annotated, Any, Dict, List

from langchain_aws import ChatBedrock
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import INTERVENTION_PLANNER_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.core.models import CausalGraph
from indra_agent.services.graph_analysis import GraphAnalysisService

logger = logging.getLogger(__name__)


def create_intervention_planner_tools():
    """Create tools for intervention planner agent.

    Returns:
        List of LangChain tools for intervention analysis
    """
    # Initialize graph analysis service
    graph_analysis = GraphAnalysisService()

    @tool
    async def analyze_graph_structure(
        graph_json: Annotated[str, "JSON string of CausalGraph from causal discovery"],
        target_biomarkers: Annotated[List[str], "List of biomarker node IDs to optimize"] = None
    ) -> str:
        """Analyze causal graph structure to identify intervention opportunities.

        This tool examines the causal graph to find:
        - Convergent nodes (high in-degree) that affect multiple targets
        - Upstream environmental/molecular nodes that can be intervened on
        - Critical pathways connecting interventions to target biomarkers

        Args:
            graph_json: JSON string containing CausalGraph with nodes and edges
            target_biomarkers: Optional list of biomarker IDs to focus on

        Returns:
            JSON string with graph analysis results
        """
        try:
            graph_data = json.loads(graph_json)
            causal_graph = graph_data.get("causal_graph", {})

            nodes = causal_graph.get("nodes", [])
            edges = causal_graph.get("edges", [])

            # Build adjacency structures
            in_degree = {node["id"]: 0 for node in nodes}
            out_degree = {node["id"]: 0 for node in nodes}
            downstream_targets = {node["id"]: set() for node in nodes}

            for edge in edges:
                source = edge["source"]
                target = edge["target"]
                in_degree[target] += 1
                out_degree[source] += 1
                downstream_targets[source].add(target)

            # Find convergent nodes (in_degree > 1)
            convergent_nodes = [
                {
                    "id": node_id,
                    "type": next((n["type"] for n in nodes if n["id"] == node_id), "unknown"),
                    "label": next((n["label"] for n in nodes if n["id"] == node_id), node_id),
                    "in_degree": degree,
                    "is_biomarker": next((n["type"] == "biomarker" for n in nodes if n["id"] == node_id), False)
                }
                for node_id, degree in in_degree.items()
                if degree > 1
            ]

            # Sort by in_degree descending
            convergent_nodes.sort(key=lambda x: x["in_degree"], reverse=True)

            # Find intervening nodes (environmental or molecular with high out-degree)
            intervening_candidates = [
                {
                    "id": node["id"],
                    "type": node["type"],
                    "label": node["label"],
                    "out_degree": out_degree[node["id"]],
                    "affects_biomarkers": len([
                        t for t in downstream_targets[node["id"]]
                        if any(n["id"] == t and n["type"] == "biomarker" for n in nodes)
                    ])
                }
                for node in nodes
                if node["type"] in ["environmental", "molecular"]
                and out_degree[node["id"]] > 0
            ]

            # Sort by out_degree descending
            intervening_candidates.sort(key=lambda x: x["out_degree"], reverse=True)

            # Find pathways from environmental nodes to target biomarkers
            if target_biomarkers:
                target_set = set(target_biomarkers)
            else:
                target_set = {n["id"] for n in nodes if n["type"] == "biomarker"}

            critical_pathways = []
            for env_node in [n for n in nodes if n["type"] == "environmental"]:
                for target_id in target_set:
                    # Simple BFS to find if path exists
                    visited = set()
                    queue = [(env_node["id"], [env_node["id"]])]

                    while queue:
                        current, path = queue.pop(0)
                        if current == target_id:
                            # Found a path
                            path_edges = []
                            for i in range(len(path) - 1):
                                edge = next((e for e in edges if e["source"] == path[i] and e["target"] == path[i+1]), None)
                                if edge:
                                    path_edges.append({
                                        "source": edge["source"],
                                        "target": edge["target"],
                                        "relationship": edge["relationship"],
                                        "effect_size": edge["effect_size"]
                                    })

                            critical_pathways.append({
                                "source": env_node["id"],
                                "target": target_id,
                                "path_length": len(path) - 1,
                                "nodes": path,
                                "edges": path_edges
                            })
                            break

                        if current in visited:
                            continue
                        visited.add(current)

                        # Find outgoing edges
                        for edge in edges:
                            if edge["source"] == current and edge["target"] not in visited:
                                queue.append((edge["target"], path + [edge["target"]]))

            return json.dumps({
                "status": "success",
                "convergent_nodes": convergent_nodes[:5],  # Top 5
                "intervening_candidates": intervening_candidates[:5],  # Top 5
                "critical_pathways": critical_pathways,
                "summary": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "num_convergent_nodes": len(convergent_nodes),
                    "num_environmental_nodes": len([n for n in nodes if n["type"] == "environmental"]),
                    "num_biomarker_nodes": len([n for n in nodes if n["type"] == "biomarker"])
                }
            })

        except Exception as e:
            logger.error(f"Graph structure analysis failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def find_convergent_nodes(
        graph_json: Annotated[str, "JSON string of CausalGraph"],
        min_in_degree: Annotated[int, "Minimum in-degree to consider convergent"] = 2
    ) -> str:
        """Identify convergent nodes where multiple causal paths meet.

        Convergent nodes are high-value intervention targets because they integrate
        signals from multiple upstream pathways. For example, IRS-1 receives inputs
        from both IL-6 (inflammatory) and JNK (metabolic stress).

        Args:
            graph_json: JSON string containing CausalGraph
            min_in_degree: Minimum number of incoming edges to be considered convergent

        Returns:
            JSON string with convergent nodes and their upstream sources
        """
        try:
            graph_data = json.loads(graph_json)
            causal_graph = graph_data.get("causal_graph", {})

            nodes = causal_graph.get("nodes", [])
            edges = causal_graph.get("edges", [])

            # Map node IDs to labels
            node_labels = {node["id"]: node["label"] for node in nodes}
            node_types = {node["id"]: node["type"] for node in nodes}

            # Find incoming edges for each node
            incoming_edges = {}
            for edge in edges:
                target = edge["target"]
                if target not in incoming_edges:
                    incoming_edges[target] = []
                incoming_edges[target].append({
                    "source": edge["source"],
                    "source_label": node_labels.get(edge["source"], edge["source"]),
                    "relationship": edge["relationship"],
                    "effect_size": edge["effect_size"]
                })

            # Filter convergent nodes
            convergent = []
            for node_id, edges_in in incoming_edges.items():
                if len(edges_in) >= min_in_degree:
                    convergent.append({
                        "node_id": node_id,
                        "label": node_labels.get(node_id, node_id),
                        "type": node_types.get(node_id, "unknown"),
                        "in_degree": len(edges_in),
                        "incoming_edges": edges_in
                    })

            # Sort by in_degree descending
            convergent.sort(key=lambda x: x["in_degree"], reverse=True)

            return json.dumps({
                "status": "success",
                "convergent_nodes": convergent,
                "count": len(convergent)
            })

        except Exception as e:
            logger.error(f"Convergent node detection failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def detect_feedback_loops(
        graph_json: Annotated[str, "JSON string of CausalGraph"]
    ) -> str:
        """Detect feedback loops (cycles) in the causal graph.

        Feedback loops are critical for understanding disease dynamics. For example,
        the inflammation-insulin resistance loop: IL-6 → IRS-1 inhibition → hyperglycemia
        → AGEs → more inflammation (back to IL-6).

        Args:
            graph_json: JSON string containing CausalGraph

        Returns:
            JSON string with detected cycles
        """
        try:
            graph_data = json.loads(graph_json)
            causal_graph = graph_data.get("causal_graph", {})

            nodes = causal_graph.get("nodes", [])
            edges = causal_graph.get("edges", [])

            # Build adjacency list
            adjacency = {node["id"]: [] for node in nodes}
            edge_map = {}

            for edge in edges:
                source = edge["source"]
                target = edge["target"]
                adjacency[source].append(target)
                edge_map[(source, target)] = edge

            # DFS-based cycle detection
            def find_cycles(start_node, current_node, path, visited_in_path, all_cycles):
                """DFS to find cycles."""
                if current_node in visited_in_path:
                    # Found a cycle
                    cycle_start_idx = path.index(current_node)
                    cycle = path[cycle_start_idx:] + [current_node]

                    # Build cycle with edges
                    cycle_edges = []
                    for i in range(len(cycle) - 1):
                        edge = edge_map.get((cycle[i], cycle[i + 1]))
                        if edge:
                            cycle_edges.append({
                                "source": edge["source"],
                                "target": edge["target"],
                                "relationship": edge["relationship"],
                                "effect_size": edge["effect_size"]
                            })

                    all_cycles.append({
                        "nodes": cycle,
                        "edges": cycle_edges,
                        "length": len(cycle) - 1
                    })
                    return

                visited_in_path.add(current_node)
                path.append(current_node)

                for neighbor in adjacency.get(current_node, []):
                    find_cycles(start_node, neighbor, path, visited_in_path, all_cycles)

                path.pop()
                visited_in_path.remove(current_node)

            # Find all cycles
            all_cycles = []
            for node_id in adjacency.keys():
                find_cycles(node_id, node_id, [], set(), all_cycles)

            # Remove duplicates (cycles detected from different starting points)
            unique_cycles = []
            seen_sets = []
            for cycle in all_cycles:
                cycle_set = frozenset(cycle["nodes"])
                if cycle_set not in seen_sets:
                    seen_sets.append(cycle_set)
                    unique_cycles.append(cycle)

            return json.dumps({
                "status": "success",
                "feedback_loops": unique_cycles,
                "count": len(unique_cycles)
            })

        except Exception as e:
            logger.error(f"Feedback loop detection failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def compute_synergy_score(
        graph_json: Annotated[str, "JSON string of CausalGraph"],
        intervention_node_id: Annotated[str, "Node ID to intervene on"],
        target_biomarkers: Annotated[List[str], "List of biomarker node IDs to optimize"]
    ) -> str:
        """Compute synergy score for a single intervention affecting multiple targets.

        Synergy occurs when a single intervention affects multiple disease pathways
        simultaneously. For example, reducing PM2.5 exposure decreases both inflammation
        (CRP) and insulin resistance (HbA1c) via shared oxidative stress pathway.

        Synergy score interpretation:
        - Score < 1.0: Sub-additive (no synergy)
        - Score = 1.0: Additive (independent effects)
        - Score > 1.0: Super-additive (true synergy from convergent pathways)

        Args:
            graph_json: JSON string containing CausalGraph
            intervention_node_id: Node ID to intervene on (e.g., "PM2.5", "oxidative_stress")
            target_biomarkers: List of biomarker IDs to optimize (e.g., ["CRP", "HbA1c"])

        Returns:
            JSON string with synergy analysis
        """
        try:
            graph_data = json.loads(graph_json)
            causal_graph_dict = graph_data.get("causal_graph", {})

            # Convert to CausalGraph Pydantic model
            causal_graph = CausalGraph(**causal_graph_dict)

            # Compute synergy using graph analysis service
            synergy_result = graph_analysis.compute_multi_target_synergy(
                graph=causal_graph,
                intervention_node_id=intervention_node_id,
                target_biomarkers=target_biomarkers
            )

            return json.dumps({
                "status": "success",
                **synergy_result
            })

        except Exception as e:
            logger.error(f"Synergy computation failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    return [
        analyze_graph_structure,
        find_convergent_nodes,
        detect_feedback_loops,
        compute_synergy_score
    ]


async def create_intervention_planner_agent(handoff_tools=None):
    """Create intervention planner agent using ReAct pattern.

    Args:
        handoff_tools: Optional list of handoff tools for delegation

    Returns:
        LangGraph ReAct agent configured for intervention planning
    """
    settings = get_settings()
    config = INTERVENTION_PLANNER_CONFIG

    # Initialize LLM with explicit credentials
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        model_kwargs={"temperature": config.temperature},
    )

    # Get intervention planner tools
    intervention_tools = create_intervention_planner_tools()

    # Combine with handoff tools if provided
    all_tools = intervention_tools + (handoff_tools or [])

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=config.system_prompt,
        name="intervention_planner",  # Required by langgraph_supervisor
    )

    logger.info("Intervention planner ReAct agent created successfully")
    return agent
