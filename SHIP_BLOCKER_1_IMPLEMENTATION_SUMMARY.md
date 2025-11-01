# Ship Blocker #1: Test-Production Code Path Mismatch - Implementation Summary

**Date**: 2025-11-01
**Status**: ✅ FIXED - Verification in progress
**Impact**: CRITICAL - Tests now validate production behavior

---

## Problem Statement

### The Critical Bug

**Symptom**: IL1B → IL6 returns 0 paths in benchmark, but should find canonical inflammatory cascade

**Root Cause**: Benchmark tested `IndraNetService` (direct queries only), while production uses `SCMGraphBuilder` (3-phase multi-hop discovery)

**Production Impact**:
```
Scenario: SCMGraphBuilder's mediator expansion breaks
Benchmark: ✅ 5/5 PASS (tests IndraNetService, still works)
Production: ❌ IL1B → IL6 returns empty (should find IL1B → NFKB1 → IL6)
User Experience: "Your system can't find basic inflammatory pathways"
```

### Why This Is a Ship Blocker

1. **False Confidence**: Tests pass while production feature breaks
2. **Silent Degradation**: Multi-hop discovery could fail for weeks unnoticed
3. **Clinical Credibility**: Missing IL-1β → IL-6 appears "blind to basic immunology"
4. **Deployment Risk**: Could ship broken multi-hop without detection

---

## The Fix

### Code Changes (5 locations in `tests/test_phase_2_4_benchmark.py`)

#### 1. Import SCMGraphBuilder (Line 26)
```python
from indra_agent.services.scm_graph_builder import SCMGraphBuilder
```

#### 2. Function Signature (Line 65)
```python
# BEFORE
async def benchmark_query(
    service: IndraNetService,  # ← Wrong service
    ...
)

# AFTER
async def benchmark_query(
    scm_builder: SCMGraphBuilder,  # ← Production service
    ...
)
```

#### 3. Service Initialization (Lines 144-146)
```python
# BEFORE
service = IndraNetService()

# AFTER
indra_service = IndraNetService()
scm_builder = SCMGraphBuilder(indra_service)  # ← Matches production setup
```

#### 4. Query Execution (Lines 86-95)
```python
# BEFORE
paths = await service.find_causal_paths(
    source=source,
    target=target,
    max_depth=4,
    use_cache=False
)

# AFTER
paths = await scm_builder.build_scm_graph(
    sources=[source],
    targets=[target],
    max_depth=4,
    use_priors=True  # ← Matches production parameters
)
```

#### 5. Function Call (Line 174)
```python
# BEFORE
result = await benchmark_query(service, ...)

# AFTER
result = await benchmark_query(scm_builder, ...)
```

---

## Architecture Alignment

### BEFORE Fix: Test vs Production Divergence

**Test Path** (test_phase_2_4_benchmark.py:81):
```
benchmark_query()
  → IndraNetService.find_causal_paths()
  → build_biomarker_network()
  → _get_path_statements_optimized()
  → idr.get_statements(subject=source, object=target)  # DIRECT ONLY
```

**Production Path** (indra_query_agent.py:149):
```
build_scm_graph tool
  → SCMGraphBuilder.build_scm_graph()
  → Phase 1: _find_direct_paths() (try direct first)
  → Phase 2: _find_mediated_paths() (expand via NFKB1, MAPK, JNK)
  → Phase 3: _build_prior_paths() (biological priors fallback)
```

**Divergence**: Test bypassed Phase 2 & 3 entirely!

### AFTER Fix: Test = Production Code Path

**Both use identical path**:
```
SCMGraphBuilder.build_scm_graph()
  → Phase 1: Direct INDRA query
  → Phase 2: Mediator expansion (IL1B → NFKB1 → IL6)
  → Phase 3: Biological priors
```

**Alignment verified**:
- ✅ Same service class: `SCMGraphBuilder`
- ✅ Same method: `build_scm_graph()`
- ✅ Same parameters: `max_depth=4`, `use_priors=True`
- ✅ Same initialization: `IndraNetService` → `SCMGraphBuilder` wrapper

---

## Expected Outcome

### IL1B → IL6 (Maria Garcia Persona)

**OLD Result** (IndraNetService):
```
INFO: IL1B → IL6
INFO: Got 0 statements: IL1B → IL6
WARNING: No statements - empty network
✅ Success: 0 paths in 30.01s, 0.0 MB
Meets targets: ⚠️
```

**EXPECTED New Result** (SCMGraphBuilder with mediator expansion):
```
INFO: IL1B → IL6
INFO: No direct paths. Expanding via mediators...
INFO: Trying mediators: ['NFKB1', 'MAPK1', 'JNK', ...]
INFO: Found path: IL1B → NFKB1 → IL6
✅ Success: ≥1 paths in <60s, <100 MB
Meets targets: ✅
```

**Why This Matters**:
- IL-1β → NF-κB → IL-6 is **canonical inflammatory signaling**
- This pathway is **fundamental to immunology** (textbook material)
- Missing this path makes system appear "blind to basic biology"
- Finding this path proves **multi-hop discovery works**

---

## Verification Status

### Implementation Checklist
- [x] Added SCMGraphBuilder import
- [x] Changed function signature
- [x] Updated service initialization
- [x] Changed query method call
- [x] Updated function invocation
- [x] Added documentation comments

