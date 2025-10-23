# Real-Time Progress Tracking Specification

## Executive Summary

The current causal discovery workflow takes 30+ seconds but provides zero feedback to users during execution. This creates anxiety and uncertainty. We need **granular, real-time progress updates** that:

1. **Backend**: Emit progress at every meaningful computational step
2. **Frontend**: Display progress with delightful, intuitive UX that resonates with users
3. **Engineering**: Use Server-Sent Events (SSE) for true streaming without polling

## Problem Statement

### Current User Experience
```
User submits query → [BLACK BOX FOR 30-60 SECONDS] → Result appears
```

**User feels:**
- ❌ Anxious: "Did it break?"
- ❌ Frustrated: "How much longer?"
- ❌ Disconnected: "What's even happening?"

### Target User Experience
```
User submits query →
  [✓ Extracting biomarkers... (0.5s)]
  [✓ Grounding to INDRA database... (2s)]
  [✓ Querying 1.2M causal relationships... (8s)]
  [⟳ Building causal graph from 47 pathways... (5s)]
  [⟳ Applying genetic modifiers (GSTM1_null)... (3s)]
  [⟳ Computing temporal predictions... (12s)]
→ Result appears
```

**User feels:**
- ✅ Informed: "I see exactly what's happening"
- ✅ Patient: "This is complex work, makes sense it takes time"
- ✅ Engaged: "Wow, 1.2M relationships? This is thorough!"
- ✅ Trusted: "The system is working, I can see progress"

## Architecture: Server-Sent Events (SSE)

### Why SSE over WebSockets?
- **Simpler**: Unidirectional server→client (perfect for progress)
- **HTTP/2**: Automatic reconnection, better for proxy/CDN
- **Standards**: Native `EventSource` API in browsers
- **Scaling**: Stateless, works with serverless

### SSE Flow
```
Frontend                    Backend
   |                           |
   |-- GET /stream/{id} ------>|
   |                           | [Initiate workflow]
   |<-- SSE: progress 1 -------| emit("Extracting biomarkers...")
   |<-- SSE: progress 2 -------| emit("Grounding entities...")
   |<-- SSE: progress 3 -------| emit("Querying INDRA...")
   |<-- SSE: progress N -------| emit("Building graph...")
   |<-- SSE: complete --------|  emit("DONE", data=response)
   |                           |
   [Close EventSource]
```

## Backend: Progress Emission Points

### Granular Steps (15 total)

| Step | Agent/Service | Action | Duration | Progress % |
|------|---------------|--------|----------|------------|
| 1 | Supervisor | Initial routing decision | 0.5s | 3% |
| 2 | MeSH Enrichment | Enriching biomarker terms with MeSH ontology | 2s | 8% |
| 3 | MeSH Enrichment | Sending enriched terms to Writer KG | 1.5s | 13% |
| 4 | INDRA Agent | Extracting entities from query | 1s | 18% |
| 5 | INDRA Agent | Grounding entities to INDRA database | 3s | 28% |
| 6 | INDRA Agent | Querying INDRA for causal paths (searching 1.2M+ statements) | 8s | 48% |
| 7 | INDRA Agent | Ranking paths by evidence and belief scores | 2s | 56% |
| 8 | INDRA Agent | Building causal graph from top paths | 3s | 65% |
| 9 | Web Researcher | Fetching environmental data (if location history) | 5s | 72% |
| 10 | Supervisor | Applying genetic modifiers to graph | 2s | 77% |
| 11 | Validation Agent | Validating graph structure (DAG, stability) | 1.5s | 82% |
| 12 | Validation Agent | Auto-fixing violations (if found) | 1s | 85% |
| 13 | Temporal Engine | Building structural causal model (SCM) | 4s | 90% |
| 14 | Temporal Engine | Running Monte Carlo simulations (1000 iterations) | 8s | 96% |
| 15 | Supervisor | Generating explanations and insights | 2s | 100% |

**Total: ~45 seconds**

### Progress Message Schema

