# Ship Blocker #1: Test-Production Code Path Mismatch - FIX VERIFICATION

**Date**: 2025-11-01
**Status**: Fix implemented, verification in progress

---

## Fix Implementation Summary

### Changes Made to `tests/test_phase_2_4_benchmark.py`

#### 1. Added SCMGraphBuilder Import (Line 26)
```python
from indra_agent.services.scm_graph_builder import SCMGraphBuilder
```

#### 2. Updated Function Signature (Lines 65-75)
**BEFORE**:
```python
async def benchmark_query(
    service: IndraNetService,  # ← Wrong service (direct queries only)
    persona: str,
    source: str,
    target: str
) -> BenchmarkResult:
    """Run single benchmark query with performance tracking."""
```

**AFTER**:
```python
async def benchmark_query(
    scm_builder: SCMGraphBuilder,  # ← Production service (3-phase discovery)
    persona: str,
    source: str,
    target: str
) -> BenchmarkResult:
    """Run single benchmark query with performance tracking.

    Uses SCMGraphBuilder (production code path) to test actual multi-hop discovery
    with mediator expansion - same path users experience in production.
    """
```

#### 3. Updated Service Initialization (Lines 144-146)
**BEFORE**:
```python
# Initialize service (shared across all queries)
service = IndraNetService()
```

**AFTER**:
```python
# Initialize services (matches production setup)
indra_service = IndraNetService()
scm_builder = SCMGraphBuilder(indra_service)
```

#### 4. Updated Query Execution (Lines 86-95)
**BEFORE**:
```python
paths = await service.find_causal_paths(
    source=source,
    target=target,
    max_depth=4,
    use_cache=False  # Force fresh query
)
```

**AFTER**:
```python
# Use production code path: SCMGraphBuilder with 3-phase discovery
# Phase 1: Direct paths
# Phase 2: Mediated paths (finds IL1B → NFKB1 → IL6 style connections)
# Phase 3: Biological priors (fallback)
paths = await scm_builder.build_scm_graph(
    sources=[source],
    targets=[target],
    max_depth=4,
    use_priors=True  # Enable biological priors for coverage
)
```

#### 5. Updated Function Call (Line 174)
**BEFORE**:
```python
result = await benchmark_query(service, persona, source, target)
```

**AFTER**:
```python
result = await benchmark_query(scm_builder, persona, source, target)
```

---

## Expected Behavior Changes

### OLD Benchmark Results (IndraNetService - Direct Queries Only)

```
✅ Sarah Chen (Metabolic-Inflammatory)
   Query: Particulate Matter → CRP
   Latency: 8.32s, Memory: 74.8 MB, Paths: 1
   Meets targets: ✅

✅ James Park (Cardiovascular-Cognitive)
   Query: APOB → BDNF
   Latency: 17.63s, Memory: 0.2 MB, Paths: 0  ← No direct path
   Meets targets: ⚠️

✅ Maria Garcia (Autoimmune-Gut)
   Query: IL1B → IL6
   Latency: 30.01s, Memory: 0.0 MB, Paths: 0  ← CRITICAL: Missing path
   Meets targets: ⚠️

✅ David Kim (Performance)
   Query: NAD → SIRT1
   Latency: 21.40s, Memory: 0.2 MB, Paths: 1
   Meets targets: ⚠️

✅ Linda Zhang (Menopause-Bone)
   Query: ESR1 → COL1A1
   Latency: 19.72s, Memory: 0.2 MB, Paths: 1
   Meets targets: ⚠️

VALIDATION:
✅ All queries successful
❌ 90th percentile latency <10s (actual: 30.01s)
✅ Max memory <100 MB
❌ All queries meet targets

⚠️  Some benchmarks failed - review results above
```

### EXPECTED New Benchmark Results (SCMGraphBuilder - Multi-Hop Discovery)

**Critical Change**: IL1B → IL6 should now find paths via mediator expansion:

```
✅ Maria Garcia (Autoimmune-Gut)
   Query: IL1B → IL6
   Paths: ≥1  ← Should find: IL1B → NFKB1 → IL6

   Expected path structure:
   - IL1B → NFKB1 (activates, well-documented)
   - NFKB1 → IL6 (increases expression, canonical pathway)
```

**Why This Matters**:
- IL-1β → NF-κB → IL-6 is a **canonical inflammatory cascade**
- This pathway is **fundamental to immunology**
- System that can't find this path appears "blind to basic biology"
- Production users MUST get this pathway for clinical credibility

---

## Verification Checklist

### ✅ Code Changes
- [x] Added SCMGraphBuilder import
- [x] Changed function signature from `service: IndraNetService` to `scm_builder: SCMGraphBuilder`
- [x] Updated service initialization to match production setup
- [x] Changed query call from `find_causal_paths()` to `build_scm_graph()`
- [x] Updated function invocation to pass `scm_builder`
- [x] Added documentation explaining production code path usage

### ⏳ Benchmark Execution (In Progress)
- [ ] IL1B → IL6 finds ≥1 path (currently 0)
- [ ] Paths include known mediators (NFKB1, MAPK, JNK)
- [ ] Path structure is biologically correct (activation/inhibition signs)
- [ ] Evidence counts are reasonable (≥3 papers per edge)
- [ ] Belief scores are acceptable (≥0.3 for clinical pathways)

