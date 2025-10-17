# Lobster vs INDRA Agent Architecture Comparison

## Executive Summary

This document compares the multi-agent architectures of two systems:
- **Lobster**: Bio

informatics multi-agent system for omics data analysis
- **INDRA Agent (digitalme)**: Causal discovery system for bio-ontology querying

Both use LangGraph for multi-agent orchestration, but with significantly different architectural approaches.

---

## Architecture Comparison

### State Management

#### Lobster Approach
```python
# Agent-specific state classes inheriting from AgentState
class SingleCellExpertState(AgentState):
    next: str
    task_description: str
    analysis_results: Dict[str, Any]
    clustering_parameters: Dict[str, Any]
    cell_type_annotations: Dict[str, Any]
    quality_control_metrics: Dict[str, Any]
    # ... many more fields specific to single-cell analysis

class BulkRNASeqExpertState(AgentState):
    next: str
    task_description: str
    differential_expression_results: Dict[str, Any]
    pathway_enrichment_results: Dict[str, Any]
    # ... different fields for bulk RNA-seq
```

**Pros:**
- Type-safe: Each agent has explicit state schema
- Clear contracts: Know exactly what fields each agent needs
- Debugging: Easy to inspect agent-specific state
- Isolation: Agents can't accidentally modify other agents' state

**Cons:**
- Boilerplate: Need to define state class for each agent
- Rigid: Adding fields requires code changes
- Overhead: More classes to maintain

#### INDRA Agent Approach
```python
# Single shared state for all agents
class OverallState(TypedDict, total=False):
    # Request
    request_id: str
    query: Dict
    user_context: Dict
    options: Dict

    # Entities
    entities: List[str]
    mesh_enriched_entities: List[Dict]
    source_entities: List[str]
    target_entities: List[str]

    # Results
    causal_graph: Dict
    explanations: List[str]
    metadata: Dict

    # Routing
    current_agent: str
    next_agent: str
```

**Pros:**
- Simple: Single state definition
- Flexible: Easy to add new fields
- Minimal boilerplate: No agent-specific state classes
- Easier initial development

**Cons:**
- Less type safety: Agents can access any field
- Hidden dependencies: Hard to know what each agent needs/produces
- Potential conflicts: Field name collisions between agents
- Harder to refactor: Need to trace field usage across all agents

---

### Agent Creation Pattern

#### Lobster Approach
```python
# Registry-based dynamic agent creation
def create_bioinformatics_graph(data_manager, ...):
    # Get worker agents from registry
    worker_agents = get_worker_agents()

    for agent_name, agent_config in worker_agents.items():
        # Import factory function dynamically
        factory_function = import_agent_factory(agent_config.factory_function)

        # Create agent
        agent = factory_function(
            data_manager=data_manager,
            callback_handler=callback_handler,
            agent_name=agent_config.name,
        )
        agents.append(agent)
```

**Registry Configuration:**
```python
# config/agent_registry.py
AGENT_REGISTRY = {
    "singlecell_expert_agent": AgentConfig(
        name="singlecell_expert_agent",
        display_name="Single-Cell RNA-seq Expert",
        description="Specialist in single-cell RNA-seq analysis",
        factory_function="lobster.agents.singlecell_expert:singlecell_expert",
        state_schema=SingleCellExpertState,
        # ... more config
    ),
    # ... more agents
}
```

**Pros:**
- Modular: Easy to add/remove agents
- Configurable: Agent behavior controlled by registry
- Discoverable: All agents listed in one place
- Testable: Can load subsets of agents
- Deployment flexibility: Different environments can have different agent sets

**Cons:**
- Indirection: Need to trace through registry to find agent code
- Complexity: More moving parts (registry, factory functions, config)
- Learning curve: Developers need to understand registry system

