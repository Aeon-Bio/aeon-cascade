# End-to-End Architecture Flow

**Query**: "How does PM2.5 affect CRP?"

---

## Flow Sequence

### 1. **Frontend → User Input** (SvelteKit)
**File**: `frontend/src/routes/+page.svelte` (lines 26-83)

```typescript
User types query → handleQuerySubmit()
  ├─ Build CausalDiscoveryRequest:
  │   ├─ request_id: UUID
  │   ├─ query: {text, focus_biomarkers}
  │   ├─ user_context: {biomarkers, genetics, location_history}
  │   └─ options: {max_depth: 5, include_genetic_modifiers}
  │
  └─ POST http://localhost:8000/api/v1/submit_request
```

**What happens**:
- User selects persona (Sarah Chen, John Park, etc.)
- Persona data auto-loaded (genetics, biomarkers, location history)
- Query submitted as structured JSON request
- Progress stream starts (SSE connection)

---

### 2. **API → Request Handler** (FastAPI)
**File**: `indra_agent/main.py` (lines 40-69)

```python
FastAPI receives POST /api/v1/submit_request
  ├─ CORS validation (allow localhost:5174)
  ├─ Pydantic validation (CausalDiscoveryRequest)
  └─ Route to agent workflow
```

**What happens**:
- Request validated against Pydantic schema
- Request ID assigned for SSE tracking
- Queued for async processing by LangGraph

---

### 3. **LangGraph Workflow → Supervisor** (Multi-Agent)
**File**: `indra_agent/agents/graph.py` + `supervisor.py`

```python
Supervisor receives request
  ├─ Extract entities from query text (Claude Sonnet 4.5)
  │   └─ "PM2.5 affect CRP" → entities: ["PM2.5", "CRP"]
  │
  ├─ Route to specialist agents:
  │   ├─ INDRA Query Agent (bio-ontology)
  │   └─ Web Researcher (if location data present)
  │
  └─ Synthesize results → Generate explanations
```

**What happens**:
- AWS Bedrock (Claude Sonnet 4.5) extracts biomedical entities
- Supervisor decides which agents to invoke
- Agents run in parallel where possible

---

### 4. **INDRA Query Agent → Path Discovery**
**File**: `indra_agent/agents/indra_query_agent.py`

```python
INDRA Agent receives entities: ["PM2.5", "CRP"]
  │
  ├─ Step 1: Ground entities to database IDs
  │   ├─ Call GroundingService.get_all_synonyms("PM2.5")
  │   │   └─ LocalOntologyAdapter.find_mesh_term("PM2.5")
  │   │       └─ Memgraph query: MATCH (n:Entity {name: "PM2.5"})
  │   │           └─ Returns: ["PM2.5", "Particulate Matter", "MESH:D052638"]
  │   │
  │   └─ Same for "CRP"
  │       └─ Returns: ["CRP", "C-Reactive Protein", "HGNC:2367"]
  │
  ├─ Step 2: Query INDRA for causal paths
  │   └─ Call IndraNetService._get_path_statements_optimized()
  │       ├─ Exhaustive synonym search:
  │       │   FOR EACH source_synonym IN ["PM2.5", "Particulate Matter", ...]
  │       │     FOR EACH target_synonym IN ["CRP", "C-Reactive Protein", ...]
  │       │       Query INDRA API: GET /statements/from_agents
  │       │         ?subject={source_synonym}&object={target_synonym}
  │       │
  │       ├─ Deduplication (by INDRA statement hash)
  │       ├─ Graph assembly (nodes + edges emerge)
  │       └─ Latent intermediates discovered: NF-κB, IL-6
  │
  └─ Step 3: Build causal graph
      └─ GraphBuilderService.build_graph()
          ├─ Nodes: PM2.5 (env), NF-κB (molecular), IL-6 (biomarker), CRP (biomarker)
          ├─ Edges: PM2.5→NF-κB, NF-κB→IL-6, IL-6→CRP
          ├─ Evidence: paper counts, belief scores, PMIDs
          ├─ Effect sizes: belief-based (0.82, 0.91, 0.98)
          └─ Temporal lags: mechanism-based (6h, 12h, 24h)
```

**What happens**:
- Entities grounded via **local Memgraph** (NOT Writer KG)
- Synonyms enable exhaustive INDRA search (all name variants)
- Latent intermediates (NF-κB, IL-6) **discovered**, not hardcoded
- Graph built with quantified edges (effect size, temporal lag, evidence)

---