```python
from pydantic import BaseModel
from typing import Literal

class ProgressUpdate(BaseModel):
    step: int  # 1-15
    agent: str  # "supervisor", "indra_query_agent", "mesh_enrichment", "web_researcher", "validation_agent", "temporal_engine"
    action: str  # Human-readable description
    progress_percent: int  # 0-100
    duration_ms: int  # Time this step took
    metadata: dict | None = None  # Optional: entity_count, path_count, etc.

class ProgressComplete(BaseModel):
    status: Literal["success", "error"]
    data: CausalDiscoveryResponse | ErrorResponse
    total_duration_ms: int
```

### Implementation: Progress Emitter Context Manager

```python
# indra_agent/core/progress.py

import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable
from pydantic import BaseModel

class ProgressUpdate(BaseModel):
    step: int
    agent: str
    action: str
    progress_percent: int
    duration_ms: int
    metadata: dict | None = None

class ProgressEmitter:
    """Emit progress updates during workflow execution."""

    def __init__(self, callback: Callable[[ProgressUpdate], None] = None):
        self.callback = callback
        self.step_counter = 0
        self.start_time = time.time()

    @asynccontextmanager
    async def step(
        self,
        agent: str,
        action: str,
        progress_percent: int,
        metadata: dict | None = None
    ) -> AsyncGenerator[None, None]:
        """Track a single workflow step.

        Usage:
            async with emitter.step("indra_query_agent", "Grounding entities", 28):
                # Do work
                grounded_entities = await ground_entities(...)
        """
        self.step_counter += 1
        step_start = time.time()

        # Emit start of step
        if self.callback:
            update = ProgressUpdate(
                step=self.step_counter,
                agent=agent,
                action=action,
                progress_percent=progress_percent,
                duration_ms=0,  # Not yet complete
                metadata=metadata,
            )
            await self.callback(update)

        try:
            yield
        finally:
            # Emit completion of step
            duration_ms = int((time.time() - step_start) * 1000)
            if self.callback:
                update = ProgressUpdate(
                    step=self.step_counter,
                    agent=agent,
                    action=f"✓ {action}",  # Mark complete
                    progress_percent=progress_percent,
                    duration_ms=duration_ms,
                    metadata=metadata,
                )
                await self.callback(update)
```

### Integration into Agents

```python
# indra_agent/agents/indra_query_agent.py

async def create_indra_query_agent(
    handoff_tools: List,
    progress_emitter: ProgressEmitter | None = None
) -> dict:
    """Create INDRA query agent with progress tracking."""

    async def indra_agent_with_progress(state: OverallState, config: RunnableConfig):
        if progress_emitter:
            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Extracting entities from query",
                progress_percent=18
            ):
                # Extract entities
                entities = await extract_entities(state)

            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Grounding entities to INDRA database",
                progress_percent=28,
                metadata={"entity_count": len(entities)}
            ):
                # Ground entities
                grounded = await ground_entities(entities)

            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Querying INDRA for causal paths (searching 1.2M+ statements)",
                progress_percent=48
            ):
                # Query INDRA
                paths = await query_indra_paths(grounded)

            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Building causal graph from top paths",
                progress_percent=65,
                metadata={"path_count": len(paths)}
            ):
                # Build graph
                graph = await build_graph(paths)

        else:
            # Original logic without progress
            entities = await extract_entities(state)
            grounded = await ground_entities(entities)
            paths = await query_indra_paths(grounded)
            graph = await build_graph(paths)

        return {"causal_graph": graph}

    # ... rest of agent setup
```

## Frontend: Delightful Progress UX

### Design Principles

1. **Emotional Resonance**: Use language that makes users feel the complexity and care
2. **Visual Hierarchy**: Progress bar + current step + completed steps
3. **Transparency**: Show real technical details (not just "Loading...")
4. **Delight**: Animate transitions, celebrate completions
5. **Context**: Explain why each step matters

