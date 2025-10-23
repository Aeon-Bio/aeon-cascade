# Aeon Cascade Frontend - Complete Implementation Plan

## Executive Summary

**Current State**: The frontend is a basic demo that only calls `/api/v1/causal_discovery` and displays static results.

**Backend Power**: We have built a full-featured SCM inference system with temporal predictions, intervention planning, graph validation, and data parsers - **none of which are exposed in the UI**.

**Gap**: 20+ implemented backend features are unused, representing 80% of the system's value.

---

## Critical Missing Features (Prioritized)

### 🔴 **PRIORITY 1: Intervention Planning (The Core Value Prop)**

**Status**: ❌ Endpoint exists (`/api/v1/intervene`) but frontend never calls it

**What's Missing**:
1. Graph ID persistence (`graph-{request_id}` from causal_discovery response)
2. Intervention UI: Node selection + target value input
3. API call to `/api/v1/intervene` with InterventionRequest
4. Display intervention results:
   - Baseline vs. post-intervention predictions
   - Affected pathways with total effect sizes
   - Timeline visualization (3 months, 6 months, 12 months)

**Implementation**:
```typescript
// +page.svelte
let currentGraphId = $state<string | null>(null);
let interventionResult = $state<InterventionResponse | null>(null);

// After causal_discovery success:
currentGraphId = `graph-${response.request_id}`;

// In InterventionPlanner.svelte:
async function runIntervention(nodeId: string, targetValue: number) {
  const request: InterventionRequest = {
    request_id: crypto.randomUUID(),
    graph_id: currentGraphId!,
    intervention: { node_id: nodeId, value: targetValue },
    target_biomarkers: $selectedPersona.keyBiomarkers,
    horizon_days: 90,
    confidence_level: 0.95
  };

  const result = await performIntervention(request);
  interventionResult = result;
}
```

**UI Components Needed**:
- InterventionSelector: Dropdown of graph nodes + number input for target value
- InterventionResults: Table showing baseline → post-intervention deltas
- PathwayExplorer: Visual display of affected pathways with effect sizes
- TimelineChart: Line graph showing biomarker trajectories over 90 days

**Estimated Effort**: 4-6 hours

---

### 🔴 **PRIORITY 2: Temporal Predictions from Backend SCM**

**Status**: ❌ Frontend duplicates temporal logic in JavaScript; backend SCM engine unused

**What's Missing**:
1. Backend temporal predictions are computed during `/api/v1/intervene` but not exposed separately
2. Frontend `TemporalPrediction.svelte` uses hardcoded formulas instead of calling backend
3. No visualization of confidence intervals or Monte Carlo distributions

**Backend Already Has**:
- `TemporalModelEngine` (Monte Carlo simulation, 1000 iterations)
- `SCMInferenceEngine` (closed-form Gaussian SCM with analytical solutions)
- Risk stratification (low/moderate/high risk levels)
- Genetic modifier application in predictions

**Implementation**:
```typescript
// Option A: Use intervention endpoint with baseline (do-nothing) intervention
const baselinePrediction = await performIntervention({
  request_id: crypto.randomUUID(),
  graph_id: currentGraphId!,
  intervention: { node_id: 'PM2.5', value: currentPersona.locationHistory[0].avgPM25 },
  target_biomarkers: ['CRP', 'IL-6', 'HbA1c'],
  horizon_days: 365
});

// Option B: Create new endpoint /api/v1/predict for baseline predictions
```

**UI Components**:
- PredictionTimeline: Multi-line chart with confidence bands
- RiskStratification: Color-coded risk levels for each biomarker
- GeneticModifierDisplay: Show how genetic variants amplify/attenuate predictions

**Estimated Effort**: 3-4 hours

---

### 🟡 **PRIORITY 3: Graph Analysis Features**

**Status**: ❌ Backend has full graph analysis services; frontend duplicates in JavaScript

**What's Missing**:
1. **Convergent Nodes**: Backend identifies nodes with ≥2 incoming edges (high-value targets)
2. **Feedback Loops**: Backend detects cycles (e.g., inflammation ↔ insulin resistance)
3. **Pathway Finding**: Backend finds all paths source → target with total effect sizes
4. **Synergy Scoring**: Backend computes multi-target synergy scores

**Current Implementation**:
- Frontend's `InterventionPlanner.svelte:47-81` duplicates convergent node logic
- No display of feedback loops
- No pathway exploration beyond what's in `key_insights`

**Backend Services Available**:
- `GraphAnalysisService.find_convergent_nodes()` (lines 20-66)
- `GraphAnalysisService.detect_feedback_loops()` (lines 68-147)
- `GraphAnalysisService.find_pathways()` (lines 149-211)
- `GraphAnalysisService.compute_multi_target_synergy()` (lines 213-303)

