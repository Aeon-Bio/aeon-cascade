# Agent-Driven Graph Construction FSM Architecture

**Version**: 1.0
**Date**: October 2025
**Status**: Specification

## Overview

This document specifies the **Finite State Machine (FSM) architecture** for agent-driven causal graph construction. The system uses LLM agents to automatically discover, validate, and refine causal relationships by integrating three knowledge sources:

1. **INDRA Bio-Ontology**: Literature-backed causal pathways (3.8M+ statements from PubMed)
2. **Writer Knowledge Graph (MeSH)**: Medical Subject Headings ontology for semantic enrichment
3. **Research Literature**: Dynamic web search for emerging pathways

The FSM ensures **systematic exploration** of biological mechanisms, **validation** of causal claims, and **refinement** to optimal graph topology for SCM inference.

---

## Design Principles

### 1. Systematic Discovery
- Start from **high-confidence anchors** (known exposures → known biomarkers)
- Expand via **ontology traversal** (MeSH broader/narrower terms)
- Validate via **evidence triangulation** (INDRA + literature)

### 2. Brittleness Avoidance
- Only include **identifiable** causal edges (see `mathematical-foundation.md` §3)
- Require **minimum evidence threshold** (≥10 papers or belief ≥0.6)
- Prefer **direct mechanisms** over multi-hop speculation

### 3. Engineering Practicality
- **Deterministic transitions** (no stochastic routing)
- **Timeout safeguards** (max 5s per state, 30s total)
- **Graceful degradation** (return partial graph if agent fails)

---

## FSM States

### State 0: INIT
**Purpose**: Parse user query and extract seed entities
**Agent**: Supervisor
**Input**: `CausalDiscoveryRequest` with query text and user context
**Output**: `seed_entities: List[SeedEntity]`

**Operations**:
1. LLM extracts biomarkers, exposures, conditions from query
2. Classify entity types: `environmental`, `biomarker`, `condition`, `intervention`
3. Validate entities exist in INDRA namespace (HGNC, MESH, CHEBI)

**Transition Conditions**:
- `len(seed_entities) ≥ 2` → State 1 (MESH_ENRICHMENT)
- `len(seed_entities) == 1` → State 1 (expand to find targets)
- `len(seed_entities) == 0` → State ERROR (invalid query)

**Example**:
```python
# Input query: "How does PM2.5 affect CRP in people with GSTM1 variants?"
seed_entities = [
    SeedEntity(name="PM2.5", type="environmental", mesh_id="D052638"),
    SeedEntity(name="CRP", type="biomarker", hgnc_id="HGNC:2367"),
    SeedEntity(name="GSTM1", type="genetic", hgnc_id="HGNC:4425")
]
```

**Timeout**: 3s (LLM call + grounding lookups)

---

### State 1: MESH_ENRICHMENT
**Purpose**: Expand seed entities using MeSH ontology to discover related pathways
**Agent**: MeSH Enrichment Agent (new)
**Input**: `seed_entities`
**Output**: `enriched_entities: List[EnrichedEntity]`

**Operations**:
1. For each seed entity, query Writer KG:
   - **Synonyms**: Alternative terms (e.g., "C-reactive protein" → "CRP")
   - **Broader terms**: Parent concepts (e.g., "CRP" → "Acute-phase proteins")
   - **Narrower terms**: Specific instances (e.g., "PM2.5" → "Diesel exhaust particles")
   - **Related terms**: Semantic neighbors (e.g., "oxidative stress" near "PM2.5")

2. Filter enriched entities by relevance:
   - Keep if ≥2 semantic hops from seed entities
   - Discard if unrelated to query domain (e.g., "bone density" for inflammation query)

3. Prioritize entities for pathway search:
   - **Priority 1**: Direct seed entities (user-specified)
   - **Priority 2**: Narrower terms (more specific)
   - **Priority 3**: Related mechanistic terms (oxidative stress, NF-κB)
   - **Priority 4**: Broader terms (less specific, used as fallback)

**Transition Conditions**:
- `len(enriched_entities) > 0` → State 2 (INDRA_QUERY)
- `len(enriched_entities) == 0` → Skip to State 2 with seed entities only