### Component: ProgressStream.svelte

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  interface ProgressUpdate {
    step: number;
    agent: string;
    action: string;
    progress_percent: number;
    duration_ms: number;
    metadata?: Record<string, any>;
  }

  let progressUpdates = $state<ProgressUpdate[]>([]);
  let currentStep = $state<ProgressUpdate | null>(null);
  let overallProgress = $state(0);
  let isComplete = $state(false);
  let eventSource: EventSource | null = null;

  interface Props {
    requestId: string;
    onComplete: (data: any) => void;
    onError: (error: string) => void;
  }

  let { requestId, onComplete, onError }: Props = $props();

  onMount(() => {
    // Connect to SSE stream
    eventSource = new EventSource(`http://localhost:8000/api/v1/stream/${requestId}`);

    eventSource.addEventListener('progress', (event) => {
      const update: ProgressUpdate = JSON.parse(event.data);
      progressUpdates.push(update);
      currentStep = update;
      overallProgress = update.progress_percent;
    });

    eventSource.addEventListener('complete', (event) => {
      const result = JSON.parse(event.data);
      isComplete = true;
      overallProgress = 100;
      eventSource?.close();

      if (result.status === 'success') {
        onComplete(result.data);
      } else {
        onError(result.data.error.message);
      }
    });

    eventSource.onerror = () => {
      onError('Connection lost. Please retry.');
      eventSource?.close();
    };
  });

  onDestroy(() => {
    eventSource?.close();
  });

  function getAgentIcon(agent: string): string {
    const icons: Record<string, string> = {
      'supervisor': '🧠',
      'mesh_enrichment': '🔬',
      'indra_query_agent': '🧬',
      'web_researcher': '🌍',
      'validation_agent': '✓',
      'temporal_engine': '⏱️'
    };
    return icons[agent] || '⚙️';
  }

  function formatDuration(ms: number): string {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  }
</script>

