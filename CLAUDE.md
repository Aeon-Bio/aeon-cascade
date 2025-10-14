# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

INDRA Bio-Ontology Agentic System: A LangGraph-based multi-agent system for querying the INDRA bio-ontology to discover causal paths between environmental exposures, molecular mechanisms, and clinical biomarkers. The system uses AWS Bedrock (Claude Sonnet 4.5) for agent orchestration and integrates with the INDRA knowledge graph API.

## Development Commands

### Environment Setup
```bash
# Install with uv (recommended) or pip
pip install -e .

# Create .env from template
cp .env.example .env
# Then edit .env to add AWS credentials
```

### Running the Application
```bash
# Start FastAPI server (development)
python -m indra_agent.main

# Alternative with uvicorn
uvicorn indra_agent.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=indra_agent --cov-report=html

# Run single test
pytest tests/test_basic.py::test_function_name -v
```

### Code Quality
```bash
# Format code (Black)
black indra_agent/

# Lint (Ruff)
ruff check indra_agent/

# Type check (if mypy is installed)
mypy indra_agent/
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# API docs (interactive)
open http://localhost:8000/docs

# Test causal discovery endpoint
curl -X POST http://localhost:8000/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_request.json
```

## High-Level Architecture

### LangGraph Multi-Agent System

The system uses a **supervisor pattern** where a central orchestrator routes work to specialist agents:

```
User Request → FastAPI → LangGraph Workflow
                         ├─ Supervisor (orchestration)
                         ├─ INDRA Query Agent (bio-ontology)
                         └─ Web Researcher (environmental data)
```

**Workflow execution** (`indra_agent/agents/graph.py`):
1. Supervisor receives request and extracts entities
2. Routes to Web Researcher (if location data present) or INDRA Agent (otherwise)
3. INDRA Agent queries INDRA API, builds causal graph
4. Web Researcher fetches pollution data, calculates exposure deltas
5. Supervisor synthesizes results, generates explanations

**State management** (`indra_agent/agents/state.py`):
- Shared `OverallState` TypedDict passed between all agents
- Contains: request context, extracted entities, agent results, routing info
- Each agent updates state, supervisor decides next routing

### INDRA Integration Strategy

**Entity Grounding** (`indra_agent/services/grounding_service.py`):
- Pre-defined mappings for common entities (CRP → HGNC:2367, PM2.5 → MESH:D052638)
- Fallback to INDRA grounding API for unknown entities
- Database priority: HGNC (genes) > MESH (chemicals) > GO (processes) > CHEBI

**Path Discovery** (`indra_agent/services/indra_service.py`):
- Multi-strategy: direct path search + neighborhood expansion
- Ranks paths by: evidence count (40%), belief score (30%), path length (30%)
- Caches responses in `config/cached_responses.py` for demo reliability

**Graph Construction** (`indra_agent/services/graph_builder.py`):
- Converts INDRA paths to API-compliant causal graphs
- Effect size: `min(belief * 0.8 + evidence_boost, 0.95)` where boost depends on paper count
- Temporal lag: mapped by statement type (Phosphorylation: 1h, IncreaseAmount: 12h, etc.)

### API Contract Compliance

**Critical constraints** (see `agentic-system-spec.md`):
- `effect_size` MUST be ∈ [0, 1] (used for Monte Carlo weights)
- `temporal_lag_hours` MUST be ≥ 0 (causality violation otherwise)
- Node types MUST be: "environmental" | "molecular" | "biomarker" | "genetic"
- Relationship types MUST be: "activates" | "inhibits" | "increases" | "decreases"

**Genetic modifiers**:
- Applied via `config/cached_responses.py::get_genetic_modifier()`
- Only included if affected nodes present in graph
- Examples: GSTM1_null amplifies oxidative_stress by 1.3×

## Key Configuration Files

### Environment Variables (.env)
Required:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`: Bedrock access
- Model: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

Optional:
- `IQAIR_API_KEY`: Real-time pollution data
- `INDRA_BASE_URL`: Default https://db.indra.bio
- `APP_PORT`: Default 8000

### Agent Prompts (config/agent_config.py)
- Supervisor: Orchestration, entity extraction, explanation generation
- INDRA Agent: Entity grounding, path search, graph building
- Web Researcher: Pollution data, exposure deltas

All agents use temperature=0.0 for deterministic output.

## Important Implementation Details

### Temporal Lag Estimation
Based on biological mechanism type (see `TEMPORAL_LAG_MAP` in `graph_builder.py`):
- Fast signaling (Phosphorylation): 1 hour
- Protein binding (Complex): 2 hours
- Transcription factor (Activation): 6 hours
- Gene expression (IncreaseAmount): 12 hours

### Effect Size Calculation
Combines INDRA belief score with evidence count:
```python
effect = belief * 0.8
if evidence_count > 100: effect += 0.15
elif evidence_count > 50: effect += 0.10
elif evidence_count > 20: effect += 0.05
return min(effect, 0.95)  # Cap to avoid determinism
```

### Pre-cached Responses
For hackathon reliability, key paths are cached:
- PM2.5 → IL-6 (via NF-κB): 47 papers, belief 0.82
- IL-6 → CRP: 312 papers, belief 0.98
- PM2.5 → oxidative stress: 31 papers, belief 0.78

Fallback to cache if INDRA API unavailable.

### Node Type Inference
Heuristic-based (`_infer_node_type` in `graph_builder.py`):
- MESH database OR known exposures → "environmental"
- GO database OR known processes → "molecular"
- Known clinical markers (CRP, IL-6, 8-OHdG) → "biomarker"
- Default → "molecular"

## Troubleshooting

### "No module named 'indra_agent'"
Install in editable mode: `pip install -e .`

### AWS Bedrock access issues
1. Check credentials in `.env`
2. Verify Bedrock access in your AWS account
3. Confirm Claude Sonnet 4.5 available in region (us-east-1 recommended)
4. Model ID: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

### INDRA API timeouts
System automatically falls back to cached responses. Check logs for "using cache" warnings.

### Port 8000 in use
Set `APP_PORT=8001` in `.env` or use `uvicorn indra_agent.main:app --port 8001`

## Project Structure Notes

**Service layer** (`indra_agent/services/`): Stateless services for INDRA API, grounding, graph building, web data. These are called by agents but contain no LLM logic.

**Agent layer** (`indra_agent/agents/`): LangGraph agents with AWS Bedrock LLMs. Each agent has system prompt in `config/agent_config.py`.

**Core layer** (`indra_agent/core/`): Pydantic models matching API specification, client wrappers, state management.

**API layer** (`indra_agent/api/`): FastAPI routes that invoke LangGraph workflow.

## API Response Format

Always return status="success" even if no paths found (empty graph). Only return status="error" for:
- `NO_CAUSAL_PATH`: Query nonsensical (e.g., "coffee affects eye color")
- `TIMEOUT`: Processing took >5 seconds
- `INVALID_REQUEST`: Missing required fields

Explanations must be 3-5 items, each <200 characters. Priority order:
1. Environmental delta (if location history present)
2. Genetic context (if variants affect graph)
3. Highest evidence edge
4. Causal chain summary
5. Expected outcome

## Testing Strategy

**Unit tests**: Test individual services (grounding, graph builder, etc.)
**Integration tests**: Test full workflow with cached INDRA responses
**Contract tests**: Validate response against API specification (effect_size range, temporal_lag ≥ 0, etc.)

Use pytest fixtures in `tests/fixtures/` for sample requests/responses.