**Example**:
```python
# Input: seed_entities = [PM2.5, CRP]
# Writer KG queries:
enriched_entities = [
    # Seed entities (Priority 1)
    EnrichedEntity(name="PM2.5", mesh_id="D052638", priority=1),
    EnrichedEntity(name="CRP", hgnc_id="HGNC:2367", priority=1),

    # Related mechanistic terms (Priority 3)
    EnrichedEntity(name="NF-κB", hgnc_id="HGNC:7794", priority=3, source="related_to_PM2.5"),
    EnrichedEntity(name="oxidative stress", mesh_id="D018384", priority=3, source="related_to_PM2.5"),
    EnrichedEntity(name="IL-6", hgnc_id="HGNC:6018", priority=3, source="broader_than_CRP"),

    # Narrower terms (Priority 2)
    EnrichedEntity(name="hs-CRP", mesh_id="D002097", priority=2, source="narrower_than_CRP")
]
```

**Timeout**: 5s (multiple Writer KG API calls)

---

### State 2: INDRA_QUERY
**Purpose**: Discover causal pathways from literature using INDRA Network Search
**Agent**: INDRA Query Agent
**Input**: `enriched_entities`
**Output**: `indra_paths: List[CausalPath]`

**Operations**:
1. **Direct path search**: For each (source, target) pair in enriched entities:
   - Query INDRA `/api/query` with `NetworkSearchQuery`
   - Parameters: `depth_limit=4`, `weighted="belief"`, `k_shortest=10`
   - Rank paths by: `score = 0.4·evidence_count + 0.3·belief + 0.3·(1/path_length)`

2. **Neighborhood expansion**: If direct paths insufficient (<3 paths found):
   - For Priority 1 entities, query INDRA for **common neighbors**
   - E.g., "What connects PM2.5 and CRP?" → discover IL-6, TNF-α as mediators

3. **Evidence extraction**: For each path, extract:
   - Statement types (Phosphorylation, IncreaseAmount, Activation, Complex)
   - Belief scores (0-1, from INDRA Belief Engine)
   - Evidence counts (number of supporting papers)
   - Publication years (for recency weighting)
   - Databases (PubMed, Reactome, PathwayCommons)

4. **Path filtering**:
   - Discard paths with belief <0.5 (low confidence)
   - Discard paths with <5 papers (insufficient evidence)
   - Discard paths >4 hops (too speculative)

**Transition Conditions**:
- `len(indra_paths) ≥ 1` → State 3 (GRAPH_CONSTRUCTION)
- `len(indra_paths) == 0 AND location_history present` → State 2b (WEB_RESEARCHER)
- `len(indra_paths) == 0 AND no location` → State ERROR (no causal pathway)

**Example**:
```python
# INDRA query: PM2.5 → CRP
indra_paths = [
    CausalPath(
        nodes=["PM2.5", "oxidative_stress", "NF-κB", "IL-6", "CRP"],
        edges=[
            Edge(source="PM2.5", target="oxidative_stress",
                 belief=0.78, evidence_count=31, stmt_type="IncreaseAmount"),
            Edge(source="oxidative_stress", target="NF-κB",
                 belief=0.82, evidence_count=47, stmt_type="Activation"),
            Edge(source="NF-κB", target="IL-6",
                 belief=0.87, evidence_count=89, stmt_type="IncreaseAmount"),
            Edge(source="IL-6", target="CRP",
                 belief=0.98, evidence_count=312, stmt_type="IncreaseAmount")
        ],
        score=0.4*479 + 0.3*0.86 + 0.3*0.2 = 192.06
    )
]
```

**Timeout**: 10s (multiple INDRA API calls with retry logic)

---

### State 2b: WEB_RESEARCHER (Optional)
**Purpose**: Augment with environmental exposure data if location history available
**Agent**: Web Researcher Agent
**Input**: `user_context.location_history`, `seed_entities`
**Output**: `environmental_data: Dict`

**Operations**:
1. Extract locations from user history (cities, countries, time periods)
2. Query IQAir API or similar for pollution data (PM2.5, NO2, O3)
3. Calculate exposure deltas:
   - Compare current location to reference (e.g., SF baseline)
   - Express as multipliers: `{"PM2.5": 1.8}` means 1.8× increase

4. Augment seed entities with exposure levels

**Transition Conditions**:
- Always → State 3 (GRAPH_CONSTRUCTION)

**Example**:
```python
# Input: location_history = [{"city": "Los Angeles", "start": "2024-01-01", ...}]
environmental_data = {
    "current_location": "Los Angeles",
    "baseline_location": "San Francisco",
    "pollutant_multipliers": {
        "PM2.5": 1.8,  # LA has 1.8× higher PM2.5 than SF
        "NO2": 1.5
    },
    "summary": "Exposure to PM2.5 increased by 80% compared to baseline"
}
```

