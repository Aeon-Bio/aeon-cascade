# Aeon Cascade

Systems medicine intelligence that discovers causal pathways from environmental exposures through molecular mechanisms to biomarker changes. Backed by INDRA's 3.8M literature statements and a local knowledge graph with 296K biological entities.

## What This Does

Query: *"If I move from San Francisco (PM2.5: 8 µg/m³) to LA (35 µg/m³), how will my CRP change?"*

Response: PM2.5 → oxidative stress → NF-κB → IL-6 → CRP (+1.2 mg/L expected increase, based on 312 papers)

Every pathway is literature-backed. Every effect size is quantified. Every temporal lag is estimated.

## Architecture

```
Query → LangGraph agents → INDRA bio-ontology + Local graph → Causal network
         ├─ Entity grounding (Memgraph: 296K entities)
         ├─ Path discovery (INDRA: 3.8M statements)
         ├─ Evidence scoring (paper counts + belief)
         └─ Temporal modeling (mechanism-based lags)
```

**Local knowledge graph** (Memgraph):
- 296,613 entities: FPLX (579), GO (12,182), CHEBI (218,261), HGNC (34,667)
- 464,894 relationships: hierarchical + causal
- <100ms queries, $0/month, self-hosted

**INDRA integration**:
- Exhaustive synonym search (discovers latent intermediates)
- Evidence-weighted ranking (belief scores + paper counts)
- Genetic modifiers (GSTM1_null amplifies oxidative stress 1.3×)

## Running It

### Quick Start (API)

```bash
# Prerequisites: Python 3.11+, AWS Bedrock access (Claude Sonnet 4.5)

# Install
pip install -e .

# Configure
cp .env.example .env
# Add: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION

# Start Memgraph (local ontology)
docker-compose -f docker-compose.local-ontology.yml up -d

# Run
python -m indra_agent.main

# Query
curl -X POST http://localhost:8000/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test",
    "user_context": {"user_id": "user1"},
    "query": {"text": "How does PM2.5 affect CRP?"}
  }'
```

API docs: http://localhost:8000/docs

### Frontend (Optional)

SvelteKit interface with evidence indicators, temporal cascade visualization, and interactive causal graphs.

```bash
cd frontend/
npm install
npm run dev
```

## What You Get

**API Response**:
```json
{
  "causal_graph": {
    "nodes": [
      {"id": "PM2.5", "type": "environmental"},
      {"id": "NFKB1", "type": "molecular"},
      {"id": "IL6", "type": "biomarker"},
      {"id": "CRP", "type": "biomarker"}
    ],
    "edges": [
      {
        "source": "PM2.5",
        "target": "NFKB1",
        "evidence": {"count": 47, "confidence": 0.82},
        "effect_size": 0.82,
        "temporal_lag_hours": 6
      }
    ]
  },
  "explanations": [
    "PM2.5 activates NF-κB (47 papers, 6h lag)",
    "NF-κB increases IL-6 (89 papers, 12h lag)",
    "IL-6 increases CRP (312 papers, 24h lag)"
  ]
}
```

**Guarantees**:
- Effect sizes ∈ [0, 1] (Monte Carlo compatible)
- Temporal lags ≥ 0 (causality preserved)
- Evidence transparent (PMID references, paper counts)
- DAG constraints (no feedback loops)

## Key Files

```
indra_agent/
├── agents/                  # LangGraph multi-agent system
│   ├── indra_query_agent.py # INDRA path discovery
│   ├── supervisor.py        # Orchestration
│   └── graph.py            # Workflow definition
├── services/
│   ├── indranet_service.py  # INDRA querying (exhaustive synonym search)
│   ├── grounding_service.py # Entity→ID via local ontology
│   ├── graph_builder.py     # Causal graph construction
│   └── local_ontology/      # Memgraph adapter + strategies
├── core/
│   ├── models.py           # API contract (Pydantic)
│   └── client.py           # Main interface
└── main.py                 # FastAPI entry

tests/
├── test_biological_correctness.py  # Ship Blocker #2
├── test_mdl_validation.py          # Ship Blocker #4
└── test_transparent_failure_modes.py # Ship Blocker #3

frontend/src/
├── routes/+page.svelte     # Query interface
└── lib/components/
    ├── CausalGraph.svelte  # Interactive graph
    └── TemporalCascade.svelte # Time visualization
```

## Configuration

**Required**:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (Bedrock)
- Model: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

**Optional**:
- `IQAIR_API_KEY` (real-time pollution data)
- `INDRA_BASE_URL` (default: https://db.indra.bio)

## Technology

- **LangGraph**: Multi-agent orchestration
- **AWS Bedrock**: Claude Sonnet 4.5 (entity extraction, synthesis)
- **INDRA**: 3.8M bio-ontology statements
- **Memgraph**: Graph database (bolt://localhost:7687)
- **FastAPI**: REST API
- **SvelteKit**: Frontend (optional)

## Production Status

**Validation** (Ship Blockers 1-5, all resolved):
- Test-production alignment: IL1B→IL6 path verified
- Biological correctness: 6 tests, canonical pathways validated
- Transparent failures: 5 failure modes with structured explanations
- MDL validation: 3/3 KEGG/REACTOME pathways matched
- Clinical positioning: "Mechanism Explorer" (21st Century Cures Act exemption)

**Integration**: Local ontology 100% complete (dependency injection implemented, zero external KG dependencies)

**Deployment**: Frontend UI with evidence indicators, disclaimers, temporal guidance

## License

MIT
