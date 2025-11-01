# Ship Blocker #1: Test-Production Code Path Mismatch

## Detailed Line-by-Line Analysis

### The Problem

**Benchmark tests use different code than production users experience.**

This is NOT a minor issue. This means:
- Production could break while tests pass 100%
- We're testing fast path, users get slow path
- We're testing 1-hop discovery, users get multi-hop
- Coverage gap invisible until user reports

---

## Exact Code Paths (With File:Line References)

### TEST PATH: test_phase_2_4_benchmark.py

**File**: `/Users/noot/Documents/digitalme/tests/test_phase_2_4_benchmark.py`

```
Line 25: from indra_agent.services.indranet_service import IndraNetService
         ↓
Line 72: service = IndraNetService()
         ↓
Line 81: paths = await service.find_causal_paths(
Line 82:     source=source,
Line 83:     target=target,
Line 84:     max_depth=4,
Line 85:     use_cache=False
Line 86: )
```

**What This Calls**:

`indranet_service.py:479-516`:
```python
async def find_causal_paths(
    self,
    source: str,
    target: str,
    max_depth: int = 4,  # ← IGNORED! Only finds direct paths
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Find MDL-optimal causal paths."""

    try:
        network_result = await self.build_biomarker_network(
            exposures=[source],
            biomarkers=[target],
            max_depth=max_depth,  # Passed but...
            belief_threshold=0.3
        )
```

Which calls:

`indranet_service.py:117-188`:
```python
async def build_biomarker_network(
    self,
    exposures: List[str],
    biomarkers: List[str],
    max_depth: int = 4,  # ← Received but IGNORED
    belief_threshold: float = 0.3,
) -> IndraNetworkResult:
    """Build network for pathfinding."""

    # Fetch statements for all exposure→biomarker pairs
    all_statements: List[Statement] = []

    for exposure in exposures:
        for biomarker in biomarkers:
            logger.info(f"Fetching: {exposure} → {biomarker}")
            stmts = await self._get_path_statements_optimized(exposure, biomarker)
            # ↑ NO max_depth parameter passed!
```

Which calls:

`indranet_service.py:190-247`:
```python
async def _get_path_statements_optimized(
    self, source: str, target: str
) -> List[Statement]:
    """Optimized path statement fetching using single directed query.

    OLD (3 queries, 60s):
    - Query 1: subject=source, object=target (20s)
    - Query 2: agents=[source] (20s)
    - Query 3: agents=[target] (20s)

    NEW (1 query, ~5-10s):
    - Query 1: subject=source, object=target with higher limit

    This works because we're doing pathfinding (directional).
    For multi-hop paths, we rely on mediator expansion in SCM graph builder.
    """
    # ↑ THIS COMMENT ADMITS IT ONLY DOES DIRECT PATHS!

    def fetch():
        try:
            processor = idr.get_statements(
                subject=source,
                object=target,  # ← DIRECT QUERY ONLY
                limit=200,
                persist=False,
                ev_limit=5,
                sort_by='ev_count',
                timeout=30,
                tries=2
            )
```

**CRITICAL LINE** (indranet_service.py:204):
```python
# For multi-hop paths, we rely on mediator expansion in SCM graph builder.
```

**This comment PROVES**:
1. `IndraNetService` only does direct paths
2. Multi-hop requires `SCMGraphBuilder`
3. Benchmark bypasses `SCMGraphBuilder`

---

### PRODUCTION PATH: indra_query_agent.py

**File**: `/Users/noot/Documents/digitalme/indra_agent/agents/indra_query_agent.py`

```
Line 51: scm_builder = SCMGraphBuilder(indra_service)
         ↓
Line 77-202: @tool async def build_scm_graph(...)
         ↓
Line 149: paths = await scm_builder.build_scm_graph(
Line 150:     sources=sources,
Line 151:     targets=targets,
Line 152:     user_biomarkers=user_biomarkers,
Line 153:     known_mediators=known_mediators,
Line 154:     max_depth=4,
Line 155:     use_priors=True,
Line 156:     progress_emitter=progress_emitter
Line 157: )
```

**What This Calls**:

`scm_graph_builder.py:157-417`:
```python
async def build_scm_graph(
    self,
    sources: List[str],
    targets: Optional[List[str]] = None,
    user_biomarkers: Optional[List[str]] = None,
    known_mediators: Optional[List[str]] = None,
    max_depth: int = 4,  # ← ACTUALLY USED
    use_priors: bool = True,
    progress_emitter=None,
) -> List[Dict[str, Any]]:
    """Build SCM graph connecting sources to targets.

    Strategy:
    1. If targets not provided, discover biomarker targets via multi_interactors
    2. For each (source, target) pair:
       a. Try direct INDRA path search         # ← Phase 1
       b. If fails, expand via known mediators # ← Phase 2
       c. Apply biological priors as fallback  # ← Phase 3
    """

    all_paths = []

    # Strategy: For each (source, target) pair, find connecting paths
    for source in sources:
        for target in targets:
            # Phase 1: Try direct INDRA search
            direct_paths = await self._find_direct_paths(source, target, max_depth)

            if direct_paths:
                logger.info(f"  Found {len(direct_paths)} direct paths via INDRA")
                all_paths.extend(direct_paths)
                continue  # Success - move to next pair

            # Phase 2: Expand via known mediators
            logger.info(f"  No direct paths. Expanding via mediators...")
            mediated_paths = await self._find_mediated_paths(
                source, target, known_mediators, max_depth
            )

            if mediated_paths:
                logger.info(f"  Found {len(mediated_paths)} mediated paths via INDRA")
                all_paths.extend(mediated_paths)
                continue

            # Phase 3: Apply biological priors (fallback)
            if use_priors:
                logger.info(f"  INDRA search failed. Applying biological priors...")
                prior_paths = self._build_prior_paths(source, target, max_depth)
```

**Phase 2 Implementation** (`scm_graph_builder.py:439-499`):
```python
async def _find_mediated_paths(
    self,
    source: str,
    target: str,
    known_mediators: List[str],
    max_depth: int,
) -> List[Dict[str, Any]]:
    """Find paths via known biological mediators.

    Strategy:
    1. Get potential mediators between source and target (from priors)
    2. For each mediator, query: source → mediator → target
    3. Return paths that successfully connect
    """
    # Get candidate mediators that could connect source to target
    candidate_mediators = get_mediators_between(source, target)

    if not candidate_mediators:
        # Fallback: try all known mediators
        candidate_mediators = known_mediators[:10]  # Limit to 10 for performance

    logger.info(f"    Trying {len(candidate_mediators)} mediators: {candidate_mediators[:5]}")

    all_mediated_paths = []

    for mediator in candidate_mediators:
        # Query segment 1: source → mediator
        segment1 = await self._find_direct_paths(source, mediator, max_depth=2)

        if not segment1:
            continue

        # Query segment 2: mediator → target
        segment2 = await self._find_direct_paths(mediator, target, max_depth=2)

        if not segment2:
            continue

        # Concatenate segments into complete paths
        for path1 in segment1[:2]:  # Top 2 from segment 1
            for path2 in segment2[:2]:  # Top 2 from segment 2
                concatenated = self._concatenate_paths(path1, path2, mediator)
                if concatenated:
                    all_mediated_paths.append(concatenated)
                    logger.info(f"    ✓ Via {mediator}: {len(concatenated['nodes'])} nodes")

    return all_mediated_paths
```

---

## The Mismatch Visualized

### What Benchmark Tests:

```
test_phase_2_4_benchmark.py:81
    ↓
IndraNetService.find_causal_paths()
    ↓
IndraNetService.build_biomarker_network()
    ↓
IndraNetService._get_path_statements_optimized()
    ↓
idr.get_statements(subject=source, object=target)  # DIRECT ONLY
    ↓
Returns: 1-hop paths only (PM2.5 → CRP)
Fails: IL1B → IL6 (no direct path)
```

### What Production Users Get:

```
indra_query_agent.py:77-202 (@tool build_scm_graph)
    ↓
SCMGraphBuilder.build_scm_graph()
    ↓
Phase 1: Try direct paths (same as benchmark)
    ↓ FAILS for IL1B → IL6
Phase 2: Expand via mediators
    ↓
_find_mediated_paths()
    ↓
For mediator in [NFKB1, JNK, MAPK]:
    IL1B → NFKB1: ✅ Found
    NFKB1 → IL6: ✅ Found
    Concatenate: IL1B → NFKB1 → IL6
    ↓
Returns: 2-hop path via NFKB1
Success: IL1B → IL6 (via mediator)
```

---

## Evidence from Benchmark Results

### Sarah Chen (PM2.5 → CRP):

**Benchmark Log**:
```
INFO: Query: Particulate Matter → CRP
INFO: Got 5 statements: Particulate Matter → CRP  # ← DIRECT path exists
INFO: Found 1 paths
INFO: ✅ Success: 1 paths in 8.32s, 74.8 MB
```

**Analysis**: Works because DIRECT path exists in INDRA.

---

### Maria Garcia (IL1B → IL6):