**Timeout**: 5s (API calls with caching)

---

### State 3: GRAPH_CONSTRUCTION
**Purpose**: Convert INDRA paths to structured causal graph (SCM format)
**Agent**: Graph Builder Service (enhanced)
**Input**: `indra_paths`, `environmental_data`, `user_genetics`
**Output**: `causal_graph: CausalGraph`

**Operations**:
1. **Node creation**:
   - Extract unique entities from all paths
   - Classify node types: `environmental`, `molecular`, `biomarker`, `genetic`
   - Add grounding (HGNC, MESH, CHEBI IDs)

2. **Edge creation**:
   - Merge duplicate edges (same source→target) by averaging belief scores
   - Calculate **effect sizes** from INDRA belief (see formula below)
   - Infer **temporal lags** from statement types (see `mathematical-foundation.md` §7.1)
   - Map relationship types: `IncreaseAmount` → `increases`, `Activation` → `activates`

3. **Effect size formula** (NEW - replaces heuristic):
   ```
   W_ij = min(0.6 · belief + 0.1 · log(1 + evidence_count), 0.95)

   Where:
   - belief ∈ [0, 1] from INDRA Belief Engine
   - evidence_count = number of supporting papers
   - 0.6 weight reflects belief reliability (based on INDRA validation studies)
   - 0.1·log(1+n) captures evidence accumulation (diminishing returns)
   - 0.95 cap prevents deterministic edges (maintain uncertainty)
   ```

4. **Genetic modifier application**:
   - For each user genetic variant (e.g., `GSTM1: null`):
     - Check if variant affects any nodes in graph (via cached modifier table)
     - If yes, apply multiplier to **incoming edges** of affected nodes
     - Example: `GSTM1_null` amplifies oxidative stress by 1.3×
   - Only include modifiers if affected nodes present (avoid spurious genetics)

5. **Environmental node injection**:
   - If `environmental_data` present, add nodes: `PM2.5`, `NO2`, etc.
   - Connect to molecular nodes via INDRA paths (e.g., PM2.5 → oxidative stress)
   - Use exposure multipliers as baseline values for predictions

**Transition Conditions**:
- `len(causal_graph.edges) ≥ 1` → State 4 (VALIDATION)
- `len(causal_graph.edges) == 0` → State ERROR (no relationships found)

**Example**:
```python
# Output causal graph from PM2.5 → CRP query
causal_graph = CausalGraph(
    nodes=[
        Node(id="PM2.5", name="Particulate Matter", type="environmental",
             grounding={"MESH": "D052638"}),
        Node(id="oxidative_stress", name="Oxidative Stress", type="molecular",
             grounding={"MESH": "D018384"}),
        Node(id="NF-κB", name="NF-kappa B", type="molecular",
             grounding={"HGNC": "7794"}),
        Node(id="IL-6", name="Interleukin-6", type="biomarker",
             grounding={"HGNC": "6018"}),
        Node(id="CRP", name="C-Reactive Protein", type="biomarker",
             grounding={"HGNC": "2367"})
    ],
    edges=[
        Edge(source="PM2.5", target="oxidative_stress",
             relationship="increases",
             effect_size=0.6*0.78 + 0.1*log(32) = 0.468 + 0.345 = 0.813,
             temporal_lag_hours=12,  # IncreaseAmount → 12h
             evidence=Evidence(paper_count=31, belief=0.78)),
        Edge(source="oxidative_stress", target="NF-κB",
             relationship="activates",
             effect_size=0.6*0.82 + 0.1*log(48) = 0.492 + 0.387 = 0.879,
             temporal_lag_hours=6,  # Activation → 6h
             evidence=Evidence(paper_count=47, belief=0.82)),
        # ... remaining edges
    ],
    genetic_modifiers=[
        GeneticModifier(
            variant="GSTM1_null",
            affected_nodes=["oxidative_stress"],
            effect_type="amplifies",
            magnitude=1.3,
            evidence="PMID:12345678"
        )
    ]
)
```

**Timeout**: 2s (matrix operations, no API calls)

---

### State 4: VALIDATION
**Purpose**: Verify graph satisfies SCM identifiability and biological constraints
**Agent**: Validation Agent (new)
**Input**: `causal_graph`
**Output**: `validation_result: ValidationResult`

