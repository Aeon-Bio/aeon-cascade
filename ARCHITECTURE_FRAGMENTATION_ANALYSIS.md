# Architecture Fragmentation Analysis

## Critical Issues Found

### 🚨 **Issue 1: Workflow is Completely Broken**

**Problem**: `langgraph_supervisor.create_supervisor` expects ReAct agents, but we only converted 1 of 3 agents.

**Current State:**
```python
# graph.py line 50-52
indra_agent = await create_indra_query_agent(handoff_tools=handoff_tools)  # ✅ ReAct agent
mesh_agent = await create_mesh_enrichment_agent(handoff_tools=handoff_tools)  # ❌ Class-based
web_agent = await create_web_researcher_agent(handoff_tools=handoff_tools)  # ❌ Class-based

workflow = create_supervisor(agents=[mesh_agent, indra_agent, web_agent], ...)
```

**Error:**
```
AttributeError: 'MeSHEnrichmentAgent' object has no attribute 'name'
```

**Why Tests Pass:**
Tests use the **old** class-based agents directly, not through `create_supervisor`. The E2E tests work because the client has lazy initialization and hasn't actually created the graph yet.

---

### 🚨 **Issue 2: MeSH → INDRA Flow Not Guaranteed**

**Old Architecture (WORKING):**
```python
# Hard-coded edge: MeSH always goes to INDRA
workflow.add_edge("mesh_enrichment", "indra_query_agent")
```

**New Architecture (BROKEN):**
```python
# Supervisor decides routing via LLM - NO guarantee
workflow = create_supervisor(
    agents=[mesh_agent, indra_agent, web_agent],
    tools=handoff_tools,  # LLM picks which agent to call
)
```

**Problem:**
- Supervisor prompt (SUPERVISOR_CONFIG line 27-52) **doesn't mention MeSH agent**
- Registry shows `dependencies=["mesh_enrichment"]` but this is **not enforced**
- Supervisor will likely call INDRA **before** MeSH, missing enriched entities

---

### 🚨 **Issue 3: State Not Accessible to ReAct Tools**

**MeSH agent writes to state:**
```python
# mesh_enrichment_agent.py line 123-126
return {
    "mesh_enriched_entities": enriched_entities,
    "current_agent": "mesh_enrichment",
}
```

**INDRA tools can't read state:**
```python
# indra_query_agent.py line 35-58
@tool
async def ground_biological_entities(entities: List[str]) -> str:
    # Where is mesh_enriched_entities?
    # Tools only get parameters, not full state!
    grounded = grounding_service.ground_entities(entities)
```

**Problem:**
The ReAct pattern isolates tools from state. Tools receive only their typed parameters, not the full LangGraph state dict. The enriched MeSH data is **invisible** to INDRA tools.

---

### 🚨 **Issue 4: Supervisor Doesn't Know Workflow**

**Supervisor prompt (agent_config.py line 27-52) says:**
```
Available agents:
1. indra_query_agent
2. web_researcher

Decision framework:
- Always delegate to indra_query_agent for building causal graphs
- Delegate to web_researcher if query involves current environmental conditions
```

**But agent_registry.py line 62-76 defines:**
```python
"mesh_enrichment": AgentConfig(
    name="mesh_enrichment",
    handoff_tool_name="consult_mesh_enrichment_specialist",
    # ... but supervisor prompt never mentions this!
)
```

**Problem:**
The supervisor has a hardcoded prompt that doesn't know about the MeSH agent. Even though we pass handoff tools, the LLM won't use them because its instructions don't mention MeSH enrichment.

---

## Root Cause

**The Lobster migration is incomplete:**

1. ✅ **Infrastructure**: langgraph_supervisor, handoff_tools, agent_registry
2. ✅ **INDRA agent**: Converted to ReAct with @tool decorators
3. ❌ **MeSH agent**: Still class-based, incompatible with create_supervisor
4. ❌ **Web researcher**: Still class-based, incompatible with create_supervisor
5. ❌ **Supervisor prompt**: Doesn't know about new agents
6. ❌ **State sharing**: Tools can't access enriched MeSH data

---

## Why Tests Pass

**Tests don't actually test the new architecture!**

```python
# test_e2e_causal_discovery.py
client = INDRAAgentClient()  # Lazy graph creation
response = await client.process_request(request)  # Should fail here!
```