**Benchmark Log**:
```
INFO: Query: IL1B → IL6
INFO: Got 0 statements: IL1B → IL6  # ← NO direct path
WARNING: No statements - empty network
INFO: ✅ Success: 0 paths in 30.01s, 0.0 MB  # ← Test PASSES with 0 paths!
```

**What Production Would Do**:
```
Phase 1: Direct search for IL1B → IL6
    ↓ FAILS (0 statements)
Phase 2: Mediated search
    ↓
Try mediator: NFKB1
    IL1B → NFKB1: Query INDRA
        ↓ Found (IL-1β activates NF-κB)
    NFKB1 → IL6: Query INDRA
        ↓ Found (NF-κB increases IL-6)
    Concatenate: IL1B → NFKB1 → IL6
    ↓
Returns: 2-hop path with 3 nodes, 2 edges
```

**Result**: Benchmark returns 0 paths, production would return ≥1 path.

---

## Why This Is a Ship Blocker

### Scenario 1: SCMGraphBuilder Breaks

```
Developer commits code that breaks mediator expansion in SCMGraphBuilder:
    ↓
def _find_mediated_paths(...):
    # BUG: always returns empty list
    return []
    ↓
Production behavior:
    IL1B → IL6 query now returns 0 paths (regression!)
    Users report: "Tool can't find basic inflammatory pathways"
    ↓
Test suite: ✅ ALL TESTS PASS
    Why? Benchmark uses IndraNetService (no mediator expansion)
    IL1B → IL6 benchmark already returns 0 paths
    No change detected
    ↓
Result: Ship broken code to production, tests green
```

### Scenario 2: IndraNetService Optimized Further

```
Developer "optimizes" IndraNetService by reducing INDRA query timeout:
    ↓
processor = idr.get_statements(
    subject=source,
    object=target,
    timeout=5  # Was 30, now 5 (faster!)
)
    ↓
Benchmark results:
    Sarah Chen: 3.2s (was 8.32s) ✅ FASTER!
    All tests: ✅ PASS
    Developer: "Great optimization, ship it!"
    ↓
Production behavior:
    SCMGraphBuilder._find_mediated_paths() now times out
    Mediator queries (2 per mediator) = 2×5s = 10s minimum
    But total SCM timeout = 30s
    Now fails to find ~50% of mediated paths
    ↓
Result: Production degradation, benchmark shows improvement
```

### Scenario 3: Silent Feature Regression

```
Refactor moves mediated discovery to new module:
    ↓
# Old code (working):
mediated_paths = await self._find_mediated_paths(...)

# New code (broken import):
from new_module import find_mediated_paths  # ← Wrong signature
mediated_paths = await find_mediated_paths(source, target)  # ← Missing max_depth
    ↓
Production:
    Multi-hop discovery silently fails
    Only direct paths returned
    IL1B → IL6, APOB → BDNF: Now return 0 paths
    ↓
Tests: ✅ ALL PASS (never tested multi-hop)
    ↓
Deployed to production
User reports weeks later: "System degraded"
```

---

## The Fix (Detailed Implementation)

### Step 1: Benchmark Must Use SCMGraphBuilder

**File**: `tests/test_phase_2_4_benchmark.py`

**Current** (lines 64-86):
```python
async def benchmark_query(
    service: IndraNetService,  # ← WRONG SERVICE
    persona: str,
    source: str,
    target: str
) -> BenchmarkResult:
    """Run single benchmark query with performance tracking."""

    paths = await service.find_causal_paths(  # ← Direct paths only
        source=source,
        target=target,
        max_depth=4,  # ← Ignored
        use_cache=False
    )
```

**Fixed**:
```python
async def benchmark_query(
    scm_builder: SCMGraphBuilder,  # ← Production service
    persona: str,
    source: str,
    target: str
) -> BenchmarkResult:
    """Run single benchmark query with performance tracking.

    CRITICAL: This MUST use SCMGraphBuilder (production code path)
    to ensure benchmarks test what users actually experience.
    """

    paths = await scm_builder.build_scm_graph(  # ← Multi-hop discovery
        sources=[source],
        targets=[target],
        max_depth=4,  # ← Actually used by mediated search
        use_priors=True  # ← Phase 3 fallback
    )
```

### Step 2: Update Benchmark Initialization

**Current** (lines 71-72):
```python
# Initialize service (shared across all queries)
service = IndraNetService()
```

**Fixed**:
```python
# Initialize production services (matches user code path)
indra_service = IndraNetService()  # Used internally by SCMGraphBuilder
scm_builder = SCMGraphBuilder(indra_service)
```