**Implementation Options**:
1. **Expose via new endpoint**: `POST /api/v1/graph/analyze` (preferred)
2. **Include in causal_discovery response**: Add `feedback_loops`, `convergent_nodes`, `synergy_scores`

**UI Components**:
- FeedbackLoopDisplay: Circular graph highlighting cycles with amplification factors
- ConvergentNodeExplorer: Table/cards showing integration points + incoming sources
- SynergyMatrix: Heatmap showing multi-target intervention synergy scores

**Estimated Effort**: 4-5 hours

---

### 🟡 **PRIORITY 4: Data Upload Pipeline**

**Status**: ❌ Parsers exist for VCF/labs/environmental data but no upload endpoints

**What's Missing**:
1. File upload UI (drag-drop or file picker)
2. Backend endpoints accepting files:
   - `POST /api/v1/upload/vcf`
   - `POST /api/v1/upload/lab_report`
   - `POST /api/v1/upload/environmental`
3. Parser integration in routes (currently parsers are standalone services)
4. User data persistence (currently hardcoded personas)

**Backend Parsers Ready**:
- `VCFParser` (parses 23andMe, Ancestry.com VCF files)
- `LabParser` (parses Quest/LabCorp text reports)
- `EnvironmentalParser` (parses JSON with PM2.5 timeseries)

**Implementation**:
```python
# In routes.py
@router.post("/api/v1/upload/vcf")
async def upload_vcf(file: UploadFile):
    content = await file.read()
    parser = VCFParser()
    variants = parser.parse_vcf(content.decode('utf-8'))
    return {"user_id": user_id, "variants": variants, "count": len(variants)}

@router.post("/api/v1/upload/lab_report")
async def upload_lab_report(file: UploadFile):
    content = await file.read()
    parser = LabParser()
    report = parser.parse_lab_report(content.decode('utf-8'))
    return {"biomarkers": report.biomarkers, "date": report.collection_date}
```

**Frontend**:
```svelte
<!-- FileUploader.svelte -->
<input type="file" accept=".vcf,.txt,.json" on:change={handleFileUpload} />

<script>
async function handleFileUpload(event) {
  const file = event.target.files[0];
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/v1/upload/vcf', {
    method: 'POST',
    body: formData
  });

  const data = await response.json();
  // Update persona with parsed data
}
</script>
```

**Estimated Effort**: 6-8 hours

---

### 🟡 **PRIORITY 5: Graph Validation & Auto-Fix**

**Status**: ❌ ValidationAgent exists but never called; invalid graphs could crash SCM inference

**What's Missing**:
1. Graph validation after causal_discovery (before displaying)
2. Auto-fix violations (cycles, invalid parameters, unstable graphs)
3. UI to show validation warnings/errors
4. Manual override for users to accept/reject auto-fixes

**Backend Ready**:
- `ValidationAgent` (comprehensive checks)
- `fix_violations()` (auto-repair)

**Implementation**:
```python
# In routes.py after causal discovery
if isinstance(response, CausalDiscoveryResponse):
    # Validate graph
    validator = ValidationAgent()
    violations = validator.validate_graph(response.causal_graph)

    if violations:
        # Auto-fix
        fixed_graph = validator.fix_violations(response.causal_graph, violations)
        response.causal_graph = fixed_graph
        response.metadata = {
            "violations_found": len(violations),
            "auto_fixed": True
        }
```

**Frontend**:
```svelte
{#if response.metadata?.violations_found}
  <div class="warning-banner">
    ⚠️ Graph had {response.metadata.violations_found} issues (auto-fixed)
    <button on:click={showDetails}>View Details</button>
  </div>
{/if}
```

**Estimated Effort**: 2-3 hours

---

### 🟢 **PRIORITY 6: Temporal Dependencies Visualization**

**Status**: ❌ No display of temporal lag information from causal edges

**What's in Backend**:
- Each `CausalEdge` has `temporal_lag_hours` (e.g., PM2.5 → IL-6: 12 hours)
- Based on biological mechanism type (Phosphorylation: 1h, Transcription: 6h, etc.)

**What's Missing**:
- Timeline view showing cascade of events
- Sankey diagram with temporal annotations
- "What happens when?" narrative

**Implementation**:
```svelte
<!-- TemporalCascade.svelte -->
<div class="timeline">
  {#each sortedEdges as edge, i}
    <div class="event" style="left: {edge.cumulative_lag}px">
      <strong>T+{edge.cumulative_lag}h:</strong>
      {edge.source} → {edge.target}
      <span class="mechanism">{edge.mechanism}</span>
    </div>
  {/each}
</div>

<script>
// Sort edges by cumulative temporal lag
const sortedEdges = computeTemporalOrder($causalGraph.edges);
</script>
```