<div class="progress-container">
  <!-- Overall Progress Bar -->
  <div class="progress-header">
    <h3 class="text-xl font-semibold text-gray-900">
      {isComplete ? '✓ Analysis Complete' : '🔍 Discovering Causal Pathways...'}
    </h3>
    <span class="text-sm text-gray-600">{overallProgress}%</span>
  </div>

  <div class="progress-bar-container">
    <div
      class="progress-bar-fill"
      style="width: {overallProgress}%"
    ></div>
  </div>

  <!-- Current Step -->
  {#if currentStep && !isComplete}
    <div class="current-step animate-pulse">
      <div class="flex items-center space-x-3">
        <span class="text-2xl">{getAgentIcon(currentStep.agent)}</span>
        <div class="flex-1">
          <p class="text-sm font-medium text-gray-900">{currentStep.action}</p>
          {#if currentStep.metadata}
            <p class="text-xs text-gray-600 mt-1">
              {#if currentStep.metadata.entity_count}
                Processing {currentStep.metadata.entity_count} entities
              {/if}
              {#if currentStep.metadata.path_count}
                Found {currentStep.metadata.path_count} causal pathways
              {/if}
            </p>
          {/if}
        </div>
        <div class="loading-spinner"></div>
      </div>
    </div>
  {/if}

  <!-- Completed Steps Timeline -->
  <div class="completed-steps">
    {#each progressUpdates.filter(u => u.action.startsWith('✓')) as update}
      <div class="completed-step">
        <div class="flex items-start space-x-3">
          <span class="text-green-600">✓</span>
          <div class="flex-1">
            <p class="text-sm text-gray-700">{update.action.replace('✓ ', '')}</p>
            {#if update.metadata}
              <p class="text-xs text-gray-500 mt-0.5">
                {#if update.metadata.entity_count}
                  {update.metadata.entity_count} entities
                {/if}
                {#if update.metadata.path_count}
                  {update.metadata.path_count} pathways
                {/if}
              </p>
            {/if}
          </div>
          <span class="text-xs text-gray-400">{formatDuration(update.duration_ms)}</span>
        </div>
      </div>
    {/each}
  </div>

  <!-- Insight Box -->
  <div class="insight-box">
    <p class="text-xs text-blue-700">
      <strong>💡 Why does this take time?</strong> We're analyzing millions of peer-reviewed
      scientific papers to find evidence-based causal pathways specific to your biomarkers,
      genetics, and environmental exposures. This isn't a keyword search—it's systems medicine.
    </p>
  </div>
</div>

<style>
  .progress-container {
    @apply bg-white rounded-lg border border-gray-200 p-6 space-y-4;
  }

  .progress-header {
    @apply flex items-center justify-between;
  }

  .progress-bar-container {
    @apply w-full h-3 bg-gray-200 rounded-full overflow-hidden;
  }

  .progress-bar-fill {
    @apply h-full bg-gradient-to-r from-primary-500 to-primary-600 transition-all duration-500 ease-out;
  }

  .current-step {
    @apply bg-blue-50 border border-blue-200 rounded-lg p-4;
  }

  .completed-steps {
    @apply space-y-2 max-h-64 overflow-y-auto;
  }

  .completed-step {
    @apply bg-gray-50 rounded px-3 py-2 border-l-2 border-green-500;
  }

  .insight-box {
    @apply bg-blue-50 border border-blue-200 rounded-lg p-3;
  }

  .loading-spinner {
    @apply w-5 h-5 border-2 border-primary-600 border-t-transparent rounded-full animate-spin;
  }
</style>
```

### Integration into Query Flow

```svelte
<!-- src/routes/+page.svelte -->

<script lang="ts">
  import ProgressStream from '$lib/components/ProgressStream.svelte';

  let showProgress = $state(false);
  let currentRequestId = $state<string | null>(null);

  async function handleQuerySubmit(event: CustomEvent<string>) {
    const queryText = event.detail;
    if (!$selectedPersona) return;

    // Generate request ID
    const requestId = crypto.randomUUID();
    currentRequestId = requestId;

    // Show progress UI
    showProgress = true;

    // Start streaming request (SSE will handle updates)
    const request: CausalDiscoveryRequest = {
      request_id: requestId,
      query: { text: queryText, focus_biomarkers: $selectedPersona.keyBiomarkers },
      user_context: { /* ... */ },
      options: { max_graph_depth: 5 }
    };

    // POST to initiate (backend will stream via SSE)
    await fetch('http://localhost:8000/api/v1/causal_discovery', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request)
    });
  }

  function handleComplete(data: CausalDiscoveryResponse) {
    causalGraph.set(data.causal_graph);
    keyInsights.set(data.key_insights);
    showProgress = false;
    selectedTab = 'graph';
  }

  function handleError(error: string) {
    showProgress = false;
    error.set(error);
  }
</script>

{#if showProgress && currentRequestId}
  <ProgressStream
    requestId={currentRequestId}
    onComplete={handleComplete}
    onError={handleError}
  />
{:else}
  <!-- Normal query builder -->
  <QueryBuilder on:submit={handleQuerySubmit} />
{/if}
```

## Backend Implementation: SSE Endpoint

```python
# indra_agent/api/routes.py

from fastapi import Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

@router.get("/api/v1/stream/{request_id}")
async def stream_progress(request_id: str):
    """Stream progress updates via Server-Sent Events.

    Frontend connects via EventSource:
        const es = new EventSource(`/api/v1/stream/${request_id}`);
        es.addEventListener('progress', (e) => { ... });
        es.addEventListener('complete', (e) => { ... });
    """

    async def event_generator():
        """Generate SSE events for this request."""

        # Create progress callback
        progress_queue = asyncio.Queue()

        async def progress_callback(update: ProgressUpdate):
            await progress_queue.put(update)

        # Create emitter with callback
        emitter = ProgressEmitter(callback=progress_callback)

        # Start workflow task
        async def run_workflow():
            try:
                # Create request (would come from store in real implementation)
                # For now, assume it's passed or reconstructed

                client = get_client()
                response = await client.process_request_with_progress(
                    request=stored_request,
                    progress_emitter=emitter
                )

                # Send completion event
                await progress_queue.put({
                    "type": "complete",
                    "status": "success" if isinstance(response, CausalDiscoveryResponse) else "error",
                    "data": response.model_dump()
                })

            except Exception as e:
                logger.error(f"Workflow error: {e}", exc_info=True)
                await progress_queue.put({
                    "type": "complete",
                    "status": "error",
                    "data": {"error": {"code": "WORKFLOW_ERROR", "message": str(e)}}
                })

        # Start workflow in background
        workflow_task = asyncio.create_task(run_workflow())

        # Stream progress updates
        while True:
            try:
                # Wait for next update with timeout
                update = await asyncio.wait_for(progress_queue.get(), timeout=60)

                if isinstance(update, dict) and update.get("type") == "complete":
                    # Final event
                    yield {
                        "event": "complete",
                        "data": json.dumps(update)
                    }
                    break
                else:
                    # Progress update
                    yield {
                        "event": "progress",
                        "data": json.dumps(update.model_dump())
                    }

            except asyncio.TimeoutError:
                # Send keepalive
                yield {
                    "event": "ping",
                    "data": json.dumps({"status": "alive"})
                }

        # Ensure workflow completes
        await workflow_task

    return EventSourceResponse(event_generator())
```

## Modified Client with Progress Support

```python
# indra_agent/core/client.py

class INDRAAgentClient:
    """Client for INDRA agent system with progress tracking."""

    async def process_request_with_progress(
        self,
        request: CausalDiscoveryRequest,
        progress_emitter: ProgressEmitter
    ) -> CausalDiscoveryResponse | ErrorResponse:
        """Process request with granular progress updates.

        Args:
            request: Causal discovery request
            progress_emitter: Progress emitter for tracking

        Returns:
            CausalDiscoveryResponse or ErrorResponse
        """

        # Initialize graph with progress
        async with progress_emitter.step(
            agent="supervisor",
            action="Initializing causal discovery workflow",
            progress_percent=3
        ):
            graph = await create_causal_discovery_graph_with_progress(progress_emitter)

        # Prepare state
        state = {
            "request_id": request.request_id,
            "query": request.query.model_dump(),
            "user_context": request.user_context.model_dump(),
            "options": request.options.model_dump(),
            "messages": [],
        }

        # Run workflow (agents will use progress_emitter internally)
        config = RunnableConfig(
            recursion_limit=50,
            configurable={"progress_emitter": progress_emitter}
        )

        result = await graph.ainvoke(state, config=config)

        # Convert to response
        if result.get("next_agent") == "END":
            return CausalDiscoveryResponse(
                request_id=request.request_id,
                status="success",
                causal_graph=result["causal_graph"],
                key_insights=result.get("explanations", []),
                metadata=result.get("metadata", {}),
                predictions=result.get("predictions", {}),
            )
        else:
            return ErrorResponse(
                request_id=request.request_id,
                error={"code": "TIMEOUT", "message": "Workflow timed out"}
            )
```

## Testing Strategy

### Backend Tests

```python
# tests/test_progress_tracking.py

import pytest
from indra_agent.core.progress import ProgressEmitter, ProgressUpdate

@pytest.mark.asyncio
async def test_progress_emitter():
    """Test progress emitter context manager."""

    updates = []

    async def callback(update: ProgressUpdate):
        updates.append(update)

    emitter = ProgressEmitter(callback=callback)

    async with emitter.step("test_agent", "Testing step", 50):
        await asyncio.sleep(0.1)  # Simulate work

    assert len(updates) == 2  # Start and end
    assert updates[0].action == "Testing step"
    assert updates[1].action == "✓ Testing step"
    assert updates[1].duration_ms > 0
```

### Frontend Tests

```typescript
// tests/ProgressStream.test.ts

import { render, waitFor } from '@testing-library/svelte';
import ProgressStream from '$lib/components/ProgressStream.svelte';

test('displays progress updates', async () => {
  const mockEventSource = {
    addEventListener: vi.fn((event, handler) => {
      if (event === 'progress') {
        setTimeout(() => handler({
          data: JSON.stringify({
            step: 1,
            agent: 'indra_query_agent',
            action: 'Grounding entities',
            progress_percent: 28
          })
        }), 100);
      }
    }),
    close: vi.fn()
  };

  globalThis.EventSource = vi.fn(() => mockEventSource);

  const { getByText } = render(ProgressStream, {
    props: {
      requestId: 'test-123',
      onComplete: vi.fn(),
      onError: vi.fn()
    }
  });

  await waitFor(() => {
    expect(getByText(/Grounding entities/i)).toBeInTheDocument();
  });
});
```

## Performance Considerations

### Backend
- **Non-blocking I/O**: All progress emissions are async, don't block workflow
- **Queue-based**: Use asyncio.Queue for thread-safe progress updates
- **Timeout handling**: 60s keepalive pings prevent connection drops
- **Memory**: Limit progress history to last 50 updates

### Frontend
- **Auto-scrolling**: Keep latest step visible
- **Throttling**: Update UI max once per 100ms (debounce rapid events)
- **Cleanup**: Always close EventSource on unmount
- **Fallback**: If SSE fails, show generic loading with retry button

## Migration Path

### Phase 1: Backend Infrastructure (Week 1)
1. Implement `ProgressEmitter` class
2. Add SSE endpoint `/api/v1/stream/{request_id}`
3. Modify `INDRAAgentClient` to accept progress_emitter
4. Add progress emission to Supervisor agent

### Phase 2: Agent Integration (Week 2)
5. Add progress emission to INDRA Query Agent (5 steps)
6. Add progress emission to MeSH Enrichment Agent (2 steps)
7. Add progress emission to Web Researcher (1 step)
8. Add progress emission to Validation Agent (2 steps)
9. Add progress emission to Temporal Engine (2 steps)

### Phase 3: Frontend UX (Week 3)
10. Create `ProgressStream.svelte` component
11. Integrate into query flow
12. Add animations and visual polish
13. User testing and iteration

### Phase 4: Polish & Optimization (Week 4)
14. Add error recovery and retry logic
15. Performance optimization (throttling, memory)
16. A/B test messaging and UX
17. Documentation and rollout

## Success Metrics

- **User Anxiety**: Reduce "Is it working?" support tickets by 80%
- **Perceived Speed**: Users report feeling workflow is faster (even if actual time same)
- **Trust**: 95% of users understand what's happening during analysis
- **Completion Rate**: Increase query completion rate (fewer abandons during wait)

## Alternative Approaches (Rejected)

### Polling
❌ **Why not**: Adds unnecessary server load, 1-2s lag, not real-time

### WebSockets
❌ **Why not**: Overkill for unidirectional streaming, harder to scale, no auto-reconnect

### Progress Estimation
❌ **Why not**: Fake progress bars erode trust, we can do better with real tracking

## Appendix: User-Facing Messages

### Message Design Principles
1. **Specific over generic**: "Querying 1.2M causal relationships" > "Loading..."
2. **Scientific credibility**: Reference papers, databases, methods
3. **Empathy**: Acknowledge complexity: "This is thorough work and takes time"
4. **Transparency**: Show real technical details when helpful
5. **Celebration**: Use ✓ checkmarks, positive language for completed steps

### Example Messages

**Generic** (❌):
- "Processing..."
- "Please wait..."
- "Loading results..."

**Specific** (✅):
- "Grounding biomarkers to INDRA database (1.2M+ curated statements)"
- "Applying your GSTM1_null genetic variant to oxidative stress pathways"
- "Running Monte Carlo simulations (1000 iterations) for temporal predictions"
- "Found 47 peer-reviewed papers supporting this causal pathway"

---

**Status**: Ready for implementation
**Priority**: HIGH - Directly impacts user trust and completion rates
**Estimated Effort**: 3-4 weeks (full-stack)
