# Architecture Refactor Plan - Revised for healthos_bot Integration

**Status:** In Progress
**Last Updated:** 2025-10-20
**Goal:** Fix architectural issues identified by Gemini-2.5-pro brutalist analysis while preserving healthos_bot functionality and integrating temporal predictions

## Architecture Overview

### Current State (3-Tier System)
```
healthos_bot (Telegram Frontend)
    ↓ Direct Python Import
indra_agent (Causal Discovery)
    ↓ [NOT INTEGRATED YET]
aeon-gateway (Temporal Predictions) [STANDALONE]
```

### Target State (Integrated 3-Tier System)
```
healthos_bot (Telegram Frontend)
    ↓ Direct Python Import
indra_agent (Causal Discovery + Temporal Predictions)
    ↓ Internal Module Call
TemporalModelEngine (moved from aeon-gateway)
```

**Key Decision:** Move `TemporalModelEngine` into `indra_agent` service as an internal module. The aeon-gateway service will be deprecated in favor of direct integration.

## Core Issues Identified

1. **Synchronous Blocking:** `aeon-gateway/src/main.py:92` uses `AgenticSystemClientSync` (blocks worker threads)
2. **In-Process Mocking:** `aeon-gateway/src/main.py:89-99` has `if agentic_url:... else:...` conditional
3. **Dead Code:** Root `main.py` (prints "Hello from digitalme!")
4. **Unbounded Agent Execution:** `indra_agent/agents/graph.py` has no iteration limits on LangGraph workflow
5. **Configuration Scattered:** AWS credentials in multiple locations, no single source of truth
6. **Missing Integration:** healthos_bot → indra_agent works, but temporal predictions (aeon-gateway) are NOT integrated

## Refactoring Phases (With Dependency Tracing)

### Phase 1: Clean Up Dead Code ✅
**Target:** Root `main.py`

**Actions:**
1. Delete `/Users/noot/Documents/digitalme/main.py` (7 lines, just prints "Hello")
2. Verify no imports reference it
3. Update any documentation that references it

**Dependencies:** None (isolated file)

**Status:** Ready to execute

---

### Phase 2: Remove In-Process Mocking (aeon-gateway) 🔄
**Target:** `aeon-gateway/src/main.py:89-99`

**Current Code:**
```python
if agentic_url:
    agentic_system = AgenticSystemClientSync(base_url=agentic_url)
    agentic_response = agentic_system.query(request)
else:
    agentic_system = MockAgenticSystem()
    agentic_response = agentic_system.query(request)
```

**Actions:**
1. Replace with FastAPI dependency injection pattern
2. Create `aeon-gateway/src/dependencies.py`:
```python
from src.agentic_client import AgenticSystemClient
from tests.mocks.agentic_system import MockAgenticSystem
import os

async def get_agentic_client():
    """FastAPI dependency for agentic system client."""
    agentic_url = os.getenv("AGENTIC_SYSTEM_URL")
    if agentic_url:
        return AgenticSystemClient(base_url=agentic_url)
    return MockAgenticSystem()
```

3. Update `src/main.py` to use dependency injection:
```python
from fastapi import Depends
from src.dependencies import get_agentic_client

@app.post("/api/v1/gateway/query")
async def process_query(
    request: QueryRequest,
    agentic_client = Depends(get_agentic_client)
):
    agentic_response = await agentic_client.query(request)
    # ... rest of logic
```

**Dependencies:**
- **Modified:** `aeon-gateway/src/main.py` (lines 61-145)
- **Created:** `aeon-gateway/src/dependencies.py`
- **Affects:** `tests/mocks/agentic_system.py` (ensure async compatibility)

**Status:** Pending

---

### Phase 3: Fix Synchronous Blocking (aeon-gateway) 🔄
**Target:** Replace `AgenticSystemClientSync` with async `AgenticSystemClient`

**Actions:**
1. Remove `AgenticSystemClientSync` class from `src/agentic_client.py` (lines 89-142)
2. Update `AgenticSystemClient.query()` to be fully async (already implemented)
3. Verify all callers use async pattern

**Dependencies:**
- **Modified:** `aeon-gateway/src/agentic_client.py` (lines 89-142 deleted)
- **Modified:** `aeon-gateway/src/main.py` (endpoint already async after Phase 2)
- **Affects:** Any tests using `AgenticSystemClientSync` → update to use async client

**Status:** Pending

---

### Phase 4: Add Max Iteration Limits (indra_agent) 🔄
**Target:** `indra_agent/agents/graph.py` - prevent unbounded agent execution