**Operations**:
1. **Structural validation**:
   - Check graph is acyclic (DAG) for identifiability
   - If cycles detected, apply **temporal stratification** (convert to DBN - see §7)
   - Verify all nodes reachable from environmental/genetic root nodes

2. **Parameter validation**:
   - `effect_size ∈ [0, 1]` for all edges (required for SCM inference)
   - `temporal_lag_hours ≥ 0` (causality violation otherwise)
   - Relationship types valid: `activates`, `inhibits`, `increases`, `decreases`

3. **Evidence validation**:
   - All edges have ≥5 papers OR belief ≥0.6
   - No contradictory edges (both `increases` and `decreases` for same pair)
   - Warn if low-evidence edges present (suggest refinement)

4. **Biological plausibility** (soft checks):
   - Environmental → molecular → biomarker ordering preserved
   - Temporal lags increase along causal chain (no time-travel)
   - Effect sizes decay with path length (no amplification cascades)

**Transition Conditions**:
- `validation_result.is_valid == True` → State 5 (REFINEMENT) or State 6 (FINALIZE)
- `validation_result.is_valid == False AND fixable` → State 3 (rebuild with fixes)
- `validation_result.is_valid == False AND unfixable` → State ERROR (return partial graph)

**Example**:
```python
validation_result = ValidationResult(
    is_valid=True,
    warnings=[
        "Edge PM2.5→oxidative_stress has only 31 papers (threshold: 50 for high confidence)"
    ],
    structural_checks={
        "is_dag": True,
        "is_connected": True,
        "has_root_nodes": True  # PM2.5 is root
    },
    parameter_checks={
        "effect_sizes_valid": True,  # all ∈ [0, 1]
        "temporal_lags_valid": True  # all ≥ 0
    },
    biological_plausibility={
        "topological_ordering": True,  # env → molecular → biomarker
        "temporal_consistency": True,  # lags increase along paths
        "effect_decay": True  # no amplification cascades
    }
)
```

**Timeout**: 1s (graph algorithms)

---

### State 5: REFINEMENT (Optional)
**Purpose**: Agent-driven iterative improvement of causal graph
**Agent**: Refinement Agent (new)
**Input**: `causal_graph`, `validation_result`
**Output**: `refined_graph: CausalGraph`

**Operations**:
1. **Gap filling**: If validation warnings suggest missing mechanisms:
   - Identify sparse regions (nodes with <2 incoming edges)
   - Query INDRA for additional incoming paths
   - Example: If IL-6 → CRP has no mediators, search for "What regulates CRP?"

2. **Evidence strengthening**: For low-evidence edges:
   - Query Writer KG for recent literature (2024-2025 papers)
   - Re-query INDRA with relaxed thresholds (`belief_cutoff=0.4`)
   - If still insufficient, mark edge as "speculative" (reduced effect size)

3. **Contradiction resolution**: If contradictory edges found:
   - Query LLM to resolve (e.g., "Does NF-κB activate or inhibit IL-6?")
   - Prioritize higher-belief edge
   - If unresolvable, remove both edges

4. **Pruning**: Remove low-impact nodes:
   - Calculate **betweenness centrality** (how often node appears in paths)
   - Remove nodes with centrality <0.1 AND no direct connection to biomarkers
   - Example: Remove "TNF-α" if it's a side branch with weak evidence

**Transition Conditions**:
- After 1 iteration → State 6 (FINALIZE)
- Max 2 iterations to avoid infinite loops

**Example**:
```python
# Before refinement: PM2.5 → oxidative_stress → NF-κB → IL-6 → CRP
# Refinement discovers: oxidative_stress → IL-6 (direct path, 18 papers, belief 0.71)
# After refinement: Graph now has shortcut edge, improving prediction accuracy
```

**Timeout**: 5s per iteration (INDRA queries + LLM calls)

---

### State 6: FINALIZE
**Purpose**: Generate explanations and metadata for API response
**Agent**: Supervisor
**Input**: `causal_graph`, `validation_result`, `metadata`
**Output**: `CausalDiscoveryResponse`

**Operations**:
1. **Explanation generation** (LLM-driven):
   - Priority 1: Environmental exposure changes (if location history present)
   - Priority 2: Genetic modifiers (if user genetics present)
   - Priority 3: Strongest causal relationship (highest evidence edge)
   - Priority 4: Overall mechanism summary
   - Priority 5: Expected health outcome
   - Constraint: Each explanation <200 chars

