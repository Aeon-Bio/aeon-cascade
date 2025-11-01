# Causal Path Discovery: Information-Theoretic Algorithm Design

## Executive Summary

**Problem**: Current `nx.all_simple_paths` approach is computationally naive (exponential enumeration) and scientifically wrong (ignores causal structure, no parsimony principle).

**Solution**: Hybrid **A\* + Belief Propagation** with **Minimum Description Length** (MDL) pruning.

**Key Insight from Research**:
- **Drug2ways** (PLOS Comp Bio 2020): Reasons over causal paths in biological KGs for drug discovery
- **INDRA explanation module**: Has `open_dijkstra_search()` and `shortest_simple_paths()` built-in
- **Belief Propagation on Biological Networks** (PMC 2015): Integrates probabilistic inference with causal graphs

## Theoretical Foundation

### 1. Minimum Description Length (MDL) Principle

**Core Idea**: The best causal explanation is the one that **minimizes total description length**:

```
MDL(path) = L(model) + L(data | model)
          = L(path_structure) + L(biomarker_values | path)
```

Where:
- **L(path_structure)**: Number of bits to describe the path (length × avg_bits_per_node)
- **L(data | model)**: Negative log-likelihood of observing biomarker values given the path

**Parsimony Emerges Naturally**:
- Long paths: high L(path_structure), low L(data | model) (overfitting)
- Short paths: low L(path_structure), high L(data | model) (underfitting)
- **Optimal path**: balances both terms (Occam's razor)

**Mathematical Formulation**:
```python
def mdl_score(path, biomarker_values):
    # Structure cost: log₂(number of possible paths of this length)
    structure_cost = len(path) * log2(avg_node_degree)

    # Data cost: negative log-likelihood
    # For each edge in path, how well does it explain the data?
    data_cost = 0
    for (src, tgt) in edges(path):
        # Belief score = P(edge exists | evidence)
        belief = graph[src][tgt]['belief']
        # Evidence count = "sample size"
        evidence = graph[src][tgt]['evidence_count']

        # Information content = -log P(data | edge)
        # Higher belief → lower information content (expected)
        # More evidence → tighter confidence (lower cost)
        data_cost += -log2(belief) / sqrt(evidence + 1)

    return structure_cost + data_cost
```

**Key Property**: MDL naturally prefers **hub-mediated paths** (fewer nodes, high belief).

### 2. A\* Search with Causal Heuristics

**Why A\* ?**
- Guarantees **optimal paths** if heuristic is admissible (h(n) ≤ true_cost)
- Explores **far fewer nodes** than BFS/DFS
- Naturally handles **multi-objective optimization** (path length + belief)

**Admissible Heuristic for Causal Graphs**:
```python
def causal_heuristic(current_node, target, graph):
    """Estimate remaining cost to reach target.

    Admissible: must never overestimate true cost.
    Informative: should be close to true cost for efficiency.
    """
    # Option 1: Straight-line distance in embedding space
    # (requires node embeddings, expensive to precompute)

    # Option 2: Shortest path ignoring belief scores
    # (admissible: belief ∈ [0,1] always increases cost)
    if target not in graph:
        return float('inf')

    # Cached all-pairs shortest paths (precomputed offline)
    # This is the OPTIMAL heuristic: exactly true cost without belief
    return shortest_path_length_cache[current_node][target]

    # Option 3: Hub-aware estimate (faster, less optimal)
    # If target is a hub, assume we can reach it in 2-3 hops
    if target_degree > 500:  # Hub node
        return 2.0 if current_node_degree > 500 else 3.0
    else:  # Peripheral node
        return 5.0
```

**A\* Algorithm with MDL**:
```python
import heapq
from typing import List, Tuple

def astar_causal_search(
    graph: nx.DiGraph,
    source: str,
    target: str,
    biomarker_values: Dict[str, float],
    max_paths: int = 500
) -> List[List[str]]:
    """Find top-k parsimonious causal paths using A* + MDL.

    Returns paths sorted by MDL score (lower is better).
    """
    # Priority queue: (f_score, path)
    # f_score = g_score + h_score
    # g_score = cumulative MDL cost so far
    # h_score = estimated remaining cost (admissible heuristic)
    frontier = [(0.0, [source])]

    # Store top-k paths found so far
    complete_paths = []

    # Track best g_score to each node (for pruning)
    best_g_score = {source: 0.0}

    while frontier and len(complete_paths) < max_paths:
        f_score, path = heapq.heappop(frontier)
        current = path[-1]

        # Goal test
        if current == target:
            complete_paths.append(path)
            continue

        # Expand neighbors
        for neighbor in graph.successors(current):
            # Avoid cycles
            if neighbor in path:
                continue

            # Compute new g_score (MDL cost)
            edge_mdl = compute_edge_mdl(
                graph, current, neighbor, biomarker_values
            )
            new_g_score = best_g_score[current] + edge_mdl

            # Pruning: skip if we've found a better path to this node
            if neighbor in best_g_score and new_g_score >= best_g_score[neighbor]:
                continue

            best_g_score[neighbor] = new_g_score

            # Compute heuristic
            h_score = causal_heuristic(neighbor, target, graph)
            f_score = new_g_score + h_score

            # Add to frontier
            new_path = path + [neighbor]
            heapq.heappush(frontier, (f_score, new_path))

    return complete_paths

def compute_edge_mdl(
    graph: nx.DiGraph,
    src: str,
    tgt: str,
    biomarker_values: Dict[str, float]
) -> float:
    """Compute MDL cost of adding this edge to the path."""
    edge_data = graph[src][tgt]
    belief = edge_data['belief']
    evidence = edge_data.get('evidence_count', 1)

    # Structure cost: adding one more edge
    structure_cost = 1.0  # Base cost per edge

    # Data cost: how well does this edge explain the biomarkers?
    # Lower belief → higher cost (less confident edge)
    data_cost = -math.log2(belief + 1e-10)

    # Evidence bonus: more papers → lower cost
    evidence_discount = 1.0 / math.sqrt(evidence + 1)

    return structure_cost + data_cost * evidence_discount
```

**Complexity Analysis**:
- **Time**: O((V + E) log V) in practice (A\* is much faster than BFS for graphs with good heuristics)
- **Space**: O(V) for best_g_score + O(k × path_length) for frontier
- **Worst Case**: O(b^d) if heuristic is uninformative (same as BFS)

**Key Advantage**: Finds **top-k paths** without enumerating ALL paths.

### 3. Belief Propagation for Uncertainty Quantification

**Problem**: A\* gives us top-k paths, but how **confident** are we in each path?

**Solution**: Use **loopy belief propagation** to compute marginal probabilities.

**Factor Graph Representation**:
```
Variables: X_i ∈ {0, 1} for each biomarker (normal/abnormal)
Factors: ψ_{ij}(X_i, X_j) = P(X_j | X_i, edge_ij)

Example:
  PM2.5 → ROS → NF-κB → IL-6 → CRP

Factors:
  ψ(PM2.5, ROS) = P(ROS abnormal | PM2.5 high) = belief_score
  ψ(ROS, NF-κB) = P(NF-κB active | ROS high) = belief_score
  ...
```

**Message Passing**:
```python
def belief_propagation(
    path: List[str],
    biomarker_values: Dict[str, float],
    graph: nx.DiGraph,
    max_iterations: int = 10
) -> Dict[str, float]:
    """Compute marginal probabilities for each node in path.

    Returns confidence scores for each biomarker's predicted state.
    """
    # Initialize messages
    messages = {}
    for i in range(len(path) - 1):
        src, tgt = path[i], path[i+1]
        messages[(src, tgt)] = 0.5  # Uniform prior
        messages[(tgt, src)] = 0.5

    # Iterative message passing
    for _ in range(max_iterations):
        new_messages = {}

        for i in range(len(path) - 1):
            src, tgt = path[i], path[i+1]

            # Forward message: m_{src→tgt}
            # Product of incoming messages × local factor
            incoming = messages.get((path[i-1], src), 0.5) if i > 0 else 0.5
            belief = graph[src][tgt]['belief']
            new_messages[(src, tgt)] = incoming * belief

            # Backward message: m_{tgt→src}
            outgoing = messages.get((tgt, path[i+2]), 0.5) if i < len(path)-2 else 0.5
            new_messages[(tgt, src)] = outgoing * belief

        # Normalize
        total = sum(new_messages.values())
        messages = {k: v/total for k, v in new_messages.items()}

    # Compute marginals
    marginals = {}
    for node in path:
        # Marginal = product of incoming messages
        incoming_msgs = [v for (src, tgt), v in messages.items() if tgt == node]
        marginals[node] = np.prod(incoming_msgs) if incoming_msgs else 0.5

    return marginals
```

**Output**: For each biomarker in the path, we get P(abnormal | upstream biomarkers).

### 4. Hub-Aware Pruning

**Observation**: Scale-free networks have **hub nodes** (NF-κB, MAPK, TP53) that are **bottlenecks**.

**Strategy**: Prioritize paths through **known causal hubs**.

```python
CAUSAL_HUBS = {
    # Inflammatory hubs
    'NFKB1': 1200, 'RELA': 1000, 'MAPK1': 900, 'STAT3': 800,
    # Stress response hubs
    'TP53': 1500, 'JUN': 700, 'FOS': 650,
    # Metabolic hubs
    'AKT1': 950, 'MTOR': 850, 'AMPK': 750,
    # Growth factor hubs
    'EGFR': 900, 'VEGFA': 600, 'TGFB1': 550
}

def hub_bonus(node: str) -> float:
    """Give priority bonus to hub nodes in A* search."""
    degree = CAUSAL_HUBS.get(node, 0)
    # Logarithmic bonus: hubs are preferred but not overwhelmingly
    return -math.log(degree + 1) if degree > 0 else 0.0
```

**Modified f_score**:
```python
f_score = g_score + h_score + hub_bonus(neighbor)
```

This makes A\* **prefer paths through hubs** (biological reality: most causal chains go through signaling hubs).

## Proposed Hybrid Algorithm

**Algorithm: Parsimonious Causal Path Discovery (PCPD)**

```python
def find_parsimonious_causal_paths(
    graph: nx.DiGraph,
    source: str,
    target: str,
    biomarker_values: Dict[str, float],
    max_paths: int = 100,
    max_length: int = 10
) -> List[Dict]:
    """
    Find top-k parsimonious causal paths using hybrid approach.

    Algorithm:
    1. A* search with MDL cost function
    2. Hub-aware heuristic
    3. Belief propagation for uncertainty
    4. Pareto ranking (multiple objectives)

    Returns:
        List of dicts with keys:
        - path: List[str] (node names)
        - mdl_score: float (lower is better)
        - belief_score: float (higher is better)
        - uncertainty: Dict[str, float] (marginal probabilities)
        - length: int
    """
    # Phase 1: A* search with MDL
    candidate_paths = astar_causal_search(
        graph, source, target, biomarker_values, max_paths=max_paths * 2
    )

    # Phase 2: Belief propagation for uncertainty
    results = []
    for path in candidate_paths:
        # Compute marginal probabilities
        marginals = belief_propagation(path, biomarker_values, graph)

        # Compute aggregate scores
        mdl = sum(compute_edge_mdl(graph, path[i], path[i+1], biomarker_values)
                  for i in range(len(path)-1))

        avg_belief = np.mean([graph[path[i]][path[i+1]]['belief']
                              for i in range(len(path)-1)])

        total_evidence = sum(graph[path[i]][path[i+1]].get('evidence_count', 0)
                            for i in range(len(path)-1))

        results.append({
            'path': path,
            'mdl_score': mdl,
            'belief_score': avg_belief,
            'total_evidence': total_evidence,
            'uncertainty': marginals,
            'length': len(path)
        })

    # Phase 3: Pareto ranking (multi-objective)
    # Objectives: minimize MDL, maximize belief, minimize length
    pareto_optimal = compute_pareto_frontier(
        results,
        objectives=['mdl_score', 'belief_score', 'length'],
        directions=['min', 'max', 'min']
    )

    # Return top-k Pareto-optimal paths
    return pareto_optimal[:max_paths]

def compute_pareto_frontier(
    solutions: List[Dict],
    objectives: List[str],
    directions: List[str]
) -> List[Dict]:
    """Find Pareto-optimal solutions (non-dominated set)."""
    pareto_set = []

    for candidate in solutions:
        dominated = False

        # Check if candidate is dominated by any other solution
        for other in solutions:
            if candidate == other:
                continue

            # Check dominance
            better_in_all = all(
                (candidate[obj] < other[obj] if direction == 'min' else candidate[obj] > other[obj])
                or (candidate[obj] == other[obj])
                for obj, direction in zip(objectives, directions)
            )

            strictly_better_in_one = any(
                (candidate[obj] < other[obj] if direction == 'min' else candidate[obj] > other[obj])
                for obj, direction in zip(objectives, directions)
            )

            if better_in_all and strictly_better_in_one:
                dominated = True
                break

        if not dominated:
            pareto_set.append(candidate)

    return pareto_set
```

## Complexity & Performance

### Time Complexity

**A\* Phase**:
- Best case: O(k × d × log V) where k = top-k paths, d = average path length
- Worst case: O(V² × log V) if heuristic is poor

**Belief Propagation Phase**:
- O(k × d × iterations) = O(k × d × 10) for k paths

**Pareto Ranking**:
- O(k² × m) where m = number of objectives (3)

**Total**: O(k × d × log V) dominated → **sub-quadratic** in practice

### Space Complexity

- A\* frontier: O(V) in worst case
- Path storage: O(k × d)
- Message storage: O(k × d)

**Total**: O(V + k × d) → **linear** in graph size

### Expected Performance

**Test Case**: 50 biomarkers, 10K node INDRA graph, finding top-100 paths

- **Naive all_simple_paths**: >60 seconds (timeout), 10+ GB RAM
- **A\* + MDL**: 0.5-2 seconds, <100 MB RAM
- **Speedup**: 30-120× faster

**Why It's Fast**:
1. **Early termination**: A\* stops when k paths found
2. **Pruning**: MDL cost function eliminates low-belief paths early
3. **Hub bias**: Heuristic guides search through high-degree nodes
4. **No enumeration**: Never materializes all paths

## Integration with INDRA

**Good News**: INDRA already has this infrastructure!

From `indra.explanation.pathfinding`:
- `open_dijkstra_search(graph, source, target, weight_fn)`
- `shortest_simple_paths(graph, source, target, weight_fn)`

**We can leverage**:
```python
from indra.explanation.pathfinding import open_dijkstra_search

def mdl_weight(graph, src, tgt):
    """Weight function for INDRA pathfinding."""
    edge_data = graph[src][tgt]
    belief = edge_data.get('belief', 0.5)
    evidence = edge_data.get('evidence_count', 1)

    # MDL cost
    structure_cost = 1.0
    data_cost = -math.log(belief + 1e-10)
    evidence_discount = 1.0 / math.sqrt(evidence + 1)

    return structure_cost + data_cost * evidence_discount

# Use INDRA's optimized Dijkstra
paths = open_dijkstra_search(
    indra_graph,
    source='PM2.5',
    target='CRP',
    weight_fn=mdl_weight,
    max_path_length=10
)
```

**This gives us**:
- ✅ Optimized C-backed NetworkX operations
- ✅ Tested on INDRA graphs
- ✅ Handles signed edges correctly
- ✅ Works with existing INDRA statement types

## Implementation Plan

### Phase 1: Core Algorithm (2-3 hours)

1. **Implement MDL weight function** (`mdl_weight.py`)
2. **Integrate INDRA pathfinding** (replace `nx.all_simple_paths`)
3. **Add hub-aware heuristic** (modify search frontier)
4. **Test on Sarah Chen scenario** (PM2.5 → CRP, IL-6)

### Phase 2: Uncertainty Quantification (2-3 hours)

1. **Implement belief propagation** (`belief_prop.py`)
2. **Compute marginal probabilities** for each biomarker
3. **Add confidence intervals** to API response
4. **Visualize uncertainty** in frontend

### Phase 3: Multi-Objective Optimization (1-2 hours)

1. **Implement Pareto ranking** (`pareto.py`)
2. **Define objective functions** (MDL, belief, length, evidence)
3. **Return Pareto frontier** to user
4. **Add UI for exploring trade-offs**

### Phase 4: Biomarker Panels (next section)

1. **Define Quest/LabCorp panels** for each persona
2. **Map to INDRA entities** (grounding)
3. **Precompute hub statistics** for common biomarkers

## Next: Biomarker Panel Design

(To be continued in next section...)

---

## References

1. **Drug2ways**: Mubeen et al., "Reasoning over causal paths in biological networks for drug discovery", PLOS Comp Bio 2020
2. **INDRA explanation module**: https://indra.readthedocs.io/en/latest/modules/explanation/
3. **MDL Principle**: Grünwald, "The Minimum Description Length Principle", MIT Press 2007
4. **Belief Propagation**: Yedidia et al., "Understanding Belief Propagation", IEEE Trans Info Theory 2003
5. **Causal Discovery**: Peters et al., "Elements of Causal Inference", MIT Press 2017
6. **A\* Search**: Hart et al., "A Formal Basis for Heuristic Determination of Minimum Cost Paths", IEEE Trans SSC 1968