**Actions:**
1. Update `create_causal_discovery_graph()` in `indra_agent/agents/graph.py`:
```python
from langgraph.graph import StateGraph

# ... existing agent setup ...

# Compile with recursion limit
MAX_ITERATIONS = 20
workflow = workflow.compile(
    checkpointer=None,
    interrupt_before=[],
    interrupt_after=[],
    recursion_limit=MAX_ITERATIONS
)
```

2. Add timeout to `indra_agent/core/client.py`:
```python
import asyncio

async def process_request(self, request: CausalDiscoveryRequest):
    try:
        # Add 30-second timeout
        final_state = await asyncio.wait_for(
            self.graph.ainvoke(initial_state),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        return ErrorResponse(
            request_id=request.request_id,
            error=ErrorInfo(
                code="TIMEOUT",
                message="Query timed out after 30 seconds"
            )
        )
```

**Dependencies:**
- **Modified:** `indra_agent/agents/graph.py` (lines 40-80)
- **Modified:** `indra_agent/core/client.py` (lines 74-76)
- **Affects:** `healthos_bot/bot/bot.py` will receive timeout errors gracefully (already handles ErrorResponse)

**Status:** Pending

---

### Phase 5: Consolidate Configuration 🔄
**Target:** Single source of truth for AWS credentials, INDRA URLs, etc.

**Actions:**
1. Verify `indra_agent/config/settings.py` has all required fields:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # AWS Bedrock (REQUIRED)
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"

    # INDRA API
    indra_base_url: str = "https://network.indra.bio"
    indra_cache_ttl: int = 3600
    indra_timeout: int = 30

    # Optional API keys
    iqair_api_key: str | None = None
    writer_api_key: str | None = None

    # Agent configuration
    agent_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    agent_temperature: float = 0.0

    class Config:
        env_file = ".env"
        case_sensitive = False
```

2. Align environment variable names across all services:
   - `healthos_bot/config/config.env`
   - `docker-compose.yml` (root)
   - `healthos_bot/docker-compose.yml`

3. Remove duplicate configuration loading

**Dependencies:**
- **Modified:** `indra_agent/config/settings.py` (ensure consistency)
- **Modified:** `healthos_bot/config/config.env` (ensure same var names)
- **Modified:** `docker-compose.yml` (root and healthos_bot)
- **Affects:** All services read from same environment variables

**Status:** Pending

---

### Phase 6: Integrate Temporal Predictions ⚠️ **REQUIRED**
**Target:** Move `TemporalModelEngine` into `indra_agent` and integrate predictions into response flow

#### Step 6.1: Move TemporalModelEngine to indra_agent

**Actions:**
1. Copy `aeon-gateway/src/temporal_model.py` to `indra_agent/services/temporal_model.py`
2. Update imports in `temporal_model.py`:
```python
# OLD (aeon-gateway)
from src.models.gateway import CausalGraph, PredictionTimeline

# NEW (indra_agent)
from indra_agent.core.models import CausalGraph, PredictionTimeline
```

3. Add `PredictionTimeline` model to `indra_agent/core/models.py`:
```python
class PredictionTimeline(BaseModel):
    """Prediction for a single biomarker over time"""
    baseline: float
    timeline: List[Dict]  # [{day, mean, confidence_interval, risk_level}]
    unit: str
```

4. Update `CausalDiscoveryResponse` in `indra_agent/core/models.py` to include predictions:
```python
class CausalDiscoveryResponse(BaseModel):
    request_id: str
    causal_graph: CausalGraph
    metadata: Metadata
    explanations: List[str]
    predictions: Dict[str, PredictionTimeline] | None = None  # NEW
```

**Dependencies:**
- **Created:** `indra_agent/services/temporal_model.py` (copied from aeon-gateway)
- **Modified:** `indra_agent/core/models.py` (add PredictionTimeline, update CausalDiscoveryResponse)
- **Affects:** `aeon-gateway/src/temporal_model.py` (will be deprecated but kept for reference)

#### Step 6.2: Integrate Predictions into Supervisor

**Actions:**
1. Update `indra_agent/agents/supervisor.py` `_finalize_response()` method (lines 165-251):
```python
async def _finalize_response(state: OverallState) -> OverallState:
    """Generate final explanations and predictions."""
    # ... existing explanation logic ...

    # Generate temporal predictions if user context available
    predictions = {}
    if state.get("user_context") and state.get("causal_graph"):
        try:
            from indra_agent.services.temporal_model import TemporalModelEngine

            engine = TemporalModelEngine(n_simulations=1000)
            user_ctx = state["user_context"]
            causal_graph = CausalGraph(**state["causal_graph"])

            # Build model
            model = engine.build_model(
                causal_graph=causal_graph,
                user_genetics=user_ctx.get("genetics", {}),
                baseline_biomarkers=user_ctx.get("current_biomarkers", {})
            )

            # Infer environmental changes from location history
            env_changes = _infer_environmental_changes_from_location(
                user_ctx.get("location_history", [])
            )

            # Generate predictions
            predictions = engine.predict(
                model=model,
                environmental_changes=env_changes,
                horizon_days=90
            )
        except Exception as e:
            logger.warning(f"Failed to generate predictions: {e}")
            predictions = {}

    # Update state
    state["predictions"] = predictions
    return state