**Estimated Effort**: 3-4 hours

---

## Architecture Fixes (Critical)

### 1. **State Management Refactor**

**Problem**: Global `writable` stores create invisible dependencies

**Solution**: Domain-specific stores
```typescript
// lib/stores/causalDiscovery.ts
export const causalDiscoveryStore = () => {
  const { subscribe, set, update } = writable({
    graph: null,
    graphId: null,
    requestId: null,
    insights: [],
    isLoading: false,
    error: null
  });

  return {
    subscribe,
    async query(request) { /* orchestrate API call */ },
    reset() { set(initialState) }
  };
};

// lib/stores/intervention.ts
export const interventionStore = () => {
  const { subscribe, set } = writable({
    result: null,
    isLoading: false,
    error: null
  });

  return {
    subscribe,
    async intervene(graphId, intervention) { /* call API */ }
  };
};
```

### 2. **Lazy Loading**

**Problem**: Cytoscape.js (500KB) loaded on initial bundle

**Solution**:
```svelte
<!-- CausalGraph.svelte -->
<script>
  import { onMount } from 'svelte';

  let cytoscape;

  onMount(async () => {
    // Dynamic import
    const cytoscapeModule = await import('cytoscape');
    cytoscape = cytoscapeModule.default;
    renderGraph();
  });
</script>
```

### 3. **Environment Variables**

**Problem**: API URLs hardcoded

**Solution**:
```typescript
// lib/api/config.ts
import { PUBLIC_API_BASE_URL } from '$env/static/public';

export const API_BASE = PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1';
```

```bash
# .env.production
PUBLIC_API_BASE_URL=https://api.aeoncascade.com/api/v1
```

---

## Implementation Roadmap

### Week 1: Core Functionality
- [ ] Day 1-2: Wire up `/api/v1/intervene` endpoint (Priority 1)
- [ ] Day 3: Implement intervention UI with node selector
- [ ] Day 4-5: Build intervention results display with timeline charts

### Week 2: Advanced Features
- [ ] Day 6-7: Integrate backend temporal predictions (Priority 2)
- [ ] Day 8: Add graph analysis features (Priority 3)
- [ ] Day 9-10: Build feedback loop and pathway visualizations

### Week 3: Data Pipeline & Polish
- [ ] Day 11-12: Implement file upload endpoints and parsers (Priority 4)
- [ ] Day 13: Add graph validation UI (Priority 5)
- [ ] Day 14: Build temporal cascade visualization (Priority 6)
- [ ] Day 15: Architecture refactoring (state management, lazy loading)

### Week 4: Testing & Deployment
- [ ] Day 16-17: End-to-end testing with all 6 personas
- [ ] Day 18: Performance optimization and bundle size reduction
- [ ] Day 19: Security hardening (auth, env vars, CORS)
- [ ] Day 20: Production deployment and monitoring

---

## Success Metrics

### Before (Current State)
- ❌ 1 API endpoint used (`/api/v1/causal_discovery`)
- ❌ 0 interventions tested
- ❌ 0 temporal predictions from backend
- ❌ 0 file uploads supported
- ❌ Hardcoded persona data only
- ❌ No graph validation
- ❌ No feedback loop detection
- ❌ Static UI (no interactivity beyond query submission)

### After (Fully Implemented)
- ✅ 2+ API endpoints used (`/causal_discovery`, `/intervene`, `/graph/analyze`)
- ✅ Real-time intervention planning with SCM do-calculus
- ✅ Temporal predictions with confidence intervals (90-day horizon)
- ✅ File upload for VCF, lab reports, environmental data
- ✅ User-provided data (not just personas)
- ✅ Automatic graph validation and repair
- ✅ Feedback loop highlighting
- ✅ Interactive graph exploration with pathway tracing
- ✅ Timeline visualization showing temporal cascade
- ✅ Production-ready architecture (env vars, lazy loading, domain stores)

---

## Estimated Total Effort

**Engineering Time**: 80-100 hours (4-5 weeks at 20h/week)

**Team Composition**:
- 1x Frontend Engineer (Svelte/TypeScript)
- 1x Backend Engineer (FastAPI/Python)
- 0.5x UX Designer (intervention UI, timeline charts)

**Dependencies**:
- Chart.js or Plotly.js for timeline visualizations
- File upload library (FilePond or similar)
- Authentication system (if production)

---

## Quick Wins (Can Implement Today)

1. **Store graph_id in +page.svelte** (5 minutes)
2. **Add intervention API call function** (10 minutes)
3. **Create basic InterventionSelector UI** (30 minutes)
4. **Display intervention results table** (1 hour)

Start with these and you'll have a working intervention demo in < 2 hours.
