# Path A Implementation - Codebase Cleanup Audit

**Date**: 2025-01-22
**Context**: Transitioned from fake quantitative predictions (Path of Shame) to Path A (Qualitative Causal Hypothesis Explorer)

## ✅ Clean - No Action Needed

### Backend
- ✅ `indra_agent/agents/supervisor.py` - Already updated to use InsightGenerator
- ✅ `indra_agent/core/insights.py` - New, clean Path A models
- ✅ `indra_agent/services/insight_generator.py` - New, clean service
- ✅ No imports of `temporal_model` anywhere in active code

### Frontend
- ✅ `frontend/src/lib/components/CausalInsights.svelte` - New, clean component
- ✅ `frontend/src/routes/+page.svelte` - Updated to use insights instead of predictions
- ✅ No references to `TemporalPrediction` component in active code

### Tests
- ✅ No test files explicitly for temporal predictions
- ✅ No assertions on `predictions` field found in main tests

## ⚠️ Needs Cleanup - Optional Removal (Non-Breaking)

### Backend - Unused Code (Can be safely removed)

1. **`indra_agent/services/temporal_model.py`**
   - Status: Orphaned - No imports found
   - Action: DELETE (not used by Path A)
   - Impact: None (dead code)

2. **`indra_agent/core/models.py` - Lines 133-162**
   - `PredictionTimeline` class (unused in CausalDiscoveryResponse)
   - Action: DELETE or mark as deprecated
   - Impact: Only used in InterventionResponse (separate API), keep for now

### Frontend - Unused Components

3. **`frontend/src/lib/components/TemporalPrediction.svelte`**
   - Status: Orphaned - No references in active code
   - Action: DELETE (not used by Path A)
   - Impact: None (dead code)

### Services - Old Intervention/SCM Code

4. **SCM-related services** (if intervention API not used):
   - `indra_agent/services/scm_graph_builder.py`
   - `indra_agent/services/scm_inference.py`
   - `indra_agent/services/graph_analysis.py`
   - Status: Used by intervention API (/api/v1/intervene)
   - Action: KEEP for now (separate feature from causal discovery)
   - Note: Intervention API still uses quantitative predictions - may need Path A treatment later

## 🔴 Needs Update - Documentation Inconsistencies

### Main Documentation

5. **README.md** - Line 7
   - Issue: "predictions come with confidence intervals derived from mathematical foundations"
   - Should say: "generates evidence-based hypotheses with categorical strength ratings"
   - Action: UPDATE

6. **CLAUDE.md** - Line 647
   - Issue: "`effect_size` MUST be ∈ [0, 1] (used for Monte Carlo weights)"
   - Still valid for graph edges, but Monte Carlo no longer used
   - Action: UPDATE comment to clarify effect_size is for graph structure, not predictions

### Implementation Docs

7. **docs/PROGRESS_IMPLEMENTATION_STATUS.md**
   - References "Generate temporal predictions" in step descriptions
   - Action: UPDATE to reflect Path A (qualitative insights)

8. **docs/REALTIME_PROGRESS_TRACKING.md**
   - Step 14 mentions "Running Monte Carlo simulations"
   - Action: UPDATE to "Generating evidence-based insights" or similar

9. **docs/mathematical-foundation.md**
   - Entire document about SCM math that we no longer use for causal discovery predictions
   - Action: ✅ COMPLETED - Added disclaimer at top explaining this is for intervention API only, not causal discovery

10. **docs/ENGINEERING_PLAN_PRINCIPLED_IMPLEMENTATION.md**
    - References temporal prediction models
    - Action: ARCHIVE or UPDATE with Path A approach

## 📋 Recommended Cleanup Order

### Priority 1: Documentation (User-Facing)
1. Update README.md with Path A description
2. Update CLAUDE.md to clarify effect_size usage
3. Add disclaimer to mathematical-foundation.md

### Priority 2: Dead Code Removal (Non-Breaking)
4. Delete `indra_agent/services/temporal_model.py`
5. Delete `frontend/src/lib/components/TemporalPrediction.svelte`

### Priority 3: Implementation Docs
6. Update progress tracking docs to reflect Path A
7. Archive or update engineering plans

### Priority 4: Future Consideration
8. Decide if intervention API needs Path A treatment
9. Consider deprecating PredictionTimeline if intervention API updated

## Notes on Intervention API

The intervention API (`/api/v1/intervene`) still uses:
- `BiomarkerPrediction` with confidence intervals
- `InterventionResponse` with quantitative predictions
- SCM inference for do-calculus

**Decision**: Keep for now as separate feature. May need Path A treatment in future if scientific validity concerns apply equally to interventions.

## Files Changed in Path A Implementation

**Created**:
- `indra_agent/core/insights.py`
- `indra_agent/services/insight_generator.py`
- `frontend/src/lib/components/CausalInsights.svelte`
- `docs/ADDRESSING_BRUTALIST_CRITIQUE.md`

**Modified**:
- `indra_agent/agents/supervisor.py` (removed _generate_predictions)
- `indra_agent/core/models.py` (predictions → insights)
- `frontend/src/routes/+page.svelte` (TemporalPrediction → CausalInsights)

**Deleted** (pending):
- None yet

## Summary

**Clean State**:
- Core Path A implementation is clean and consistent
- No active code imports or uses old prediction system
- Tests don't assert on predictions field

**Minor Cleanup Needed**:
- 2 dead code files can be deleted
- Documentation needs updates to reflect Path A
- Implementation docs reference old approach

**Impact**: Low - mostly documentation and dead code cleanup. No breaking changes.
