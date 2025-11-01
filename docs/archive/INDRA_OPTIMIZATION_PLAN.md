# INDRA Optimization Plan: From 120s to <10s

## Current Bottlenecks (Identified)

### 1. **Unnecessary Neighborhood Fetching** ❌ WASTEFUL
**Current approach** (`build_biomarker_network`):
```python
# Strategy 1: Get neighborhoods of biomarkers (lines 166-172)
for biomarker in biomarkers:
    neighborhood_stmts = await self._get_neighborhood_statements(
        biomarker, depth=max_depth  # Fetching 200 statements PER biomarker
    )
```

**Problem**: We fetch CRP neighborhood (200 statements, ~7s) but THEN do pathfinding which fetches statements again!

**Solution**: **Skip neighborhood fetching entirely for pathfinding**
- Pathfinding only needs source → target statements
- Neighborhoods add noise and duplicate data
- **Savings**: Eliminate 1-2 API calls (~10-20 seconds)**

### 2. **Triple Statement Fetching** ❌ REDUNDANT
**Current approach** (`_get_path_statements`, lines 314-359):
```python
# Strategy 1: Direct source → target (20s timeout)
processor = idr.get_statements(subject=source, object=target, limit=50)

# Strategy 2: Statements involving source (20s timeout)
processor = idr.get_statements(agents=[source], limit=50)

# Strategy 3: Statements involving target (20s timeout)
processor = idr.get_statements(agents=[target], limit=50)
```

**Problem**: We make 3 separate API calls when 1 would suffice!

**INDRA docs say**: "when set less than 500 the effect is much the same as setting persist to false, and will guarantee a faster response."

**Solution**: Use single query with higher limit + `persist=False`
```python
# Single query with persist=False for fast response
processor = idr.get_statements(
    agents=[source, target],  # Both entities in one query
    limit=100,  # < 500 for fast response
    persist=False,  # Don't paginate
    ev_limit=3,
    timeout=10,
    tries=2  # Retry once if timeout (cache helps)
)
```
**Savings**: 3 queries → 1 query = ~40s → ~6s (6× faster)

### 3. **Inefficient Pathfinding Algorithm** ⚠️ SUBOPTIMAL

**Current**: `shortest_simple_paths()` - enumerates ALL k-shortest paths

**INDRA docs show**: `open_dijkstra_search()` - single shortest path with early termination

**Comparison**:
- `shortest_simple_paths`: O(k × V × E) - finds k paths
- `open_dijkstra_search`: O(V + E × log V) - finds 1 path, stops

**For PM2.5 → CRP**:
- We only need **1-3 best paths**, not 500!
- MDL already ranks by quality
- Early termination >> exhaustive enumeration

**Solution**: Use `open_dijkstra_search` with MDL weights + `path_limit=10`
```python
from indra.explanation.pathfinding import open_dijkstra_search

path_generator = open_dijkstra_search(
    g=network_result.graph,
    start=source,
    reverse=False,
    path_limit=10,  # Stop after 10 paths
    weight=mdl_weight_fn,
    terminal_ns=None
)
```
**Savings**: 500 paths → 10 paths = milliseconds vs seconds

### 4. **Preassembly on Small Datasets** ❌ OVERKILL

**Current**: Full preassembly pipeline on 105-305 statements
```python
# Takes 53 seconds to load bio-ontology!
preassembled_stmts = self._preassemble_statements(all_statements)
```

**INDRA docs**: Preassembly is for **merging duplicates from multiple sources**

**Reality**: We're querying INDRA DB (already pre-assembled!) with `sort_by='ev_count'`

**Solution**: Skip preassembly entirely for INDRA DB queries
```python
# INDRA DB statements are already pre-assembled!
# Just filter by belief threshold
high_quality_stmts = [
    stmt for stmt in all_statements
    if stmt.belief >= belief_threshold
]
```
**Savings**: 53 seconds → 0 seconds (ontology loading eliminated!)

### 5. **Mediator Expansion Triggers Cascade** 🌊 EXPONENTIAL

**Current**: If no direct path, expand via mediators (IL-6, ROS, TNF, NF-κB)
```python
# Each mediator triggers NEW API calls!
for mediator in mediators:
    # Fetches neighborhood: 200 statements, ~20s
    # Fetches source → mediator: 3 queries, ~40s
    # Fetches mediator → target: 3 queries, ~40s
    # Total per mediator: ~100 seconds!
```

**Problem**: 4 mediators × 100s = 400 seconds (way over budget!)

**Solution**: **Use BFS from INDRA** instead of mediator expansion
```python
from indra.explanation.pathfinding import bfs_search

# Single BFS covers all mediators automatically!
paths = bfs_search(
    g=network_result.graph,
    source_node=source,
    depth_limit=3,  # Up to 3 hops
    path_limit=10,  # Stop after 10 paths
    max_per_node=3,  # Don't explore too many branches
    max_memory=100_000_000  # 100 MB limit
)
```
**Savings**: Eliminates mediator API calls entirely!