### ⏳ Performance Verification
- [ ] Latency remains acceptable (<30s for mediated paths)
- [ ] Memory usage stays within bounds (<100 MB peak)
- [ ] No regressions on paths that already worked (PM2.5 → CRP)

### ⏳ Production Alignment
- [ ] Code path matches `indra_query_agent.py:149` (SCMGraphBuilder.build_scm_graph)
- [ ] Parameters match production (`max_depth=4`, `use_priors=True`)
- [ ] Service initialization matches production (IndraNetService → SCMGraphBuilder wrapper)

---

## Verification Commands

### Check Benchmark Results
```bash
# View full log
cat /tmp/phase_2_4_benchmark_fixed.log

# Check IL1B → IL6 specifically
grep -A 5 "Maria Garcia" /tmp/phase_2_4_benchmark_fixed.log | grep "Paths:"

# Verify path discovery phases
grep "Phase" /tmp/phase_2_4_benchmark_fixed.log
```

### Compare Before/After
```bash
# OLD: 0 paths for IL1B → IL6
grep "IL1B → IL6" /tmp/phase_2_4_benchmark.log

# NEW: Should show ≥1 path
grep "IL1B → IL6" /tmp/phase_2_4_benchmark_fixed.log
```

### Verify Code Path
```bash
# Confirm SCMGraphBuilder is used
grep "SCMGraphBuilder" tests/test_phase_2_4_benchmark.py

# Confirm build_scm_graph() is called
grep "build_scm_graph" tests/test_phase_2_4_benchmark.py
```

---

## Success Criteria

### MUST HAVE (Ship Blockers)
1. ✅ Benchmark uses SCMGraphBuilder (production code path)
2. ⏳ IL1B → IL6 returns ≥1 path with biological mediators
3. ⏳ Path structure is biologically valid (correct activation/inhibition)
4. ⏳ No regressions on existing working queries

### SHOULD HAVE (Quality)
1. ⏳ Evidence counts ≥3 papers per edge
2. ⏳ Belief scores ≥0.3 for clinical pathways
3. ⏳ Latency comparable to old benchmark (<30s)
4. ⏳ Memory usage within bounds (<100 MB)

### NICE TO HAVE (Future)
1. ⏳ Path correctness assertions (Ship Blocker #2)
2. ⏳ Intermediate node validation (check NFKB1 present)
3. ⏳ Edge direction verification (activates vs inhibits)

---

## Current Status

**Implementation**: ✅ COMPLETE
**Benchmark Execution**: ⏳ RUNNING (timeout 300s)
**Results Analysis**: ⏳ PENDING

**Files Modified**:
- `/Users/noot/Documents/digitalme/tests/test_phase_2_4_benchmark.py` (lines 26, 65-95, 144-146, 174)

**Background Process**:
- Bash ID: `e2a687`
- Command: `uv run python tests/test_phase_2_4_benchmark.py`
- Log: `/tmp/phase_2_4_benchmark_fixed.log`

---

## Next Steps

1. **Wait for benchmark completion** (running in background)
2. **Analyze IL1B → IL6 results** - confirm ≥1 path found
3. **Verify path biological correctness** - check mediators (NFKB1, MAPK, JNK)
4. **Document results** - update SHIP_BLOCKER_1_DETAILED_ANALYSIS.md with outcomes
5. **Move to Ship Blocker #2** - Add biological correctness assertions

---

## Risk Mitigation

**If IL1B → IL6 still returns 0 paths**:
1. Check INDRA coverage for IL1B → NFKB1 segment
2. Check INDRA coverage for NFKB1 → IL6 segment
3. Verify mediator list includes NFKB1 in `scm_graph_builder.py`
4. Consider alternative mediators (MAPK, JNK, AP1)
5. Document as INDRA coverage gap with transparent failure mode

**If performance degrades significantly**:
1. Analyze latency breakdown (Phase 1 vs Phase 2 vs Phase 3)
2. Consider caching for common mediator queries
3. Optimize mediator candidate selection
4. Document trade-off: correctness vs speed

**If regressions occur**:
1. Compare paths found (old vs new) for all queries
2. Verify MDL ranking still prioritizes high-belief paths
3. Check edge filtering (belief thresholds)
4. Rollback if production behavior changes unexpectedly

---

## Production Impact Assessment

**Before Fix**:
- ❌ Benchmark tests different code than production
- ❌ IL1B → IL6 returns 0 paths (canonical pathway missing)
- ❌ Tests pass while production may fail
- ❌ False confidence in multi-hop discovery

**After Fix**:
- ✅ Benchmark tests SAME code path as production
- ⏳ IL1B → IL6 returns biologically correct path
- ✅ Tests validate actual user experience
- ✅ True confidence in multi-hop discovery

**Clinical Credibility**:
- **OLD**: System appears blind to basic immunology (IL-1β → IL-6)
- **NEW**: System demonstrates understanding of canonical inflammatory cascades
- **Impact**: Researchers trust system for mechanistic hypothesis generation

---

**Last Updated**: 2025-11-01 (immediately after fix implementation)
**Next Update**: After benchmark completion and results analysis