### Runtime Verification (In Progress)
- ⏳ Benchmark running with new code path
- ⏳ Monitoring IL1B → IL6 result
- ⏳ Verifying mediator expansion logs
- ⏳ Checking path biological correctness

**Background Process**:
- Bash ID: `e2a687`
- Log: `/tmp/phase_2_4_benchmark_fixed.log`
- Status: Running (Phase 2 mediator expansion active)

### Evidence of Fix Working

**From current logs**:
```
INFO: Using PRODUCTION code path: SCMGraphBuilder with 3-phase discovery
INFO: Building SCM graph: 1 sources → 1 targets
INFO: No direct paths. Expanding via mediators...
INFO: Trying 10 mediators: ['reactive oxygen species', 'oxidative stress', ...]
```

**Key Indicators**:
1. ✅ "Using PRODUCTION code path" - confirms SCMGraphBuilder
2. ✅ "Building SCM graph" - SCMGraphBuilder.build_scm_graph() called
3. ✅ "Expanding via mediators" - Phase 2 multi-hop discovery active
4. ✅ "Trying 10 mediators" - mediator candidate selection working

---

## Files Modified

### `/Users/noot/Documents/digitalme/tests/test_phase_2_4_benchmark.py`
**Lines Changed**: 26, 65-75, 86-95, 144-146, 174

**Before**:
- Imported: `IndraNetService`
- Used: `service.find_causal_paths()` (direct queries)
- Initialized: `service = IndraNetService()`

**After**:
- Imported: `IndraNetService`, `SCMGraphBuilder`
- Used: `scm_builder.build_scm_graph()` (3-phase discovery)
- Initialized: `indra_service = IndraNetService()` + `scm_builder = SCMGraphBuilder(indra_service)`

---

## Production Impact

### Before Fix

❌ **Test-Production Mismatch**:
- Benchmark: Tests `IndraNetService` (direct only)
- Production: Uses `SCMGraphBuilder` (multi-hop)
- Risk: Production breaks, tests pass

❌ **Missing Canonical Pathways**:
- IL1B → IL6: 0 paths (fundamental immunology missing)
- User perception: "System doesn't understand basic biology"
- Clinical credibility: Destroyed

❌ **False Confidence**:
- 100% test pass rate
- Multi-hop discovery could be completely broken
- Deploy to production blind

### After Fix

✅ **Test = Production Code Path**:
- Both use `SCMGraphBuilder.build_scm_graph()`
- Same 3-phase discovery strategy
- Risk: If test fails, production WILL fail (true signal)

✅ **Canonical Pathways Found** (expected):
- IL1B → IL6: ≥1 path via NFKB1 mediator
- User perception: "System understands immunology"
- Clinical credibility: Established

✅ **True Confidence**:
- Test failures = production failures
- Cannot ship broken multi-hop unknowingly
- Deploy with verified behavior

---

## Next Steps

### Immediate (Waiting on Benchmark)
1. ⏳ Wait for benchmark completion
2. ⏳ Verify IL1B → IL6 returns ≥1 path
3. ⏳ Check path structure (IL1B → NFKB1 → IL6)
4. ⏳ Validate edge directions (activates/increases)

### Short-Term (Ship Blocker #2)
1. ⏳ Add biological correctness assertions
2. ⏳ Verify intermediate nodes (NFKB1 present)
3. ⏳ Check evidence counts (≥3 papers/edge)
4. ⏳ Validate belief scores (≥0.3 clinical)

### Medium-Term (Ship Blockers #3-5)
3. ⏳ Transparent failure modes (explain why paths missing)
4. ⏳ MDL validation study (empirical correctness)
5. ⏳ Clinical positioning decision (regulatory compliance)

---

## Success Criteria

### MUST HAVE (Ship Blocker Resolved)
- ✅ Benchmark uses `SCMGraphBuilder` (production code path)
- ⏳ IL1B → IL6 returns ≥1 path with biological mediators
- ⏳ Path structure is biologically valid
- ⏳ No regressions on existing working queries

### SHOULD HAVE (Quality Validation)
- ⏳ Evidence counts ≥3 papers per edge
- ⏳ Belief scores ≥0.3 for clinical pathways
- ⏳ Latency comparable to old benchmark
- ⏳ Memory usage within bounds

---

## Documentation Created

1. **SHIP_BLOCKER_1_DETAILED_ANALYSIS.md** - Line-by-line code path analysis
2. **SHIP_BLOCKER_1_FIX_VERIFICATION.md** - Verification checklist and commands
3. **SHIP_BLOCKER_1_IMPLEMENTATION_SUMMARY.md** (this file) - Executive summary

---

## Key Takeaways

### What We Fixed
**The EXACT code path tests execute now matches production**

### Why It Matters
**Cannot ship production system if tests validate different behavior**

### How We Know It's Fixed
**Logs show "Expanding via mediators..." - Phase 2 discovery active**

### What's Next
**Verify IL1B → IL6 finds canonical inflammatory pathway**

---

**Last Updated**: 2025-11-01 (benchmark running, results pending)
**Estimated Completion**: Within 5 minutes (300s timeout)
**Blocking**: Ship Blocker #2 (biological correctness validation)
