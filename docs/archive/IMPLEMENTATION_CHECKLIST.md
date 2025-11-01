# Implementation Checklist: MDL-Based Causal Path Discovery

## Phase 1: Core Algorithm (2-3 hours) ⚡ START HERE

### 1.1 Create MDL Weight Module
- [ ] File: `indra_agent/services/mdl_weight.py`
- [ ] Function: `compute_mdl_weight(graph, src, tgt, biomarker_values=None)`
- [ ] Tests: Unit tests for edge cases (zero belief, high evidence)
- **Estimated**: 30 min

### 1.2 Integrate INDRA Pathfinding
- [ ] File: `indra_agent/services/indranet_service.py`
- [ ] Replace: `nx.all_simple_paths` → `indra.explanation.pathfinding.shortest_simple_paths`
- [ ] Method: Update `_convert_graph_to_paths()` to use INDRA pathfinding
- [ ] Pass MDL weight function to INDRA pathfinder
- **Estimated**: 45 min

### 1.3 Add Hub-Aware Heuristic
- [ ] File: `indra_agent/services/mdl_weight.py`
- [ ] Function: `hub_bonus(node: str) -> float`
- [ ] Dict: `CAUSAL_HUBS` with 16 major biological hubs
- [ ] Integration: Add hub bonus to MDL cost calculation
- **Estimated**: 20 min

### 1.4 Test on Sarah Chen Scenario
- [ ] File: `tests/test_mdl_paths.py`
- [ ] Test: PM2.5 → CRP (should find path through NF-κB, IL-6)
- [ ] Test: PM2.5 → IL-6 (shorter path, should rank higher)
- [ ] Verify: MDL scores are lower for shorter, high-belief paths
- **Estimated**: 45 min

**Phase 1 Total: 2.5 hours**

---

## Phase 2: Uncertainty Quantification (2-3 hours)

### 2.1 Implement Belief Propagation
- [ ] File: `indra_agent/services/belief_propagation.py`
- [ ] Function: `belief_propagation(path, biomarker_values, graph, max_iterations=10)`
- [ ] Returns: Dict[str, float] (marginal probabilities for each node)
- **Estimated**: 60 min

### 2.2 Compute Marginal Probabilities
- [ ] File: `indra_agent/services/indranet_service.py`
- [ ] Method: Add `_compute_path_uncertainty()` to IndraNetService
- [ ] Call BP on each path returned from A*
- [ ] Store marginals in path metadata
- **Estimated**: 30 min

### 2.3 Add Confidence Intervals to API
- [ ] File: `indra_agent/core/models.py`
- [ ] Model: Add `uncertainty` field to CausalEdge
- [ ] Model: Add `marginal_probabilities` to CausalGraph
- [ ] Update API response schema
- **Estimated**: 30 min

### 2.4 Visualize Uncertainty in Frontend
- [ ] File: `aeon_cascade_frontend/src/components/CausalGraph.svelte`
- [ ] Add: Error bars on biomarker predictions
- [ ] Add: Confidence scores on edges (opacity/color)
- [ ] Add: Tooltip showing marginal probability
- **Estimated**: 45 min

**Phase 2 Total: 2.5 hours**

---

## Phase 3: Multi-Objective Optimization (1-2 hours)

### 3.1 Implement Pareto Ranking
- [ ] File: `indra_agent/services/pareto.py`
- [ ] Function: `compute_pareto_frontier(solutions, objectives, directions)`
- [ ] Returns: List of non-dominated paths
- **Estimated**: 30 min

### 3.2 Define Objective Functions
- [ ] File: `indra_agent/services/mdl_weight.py`
- [ ] Add: `compute_path_objectives(path, graph, biomarker_values)`
- [ ] Objectives: MDL score, belief score, length, total evidence
- [ ] Normalization: Scale each objective to [0, 1]
- **Estimated**: 20 min

### 3.3 Return Pareto Frontier to User
- [ ] File: `indra_agent/services/indranet_service.py`
- [ ] Method: Update `find_causal_paths()` to return Pareto-ranked paths
- [ ] Sort by: Weighted combination of objectives (user-configurable)
- **Estimated**: 20 min

### 3.4 Add UI for Trade-off Exploration
- [ ] File: `aeon_cascade_frontend/src/components/PathExplorer.svelte`
- [ ] Add: Slider for MDL vs Belief trade-off
- [ ] Add: Path comparison table (side-by-side)
- [ ] Add: Pareto frontier visualization (scatter plot)
- **Estimated**: 45 min

**Phase 3 Total: 2 hours**

---

## Phase 4: Biomarker Panel Integration (2-3 hours)