## Optimized Architecture

### NEW: Lean Pathfinding Service

```python
async def find_causal_paths_optimized(
    self,
    source: str,
    target: str,
    max_depth: int = 4,
) -> List[Dict[str, Any]]:
    """Optimized pathfinding: <10 seconds for PM2.5 → CRP."""

    # STEP 1: Single efficient query (6s instead of 60s)
    statements = await self._get_path_statements_optimized(source, target)

    if not statements:
        return []

    # STEP 2: Skip preassembly (save 53s!)
    # Filter by belief instead
    high_quality_stmts = [s for s in statements if s.belief >= 0.3]

    # STEP 3: Build graph (1-2s)
    graph, belief_scores, evidence_counts = self._build_signed_graph(
        high_quality_stmts, belief_threshold=0.3
    )

    # STEP 4: Use Dijkstra + MDL (milliseconds)
    mdl_weight_fn = create_mdl_weight_function(graph)

    paths = open_dijkstra_search(
        g=graph,
        start=source,
        reverse=False,
        path_limit=10,  # Stop early
        weight=mdl_weight_fn
    )

    # STEP 5: Convert to output format
    return self._format_paths(paths, graph, belief_scores, evidence_counts)

async def _get_path_statements_optimized(
    self, source: str, target: str
) -> List[Statement]:
    """Fetch statements with single optimized query."""

    def fetch_statements():
        # Single query with persist=False for fast response
        processor = idr.get_statements(
            agents=[source, target],  # Both entities
            limit=150,  # < 500 for fast response
            persist=False,  # No pagination
            ev_limit=3,  # Minimal evidence per statement
            sort_by='ev_count',  # Best first
            timeout=10,  # Shorter timeout
            tries=2  # Retry once (cache helps)
        )
        return processor.statements

    return await asyncio.to_thread(fetch_statements)
```

## Expected Performance

| Operation | Old Time | New Time | Speedup |
|-----------|----------|----------|---------|
| Neighborhood fetch | 20s | 0s (skipped) | ∞ |
| Path statements | 60s (3 queries) | 6s (1 query) | 10× |
| Preassembly | 53s (ontology) | 0s (skipped) | ∞ |
| Pathfinding | <1s (500 paths) | <0.1s (10 paths) | 10× |
| Mediator expansion | 400s (4 mediators) | 0s (BFS handles) | ∞ |
| **TOTAL** | **533s (timeout!)** | **<7s** | **76× faster** |

## Implementation Priority

### Phase 1: Quick Wins (30 min) - **Target: <20s**
1. ✅ Skip neighborhood fetching for pathfinding
2. ✅ Reduce to single statement query with `persist=False`
3. ✅ Lower limits: 150 statements (not 200)
4. ✅ Shorter timeouts: 10s (not 30s)

### Phase 2: Algorithm Swap (15 min) - **Target: <10s**
5. ✅ Replace `shortest_simple_paths` with `open_dijkstra_search`
6. ✅ Set `path_limit=10` for early termination
7. ✅ Verify MDL weight function compatible

### Phase 3: Skip Preassembly (10 min) - **Target: <7s**
8. ✅ Skip preassembly for INDRA DB queries (already assembled!)
9. ✅ Filter by belief threshold instead
10. ✅ Eliminate ontology loading (4 GB memory → 100 MB)

### Phase 4: BFS Fallback (20 min) - **Target: Eliminate timeouts**
11. ✅ Replace mediator expansion with `bfs_search`
12. ✅ Set memory limits to prevent OOM
13. ✅ Handle "no path" gracefully without cascade

## Testing Plan

```bash
# Before optimization
timeout 180 uv run python tests/test_sarah_chen_mdl.py
# Result: 120s timeout, 4.7 GB memory

# After Phase 1
timeout 60 uv run python tests/test_sarah_chen_mdl.py
# Target: <20s, <500 MB memory

# After Phase 2
timeout 30 uv run python tests/test_sarah_chen_mdl.py
# Target: <10s, <200 MB memory

# After Phase 3
timeout 15 uv run python tests/test_sarah_chen_mdl.py
# Target: <7s, <100 MB memory
```

## Risk Assessment

### Low Risk ✅
- Skip neighborhood (not used by pathfinding)
- Single query instead of 3 (same data)
- Dijkstra instead of k-shortest (faster, same paths)

### Medium Risk ⚠️
- Skip preassembly (INDRA DB already pre-assembled)
- BFS instead of mediator expansion (different algorithm)

### Mitigation
- Keep old code commented out
- A/B test on known paths (PM2.5 → IL-6)
- Validate MDL ranking still works

## Success Criteria

✅ **Latency**: <10 seconds for PM2.5 → CRP (was 120s+)
✅ **Memory**: <100 MB (was 4.7 GB)
✅ **Correctness**: Same paths found as before
✅ **MDL ranking**: Shorter, high-belief paths ranked higher

---

**Recommendation**: Implement Phase 1-3 immediately (55 minutes total work)
**Expected result**: 76× speedup, acceptable for demo and production