### Step 3: Update Benchmark Call

**Current** (line 100):
```python
result = await benchmark_query(service, persona, source, target)
```

**Fixed**:
```python
result = await benchmark_query(scm_builder, persona, source, target)
```

---

## Expected Benchmark Changes After Fix

### Before (Current Broken Benchmark):
```
✅ Sarah Chen: 1 path (PM2.5 → CRP direct)
✅ James Park: 0 paths (no APOB → BDNF direct)
✅ Maria Garcia: 0 paths (no IL1B → IL6 direct)
✅ David Kim: 1 path (NAD → SIRT1 direct)
✅ Linda Zhang: 1 path (ESR1 → COL1A1 direct)

Result: 3/5 found paths, 2/5 failed
Passes: ✅ (no correctness validation)
```

### After (Fixed Production-Matching Benchmark):
```
✅ Sarah Chen: 1+ paths (PM2.5 → CRP, may find via IL6 too)
✅ James Park: 1+ paths (APOB → ? → BDNF via mediators)
✅ Maria Garcia: 1+ paths (IL1B → NFKB1 → IL6)
✅ David Kim: 1+ paths (NAD → SIRT1, may find via SIRT3)
✅ Linda Zhang: 1+ paths (ESR1 → COL1A1, may find via transcription factors)

Result: 5/5 found paths (unless INDRA truly empty)
Latency: May increase 20-30s (mediated search slower)
Memory: Similar (paths are small)
```

### Potential Failures After Fix (GOOD - catches real bugs):

**Scenario**: If `SCMGraphBuilder._find_mediated_paths()` is broken:
```
❌ Maria Garcia: 0 paths (mediator expansion failed)
Benchmark: ❌ FAIL
    Expected: ≥1 path (IL1B → NFKB1 → IL6)
    Actual: 0 paths

Developer: "Test caught mediator bug! Fix before ship."
```

This is CORRECT behavior - test should fail when production code breaks.

---

## Non-Negotiables

### Must Have:
1. ✅ Benchmark uses `SCMGraphBuilder.build_scm_graph()`
2. ✅ Benchmark tests Phase 2 mediated discovery
3. ✅ Benchmark tests Phase 3 prior fallback
4. ✅ Failures cause test to fail (not pass with 0 paths)

### Must NOT Have:
1. ❌ Benchmark using `IndraNetService` directly
2. ❌ Tests passing with 0 paths for known pathways
3. ❌ Different code paths in test vs production

---

## Verification Checklist

After fix applied, verify:

```bash
# 1. Check imports
grep "from.*SCMGraphBuilder" tests/test_phase_2_4_benchmark.py
# Should find: from indra_agent.services.scm_graph_builder import SCMGraphBuilder

# 2. Check initialization
grep "scm_builder = SCMGraphBuilder" tests/test_phase_2_4_benchmark.py
# Should find: scm_builder = SCMGraphBuilder(indra_service)

# 3. Check function signature
grep "async def benchmark_query" tests/test_phase_2_4_benchmark.py -A 5
# Should find: scm_builder: SCMGraphBuilder (not service: IndraNetService)

# 4. Check function call
grep "scm_builder.build_scm_graph" tests/test_phase_2_4_benchmark.py
# Should find: await scm_builder.build_scm_graph(...)

# 5. Run benchmark
uv run python tests/test_phase_2_4_benchmark.py

# Expected: IL1B → IL6 NOW FINDS PATHS (if mediators working)
```

---

## Timeline

### Immediate (< 1 hour):
- [ ] Update `test_phase_2_4_benchmark.py` imports
- [ ] Change function signature
- [ ] Update initialization
- [ ] Run benchmark, verify IL1B → IL6 finds paths

### Validation (< 1 day):
- [ ] Add assertion: IL1B → IL6 must find ≥1 path
- [ ] Add assertion: Paths must contain known mediators
- [ ] Document expected behavior for each persona

### Continuous:
- [ ] Monitor: Benchmark latency may increase (mediated search slower)
- [ ] Accept: This is CORRECT - we're testing real production behavior
- [ ] Never: Go back to fast-but-wrong IndraNetService-only testing

---

## Summary

**Problem**: Benchmark tests fast path (direct only), production uses slow path (multi-hop)

**Impact**: Production can break while tests pass

**Fix**: Benchmark must call `SCMGraphBuilder.build_scm_graph()` (matches production)

**Verification**: IL1B → IL6 should find paths after fix (via NFKB1 mediator)

**Non-Negotiable**: Cannot ship while test and production code paths diverge

**Status**: SHIP BLOCKER - fix before any production deployment