### 4.1 Add Biomarker Grounding
- [ ] File: `indra_agent/services/grounding_service.py`
- [ ] Update: `BIOMARKER_GROUNDING` dict with 64 biomarkers
- [ ] Add: Quest/LabCorp test codes
- [ ] Add: INDRA entity mappings (HGNC, MESH, CHEBI)
- **Estimated**: 30 min

### 4.2 Define Persona Panels
- [ ] File: `indra_agent/config/biomarker_panels.py`
- [ ] Panels: Sarah Chen, James Park, Maria Garcia, David Kim, Linda Zhang
- [ ] Structure: `{persona: {tier1: [...], tier2: [...], tier3: [...]}}`
- [ ] Include: Test codes, normal ranges, clinical significance
- **Estimated**: 45 min

### 4.3 Update Frontend Persona Selection
- [ ] File: `aeon_cascade_frontend/src/lib/personas.ts`
- [ ] Add: Biomarker panel details to each persona
- [ ] Add: Tier selection UI (checkboxes for tier 2/3)
- [ ] Add: Cost estimation ($150-600 range)
- **Estimated**: 45 min

### 4.4 Connect Panels to Causal Pathways
- [ ] File: `indra_agent/core/client.py`
- [ ] Update: `process_request()` to auto-populate biomarkers from persona
- [ ] Logic: If user selects Sarah Chen → load inflammatory + metabolic biomarkers
- [ ] API: Pass biomarker panel to path discovery
- **Estimated**: 30 min

**Phase 4 Total: 2.5 hours**

---

## Testing & Validation (1-2 hours)

### End-to-End Tests
- [ ] Test: Sarah Chen scenario (PM2.5 → CRP, IL-6, HbA1c)
  - Expected: 3-5 paths through NF-κB, JNK
  - Expected: MDL prefers shorter path (PM2.5 → IL-6 → CRP)
  - Expected: Uncertainty quantified for each biomarker

- [ ] Test: James Park scenario (Hypertension → BDNF, Amyloid-β)
  - Expected: Paths through endothelial dysfunction
  - Expected: BBB breakdown shown with uncertainty

- [ ] Test: Multi-biomarker query (50 biomarkers)
  - Expected: <2 second response time
  - Expected: Top 100 Pareto-optimal paths
  - Expected: Memory <100 MB

### Performance Benchmarks
- [ ] Measure: Latency (target <2s for 90th percentile)
- [ ] Measure: Memory usage (target <100 MB)
- [ ] Measure: Path quality (target >90% match curated paths)
- [ ] Compare: MDL vs naive ranking (MDL should prefer shorter, high-belief)

---

## Rollout Plan

### Step 1: Backend Implementation (Phases 1-3)
**Timeline**: Day 1-2
- Implement MDL algorithm
- Test with Sarah Chen
- Validate performance

### Step 2: Biomarker Panels (Phase 4)
**Timeline**: Day 2-3
- Add all 5 persona panels
- Ground to INDRA
- Test end-to-end

### Step 3: Frontend Integration
**Timeline**: Day 3-4
- Uncertainty visualization
- Pareto frontier UI
- Persona panel selector

### Step 4: Production Deploy
**Timeline**: Day 4-5
- Load testing
- Documentation
- Deploy to prod

---

## Success Metrics

### Correctness
- ✅ Parsimonious paths: Shorter paths rank higher for same targets
- ✅ Hub preference: Paths through NF-κB, MAPK rank higher
- ✅ Evidence weighting: High-evidence edges preferred

### Performance
- ✅ Latency <2s for 90% of queries (50 biomarkers)
- ✅ Memory <100 MB per query
- ✅ 30-120× speedup vs naive enumeration

### Clinical Validity
- ✅ 90%+ agreement with curated pathways (Drug2ways benchmark)
- ✅ Uncertainty quantification for clinical decision support
- ✅ All biomarkers orderable from Quest/LabCorp

---

## Current Status

**Completed**:
- ✅ Theoretical design (MDL + A* + Belief Propagation)
- ✅ Research validation (Drug2ways, INDRA explanation module)
- ✅ Biomarker panel design (64 biomarkers, 5 personas)
- ✅ Documentation (CAUSAL_PATH_ALGORITHM_DESIGN.md, BIOMARKER_PANELS.md)

**In Progress**:
- 🚧 Phase 1: Core MDL algorithm implementation

**Next**:
- ⏳ Create `indra_agent/services/mdl_weight.py`
- ⏳ Update `indranet_service.py` to use INDRA pathfinding
- ⏳ Test on Sarah Chen scenario

---

**Ready to begin implementation!**
