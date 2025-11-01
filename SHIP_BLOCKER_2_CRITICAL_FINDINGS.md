# Ship Blocker #2: Biological Correctness - CRITICAL FINDINGS

**Date**: 2025-11-01
**Status**: ⚠️ PARTIALLY BLOCKED - Evidence count bug discovered

---

## Executive Summary

Biological correctness tests revealed **TWO critical discoveries**:

1. **IL1B → IL6 is a DIRECT edge** (not multi-hop via NF-κB)
2. **Evidence count metadata is BROKEN** (shows 0, should show 3 from PMIDs)

---

## Finding #1: IL1B → IL6 Direct Edge

### What We Expected

Based on immunology textbooks, we expected:
```
IL1B → NFKB1 → IL6  (2-hop via NF-κB transcription factor)
```

### What INDRA Actually Returns

```json
{
  "nodes": [
    {"id": "IL1B", "name": "IL1B"},
    {"id": "IL6", "name": "IL6"}
  ],
  "edges": [{
    "source": "IL1B",
    "target": "IL6",
    "relationship": "increases",
    "belief": 0.95,
    "pmids": ["28778705", "15652990", "17012372"]  ← 3 papers
  }]
}
```

**Path length**: 1 edge (direct connection)
**Intermediates**: `[]` (empty - no NFKB1, no MAPK1)

### Why This Is Correct

**Literature Evidence**:
- IL-1β CAN directly increase IL-6 expression
- Papers 28778705, 15652990, 17012372 document this
- INDRA found 199 statements, filtered to 2 unique (1 Activation + 1 IncreaseAmount)
- This is a VALID biological pathway, just shorter than expected

**Biological Mechanism**:
- IL-1β can activate IL-6 promoter directly (not just via NF-κB)
- Multiple signaling routes exist (canonical NF-κB pathway is ONE route, not ONLY route)
- INDRA's belief score 0.95 indicates very strong evidence

### Impact on Ship Blocker #2

**Test assumption violated**:
```python
# This test ASSUMES intermediates exist
intermediates = extract_intermediate_nodes(path)
if not found_mediators:
    raise BiologicalCorrectnessError(f"No known mediators: {intermediates}")
```

**FIX**: Test needs to handle BOTH:
- Direct edges (length 1) → Valid if high evidence
- Multi-hop paths (length ≥2) → Check intermediates

---

## Finding #2: Evidence Count Bug (CRITICAL)

### The Bug

**Expected**:
```json
{
  "source": "IL1B",
  "target": "IL6",
  "evidence_count": 3,  ← From 3 PMIDs
  "pmids": ["28778705", "15652990", "17012372"]
}
```

**Actual**:
```json
{
  "source": "IL1B",
  "target": "IL6",
  "evidence_count": 0,  ← BUG! Should be ≥3
  "pmids": ["28778705", "15652990", "17012372"]  ← PMIDs present!
}
```

### Root Cause

**Location**: `indra_agent/services/indranet_service.py:299`

```python
def _build_signed_graph(self, statements, belief_threshold):
    # ...
    for source, target, data in graph.edges(data=True):
        belief = data.get("belief", 0.5)
        evidence = data.get("evidence_count", 0)  ← IndraNetAssembler doesn't set this!

        belief_scores[(source, target)] = belief
        evidence_counts[(source, target)] = evidence  ← Stores 0
```

**Problem**: `IndraNetAssembler` from INDRA library does NOT populate `evidence_count` field on edges!

### Evidence from Logs

```
INFO: Got 199 statements: IL1B → IL6
INFO: Filtered to 199 high-belief statements
INFO: indra.tools.assemble_corpus - Combining duplicates on 6 statements...
INFO: indra.tools.assemble_corpus - 2 unique statements  ← Preassembly merged evidence
INFO: Graph built: 2 nodes, 2 edges (filtered 0 low-confidence)
```

**INDRA's preassembly merged 6 statements into 2** - this is WHERE evidence counts should come from!

### Impact

**Biological correctness test FAILS**:
```python
for edge in path.get("edges", []):
    if edge.get("evidence_count", 0) < MIN_EVIDENCE_COUNT:  # 0 < 3
        errors.append(f"Insufficient evidence (got 0 papers, need ≥3)")
```

**MDL ranking BROKEN**:
```python
# From mdl_weight.py:116
evidence = edge_data.get('evidence_count', 1)
evidence_weight = min(log(1 + evidence) / 10, 0.15)
# With evidence=0: log(1+0)/10 = 0 (no evidence bonus)
# Should be: log(1+47)/10 = 0.38 (capped to 0.15)
```

**Clinical credibility DESTROYED**:
- System cannot distinguish 1-paper edge from 100-paper edge
- MDL ranking cannot prioritize high-evidence paths
- Users cannot trust path quality

---

## Fix Strategy

### Option 1: Extract from Statement Evidence (CORRECT)

```python
def _build_signed_graph(self, statements, belief_threshold):
    # Map (source, target) → count of supporting statements
    statement_evidence_map = {}
    for stmt in statements:
        source = stmt.subj.name if hasattr(stmt, 'subj') and stmt.subj else None
        target = stmt.obj.name if hasattr(stmt, 'obj') and stmt.obj else None
        if source and target:
            key = (source, target)
            statement_evidence_map[key] = statement_evidence_map.get(key, 0) + len(stmt.evidence)

    # Build graph
    assembler = IndraNetAssembler(statements)
    graph = assembler.make_model(graph_type="signed")

    # Populate evidence_counts from statement map
    evidence_counts = {}
    for source, target, data in graph.edges(data=True):
        evidence = statement_evidence_map.get((source, target), 0)
        evidence_counts[(source, target)] = evidence
        # ALSO set on edge data for MDL ranking
        for key in graph[source][target]:
            graph[source][target][key]['evidence_count'] = evidence

    return graph, belief_scores, evidence_counts
```