def _infer_environmental_changes_from_location(location_history: list) -> dict:
    """Infer environmental changes from location history."""
    if not location_history:
        return {}

    last_location = location_history[-1].get('city', '').lower()
    if 'los angeles' in last_location or 'la' in last_location:
        return {"PM2.5": 1.8}  # LA has ~1.8x higher PM2.5 than SF

    return {}
```

2. Update `indra_agent/core/client.py` to pass predictions in response:
```python
# Extract results
causal_graph_dict = final_state.get("causal_graph", {})
explanations = final_state.get("explanations", [])
metadata_dict = final_state.get("metadata", {})
predictions_dict = final_state.get("predictions", {})  # NEW

# ...

response = CausalDiscoveryResponse(
    request_id=request.request_id,
    causal_graph=causal_graph,
    metadata=metadata,
    explanations=explanations,
    predictions=predictions_dict if predictions_dict else None  # NEW
)
```

**Dependencies:**
- **Modified:** `indra_agent/agents/supervisor.py` (lines 165-251)
- **Modified:** `indra_agent/core/client.py` (add predictions extraction)
- **Affects:** `healthos_bot/bot/bot.py` will receive predictions in response

#### Step 6.3: Display Predictions in healthos_bot

**Actions:**
1. Update `healthos_bot/bot/bot.py` `format_indra_response()` function (lines 204-272):
```python
def format_indra_response(response) -> str:
    """Format INDRA causal discovery response for Telegram display."""
    graph = response.causal_graph
    metadata = response.metadata
    explanations = response.explanations
    predictions = response.predictions  # NEW

    # ... existing formatting ...

    # Show predictions if available
    if predictions:
        lines.append("📊 <b>Predicted Changes (90 days):</b>")
        for biomarker, timeline in predictions.items():
            baseline = timeline.baseline
            final_prediction = timeline.timeline[-1]  # Last day
            final_mean = final_prediction['mean']
            final_risk = final_prediction['risk_level']

            change_pct = ((final_mean - baseline) / baseline) * 100
            change_emoji = "⬆️" if change_pct > 0 else "⬇️"
            risk_emoji = {"low": "🟢", "moderate": "🟡", "high": "🔴"}.get(final_risk, "⚪")

            lines.append(
                f"  {biomarker}: {baseline:.1f} → {final_mean:.1f} {timeline.unit} "
                f"({change_emoji}{abs(change_pct):.0f}%) {risk_emoji}"
            )
        lines.append("")

    lines.append("💡 <i>This analysis uses INDRA bio-ontology for evidence-based causal pathways.</i>")

    return "\n".join(lines)