#### INDRA Agent Approach
```python
# Hardcoded agent creation
def create_causal_discovery_graph():
    workflow = StateGraph(OverallState)

    # Manually define node functions
    async def supervisor_node(state, config):
        agent = await create_supervisor_agent()
        return await agent(state, config)

    async def mesh_enrichment_node(state, config):
        agent = await create_mesh_enrichment_agent()
        result = await agent(state, config)
        await agent.cleanup()
        return result

    # Add nodes manually
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("mesh_enrichment", mesh_enrichment_node)
    workflow.add_node("indra_query_agent", indra_query_node)

    # Manual routing
    workflow.add_conditional_edges("supervisor", route_supervisor, {...})
    workflow.add_edge("mesh_enrichment", "indra_query_agent")
    workflow.set_entry_point("supervisor")

    return workflow.compile()
```

**Pros:**
- Explicit: All agents and routing visible in one file
- Simple: No registry abstraction
- Direct: Easy to trace execution flow
- Minimal dependencies: Self-contained

**Cons:**
- Rigid: Adding agents requires code changes
- Not configurable: Can't easily enable/disable agents
- Duplication: Agent creation pattern repeated for each agent
- Hard to scale: Becomes unwieldy with many agents

---

### LLM Integration

#### Lobster Approach
```python
# Uses LangChain ReAct agents with tools
def singlecell_expert(data_manager, ...):
    llm = create_llm("singlecell_expert_agent", model_params)

    # Define tools using @tool decorator
    @tool
    def check_data_status(modality_name: str = "") -> str:
        """Check if single-cell data is loaded."""
        # Implementation...

    @tool
    def run_quality_control(modality_name: str, ...) -> str:
        """Run QC on single-cell data."""
        # Implementation...

    # Create ReAct agent with tools
    agent = create_react_agent(
        llm,
        tools=[check_data_status, run_quality_control, ...],
        state_schema=SingleCellExpertState,
    )
    return agent
```

**Pros:**
- Tool-centric: LLM can discover and call tools
- Flexible: LLM chooses which tools to use
- Self-documenting: Tool descriptions guide LLM
- Standard pattern: Uses LangChain best practices
- Reasoning transparency: ReAct shows tool selection reasoning

**Cons:**
- Token overhead: Tool descriptions in every prompt
- Unpredictable: LLM may choose wrong tools
- Latency: Additional LLM calls for tool selection
- Complex debugging: Hard to trace multi-step tool calls

#### INDRA Agent Approach
```python
# Direct LLM calls with service layer
class INDRAQueryAgent:
    def __init__(self):
        self.llm = ChatBedrock(model_id=..., region_name=...)
        self.grounding_service = GroundingService()
        self.indra_service = INDRAService()
        self.graph_builder = GraphBuilderService()

    async def __call__(self, state, config):
        # Direct service calls
        entities = await self._extract_entities(state)
        grounded = self.grounding_service.ground_entities(entities)
        paths = await self.indra_service.find_causal_paths(...)
        graph = self.graph_builder.build_causal_graph(paths)

        return {"causal_graph": graph.model_dump(), ...}

    async def _extract_entities(self, state):
        # LLM for specific subtask
        messages = [SystemMessage(...), HumanMessage(...)]
        response = await self.llm.ainvoke(messages)
        return json.loads(response.content)
```

**Pros:**
- Predictable: Deterministic execution flow
- Efficient: No tool selection overhead
- Debuggable: Clear execution path
- Service-oriented: Clean separation of concerns
- Type-safe: Services have explicit interfaces

**Cons:**
- Less flexible: Agent can't dynamically choose operations
- Hardcoded logic: Adding operations requires code changes
- No self-discovery: Agent can't learn new capabilities
- Tighter coupling: Agent logic tied to specific services

---

### Supervisor Pattern

#### Lobster Approach
```python
# Uses langgraph_supervisor package
workflow = create_supervisor(
    agents=agents,
    model=supervisor_model,
    prompt=system_prompt,
    supervisor_name="supervisor",
    state_schema=OverallState,
    add_handoff_messages=True,
    output_mode="last_message",
    tools=handoff_tools + supervisor_tools,
)
```

**Dynamic Prompt Generation:**
```python
def create_supervisor_prompt(data_manager, config, active_agents):
    sections = []
    sections.append(_build_role_section())
    sections.append(_build_tools_section())
    sections.append(_build_agents_section(active_agents, config))
    sections.append(_build_decision_framework(active_agents, config))
    sections.append(_build_workflow_section(active_agents, config))
    return "\n\n".join(sections)
```