2. **Metadata collection**:
   - Query time (from State 0 start)
   - INDRA paths explored
   - Total evidence papers
   - Validation warnings (if any)

3. **Temporal predictions** (if user context available):
   - Build SCM from causal graph (see `mathematical-foundation.md` §2)
   - Run 90-day prediction with Monte Carlo (see `temporal_model.py`)
   - Generate timeline: [Day 0, 30, 60, 90] with confidence intervals

**Transition Conditions**:
- Always → State END (return response)

**Example**:
```python
response = CausalDiscoveryResponse(
    request_id="req_abc123",
    status="success",
    causal_graph=causal_graph,
    explanations=[
        "PM2.5 exposure in LA is 1.8× higher than SF baseline, driving inflammation.",
        "GSTM1_null variant amplifies oxidative stress by 30%, increasing CRP risk.",
        "Strongest pathway: IL-6 → CRP (312 papers, 98% confidence).",
        "Causal chain: PM2.5 → oxidative stress → NF-κB → IL-6 → CRP.",
        "Expected CRP increase: +2.1 mg/L over 90 days if exposure persists."
    ],
    predictions={
        "CRP": PredictionTimeline(
            baseline=1.2,  # mg/L
            timeline=[
                {"day": 0, "mean": 1.2, "ci": [1.0, 1.4], "risk": "low"},
                {"day": 30, "mean": 2.1, "ci": [1.7, 2.6], "risk": "moderate"},
                {"day": 60, "mean": 3.0, "ci": [2.4, 3.8], "risk": "high"},
                {"day": 90, "mean": 3.3, "ci": [2.6, 4.2], "risk": "high"}
            ],
            unit="mg/L"
        )
    },
    metadata=Metadata(
        query_time_ms=4832,
        indra_paths_explored=12,
        total_evidence_papers=479
    )
)
```

**Timeout**: 3s (LLM explanation + prediction computation)

---

## State Transition Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  [INIT] ─(seed_entities)→ [MESH_ENRICHMENT]                   │
│    │                              │                             │
│    │                              ↓                             │
│    │                      [INDRA_QUERY] ←─────────┐            │
│    │                              │                │            │
│    │                              ↓                │            │
│    │                      [WEB_RESEARCHER]         │            │
│    │                       (if location)           │            │
│    │                              │                │            │
│    │                              ↓                │            │
│    └──────────────────────→ [GRAPH_CONSTRUCTION]  │            │
│                                   │                │            │
│                                   ↓                │            │
│                            [VALIDATION]            │            │
│                                   │                │            │
│                                   ├── valid ───────┘            │
│                                   │  (retry with fixes)         │
│                                   │                             │
│                                   ↓                             │
│                            [REFINEMENT]                         │
│                             (optional)                          │
│                                   │                             │
│                                   ↓                             │
│                            [FINALIZE]                           │
│                                   │                             │
│                                   ↓                             │
│                                 [END]                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Error paths (not shown):
- INIT → ERROR (no entities extracted)
- INDRA_QUERY → ERROR (no paths found, no location)
- VALIDATION → ERROR (unfixable structural issues)
```

---

## Agent Responsibilities

### Supervisor Agent
- **State 0 (INIT)**: Entity extraction and grounding
- **State 6 (FINALIZE)**: Explanation generation, response assembly
- **Orchestration**: Route between states, handle timeouts, aggregate results

**Key methods** (in `supervisor.py`):
- `_initial_routing()` → Decide mesh_enrichment vs indra_query_agent
- `_after_indra_agent()` → Check if web_researcher needed
- `_finalize_response()` → Generate explanations, build metadata

### MeSH Enrichment Agent (NEW)
- **State 1 (MESH_ENRICHMENT)**: Query Writer KG for ontology expansion
- **Input**: Seed entities from INIT
- **Output**: Enriched entity list with priorities

**Implementation** (create `mesh_enrichment_agent.py`):
```python
class MeshEnrichmentAgent:
    async def __call__(self, state: OverallState) -> Dict:
        seed_entities = state["seed_entities"]
        enriched = []

        for entity in seed_entities:
            # Query Writer KG
            result = await writer_kg_service.find_related_terms(entity.name)

            # Add with priorities
            for term in result:
                enriched.append(EnrichedEntity(
                    name=term["label"],
                    mesh_id=term["mesh_id"],
                    priority=self._assign_priority(term["relationship"]),
                    source=f"{term['relationship']}_to_{entity.name}"
                ))

        return {"enriched_entities": enriched}
