# Master Implementation Plan: MDL-Based Causal Path Discovery

**Status**: 🚧 Phase 1 Complete (Algorithm), Phase 2 In Progress (Optimization)
**Last Updated**: 2025-10-29
**Target**: <10 second pathfinding with <100 MB memory

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Current Status](#current-status)
3. [Performance Optimization Plan](#performance-optimization-plan)
4. [Implementation Phases](#implementation-phases)
5. [Success Criteria](#success-criteria)
6. [Related Documents](#related-documents)

---

## Project Overview

### Objective
Implement information-theoretic causal pathway discovery using Minimum Description Length (MDL) principle for biological networks, powered by INDRA bio-ontology.

### Clinical Use Case: Sarah Chen
- **Age**: 34, Software Engineer, Los Angeles
- **Conditions**: Metabolic-inflammatory syndrome (CRP: 5.2 mg/L, HbA1c: 5.9%)
- **Environmental**: High PM2.5 exposure (35 µg/m³)
- **Query**: "How does PM2.5 pollution affect my CRP biomarker?"

### Expected Pathway
```
PM2.5 → Oxidative Stress (ROS) → {
    ├─→ NF-κB → IL-6 → CRP (Inflammation)
    └─→ JNK → IRS-1 inhibition → Insulin Resistance
}
```

---

## Current Status

### ✅ Phase 1 Complete: MDL Algorithm Implementation

**Files Created**:
- `indra_agent/services/mdl_weight.py` (253 lines)
  - `compute_mdl_weight()`: Edge cost = structure + data × evidence_discount
  - `hub_bonus()`: Prioritizes 20 major signaling hubs (NF-κB, MAPK, TP53)
  - `compute_path_mdl()`: Total path cost calculation
  - `create_mdl_weight_function()`: INDRA-compatible weight factory

**Integration**:
- `indra_agent/services/indranet_service.py` (lines 627-660)
  - Replaced `nx.all_simple_paths` with INDRA `shortest_simple_paths`
  - MDL weight function with closure over graph
  - Generator-based approach for memory efficiency

**Validation**:
- ✅ MDL algorithm mathematically correct
- ✅ INDRA pathfinding integration works
- ✅ Hub-aware heuristic implemented
- ❌ Performance unacceptable: 120s timeout, 4.7 GB memory

### 📊 Performance Issues Identified

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Latency | <10s | 120s+ (timeout) | ❌ CRITICAL |
| Memory | <100 MB | 4679 MB | ❌ CRITICAL |
| Path Quality | High-belief, short | Not tested | ⏸️ BLOCKED |

**Root Causes**:
1. **Triple API calls per query** (60s wasted)
2. **Unnecessary neighborhood fetching** (20s wasted)
3. **Preassembly overkill** (53s ontology loading)
4. **Inefficient pathfinding algorithm** (enumerates 500 paths unnecessarily)
5. **Mediator expansion cascade** (400s exponential blowup)

---

## Performance Optimization Plan

### Phase 2: INDRA Query Optimization (Est: 55 minutes)

Based on INDRA documentation analysis, we identified **5 critical inefficiencies**:

#### 2.1 Quick Wins (30 min) - Target: <20s

**Changes**:
1. ✅ Skip neighborhood fetching (not used by pathfinding)
2. ✅ Single statement query with `persist=False`
3. ✅ Lower limits to 150 statements (< 500 threshold)
4. ✅ Reduce timeout to 10s (leverage cache)

**Implementation**:
```python
async def _get_path_statements_optimized(source, target):
    processor = idr.get_statements(
        agents=[source, target],  # Both entities in ONE query
        limit=150,  # < 500 for fast response
        persist=False,  # No pagination
        ev_limit=3,
        timeout=10,
        tries=2  # Retry leverages cache
    )
    return processor.statements
```

**Expected**: 60s → 6s (**10× faster**)

#### 2.2 Algorithm Swap (15 min) - Target: <10s

**Change**: Replace `shortest_simple_paths` with `open_dijkstra_search`

**Rationale**:
- `shortest_simple_paths`: O(k × V × E) - enumerates k=500 paths
- `open_dijkstra_search`: O(V + E × log V) - finds 1 path, early termination

**Implementation**:
```python
from indra.explanation.pathfinding import open_dijkstra_search

paths = open_dijkstra_search(
    g=graph,
    start=source,
    reverse=False,
    path_limit=10,  # Stop after 10 best paths
    weight=mdl_weight_fn
)
```

**Expected**: 500 paths → 10 paths (**milliseconds vs seconds**)

#### 2.3 Skip Preassembly (10 min) - Target: <7s

**Change**: Skip preassembly for INDRA DB queries (already pre-assembled!)

**Rationale**:
- Preassembly loads 4 GB bio-ontology (53 seconds!)
- INDRA DB statements are already merged/de-duplicated
- We only need belief filtering

**Implementation**:
```python
# OLD: preassembled_stmts = self._preassemble_statements(all_statements)
# NEW: Skip preassembly, just filter by belief
high_quality_stmts = [s for s in all_statements if s.belief >= 0.3]
```

**Expected**: 53s → 0s, 4.7 GB → <100 MB (**infinite speedup, memory fixed!**)

### Phase 3: BFS Fallback (20 min) - Target: Eliminate timeouts

**Change**: Replace mediator expansion with `bfs_search`

**Rationale**:
- Current mediator expansion: 4 mediators × 100s = 400s (exponential!)
- BFS handles multi-hop automatically with memory limits

**Implementation**:
```python
from indra.explanation.pathfinding import bfs_search

paths = bfs_search(
    g=graph,
    source_node=source,
    depth_limit=3,
    path_limit=10,
    max_per_node=3,
    max_memory=100_000_000  # 100 MB limit
)
```

**Expected**: Eliminates 400s mediator cascade

---

## Implementation Phases

### Phase 2.1: Quick Wins ⏳ NEXT (30 min)

**Files to modify**:
1. `indra_agent/services/indranet_service.py`
   - Create `_get_path_statements_optimized()` method
   - Update `build_biomarker_network()` to skip neighborhoods for pathfinding
   - Reduce limits and enable `persist=False`

**Testing**:
```bash
timeout 60 uv run python tests/test_sarah_chen_mdl.py
# Target: <20s, <500 MB memory
```

**Success criteria**:
- ✅ Latency <20s (was 120s)
- ✅ Memory <500 MB (was 4679 MB)
- ✅ Same paths found as before

### Phase 2.2: Algorithm Swap ⏳ NEXT (15 min)

**Files to modify**:
1. `indra_agent/services/indranet_service.py`
   - Import `open_dijkstra_search` instead of `shortest_simple_paths`
   - Update `_convert_graph_to_paths()` to use Dijkstra with `path_limit=10`
   - Verify MDL weight function compatible

**Testing**:
```bash
timeout 30 uv run python tests/test_sarah_chen_mdl.py
# Target: <10s, <200 MB memory
```

**Success criteria**:
- ✅ Latency <10s
- ✅ MDL ranking still works (shorter, high-belief paths first)

### Phase 2.3: Skip Preassembly ⏳ NEXT (10 min)

**Files to modify**:
1. `indra_agent/services/indranet_service.py`
   - Replace `_preassemble_statements()` call with simple belief filtering
   - Comment out preassembly import (avoid ontology loading)

**Testing**:
```bash
timeout 15 uv run python tests/test_sarah_chen_mdl.py
# Target: <7s, <100 MB memory
```

**Success criteria**:
- ✅ Latency <7s
- ✅ Memory <100 MB
- ✅ No ontology loading in logs

### Phase 3: BFS Fallback (20 min) - Optional

**Files to modify**:
1. `indra_agent/services/scm_graph_builder.py`
   - Replace mediator expansion with `bfs_search`
   - Set memory limits to prevent OOM

**Testing**: Same as Phase 2.3

**Success criteria**:
- ✅ No timeout on complex queries
- ✅ Memory stays <100 MB

---

## Success Criteria

### Functional Requirements
- ✅ Find causal paths between PM2.5 → CRP
- ✅ MDL ranking: shorter, high-belief paths rank higher
- ✅ Hub nodes (NF-κB, IL-6) appear in top paths
- ✅ Evidence counts and PMIDs included

### Performance Requirements
- ✅ **Latency**: <10s for 90% of queries (was 120s+)
- ✅ **Memory**: <100 MB (was 4679 MB)
- ✅ **Throughput**: 10+ queries/minute (was timeout)
- ✅ **Path Quality**: >90% match curated pathways

### Correctness Requirements
- ✅ Same paths found as exhaustive search
- ✅ MDL scores correct (lower = more parsimonious)
- ✅ Belief scores from INDRA preserved
- ✅ No crashes or data corruption

---

## Related Documents

### Current (Keep)
- `BIOMARKER_PANELS.md` - 64 biomarkers for 5 personas (Quest/LabCorp test codes)
- `CAUSAL_PATH_ALGORITHM_DESIGN.md` - MDL algorithm theory and design
- `INDRA_OPTIMIZATION_PLAN.md` - Detailed optimization analysis (this document supersedes)
- `PHASE_1_TEST_RESULTS.md` - Test results showing 120s timeout issue

### Archived (Moved to docs/archive/)
- `IMPLEMENTATION_CHECKLIST.md` - Original 4-phase plan (superseded by this document)
- `PATH_DISCOVERY_FIX.md` - Naive depth-limit fix (superseded by MDL approach)
- `ARCHITECTURE_FIX_PLAN.md` - General architecture issues (some addressed)

### Reference Only
- `CLAUDE.md` - Project overview and system architecture
- `HONEST_ARCHITECTURE.md` - Brutalist critique and architectural constraints

---

## Timeline

**Phase 1 (Complete)**: MDL algorithm implementation - 3 hours
**Phase 2.1 (Next)**: Quick wins - 30 minutes → **<20s latency**
**Phase 2.2 (Next)**: Algorithm swap - 15 minutes → **<10s latency**
**Phase 2.3 (Next)**: Skip preassembly - 10 minutes → **<7s latency, <100 MB memory**
**Phase 3 (Optional)**: BFS fallback - 20 minutes → **Eliminate all timeouts**

**Total remaining**: 55 minutes (75 minutes with Phase 3)

---

## Expected Performance After Optimization

| Operation | Before | After Phase 2.1 | After Phase 2.2 | After Phase 2.3 |
|-----------|--------|-----------------|-----------------|-----------------|
| Neighborhood fetch | 20s | 0s (skipped) | 0s | 0s |
| Path statements | 60s | 6s (single query) | 6s | 6s |
| Preassembly | 53s | 53s | 53s | 0s (skipped) |
| Pathfinding | <1s | <1s | <0.1s (Dijkstra) | <0.1s |
| **Total** | **134s** | **60s** | **7s** | **6s** |
| **Memory** | **4679 MB** | **500 MB** | **200 MB** | **<100 MB** |
| **Speedup** | **1×** | **2.2×** | **19×** | **22×** |

---

## Risk Assessment

### Low Risk ✅
- Skip neighborhood fetching (proven not needed)
- Single query with `persist=False` (INDRA docs recommended)
- Dijkstra vs k-shortest paths (same algorithm, different termination)

### Medium Risk ⚠️
- Skip preassembly (INDRA DB already pre-assembled, but untested assumption)
- Lower statement limits (may miss rare pathways)

### High Risk ⛔
- BFS instead of mediator expansion (completely different approach)

### Mitigation
- Keep old code commented out for rollback
- A/B test on known paths (PM2.5 → IL-6, IL-6 → CRP)
- Validate MDL ranking with manual inspection
- Monitor cache hit rates

---

## Next Actions

1. ✅ Create master plan (this document)
2. ⏳ Archive old planning documents
3. ⏳ Implement Phase 2.1 (30 min)
4. ⏳ Test and validate (<20s target)
5. ⏳ Implement Phase 2.2 (15 min)
6. ⏳ Test and validate (<10s target)
7. ⏳ Implement Phase 2.3 (10 min)
8. ⏳ Test and validate (<7s, <100 MB targets)
9. ⏳ Document final results
10. ⏳ Update CLAUDE.md with new performance characteristics

---

**Ready to proceed with Phase 2.1 implementation!** 🚀
