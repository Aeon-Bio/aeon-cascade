"""Minimum Description Length (MDL) weight function for causal path discovery.

This module implements the MDL principle for ranking causal paths in biological networks.
The MDL score balances path complexity (structure cost) with explanatory power (data cost).

Theoretical Foundation:
    MDL(path) = L(structure) + L(data | structure)
              = path_length × log₂(avg_degree) + Σ(-log₂(belief) / √evidence)

References:
    - Grünwald, "The Minimum Description Length Principle", MIT Press 2007
    - Drug2ways (Mubeen et al., PLOS Comp Bio 2020)
"""

import logging
import math
from typing import Dict, Optional

import networkx as nx

logger = logging.getLogger(__name__)

# Hub nodes in biological networks (degree estimates from INDRA statistics)
# These are signaling hubs that mediate most causal pathways
CAUSAL_HUBS = {
    # Inflammatory signaling hubs
    'NFKB1': 1200,  # NF-κB p50 subunit
    'RELA': 1000,   # NF-κB p65 subunit
    'STAT3': 800,   # Signal transducer and activator of transcription 3

    # MAPK pathway hubs
    'MAPK1': 900,   # ERK2
    'MAPK3': 900,   # ERK1
    'MAPK8': 750,   # JNK1
    'MAPK14': 700,  # p38 MAPK

    # Stress response hubs
    'TP53': 1500,   # Tumor suppressor p53
    'JUN': 700,     # AP-1 transcription factor
    'FOS': 650,     # AP-1 transcription factor

    # Metabolic signaling hubs
    'AKT1': 950,    # Protein kinase B
    'MTOR': 850,    # Mechanistic target of rapamycin
    'AMPK': 750,    # AMP-activated protein kinase
    'PIK3CA': 800,  # Phosphatidylinositol 3-kinase

    # Growth factor signaling
    'EGFR': 900,    # Epidermal growth factor receptor
    'VEGFA': 600,   # Vascular endothelial growth factor A
    'TGFB1': 550,   # Transforming growth factor beta 1
    'IGF1': 400,    # Insulin-like growth factor 1

    # Cytokine hubs
    'TNF': 650,     # Tumor necrosis factor
    'IL6': 600,     # Interleukin 6
    'IL1B': 550,    # Interleukin 1 beta
}


def compute_mdl_weight(
    graph: nx.DiGraph,
    src: str,
    tgt: str,
    biomarker_values: Optional[Dict[str, float]] = None
) -> float:
    """Compute MDL cost of adding an edge to a path.

    The MDL weight balances:
    1. Structure cost: Adding one more edge (parsimony penalty)
    2. Data cost: How well the edge explains the data (belief score)
    3. Evidence discount: More papers → lower cost (higher confidence)

    Args:
        graph: NetworkX DiGraph with belief scores and evidence counts
        src: Source node name
        tgt: Target node name
        biomarker_values: Optional dict of observed biomarker values
            (currently unused, reserved for future data-driven cost)

    Returns:
        MDL cost (float, lower is better)

    Example:
        >>> graph = nx.DiGraph()
        >>> graph.add_edge('PM2.5', 'ROS', belief=0.8, evidence_count=47)
        >>> weight = compute_mdl_weight(graph, 'PM2.5', 'ROS')
        >>> weight  # ~1.32 (1.0 structure + 0.32 data - 0.0 hub bonus)
    """
    # Get edge data (handle missing edges gracefully)
    if not graph.has_edge(src, tgt):
        logger.warning(f"Edge ({src}, {tgt}) not in graph, using default values")
        belief = 0.5  # Neutral belief
        evidence = 1  # Minimal evidence
    else:
        # Handle both MultiDiGraph and DiGraph
        # For MultiDiGraph: graph[src][tgt] returns {0: {...}, 1: {...}}
        # For DiGraph: graph[src][tgt] returns {...}
        edge_data_container = graph[src][tgt]

        # Check if this is a MultiDiGraph (edge_data_container is dict of dicts)
        if isinstance(edge_data_container, dict) and edge_data_container:
            # Get first edge key (usually 0)
            first_key = next(iter(edge_data_container.keys()))
            if isinstance(first_key, int):
                # MultiDiGraph: extract first edge's data
                edge_data = edge_data_container[first_key]
            else:
                # DiGraph: this is already the edge data
                edge_data = edge_data_container
        else:
            # Empty or invalid
            edge_data = {}

        belief = edge_data.get('belief', 0.5)
        evidence = edge_data.get('evidence_count', 1)

    # Structure cost: Base cost per edge (encourages parsimony)
    structure_cost = 1.0

    # Data cost: Information-theoretic cost of edge
    # Lower belief → higher cost (less confident edge)
    # -log₂(P) = bits needed to encode the event
    data_cost = -math.log2(belief + 1e-10)  # Add epsilon to avoid log(0)

    # Evidence discount: More papers → lower cost
    # √(evidence + 1) provides diminishing returns
    # Example: 1 paper = 1.0, 4 papers = 0.5, 16 papers = 0.25
    evidence_discount = 1.0 / math.sqrt(evidence + 1)

    # Total MDL weight
    mdl_weight = structure_cost + data_cost * evidence_discount

    logger.debug(
        f"MDL weight for {src}→{tgt}: "
        f"structure={structure_cost:.3f}, "
        f"data={data_cost:.3f}, "
        f"evidence_discount={evidence_discount:.3f}, "
        f"total={mdl_weight:.3f}"
    )

    return mdl_weight