```

### INDRA Query Agent
- **State 2 (INDRA_QUERY)**: Discover causal paths from INDRA
- **Input**: Enriched entities from MESH_ENRICHMENT
- **Output**: INDRA paths with evidence

**Current implementation** (in `indra_query_agent.py`):
- Already implements path search and ranking ✅
- **Enhancement needed**: Add neighborhood expansion for sparse graphs

### Web Researcher Agent
- **State 2b (WEB_RESEARCHER)**: Fetch environmental exposure data
- **Input**: User location history
- **Output**: Pollution multipliers, exposure deltas

**Current implementation** (in `web_researcher.py`):
- Already queries IQAir API ✅
- Already calculates exposure deltas ✅

### Graph Builder Service
- **State 3 (GRAPH_CONSTRUCTION)**: Convert INDRA paths to SCM format
- **Input**: INDRA paths, environmental data, user genetics
- **Output**: Structured causal graph

**Current implementation** (in `graph_builder.py`):
- Already builds nodes and edges ✅
- **Enhancement needed**: Replace heuristic effect sizes with formula
- **Enhancement needed**: Apply genetic modifiers systematically

### Validation Agent (NEW)
- **State 4 (VALIDATION)**: Verify graph satisfies SCM constraints
- **Input**: Causal graph from GRAPH_CONSTRUCTION
- **Output**: Validation result with warnings

**Implementation** (create `validation_agent.py`):
```python
class ValidationAgent:
    def validate_structure(self, graph: CausalGraph) -> Dict:
        G = nx.DiGraph()
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)

        return {
            "is_dag": nx.is_directed_acyclic_graph(G),
            "is_connected": nx.is_weakly_connected(G),
            "has_cycles": list(nx.simple_cycles(G)) if not is_dag else []
        }

    def validate_parameters(self, graph: CausalGraph) -> Dict:
        return {
            "effect_sizes_valid": all(0 <= e.effect_size <= 1 for e in graph.edges),
            "temporal_lags_valid": all(e.temporal_lag_hours >= 0 for e in graph.edges),
            "relationships_valid": all(e.relationship in VALID_RELATIONSHIPS for e in graph.edges)
        }
```

### Refinement Agent (NEW)
- **State 5 (REFINEMENT)**: Iteratively improve graph quality
- **Input**: Causal graph + validation warnings
- **Output**: Refined causal graph

**Implementation** (create `refinement_agent.py`):
```python
class RefinementAgent:
    async def __call__(self, state: OverallState) -> Dict:
        graph = state["causal_graph"]
        warnings = state["validation_result"]["warnings"]

        if "low_evidence" in warnings:
            # Re-query INDRA with relaxed thresholds
            graph = await self._strengthen_evidence(graph)

        if "sparse_graph" in warnings:
            # Fill gaps with additional INDRA queries
            graph = await self._fill_gaps(graph)

        # Prune low-impact nodes
        graph = self._prune_graph(graph, min_centrality=0.1)

        return {"causal_graph": graph}