**Agent Delegation Rules Auto-Generated:**
```python
delegation_rules = {
    "research_agent": """
       - Searching scientific literature (PubMed, bioRxiv).
       - Finding datasets associated with publications.
       ...""",
    "singlecell_expert_agent": """
       - QC on single-cell datasets.
       - Clustering cells (Leiden/Louvain).
       ...""",
}
```

**Pros:**
- Scalable: Supervisor adapts to available agents
- Configurable: Behavior controlled by SupervisorConfig
- DRY: No hardcoded agent knowledge in supervisor
- Maintainable: Agent changes auto-reflected in supervisor
- Environment-aware: Adapts prompt to system resources

**Cons:**
- Abstraction: Harder to understand supervisor logic
- Indirection: Prompt generation logic spread across functions
- Complexity: Many configuration options to learn
- Debugging: Generated prompts not immediately visible

#### INDRA Agent Approach
```python
# Manual supervisor with explicit routing
class SupervisorAgent:
    async def __call__(self, state, config):
        current_agent = state.get("current_agent", "")

        if not current_agent:
            return await self._initial_routing(state)

        if current_agent == "mesh_enrichment":
            return {}  # Edge handles routing

        if current_agent == "indra_query_agent":
            return await self._after_indra_agent(state)

        if current_agent == "web_researcher":
            return await self._after_web_researcher(state)

        return {"next_agent": "END"}

    async def _after_indra_agent(self, state):
        if not state.get("environmental_data") and state.get("user_context", {}).get("location_history"):
            return {"next_agent": "web_researcher"}
        return await self._finalize_response(state)
```

**Pros:**
- Explicit: All routing logic visible
- Simple: Easy to understand flow
- Debuggable: Can step through routing decisions
- Predictable: Deterministic routing based on state
- Fast: No LLM calls for routing decisions

**Cons:**
- Hardcoded: Adding agents requires code changes
- Brittle: State field changes break routing
- Limited reasoning: Can't adapt to new scenarios
- Redundant: Routing logic duplicated across methods
- No configurability: Behavior baked into code

---

### Configuration Management

#### Lobster Approach
```python
class SupervisorConfig:
    # Workflow control
    workflow_guidance_level: str = "detailed"  # minimal, standard, detailed
    ask_clarification_questions: bool = True
    max_clarification_questions: int = 2
    auto_suggest_next_steps: bool = True

    # Agent visibility
    show_agent_capabilities: bool = True
    include_agent_tools: bool = True
    max_tools_per_agent: int = 5

    # Data handling
    require_metadata_preview: bool = True
    require_download_confirmation: bool = True

    # Response style
    summarize_expert_output: bool = True
    verbose_delegation: bool = False

    # Context
    include_data_context: bool = True
    include_workspace_status: bool = True
    include_system_info: bool = False
```

**Pros:**
- Flexible: Many configuration dimensions
- Environment-specific: Different configs for dev/prod
- User-controlled: Can adjust supervisor behavior
- Testable: Different configs for different test scenarios
- Documentation: Config fields are self-documenting

**Cons:**
- Complexity: Many options to understand
- Combinatorial: Many possible configurations to test
- Defaults: Need sensible defaults for all options
- Maintenance: Config changes require validation

#### INDRA Agent Approach
```python
# Settings from environment variables
class Settings(BaseSettings):
    # AWS Bedrock
    agent_model: str = "us.anthropic.claude-sonnet-4-5-20250129-v1:0"
    aws_region: str = "us-east-1"

    # Writer KG (optional)
    writer_api_key: Optional[str] = None
    writer_graph_id: Optional[str] = None

    # INDRA API
    indra_base_url: str = "https://network.indra.bio"

    # App
    app_port: int = 8000
```