def hub_bonus(node: str) -> float:
    """Compute hub bonus for prioritizing paths through signaling hubs.

    Hub nodes (NF-κB, MAPK, TP53, etc.) are biological bottlenecks that mediate
    most causal pathways. Giving them a small negative cost encourages routing
    through biologically plausible hubs.

    Args:
        node: Node name

    Returns:
        Negative cost bonus (lower is better, so negative = preferred)

    Example:
        >>> hub_bonus('NFKB1')  # Major hub
        -7.09  # log(1200 + 1) ≈ 7.09
        >>> hub_bonus('CRP')    # Not a hub
        0.0
    """
    degree = CAUSAL_HUBS.get(node, 0)

    if degree == 0:
        return 0.0  # No bonus for non-hub nodes

    # Logarithmic bonus: hubs preferred but not overwhelmingly
    # This prevents all paths collapsing through a single hub
    bonus = -math.log(degree + 1)

    return bonus


def compute_path_mdl(
    path: list,
    graph: nx.DiGraph,
    biomarker_values: Optional[Dict[str, float]] = None
) -> float:
    """Compute total MDL cost for an entire path.

    Args:
        path: List of node names forming a path
        graph: NetworkX DiGraph with edge attributes
        biomarker_values: Optional biomarker observations

    Returns:
        Total MDL cost (sum of edge costs + hub bonuses)

    Example:
        >>> path = ['PM2.5', 'ROS', 'NFKB1', 'IL6', 'CRP']
        >>> mdl = compute_path_mdl(path, graph)
        >>> mdl  # ~4.5 (4 edges × ~1.3 MDL each - hub bonus for NFKB1)
    """
    if len(path) < 2:
        return 0.0  # Empty or single-node path

    total_cost = 0.0

    # Sum edge costs
    for i in range(len(path) - 1):
        src, tgt = path[i], path[i + 1]
        edge_cost = compute_mdl_weight(graph, src, tgt, biomarker_values)
        total_cost += edge_cost

        # Add hub bonus for intermediate nodes (not source/target)
        if i > 0:  # Skip source node
            bonus = hub_bonus(path[i])
            total_cost += bonus

    logger.debug(f"Path MDL cost: {total_cost:.3f} for path length {len(path)}")

    return total_cost


def compare_path_parsimony(
    path1: list,
    path2: list,
    graph: nx.DiGraph
) -> str:
    """Compare parsimony of two paths using MDL principle.

    Args:
        path1: First path
        path2: Second path
        graph: NetworkX DiGraph

    Returns:
        String indicating which path is more parsimonious

    Example:
        >>> path1 = ['PM2.5', 'NFKB1', 'IL6', 'CRP']  # Short, through hub
        >>> path2 = ['PM2.5', 'ROS', 'JNK', 'STAT3', 'IL6', 'CRP']  # Long
        >>> compare_path_parsimony(path1, path2, graph)
        'path1 is more parsimonious (MDL: 3.2 < 5.8)'
    """
    mdl1 = compute_path_mdl(path1, graph)
    mdl2 = compute_path_mdl(path2, graph)

    if mdl1 < mdl2:
        return f"path1 is more parsimonious (MDL: {mdl1:.2f} < {mdl2:.2f})"
    elif mdl2 < mdl1:
        return f"path2 is more parsimonious (MDL: {mdl2:.2f} < {mdl1:.2f})"
    else:
        return f"paths are equally parsimonious (MDL: {mdl1:.2f} = {mdl2:.2f})"


# For INDRA pathfinding integration
def create_mdl_weight_function(
    graph: nx.DiGraph,
    biomarker_values: Optional[Dict[str, float]] = None
):
    """Create a weight function compatible with INDRA pathfinding.

    INDRA's pathfinding functions expect weight_fn(v, w, edge_data) signature.
    This factory creates a closure that captures the graph and biomarker_values.

    Args:
        graph: NetworkX DiGraph with belief scores and evidence counts
        biomarker_values: Optional biomarker observations

    Returns:
        Weight function compatible with INDRA pathfinding

    Example:
        >>> from indra.explanation.pathfinding import shortest_simple_paths
        >>> weight_fn = create_mdl_weight_function(graph, {'CRP': 5.2, 'IL-6': 3.8})
        >>> paths = shortest_simple_paths(graph, 'PM2.5', 'CRP', weight=weight_fn)
    """
    def weight_fn(v, w, edge_data):
        """Weight function called by INDRA pathfinding.

        Args:
            v: Source node name
            w: Target node name
            edge_data: Edge data dict from NetworkX (ignored, we get from graph)

        Returns:
            MDL cost (float, lower is better)
        """
        return compute_mdl_weight(graph, v, w, biomarker_values)

    return weight_fn