```

---

## Error Handling

### Timeout Strategies
- **Per-state timeout**: Enforced at agent level (see timeouts in state descriptions)
- **Global timeout**: 30s total (from State 0 → State 6)
- **Graceful degradation**: Return partial graph if timeout in State 5 (refinement)

### Fallback Mechanisms
1. **INDRA API failure**: Use cached responses (see `cached_responses.py`)
2. **Writer KG failure**: Skip enrichment, proceed with seed entities only
3. **LLM failure (explanations)**: Use template-based explanations
4. **Validation failure**: Return graph with warnings, mark as "partial_graph"

### Error States
- `NO_CAUSAL_PATH`: Query nonsensical (e.g., "coffee affects eye color")
- `TIMEOUT`: Total time >30s
- `INVALID_REQUEST`: Missing required fields (user_context, query)
- `SERVICE_UNAVAILABLE`: INDRA/Writer KG both down (rare)

---

## Implementation Checklist

### Phase 1: Core FSM (Hackathon MVP)
- [x] State 0: INIT (already in `supervisor.py`)
- [ ] State 1: MESH_ENRICHMENT (new agent, ~200 lines)
- [x] State 2: INDRA_QUERY (already in `indra_query_agent.py`)
- [x] State 2b: WEB_RESEARCHER (already in `web_researcher.py`)
- [ ] State 3: GRAPH_CONSTRUCTION enhancement (replace heuristic effect sizes)
- [ ] State 4: VALIDATION (new agent, ~150 lines)
- [ ] State 6: FINALIZE (already in `supervisor.py`, enhance explanations)

**Estimated effort**: 6-8 hours

### Phase 2: Refinement (Post-Hackathon)
- [ ] State 5: REFINEMENT agent (~300 lines)
- [ ] Iterative improvement loop
- [ ] Evidence strengthening logic
- [ ] Gap-filling queries

**Estimated effort**: 4-6 hours

### Phase 3: Production Hardening
- [ ] Distributed tracing (track state transitions)
- [ ] Agent performance metrics (latency per state)
- [ ] A/B testing framework (compare graph topologies)
- [ ] Cost monitoring (LLM calls, API usage)

**Estimated effort**: 8-12 hours

---

## Example Walkthrough: "Prediabetes → what else?"

### User Query
```
"I have prediabetes. What health risks should I monitor besides blood sugar?"
```

### State 0: INIT
```python
seed_entities = [
    SeedEntity(name="prediabetes", type="condition", mesh_id="D011236")
]
# Only 1 entity → need to expand to find targets
```

### State 1: MESH_ENRICHMENT
```python
# Query Writer KG: "What are related conditions to prediabetes?"
enriched_entities = [
    # Seed
    EnrichedEntity(name="prediabetes", mesh_id="D011236", priority=1),

    # Related pathways (Priority 3)
    EnrichedEntity(name="insulin resistance", mesh_id="D007333", priority=3),
    EnrichedEntity(name="oxidative stress", mesh_id="D018384", priority=3),
    EnrichedEntity(name="inflammation", mesh_id="D007249", priority=3),
    EnrichedEntity(name="endothelial dysfunction", mesh_id="D007249", priority=3),

    # Potential biomarkers (Priority 3)
    EnrichedEntity(name="CRP", hgnc_id="HGNC:2367", priority=3),
    EnrichedEntity(name="HbA1c", mesh_id="D006442", priority=3),
    EnrichedEntity(name="8-OHdG", mesh_id="D016899", priority=3)  # oxidative stress marker
]
```

### State 2: INDRA_QUERY
```python
# Query INDRA for paths: prediabetes → [CRP, 8-OHdG, endothelial_dysfunction]
indra_paths = [
    # Path 1: prediabetes → oxidative stress → 8-OHdG (biomarker)
    CausalPath(
        nodes=["prediabetes", "insulin_resistance", "oxidative_stress", "8-OHdG"],
        edges=[
            Edge(source="prediabetes", target="insulin_resistance", belief=0.89, evidence_count=127),
            Edge(source="insulin_resistance", target="oxidative_stress", belief=0.84, evidence_count=93),
            Edge(source="oxidative_stress", target="8-OHdG", belief=0.91, evidence_count=156)
        ]
    ),

    # Path 2: prediabetes → inflammation → CRP
    CausalPath(
        nodes=["prediabetes", "insulin_resistance", "inflammation", "IL-6", "CRP"],
        edges=[
            Edge(source="prediabetes", target="insulin_resistance", belief=0.89, evidence_count=127),
            Edge(source="insulin_resistance", target="inflammation", belief=0.81, evidence_count=104),
            Edge(source="inflammation", target="IL-6", belief=0.88, evidence_count=78),
            Edge(source="IL-6", target="CRP", belief=0.98, evidence_count=312)
        ]
    ),

    # Path 3: prediabetes → endothelial dysfunction
    CausalPath(
        nodes=["prediabetes", "oxidative_stress", "NO_synthase_inhibition", "endothelial_dysfunction"],
        edges=[
            Edge(source="prediabetes", target="oxidative_stress", belief=0.84, evidence_count=93),
            Edge(source="oxidative_stress", target="NO_synthase_inhibition", belief=0.79, evidence_count=67),
            Edge(source="NO_synthase_inhibition", target="endothelial_dysfunction", belief=0.87, evidence_count=89)
        ]
    )
]
```

### State 3: GRAPH_CONSTRUCTION
```python
# Merge 3 paths into unified graph
causal_graph = CausalGraph(
    nodes=[
        Node(id="prediabetes", type="condition"),
        Node(id="insulin_resistance", type="molecular"),
        Node(id="oxidative_stress", type="molecular"),
        Node(id="inflammation", type="molecular"),
        Node(id="IL-6", type="biomarker"),
        Node(id="CRP", type="biomarker"),
        Node(id="8-OHdG", type="biomarker"),
        Node(id="NO_synthase_inhibition", type="molecular"),
        Node(id="endothelial_dysfunction", type="molecular")
    ],
    edges=[
        # Prediabetes is root cause
        Edge(source="prediabetes", target="insulin_resistance",
             effect_size=0.6*0.89 + 0.1*log(128) = 0.534 + 0.486 = 0.95,
             temporal_lag_hours=168),  # Weeks to develop

        # Insulin resistance drives 3 pathways
        Edge(source="insulin_resistance", target="oxidative_stress",
             effect_size=0.88, temporal_lag_hours=72),
        Edge(source="insulin_resistance", target="inflammation",
             effect_size=0.85, temporal_lag_hours=96),

        # Oxidative stress pathway
        Edge(source="oxidative_stress", target="8-OHdG",
             effect_size=0.92, temporal_lag_hours=6),
        Edge(source="oxidative_stress", target="NO_synthase_inhibition",
             effect_size=0.82, temporal_lag_hours=12),

        # Inflammation pathway
        Edge(source="inflammation", target="IL-6",
             effect_size=0.89, temporal_lag_hours=12),
        Edge(source="IL-6", target="CRP",
             effect_size=0.95, temporal_lag_hours=6),

        # Endothelial pathway
        Edge(source="NO_synthase_inhibition", target="endothelial_dysfunction",
             effect_size=0.88, temporal_lag_hours=24)
    ]
)
```

### State 4: VALIDATION
```python
validation_result = ValidationResult(
    is_valid=True,
    warnings=[],
    structural_checks={
        "is_dag": True,
        "is_connected": True,
        "has_root_nodes": True  # prediabetes is root
    }
)
```

### State 6: FINALIZE
```python
response = CausalDiscoveryResponse(
    status="success",
    causal_graph=causal_graph,
    explanations=[
        "Prediabetes drives 3 pathways: oxidative stress, inflammation, endothelial dysfunction.",
        "Monitor CRP (inflammation), 8-OHdG (oxidative stress), and vascular function.",
        "Insulin resistance is the central mechanism (127 papers, 89% confidence).",
        "All pathways develop over weeks to months (72-168 hour lags).",
        "Early intervention can prevent progression to type 2 diabetes."
    ],
    metadata=Metadata(
        query_time_ms=6234,
        indra_paths_explored=3,
        total_evidence_papers=621
    )
)
```

**Key insight**: From single seed entity (prediabetes), FSM discovered **3 distinct risk pathways** with **9 measurable biomarkers** (CRP, IL-6, 8-OHdG) backed by 621 papers.

---

## Comparison to Current Implementation

### Current State (healthos_bot + indra_agent)
```python
# supervisor.py line 88-123
if self.settings.is_writer_configured:
    return {"next_agent": "mesh_enrichment"}