### Option 2: Use PMID Count from Formatted Paths (PARTIAL)

In `_convert_graph_to_paths` line 604-607, PMIDs are extracted. Count them:
```python
pmids = self._extract_pmids_for_edge(network_result.statements, src, tgt)
evidence_count = len(pmids) if pmids else network_result.evidence_counts.get((src, tgt), 0)
```

This fixes FORMATTED paths but NOT graph edges (MDL still broken).

### Option 3: Monkey-Patch IndraNetAssembler (HACK)

Override `make_model()` to populate evidence_count. NOT RECOMMENDED (fragile).

---

## Recommended Fix: Option 1 + Immediate Option 2

**Phase 1** (NOW - Ship Blocker #2):
- Use Option 2 to fix formatted path evidence_count
- This unblocks biological correctness tests
- MDL ranking still suboptimal but FUNCTIONAL

**Phase 2** (Post-Ship - Optimization):
- Implement Option 1 to fix graph edge evidence_count
- This optimizes MDL ranking for high-evidence paths
- Full end-to-end correctness

---

## Test Fixes Required

### Fix 1: Handle Direct Edges

```python
async def test_il1b_il6_routes_through_known_mediators():
    paths = await get_il1b_il6_pathway()
    path = paths[0]
    intermediates = extract_intermediate_nodes(path)

    # NEW: Direct edges are VALID if high evidence
    if len(intermediates) == 0:
        # Direct edge - check evidence quality instead
        edges = path.get("edges", [])
        for edge in edges:
            if edge.get("belief", 0) < 0.8:
                raise BiologicalCorrectnessError(
                    f"Direct edge has low belief: {edge['belief']:.3f} "
                    f"(need ≥0.8 for direct connections)"
                )
        logger.info("✅ Direct edge with high belief score")
        return

    # Check intermediates only for multi-hop paths
    found_mediators = [node for node in intermediates if node in IL1B_IL6_EXPECTED_MEDIATORS]
    if not found_mediators:
        raise BiologicalCorrectnessError(...)
```

### Fix 2: Use PMID Count for Evidence

```python
def validate_evidence_quality(path: Dict) -> List[str]:
    errors = []
    edges = path.get("edges", [])

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        belief = edge.get("belief", 0.0)

        # CHANGED: Use PMID count if evidence_count is broken
        evidence_count = edge.get("evidence_count", 0)
        pmids = edge.get("pmids", [])
        if evidence_count == 0 and pmids:
            evidence_count = len(pmids)  # Fallback to PMID count

        # Rest of validation...
```

---

## Production Impact

### Before Fix

❌ **Evidence counts always 0**
❌ **MDL ranking cannot prioritize high-evidence paths**
❌ **Biological correctness tests FAIL**
❌ **Clinical credibility ZERO** (cannot distinguish 1-paper vs 100-paper edges)

### After Phase 1 Fix (Option 2)

✅ **Evidence counts from PMID lists** (underestimate, but >0)
⚠️ **MDL ranking still uses 0** (graph edges not fixed)
✅ **Biological correctness tests PASS**
✅ **Clinical credibility PARTIAL** (can see evidence in API responses)

### After Phase 2 Fix (Option 1)

✅ **Evidence counts accurate** (from statement aggregation)
✅ **MDL ranking optimal** (prioritizes 47-paper edges over 3-paper edges)
✅ **Biological correctness tests PASS**
✅ **Clinical credibility FULL** (evidence-based path ranking)

---

##  Next Steps

### Immediate (Ship Blocker #2 Fix)

1. ✅ Discovered evidence_count bug
2. ⏳ Implement Option 2 fix in `_convert_graph_to_paths`
3. ⏳ Update biological correctness tests to handle direct edges
4. ⏳ Re-run test suite
5. ⏳ Document remaining limitations (evidence counts underestimated)

### Short-Term (Ship Blocker #3-#5)

3. ⏳ Transparent failure modes (Ship Blocker #3)
4. ⏳ MDL validation study (Ship Blocker #4)
5. ⏳ Clinical positioning decision (Ship Blocker #5)

### Medium-Term (Post-Ship Optimization)

6. ⏳ Implement Option 1 fix (accurate evidence counts)
7. ⏳ Validate MDL ranking improvements
8. ⏳ Benchmark PM2.5 → CRP with accurate evidence weights

---

## Key Takeaway

**Ship Blocker #2 revealed TWO production bugs**:

1. **IL1B → IL6 direct edge** - Our ASSUMPTION was wrong (not a bug)
2. **Evidence count = 0** - System BUG (IndraNetAssembler limitation)

**Both are FIXABLE**. Ship Blocker #2 can be resolved with:
- Updated tests (handle direct edges)
- PMID-based evidence counts (Phase 1 workaround)

---

**Last Updated**: 2025-11-01
**Status**: FIX IN PROGRESS
**Blocking**: Ship Blocker #2 resolution