**Agent Config:**
```python
# config/agent_config.py
SUPERVISOR_CONFIG = {
    "name": "supervisor",
    "temperature": 0.0,
    "system_prompt": """You are a supervisor...""",
}

INDRA_QUERY_AGENT_CONFIG = {
    "name": "indra_query_agent",
    "temperature": 0.0,
    "system_prompt": """You are an INDRA query specialist...""",
}
```

**Pros:**
- Simple: Minimal configuration options
- Explicit: All config in one place
- Environment-based: Standard 12-factor app pattern
- Easy to start: Few decisions needed

**Cons:**
- Inflexible: Limited customization
- Hardcoded: Behavior changes require code edits
- No runtime config: Can't adjust without restart
- Limited testing: Hard to test different configurations

---

## Tool Integration

### Lobster: LangChain @tool Pattern
```python
@tool
def run_quality_control(
    modality_name: str,
    min_genes_per_cell: int = 200,
    max_genes_per_cell: Optional[int] = None,
    min_cells_per_gene: int = 3,
    max_mito_pct: float = 20.0,
    max_ribo_pct: Optional[float] = None,
) -> str:
    """
    Run quality control on single-cell RNA-seq data.

    Filters cells and genes based on quality metrics:
    - min_genes_per_cell: Minimum genes detected per cell
    - max_genes_per_cell: Maximum genes per cell (doublet detection)
    - min_cells_per_gene: Minimum cells expressing a gene
    - max_mito_pct: Maximum mitochondrial percentage
    - max_ribo_pct: Maximum ribosomal percentage

    Returns:
        str: Summary of QC results and filtering statistics
    """
    try:
        # Implementation...
        return f"QC complete: {before_cells} -> {after_cells} cells, {before_genes} -> {after_genes} genes"
    except Exception as e:
        return f"Error in QC: {str(e)}"
```

**Characteristics:**
- **Self-documenting**: Docstring guides LLM usage
- **Type hints**: Parameters have explicit types
- **Error handling**: Wraps exceptions in string responses
- **Return strings**: All tools return human-readable strings

### INDRA: Service Layer Pattern
```python
class GroundingService:
    """Service for grounding biological entities."""

    def ground_entity(self, entity_name: str) -> Optional[Dict]:
        """Ground a single entity to database identifier."""
        if entity_name in self.all_mappings:
            return self.all_mappings[entity_name]
        # ... more logic
        return None

    def ground_entities(self, entity_names: List[str]) -> Dict[str, Optional[Dict]]:
        """Ground multiple entities."""
        return {name: self.ground_entity(name) for name in entity_names}
```

**Characteristics:**
- **Typed returns**: Returns structured data (Dict, List, Optional)
- **Composable**: Services call each other
- **Testable**: Can unit test without LLM
- **Reusable**: Same service used across agents

---

## Workflow Patterns

### Lobster: Multi-Agent Collaboration
```
User Query
    ↓
Supervisor (decides which expert)
    ↓
Research Agent → finds publications/datasets
    ↓ (returns to supervisor)
Supervisor (decides next step)
    ↓
Data Expert → downloads/loads data
    ↓ (returns to supervisor)
Supervisor (decides next step)
    ↓
Single-Cell Expert → runs QC, clustering, annotation
    ↓ (returns to supervisor)
Supervisor → synthesizes results, suggests next steps
```

**Characteristics:**
- Hierarchical: Supervisor coordinates all agents
- Sequential: Each agent completes before next
- Iterative: Can revisit agents based on results
- Flexible: Supervisor can change plan mid-execution

### INDRA: Linear Pipeline with Optional Branching
```
User Query
    ↓
Supervisor (routing)
    ↓ (if Writer KG configured)
MeSH Enrichment Agent (parallel could add more)
    ↓ (fixed edge)
INDRA Query Agent (builds causal graph)
    ↓ (returns to supervisor)
Supervisor (checks for environmental data need)
    ↓ (optional)
Web Researcher (fetches pollution data)
    ↓ (returns to supervisor)
Supervisor → finalizes response
```

**Characteristics:**
- Pipeline: Mostly linear flow
- Conditional: Branches based on data availability
- Efficient: Minimal back-and-forth
- Predictable: Clear execution path

---

## Error Handling