else:
    # LLM decides: web_researcher or indra_query_agent
```

**Issues**:
1. No explicit FSM states (implicit in routing logic)
2. LLM routing is non-deterministic (temperature=0 but prompt-sensitive)
3. No validation step (graphs may violate SCM constraints)
4. No refinement loop (one-shot graph construction)

### Proposed FSM Architecture
- **Explicit states**: INIT → MESH → INDRA → VALIDATE → REFINE → FINALIZE
- **Deterministic transitions**: Based on data presence, not LLM decisions
- **Validation gate**: Ensures SCM identifiability before returning
- **Refinement loop**: Iteratively improves graph quality

---

## Next Steps

### Documentation
1. [x] Mathematical foundation (`mathematical-foundation.md`)
2. [x] FSM architecture (this document)
3. [ ] Engineering implementation guide
4. [ ] API specification for interventions (do-calculus)
5. [ ] Prior knowledge integration strategy

### Implementation
1. Create `MeshEnrichmentAgent` (State 1)
2. Create `ValidationAgent` (State 4)
3. Enhance `GraphBuilderService` with effect size formula
4. Add refinement loop to `SupervisorAgent`
5. Update `models.py` with `EnrichedEntity`, `ValidationResult`

### Testing
1. Unit tests for each state transition
2. Integration test: "prediabetes → what else?" walkthrough
3. Performance test: ensure <5s query time
4. Validation test: verify all graphs satisfy SCM constraints

---

**End of Specification**