```

**Dependencies:**
- **Modified:** `healthos_bot/bot/bot.py` (lines 204-272)
- **Affects:** Telegram users will see temporal predictions in bot responses

#### Step 6.4: Update Docker Configuration

**Actions:**
1. Update root `docker-compose.yml` to remove aeon-gateway service (or keep for legacy API):
```yaml
services:
  indra-agent:
    # ... existing config ...
    environment:
      # All configuration now in indra_agent
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=${AWS_REGION:-us-east-1}
      - INDRA_BASE_URL=${INDRA_BASE_URL:-https://network.indra.bio}
      - IQAIR_API_KEY=${IQAIR_API_KEY:-}
      - WRITER_API_KEY=${WRITER_API_KEY:-}

  # aeon-gateway: DEPRECATED (functionality moved to indra_agent)
  # Kept for reference/legacy API support
```

2. Update `healthos_bot/docker-compose.yml` to ensure same env vars

**Dependencies:**
- **Modified:** `docker-compose.yml` (root)
- **Modified:** `healthos_bot/docker-compose.yml`
- **Affects:** Deployment configuration

**Status:** Pending (REQUIRED for causal model integration)

---

## Testing Strategy (Regression Prevention)

### After Each Phase:

1. **Unit Tests:**
```bash
cd /Users/noot/Documents/digitalme
uv run pytest tests/test_basic.py -v
```

2. **Integration Test (healthos_bot):**
```bash
cd healthos_bot
docker-compose --env-file config/config.env up --build

# Send test message to Telegram bot:
# "How does PM2.5 pollution affect my inflammation markers?"

# Expected: Response with causal graph + temporal predictions
```

3. **Integration Test (indra_agent standalone):**
```bash
# Start FastAPI server
cd /Users/noot/Documents/digitalme
python -m indra_agent.main

# Test via curl
curl -X POST http://localhost:8000/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_request.json
```

4. **Dependency Verification Commands:**
```bash
# Verify no imports of deleted code
grep -r "AgenticSystemClientSync" --include="*.py" .
# Expected: Only in aeon-gateway (deprecated)

# Verify no in-process mocking
grep -r "if agentic_url:" aeon-gateway/src/
# Expected: Empty (after Phase 2)

# Verify temporal_model moved
ls indra_agent/services/temporal_model.py
# Expected: File exists

# Verify PredictionTimeline in models
grep "class PredictionTimeline" indra_agent/core/models.py
# Expected: Match found
```

---

## File Change Summary

### Deleted:
- `/Users/noot/Documents/digitalme/main.py` (dead code)
- `aeon-gateway/src/agentic_client.py` lines 89-142 (`AgenticSystemClientSync`)

### Created:
- `aeon-gateway/src/dependencies.py` (FastAPI dependency injection)
- `indra_agent/services/temporal_model.py` (moved from aeon-gateway)

### Modified:
- `aeon-gateway/src/main.py` (lines 61-145: remove conditionals, use DI)
- `aeon-gateway/src/agentic_client.py` (delete sync client)
- `indra_agent/agents/graph.py` (add `recursion_limit=20`)
- `indra_agent/core/client.py` (add timeout, extract predictions)
- `indra_agent/agents/supervisor.py` (lines 165-251: generate predictions)
- `indra_agent/core/models.py` (add `PredictionTimeline`, update `CausalDiscoveryResponse`)
- `indra_agent/config/settings.py` (ensure consistency)
- `healthos_bot/bot/bot.py` (lines 204-272: display predictions)
- `healthos_bot/config/config.env` (align variable names)
- `docker-compose.yml` (root: deprecate aeon-gateway, consistent env vars)
- `healthos_bot/docker-compose.yml` (consistent env vars)

### Preserved:
- `healthos_bot/` entire directory (user-facing frontend)
- `indra_agent/` core functionality (enhanced with temporal predictions)
- `aeon-gateway/` kept for reference/legacy API (functionality moved to indra_agent)

---

## Execution Order

1. ✅ **Phase 1:** Clean dead code (COMPLETED - commit 9e3ecac)
2. ✅ **Phase 2:** Remove mocking conditionals (COMPLETED - commit 9e3ecac)
3. ✅ **Phase 3:** Fix sync blocking (COMPLETED - commit 9e3ecac)
4. ✅ **Phase 4:** Add iteration limits (COMPLETED - commit 9e3ecac)
5. ✅ **Phase 5:** Consolidate config (COMPLETED - verified consistent)
6. 🔄 **Phase 6:** Integrate temporal predictions **(IN PROGRESS - REQUIRED)**
7. ⏳ **Test:** Run full test suite and verify regression-free

---

## Decision Log

### 2025-10-20: Temporal Predictions Integration
**Decision:** Move `TemporalModelEngine` from aeon-gateway into indra_agent as an internal service module.

**Rationale:**
- healthos_bot already imports indra_agent directly (no HTTP)
- Adding temporal predictions to `CausalDiscoveryResponse` provides complete causal analysis in single response
- Simplifies architecture: 2-tier (healthos_bot → indra_agent) instead of 3-tier
- aeon-gateway can remain as standalone legacy API if needed

**Alternatives Considered:**
1. Keep aeon-gateway as HTTP API → Rejected: Adds latency, complexity
2. Move aeon-gateway code to healthos_bot → Rejected: Violates separation of concerns

**Impact:**
- `CausalDiscoveryResponse` schema changes (backward compatible: predictions optional)
- healthos_bot receives richer responses with temporal predictions
- aeon-gateway service becomes optional (deprecated but functional)

---

**Plan Status:** Approved ✅
**Next Step:** Execute Phase 1 (delete root main.py)