### Lobster: Exception Hierarchy
```python
class SingleCellAgentError(Exception):
    """Base exception for single-cell agent."""
    pass

class ModalityNotFoundError(SingleCellAgentError):
    """Raised when requested modality doesn't exist."""
    pass

class PreprocessingError(Exception):
    """Raised by preprocessing service."""
    pass

class ClusteringError(Exception):
    """Raised by clustering service."""
    pass
```

**Tool Error Handling:**
```python
@tool
def run_clustering(...) -> str:
    try:
        result = clustering_service.cluster(...)
        return f"Clustering complete: {result}"
    except ClusteringError as e:
        logger.error(f"Clustering failed: {e}")
        return f"Clustering failed: {str(e)}. Please check parameters."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Unexpected error during clustering: {str(e)}"
```

### INDRA: Try-Except with Fallbacks
```python
class INDRAQueryAgent:
    async def __call__(self, state, config):
        try:
            entities = await self._extract_entities(state)
            grounded = self.grounding_service.ground_entities(entities)
            paths = await self.indra_service.find_causal_paths(...)
            graph = self.graph_builder.build_causal_graph(paths)

            return {"causal_graph": graph.model_dump(), ...}

        except Exception as e:
            logger.error(f"INDRA query agent error: {e}", exc_info=True)
            # Return empty but valid graph
            return {
                "current_agent": "indra_query_agent",
                "causal_graph": {"nodes": [], "edges": [], "genetic_modifiers": []},
                "metadata": {"error": str(e)},
            }
```

**Service-Level Fallbacks:**
```python
async def _extract_entities(self, state):
    try:
        # LLM extraction
        response = await self.llm.ainvoke(messages)
        return json.loads(response.content.strip())
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}, using fallback")
        # Fallback to service-based extraction
        return self.grounding_service.extract_entities_from_query(query_text)
```

---

## Testing Strategies

### Lobster Testing
```python
# Unit tests for individual tools
def test_quality_service():
    service = QualityService()
    result = service.calculate_qc_metrics(adata)
    assert "n_genes_by_counts" in result

# Integration tests with mocked LLM
def test_singlecell_agent_with_mock_llm(mock_llm, data_manager):
    agent = singlecell_expert(data_manager)
    result = agent.invoke({"messages": [{"role": "user", "content": "Run QC"}]})
    assert "QC complete" in result["messages"][-1]["content"]

# System tests with full graph
def test_full_workflow(test_data_manager):
    graph = create_bioinformatics_graph(test_data_manager)
    result = graph.invoke({
        "messages": [{"role": "user", "content": "Analyze this single-cell dataset"}]
    })
    assert result["last_active_agent"] == "singlecell_expert_agent"
```

### INDRA Testing
```python
# Service unit tests
def test_grounding_service():
    service = GroundingService()
    crp = service.ground_entity("CRP")
    assert crp["type"] == "biomarker"
    assert crp["database"] == "HGNC"

# Agent tests with mocked services
@pytest.mark.asyncio
async def test_indra_query_agent_with_mesh():
    agent = INDRAQueryAgent()
    state = {
        "query": {"text": "How does PM2.5 affect CRP?"},
        "mesh_enriched_entities": [sample_enriched_entity],
    }
    result = await agent(state, {})
    assert "causal_graph" in result
    assert len(result["causal_graph"]["nodes"]) > 0

# Integration tests with cached responses
@pytest.mark.asyncio
async def test_full_workflow():
    graph = create_causal_discovery_graph()
    result = await graph.ainvoke({
        "request_id": "test-001",
        "query": {"text": "PM2.5 and inflammation"},
        "user_context": {"user_id": "test"},
    })
    assert result["next_agent"] == "END"
    assert result["causal_graph"] is not None
```

---

## Performance Characteristics

### Lobster
- **Latency**: Higher due to ReAct loop (multiple LLM calls per agent)
- **Token usage**: Higher (tool descriptions in every prompt)
- **Flexibility**: High (LLM can adapt strategy)
- **Predictability**: Lower (LLM-driven tool selection)
- **Scalability**: Horizontal (easy to add agents)