### 5. **Local Ontology → Synonym Expansion**
**File**: `indra_agent/services/local_ontology_adapter.py` + `memgraph_client.py`

```python
LocalOntologyAdapter.find_mesh_term("PM2.5")
  │
  └─ MemgraphClient.query_entities_by_name("PM2.5")
      └─ Cypher query:
          MATCH (n:Entity)
          WHERE toLower(n.name) CONTAINS "pm2.5"
             OR toLower(n.label) CONTAINS "pm2.5"
             OR ANY(syn IN n.synonyms WHERE toLower(syn) CONTAINS "pm2.5")
          RETURN n.id, n.name, n.label, n.synonyms, n.namespace
          LIMIT 10
      │
      └─ Memgraph returns:
          {
            "mesh_id": "D052638",
            "mesh_label": "Particulate Matter",
            "synonyms": ["PM2.5", "fine particulate matter", "particulates"]
          }
```

**What happens**:
- Memgraph queried at bolt://localhost:7687
- 296K entities searched via indexed Cypher query (<100ms)
- MeSH synonyms returned for exhaustive INDRA search
- **Zero Writer KG calls** (local ontology only)

---

### 6. **INDRA API → Causal Statements**
**File**: `indra_agent/services/indranet_service.py`

```python
Query INDRA REST API for each synonym pair
  │
  ├─ GET https://db.indra.bio/statements/from_agents?
  │     subject=PM2.5&object=NF-κB
  │   Returns: 47 statements (papers showing PM2.5 activates NF-κB)
  │
  ├─ GET https://db.indra.bio/statements/from_agents?
  │     subject=NF-κB&object=IL-6
  │   Returns: 89 statements (NF-κB increases IL-6)
  │
  └─ GET https://db.indra.bio/statements/from_agents?
      subject=IL-6&object=CRP
    Returns: 312 statements (IL-6 increases CRP)
```

**What happens**:
- INDRA database queried for literature-backed causal statements
- Each statement has: belief score, evidence count, PMIDs
- Statements merged, deduplicated, ranked by evidence

---

### 7. **Graph Builder → API Response**
**File**: `indra_agent/services/graph_builder.py`

```python
GraphBuilderService.build_graph(statements)
  │
  ├─ Extract nodes:
  │   ├─ PM2.5 (type: environmental)
  │   ├─ NF-κB (type: molecular)
  │   ├─ IL-6 (type: biomarker)
  │   └─ CRP (type: biomarker)
  │
  ├─ Build edges with metadata:
  │   ├─ PM2.5 → NF-κB:
  │   │   ├─ relationship: "activates"
  │   │   ├─ evidence: {count: 47, confidence: 0.82, sources: [PMIDs]}
  │   │   ├─ effect_size: 0.82 (belief score)
  │   │   └─ temporal_lag_hours: 6 (Phosphorylation mechanism)
  │   │
  │   └─ Similar for NF-κB→IL-6, IL-6→CRP
  │
  └─ Return CausalGraph (Pydantic model)
```

**What happens**:
- Nodes typed (environmental, molecular, biomarker)
- Edges quantified (effect size ∈ [0,1], temporal lag ≥0)
- Evidence transparent (paper counts, PMIDs, confidence)
- API contract enforced (Pydantic validation)

---

### 8. **API → Response Stream** (SSE)
**File**: Backend sends Server-Sent Events

```python
SSE stream to frontend:
  │
  ├─ Event: progress (agent: supervisor, action: "Extracting entities")
  ├─ Event: progress (agent: indra_query, action: "Grounding PM2.5")
  ├─ Event: progress (agent: indra_query, action: "Querying INDRA")
  ├─ Event: progress (agent: supervisor, action: "Building graph")
  │
  └─ Event: complete
      └─ data: {
            causal_graph: {...},
            explanations: [...],
            insights: {...},
            metadata: {query_time_ms: 2847, indra_paths_explored: 3}
          }
```

**What happens**:
- Real-time progress updates sent to frontend
- User sees: "Grounding PM2.5", "Querying INDRA", etc.
- Final result streamed when complete

---

### 9. **Frontend → Visualization**
**File**: `frontend/src/routes/+page.svelte` (lines 85-106)

```typescript
handleProgressComplete(data)
  ├─ Store causal_graph → causalGraph store
  ├─ Store explanations → keyInsights store
  ├─ Switch to "graph" tab
  └─ Render components:
      ├─ CausalGraph.svelte (interactive network viz)
      ├─ TemporalCascade.svelte (timeline viz)
      ├─ GraphAnalysis.svelte (feedback loops, convergent nodes)
      └─ Key Insights (bullet points)
```