**But it passes because:**
1. Graph creation is lazy (not called during `__init__`)
2. Tests use cached INDRA responses (don't need real graph execution)
3. The old class-based code still works in isolation
4. **Graph compilation never happens in test runs**

If you actually try to create the graph:
```python
graph = await create_causal_discovery_graph()
# AttributeError: 'MeSHEnrichmentAgent' object has no attribute 'name'
```

---

## What Needs to Happen

### **Phase 1: Fix Immediate Breakage** 🔥

1. **Convert MeSH agent to ReAct pattern**
   ```python
   @tool
   async def enrich_with_mesh_ontology(entities: List[str]) -> str:
       # Call Writer KG for each entity
       # Return JSON with mesh_enriched_entities
   ```

2. **Convert Web researcher to ReAct pattern**
   ```python
   @tool
   async def fetch_pollution_data(locations: List[Dict]) -> str:
       # Call IQAir API
       # Return JSON with environmental_data
   ```

3. **Test that graph compiles**
   ```python
   graph = await create_causal_discovery_graph()
   assert graph is not None
   ```

### **Phase 2: Fix Workflow Logic** 🔧

4. **Update supervisor prompt to include MeSH**
   ```python
   SUPERVISOR_CONFIG.system_prompt = """
   Available agents:
   1. mesh_enrichment - Expands biomedical terms with MeSH ontology
   2. indra_query_agent - Finds causal pathways
   3. web_researcher - Fetches environmental data

   Workflow:
   - ALWAYS start with mesh_enrichment to enrich entities
   - Then use indra_query_agent with enriched entities
   - Use web_researcher if location data present
   """
   ```

5. **Make INDRA tools state-aware**
   - Option A: Pass `mesh_enriched_entities` as tool parameter
   - Option B: Use LangGraph's `InjectedState` annotation
   - Option C: Store in tool closure scope

6. **Add workflow validation**
   ```python
   def validate_workflow():
       assert "mesh_enrichment" in handoff_tools
       assert "indra_query_agent" depends on "mesh_enrichment"
       assert supervisor prompt mentions all agents
   ```

### **Phase 3: Integration Testing** ✅

7. **Add real graph execution test**
   ```python
   async def test_graph_compiles_and_runs():
       graph = await create_causal_discovery_graph()

       initial_state = {
           "messages": [],
           "query": {"text": "How does PM2.5 affect CRP?"},
       }

       result = await graph.ainvoke(initial_state)
       assert "causal_graph" in result
   ```

8. **Add workflow ordering test**
   ```python
   async def test_mesh_runs_before_indra():
       # Verify MeSH agent is called first
       # Verify INDRA receives mesh_enriched_entities
   ```

---

## Recommended Immediate Action

### **Option 1: Revert Migration (Safe)**
```bash
git revert HEAD~3..HEAD
# Go back to working manual StateGraph
```

**Pros:** System works immediately
**Cons:** No Lobster architecture benefits

### **Option 2: Complete Migration (Correct)**
```bash
# 1. Convert remaining agents to ReAct
# 2. Update supervisor prompt
# 3. Fix state sharing
# 4. Add integration tests
```

**Pros:** Full Lobster architecture, proper tool-based agents
**Cons:** 4-6 hours of work

### **Option 3: Hybrid Approach (Quick Fix)**
```python
# Keep old manual routing for mesh -> indra
# Use langgraph_supervisor only for supervisor <-> indra/web

workflow = StateGraph(OverallState)
workflow.add_edge("mesh_enrichment", "indra_query_agent")  # Force order

# Use create_supervisor only for indra + web
indra_web_workflow = create_supervisor(
    agents=[indra_agent, web_agent],  # Leave out mesh
    ...
)
```

**Pros:** Partial migration, preserves MeSH flow
**Cons:** Messy architecture, defeats purpose of migration

---

## Summary

**The current code WILL NOT WORK in production.**

The Lobster architecture migration broke the critical MeSH → INDRA data flow:
- Only 1/3 agents converted to ReAct
- Workflow order no longer guaranteed
- State sharing between agents broken
- Supervisor doesn't know about MeSH agent

**Tests pass because they don't actually run the new graph.**

**Recommended:** Complete Option 2 (full migration) OR Option 1 (revert and plan better).