### INDRA
- **Latency**: Lower (direct service calls)
- **Token usage**: Lower (minimal prompts)
- **Flexibility**: Lower (fixed execution paths)
- **Predictability**: Higher (deterministic flow)
- **Scalability**: Vertical (optimize existing agents)

---

## Use Case Suitability

### Lobster Architecture Best For:
- **Exploratory workflows**: User doesn't know exact analysis steps
- **Interactive analysis**: Many back-and-forth exchanges
- **Complex decision trees**: Many possible analysis paths
- **Research environments**: Flexibility > predictability
- **Multi-domain problems**: Requires diverse expert agents
- **Long-running sessions**: Stateful workflows with checkpointing

### INDRA Architecture Best For:
- **Well-defined workflows**: Clear input → output pipelines
- **API services**: Predictable responses for applications
- **Performance-critical**: Minimize latency and token usage
- **Production environments**: Reliability > flexibility
- **Single-domain problems**: Narrow, deep expertise
- **Stateless requests**: Each query is independent

---

## Migration Recommendations

### To Adopt Lobster-Style Architecture in INDRA Agent:

1. **Add Agent Registry**:
```python
# config/agent_registry.py
AGENT_REGISTRY = {
    "mesh_enrichment": AgentConfig(
        name="mesh_enrichment",
        display_name="MeSH Semantic Enrichment Specialist",
        factory_function="indra_agent.agents.mesh_enrichment_agent:create_mesh_enrichment_agent",
        state_schema=MeshEnrichmentState,
    ),
    "indra_query_agent": AgentConfig(...),
    "web_researcher": AgentConfig(...),
}
```

2. **Convert Services to Tools**:
```python
@tool
def ground_entities(entity_names: List[str]) -> str:
    """
    Ground biological entities to database identifiers.

    Args:
        entity_names: List of entity names to ground

    Returns:
        JSON string with grounded entities
    """
    service = GroundingService()
    result = service.ground_entities(entity_names)
    return json.dumps(result)
```

3. **Use langgraph_supervisor**:
```python
from langgraph_supervisor import create_supervisor

workflow = create_supervisor(
    agents=[mesh_agent, indra_agent, web_agent],
    model=supervisor_model,
    prompt=supervisor_prompt,
    state_schema=OverallState,
)
```

4. **Add Configuration Layer**:
```python
class INDRAConfig(BaseModel):
    enable_mesh_enrichment: bool = True
    max_graph_depth: int = 4
    require_evidence_threshold: int = 20
```

### To Adopt INDRA-Style Simplicity in Lobster:

1. **Reduce Agent State Complexity**:
```python
# Simpler state schema
class SimpleAgentState(AgentState):
    next: str
    task_description: str
    result: Dict[str, Any]
```

2. **Direct Service Calls**:
```python
class SimplifiedSingleCellAgent:
    def __init__(self, data_manager):
        self.qc_service = QualityService()
        self.clustering_service = ClusteringService()

    async def __call__(self, state, config):
        # Direct service calls, no tool selection
        qc_result = self.qc_service.run_qc(...)
        clusters = self.clustering_service.cluster(...)
        return {"result": {"qc": qc_result, "clusters": clusters}}
```

3. **Hardcode Critical Paths**:
```python
# For common workflows, skip supervisor overhead
if query_type == "standard_scrnaseq":
    return await run_standard_scrna_pipeline(data_manager, query)
```

---

## Conclusion

Both architectures have merit:

**Lobster** prioritizes:
- **Extensibility**: Easy to add agents/tools
- **Discoverability**: LLM can explore capabilities
- **Flexibility**: Adapt to diverse user needs
- **Research**: Exploratory analysis

**INDRA** prioritizes:
- **Simplicity**: Easy to understand/debug
- **Performance**: Minimal overhead
- **Predictability**: Reliable outputs
- **Production**: API services

The choice depends on your requirements:
- **Complex, interactive workflows** → Lobster architecture
- **Well-defined, API-driven workflows** → INDRA architecture
- **Hybrid** → Start with INDRA simplicity, migrate to Lobster modularity as system grows