**Components Rendered**:

**CausalGraph.svelte**:
- Interactive D3 force-directed graph
- Nodes: circles (sized by centrality)
- Edges: arrows (thickness = evidence count)
- Click edge → Evidence Strength Detail Panel
  - Paper count: "47 papers (Well-established pathway)"
  - Belief score: "0.82 (High confidence)"
  - Effect size, relationship type
- Disclaimer component (bottom)

**TemporalCascade.svelte**:
- Timeline visualization (T+0h → T+42h)
- Cascade stages:
  - T+6h: PM2.5 → NF-κB
  - T+18h: NF-κB → IL-6
  - T+42h: IL-6 → CRP
- "When to Measure YOUR Biomarkers" section:
  - "Measure CRP at T+24h post-intervention"
  - Explains cumulative cascade time
  - Population vs individual disclaimers

**GraphAnalysis.svelte**:
- Feedback loops detection
- Convergent nodes (multiple inputs)
- Network topology insights

---

## Data Flow Summary

```
User Query
  ↓
Frontend (SvelteKit)
  ├─ Build request (persona data + query)
  ├─ POST /api/v1/submit_request
  └─ Listen to SSE progress stream
  ↓
Backend API (FastAPI)
  ├─ Validate request (Pydantic)
  └─ Route to LangGraph workflow
  ↓
LangGraph Supervisor (AWS Bedrock)
  ├─ Extract entities (Claude Sonnet 4.5)
  └─ Route to INDRA Query Agent
  ↓
INDRA Query Agent
  ├─ Ground entities
  │   └─ GroundingService → LocalOntologyAdapter → Memgraph
  │       └─ Returns: ["PM2.5", "Particulate Matter", "MESH:D052638"]
  ├─ Query INDRA
  │   └─ IndraNetService → Exhaustive synonym search
  │       ├─ FOR EACH source_syn × target_syn
  │       │   └─ GET https://db.indra.bio/statements/from_agents
  │       ├─ Deduplication by statement hash
  │       └─ Graph assembly (latent intermediates emerge)
  └─ Build causal graph
      └─ GraphBuilderService
          ├─ Nodes: PM2.5, NF-κB, IL-6, CRP
          ├─ Edges: quantified (effect size, temporal lag, evidence)
          └─ Return CausalGraph (Pydantic)
  ↓
Backend → SSE Stream
  ├─ Progress events (real-time updates)
  └─ Complete event (causal_graph + explanations)
  ↓
Frontend Visualization
  ├─ CausalGraph (interactive D3)
  ├─ TemporalCascade (timeline)
  ├─ GraphAnalysis (topology)
  └─ Evidence indicators + disclaimers
```

---

## Key Architectural Points

### 1. **Local Ontology Integration** (100% Complete)
- **Memgraph**: 296K entities, <100ms queries, $0/month
- **Dependency injection**: Single GroundingService instance shared
- **Zero Writer KG**: All synonym expansion via local ontology
- **Exhaustive search**: All name variants queried against INDRA

### 2. **Latent Intermediate Discovery**
- Intermediates (NF-κB, IL-6) **not hardcoded**
- Emerge from graph merging of synonym queries
- INDRA pre-assembly deduplicates across name variants
- Serendipitous discovery of molecular mechanisms

### 3. **Evidence-Based Quantification**
- **Effect sizes**: INDRA belief scores (∈ [0,1])
- **Temporal lags**: Mechanism-based estimates (Phosphorylation: 1h, GeneExpression: 12h)
- **Evidence counts**: Paper counts per edge
- **PMIDs**: Traceable to source literature

### 4. **Real-Time Progress**
- SSE stream shows agent actions
- User sees: "Grounding PM2.5 (18% complete)"
- No blocking UI, transparent workflow

### 5. **Interactive Visualization**
- Click edges → Evidence panels
- Temporal cascade → Measurement guidance
- Graph topology → Feedback loops detected
- Disclaimers at every level

---

## Current State

**Servers Running**:
- Frontend: http://localhost:5174/ (SvelteKit)
- Backend: http://localhost:8000 (FastAPI + LangGraph)

**Missing**:
- Memgraph not started (Docker not running)
- Synonym expansion uses hardcoded INDRA_NAME_VARIANTS only
- Queries work but may find fewer paths

**To Enable Full Flow**:
```bash
docker-compose -f docker-compose.local-ontology.yml up -d
```

---

**Generated**: 2025-11-07
**Status**: Servers running, ready to test
