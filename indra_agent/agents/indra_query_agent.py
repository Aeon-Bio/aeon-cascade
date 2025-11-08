"""INDRA query agent for causal path discovery."""

import json
import logging
from typing import Annotated, Any, Dict, List, Optional

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from indra_agent.agents.state import OverallState
from indra_agent.config.agent_config import INDRA_QUERY_AGENT_CONFIG
from indra_agent.config.settings import get_settings
from indra_agent.services.graph_builder import GraphBuilderService
from indra_agent.services.grounding_service import GroundingService
from indra_agent.services.indranet_service import IndraNetService

logger = logging.getLogger(__name__)


def create_indra_tools(progress_emitter=None, cache_namespace=None):
    """Create tools for INDRA query agent.

    Args:
        progress_emitter: Optional ProgressEmitter for real-time updates
        cache_namespace: Optional unique identifier for request-scoped caching.
                        If None, generates a new UUID. CRITICAL for preventing
                        race conditions when tools are reused across requests.

    Returns:
        List of LangChain tools for INDRA operations
    """
    import uuid

    # Generate unique cache namespace for this invocation (prevents race conditions)
    if cache_namespace is None:
        cache_namespace = str(uuid.uuid4())

    logger.info(f"Creating INDRA tools with cache namespace: {cache_namespace}")

    # Initialize services (shared across tool calls)
    # Create local ontology and grounding service once
    from indra_agent.services.local_ontology_adapter import LocalOntologyAdapter
    from indra_agent.services.scm_graph_builder import SCMGraphBuilder

    local_ontology = LocalOntologyAdapter()
    # Note: local_ontology.initialize() will be called lazily on first use
    grounding_service = GroundingService(local_ontology=local_ontology)

    # Pass grounding_service to IndraNetService (dependency injection)
    # This ensures all synonym expansion uses local ontology, not Writer KG
    indra_service = IndraNetService(grounding_service=grounding_service)

    graph_builder = GraphBuilderService()
    scm_builder = SCMGraphBuilder(indra_service)

    @tool
    async def ground_biological_entities(
        entities: Annotated[List[str], "List of biological entity names to ground to database IDs"]
    ) -> str:
        """Ground biological entities to standardized database identifiers.

        This tool maps entity names (like 'PM2.5', 'IL-6', 'CRP') to database IDs
        (MESH, HGNC, GO, CHEBI) that can be used to query INDRA.

        CRITICAL: Returns entity info with 'name' field containing INDRA-compatible names.
        The 'name' field should be used for find_causal_paths queries, NOT database IDs.

        Args:
            entities: List of biological entity names

        Returns:
            JSON string with grounded entities mapping. Each entity has:
            - id: Database ID (e.g., "MESH:D052638")
            - name: INDRA-compatible entity name (e.g., "Particulate Matter") ← USE THIS FOR QUERIES
            - type: Entity type (environmental, molecular, biomarker)
            - database: Database name (MESH, HGNC, etc.)
            - identifier: Database-specific ID
        """
        # Emit progress: Step 5 - Grounding entities (28%)
        if progress_emitter:
            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Grounding entities to INDRA database",
                progress_percent=28,
                phase="grounding",
                metadata={"entity_count": len(entities)}
            ):
                pass  # Grounding happens below

        try:
            # Ground entities using local ontology
            grounded = {}
            for entity in entities:
                # Get canonical name and MeSH ID from local ontology
                canonical_name = await grounding_service.get_canonical(entity)
                mesh_id = await grounding_service.get_mesh_id(entity)
                all_synonyms = await grounding_service.get_all_synonyms(entity)

                # Determine entity type (simplified heuristic)
                entity_type = "molecular"  # Default
                if mesh_id:
                    if entity.lower() in ["pm2.5", "particulate matter", "ozone", "pollution"]:
                        entity_type = "environmental"
                    elif entity.upper() in ["CRP", "IL-6", "TNF", "HBA1C"]:
                        entity_type = "biomarker"

                grounded[entity] = {
                    "id": f"MESH:{mesh_id}" if mesh_id else None,
                    "name": canonical_name,  # USE THIS FOR INDRA QUERIES
                    "type": entity_type,
                    "database": "MESH" if mesh_id else "UNKNOWN",
                    "identifier": mesh_id,
                    "synonyms": all_synonyms
                }

            return json.dumps({
                "status": "success",
                "grounded_entities": grounded,
                "count": len([e for e in grounded.values() if e])
            })
        except Exception as e:
            logger.error(f"Entity grounding failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    # Store network result for subsequent build_causal_graph call
    network_result_cache = {}

    @tool
    async def find_causal_paths(
        source_entity: Annotated[str, "Source entity NAME (e.g., 'Particulate Matter', 'CRP'). NEVER use database IDs like 'MESH:D052638'"],
        target_entity: Annotated[str, "Target entity NAME (e.g., 'C-Reactive Protein', 'Interleukin-6'). NEVER use database IDs like 'HGNC:2367'"],
        max_depth: Annotated[int, "Maximum path depth to search"] = 2
    ) -> str:
        """Build biomarker network between source and target entities using INDRA Python library.

        This uses INDRA's comprehensive biomarker network building to discover
        mechanistic pathways connecting a source (like an environmental exposure)
        to a target (like a biomarker).

        Strategy:
        1. Get neighborhoods of biomarker (1-2 hops)
        2. Get exposure → biomarker paths (up to 3 hops)
        3. Merge duplicates via preassembly
        4. Build signed NetworkX graph with belief scores

        ⚠️ CRITICAL: You MUST pass entity NAMES, not database IDs.

        CORRECT USAGE:
          ✅ find_causal_paths("Particulate Matter", "C-Reactive Protein")
          ✅ find_causal_paths("Interleukin-6", "CRP")

        INCORRECT USAGE:
          ❌ find_causal_paths("MESH:D052638", "HGNC:2367")  # Database IDs will fail!
          ❌ find_causal_paths("HGNC:6018", "HGNC:2367")     # Database IDs will fail!

        Args:
            source_entity: Entity NAME (e.g., "Particulate Matter", "IL-6")
            target_entity: Entity NAME (e.g., "C-Reactive Protein", "CRP")
            max_depth: Maximum neighborhood depth (default: 2)

        Returns:
            JSON string with network statistics and metadata
        """
        # Emit progress: Step 6 - Querying INDRA (48%)
        if progress_emitter:
            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Building biomarker network from INDRA",
                progress_percent=48,
                phase="discovery"
            ):
                pass  # Query happens below

        try:
            # Build comprehensive biomarker network
            network_result = await indra_service.build_biomarker_network(
                exposures=[source_entity],
                biomarkers=[target_entity],
                max_depth=max_depth,
                belief_threshold=0.5
            )

            # Cache result for subsequent build_causal_graph call
            # Use namespace to prevent race conditions across concurrent requests
            cache_key = f"{cache_namespace}:{source_entity}:{target_entity}"
            network_result_cache[cache_key] = network_result

            logger.info(
                f"Built biomarker network: {len(network_result.node_names)} nodes, "
                f"{network_result.edge_count} edges"
            )

            return json.dumps({
                "status": "success",
                "num_nodes": len(network_result.node_names),
                "num_edges": network_result.edge_count,
                "num_statements": len(network_result.statements),
                "node_names": network_result.node_names,
                "cache_key": cache_key,  # For build_causal_graph to retrieve
                "total_evidence": sum(
                    count for count in network_result.evidence_counts.values()
                )
            })
        except Exception as e:
            logger.error(f"Biomarker network building failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def build_causal_graph(
        network_result_json: Annotated[str, "JSON string from find_causal_paths containing cache_key"],
        genetics_json: Annotated[str, "JSON string of genetic context"] = "{}"
    ) -> str:
        """Build a structured causal graph from INDRA biomarker network.

        This constructs a graph representation with nodes, edges, effect sizes,
        temporal lags, and genetic modifiers from the cached IndraNetworkResult.

        Args:
            network_result_json: JSON string from find_causal_paths (contains cache_key)
            genetics_json: JSON string with genetic variants

        Returns:
            JSON string with causal graph structure
        """
        # Emit progress: Step 8 - Building graph (65%)
        if progress_emitter:
            async with progress_emitter.step(
                agent="indra_query_agent",
                action="Building causal graph from network",
                progress_percent=65,
                phase="synthesis"
            ):
                pass  # Graph building happens below

        try:
            network_data = json.loads(network_result_json)

            # Check if network building failed
            if network_data.get("status") == "error":
                return json.dumps({
                    "status": "error",
                    "error": f"Network building failed: {network_data.get('error', 'Unknown error')}"
                })

            # Get cached network result
            cache_key = network_data.get("cache_key")
            if not cache_key or cache_key not in network_result_cache:
                return json.dumps({
                    "status": "error",
                    "error": "Network result not found in cache. Call find_causal_paths first."
                })

            network_result = network_result_cache[cache_key]

            # NOTE: Empty graphs (0 edges) are valid - continue processing
            # The test suite expects status="success" even with empty graphs

            genetics = json.loads(genetics_json)

            # Build causal graph from IndraNetworkResult
            causal_graph = graph_builder.build_causal_graph_from_indranet(
                indranet_result=network_result,
                genetics=genetics,
                effect_modifiers=None
            )

            return json.dumps({
                "status": "success",
                "causal_graph": causal_graph.model_dump(),
                "num_nodes": len(causal_graph.nodes),
                "num_edges": len(causal_graph.edges)
            })
        except Exception as e:
            logger.error(f"Graph building failed: {e}", exc_info=True)
            return json.dumps({"status": "error", "error": str(e)})

    @tool
    async def build_scm_graph(
        sources: Annotated[List[str], "List of SOURCE entities (e.g., ['PM2.5', 'insulin resistance', 'inflammation'])"],
        targets: Annotated[Optional[List[str]], "Optional list of TARGET biomarkers (e.g., ['CRP', 'IL-6']). If omitted, targets are discovered automatically."] = None,
        known_mediators: Annotated[List[str], "Optional list of known mediators (e.g., ['NF-κB', 'oxidative_stress'])"] = None,
        genetics_json: Annotated[str, "JSON string of genetic context from state['user_context']['genetics']"] = "{}",
        user_biomarkers_json: Annotated[str, "JSON string of user's tracked biomarkers from state['user_context']['current_biomarkers'] or state['query']['focus_biomarkers']"] = "{}"
    ) -> str:
        """Build SCM graph connecting sources to biomarker targets using target-less discovery.

        This is the PRIMARY tool for causal discovery. It uses iterative INDRA discovery
        with biological priors to build comprehensive causal graphs.

        NEW: Target-less Discovery (Recommended)
        =========================================
        When targets are NOT provided (omitted or None):
        1. System discovers downstream biomarker targets from sources using INDRA multi_interactors API
        2. Filters discovered entities to:
           a. FIRST: User's tracked biomarkers (from user_biomarkers_json)
           b. SECOND: Known biomarkers (CRP, IL-6, TNF, HbA1c, etc.)
        3. Builds causal paths: sources → discovered_biomarkers

        This PREVENTS self-loop queries that cause INDRA API 500 errors.

        ⚠️ IMPORTANT: Do NOT extract the same entities for both sources and targets.
        ✅ CORRECT: sources=['insulin resistance', 'inflammation'], targets=None, user_biomarkers_json='["CRP", "IL-6"]'
        ✅ CORRECT: sources=['PM2.5'], targets=None
        ❌ WRONG: sources=['insulin resistance'], targets=['insulin resistance'] (self-loop!)

        Traditional Strategy (when targets ARE provided):
        1. For each (source, target) pair, find connecting paths via INDRA
        2. If INDRA fails, expand via known biological mediators
        3. Apply biological priors as fallback
        4. Merge all paths into unified graph

        Use this tool when:
        - You have environmental exposures (PM2.5, ozone, insulin resistance)
        - You want to discover relevant biomarkers (targets=None recommended)
        - You want to discover shared mechanisms
        - Direct path search fails

        Args:
            sources: Environmental/exposure entities or intermediate mechanisms
            targets: Optional biomarker entities. If None, discovers targets automatically (RECOMMENDED)
            known_mediators: Optional mediators to prioritize (defaults to standard list)
            genetics_json: JSON string with genetic variants from state['user_context']['genetics']
            user_biomarkers_json: JSON string with user's tracked biomarkers. Extract from state['user_context']['current_biomarkers'].keys() or state['query']['focus_biomarkers']

        Returns:
            JSON string with SCM graph structure
        """
        try:
            logger.info(f"Building SCM graph: {sources} → {targets}")

            # Extract user biomarkers from JSON
            try:
                user_biomarkers_data = json.loads(user_biomarkers_json)
                # user_biomarkers_json can be either a list of biomarkers or a dict (from current_biomarkers)
                if isinstance(user_biomarkers_data, dict):
                    # Extract keys if it's a dict like {"CRP": 5.2, "IL-6": 3.8}
                    user_biomarkers = list(user_biomarkers_data.keys())
                elif isinstance(user_biomarkers_data, list):
                    # Already a list like ["CRP", "IL-6"]
                    user_biomarkers = user_biomarkers_data
                else:
                    user_biomarkers = None
            except (json.JSONDecodeError, TypeError):
                user_biomarkers = None

            if user_biomarkers:
                logger.info(f"Using {len(user_biomarkers)} user-tracked biomarkers: {user_biomarkers}")

            # Build SCM graph via iterative discovery (progress emitted from within)
            # INTERFACE CONTRACT: Returns Tuple[List[Dict], Optional[FailureMode]]
            paths, failure_mode = await scm_builder.build_scm_graph(
                sources=sources,
                targets=targets,
                user_biomarkers=user_biomarkers,
                known_mediators=known_mediators,
                max_depth=4,
                use_priors=True,
                progress_emitter=progress_emitter  # Pass through for streaming progress
            )

            if not paths:
                # Use transparent failure mode if available
                error_message = "No paths found connecting sources to targets (tried INDRA + priors)"
                if failure_mode:
                    # Include failure mode explanation
                    error_message = failure_mode.to_user_message()

                return json.dumps({
                    "status": "error",
                    "error": error_message,
                    "failure_reason": failure_mode.reason.value if failure_mode else None,
                    "discovery_attempts": [
                        {
                            "phase": attempt.phase,
                            "query": attempt.query,
                            "result": attempt.result,
                            "duration_ms": attempt.duration_ms,
                            "success": attempt.success
                        }
                        for attempt in (failure_mode.discovery_attempts if failure_mode else [])
                    ],
                    "suggestions": failure_mode.suggestions if failure_mode else []
                })

            # Rank paths
            ranked_paths = indra_service.rank_paths(paths)
            logger.info(f"Built SCM with {len(ranked_paths)} paths")

            # Emit progress: Step 6 - Building graph (65%)
            genetics = json.loads(genetics_json)
            if progress_emitter:
                async with progress_emitter.step(
                    agent="indra_query_agent",
                    action="Building causal graph from top paths",
                    progress_percent=65,
                    phase="synthesis",
                    metadata={"path_count": len(ranked_paths)}
                ):
                    # Build causal graph from ranked paths
                    causal_graph = graph_builder.build_causal_graph(
                        paths=ranked_paths[:5],  # Top 5 paths
                        genetics=genetics
                    )
            else:
                # No progress tracking
                causal_graph = graph_builder.build_causal_graph(
                    paths=ranked_paths[:5],  # Top 5 paths
                    genetics=genetics
                )

            return json.dumps({
                "status": "success",
                "causal_graph": causal_graph.model_dump(),
                "num_nodes": len(causal_graph.nodes),
                "num_edges": len(causal_graph.edges),
                "num_paths": len(ranked_paths),
                "paths": ranked_paths[:10]  # Return top 10 for metadata
            })

        except Exception as e:
            logger.error(f"SCM graph building failed: {e}")
            return json.dumps({"status": "error", "error": str(e)})

    return [ground_biological_entities, find_causal_paths, build_causal_graph, build_scm_graph]


async def _extract_tool_results_to_state(state: OverallState) -> Dict:
    """Extract tool results from messages and update state.

    This bridges the gap between ReAct agent tool results (in messages)
    and the shared state that other agents and the supervisor need.

    Args:
        state: Current state with messages from ReAct agent

    Returns:
        State updates dict with extracted causal_graph and indra_paths
    """
    from langchain_core.messages import ToolMessage
    import json

    messages = state.get("messages", [])

    # Find the most recent build_causal_graph tool result
    causal_graph = None
    indra_paths = []

    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            try:
                result = json.loads(msg.content)

                # Extract causal graph from build_causal_graph tool
                if result.get("status") == "success" and "causal_graph" in result:
                    causal_graph = result["causal_graph"]
                    logger.info(f"Extracted causal_graph with {result.get('num_nodes', 0)} nodes from tool results")

                # Extract paths from find_causal_paths tool
                if result.get("status") == "success" and "paths" in result:
                    indra_paths = result["paths"]
                    logger.info(f"Extracted {len(indra_paths)} INDRA paths from tool results")

            except (json.JSONDecodeError, AttributeError):
                continue

    # Return state updates
    updates = {}
    if causal_graph:
        updates["causal_graph"] = causal_graph
    if indra_paths:
        updates["indra_paths"] = indra_paths

    return updates


async def _indra_agent_node(state: OverallState, config: RunnableConfig) -> Dict:
    """INDRA agent node that extracts tool results to state.

    This wrapper runs the ReAct agent and then extracts causal_graph and indra_paths
    from the agent's own ToolMessages, updating the shared state.

    Args:
        state: Current state
        config: Runnable configuration

    Returns:
        State updates with messages, causal_graph, and indra_paths
    """
    from langchain_core.messages import ToolMessage

    settings = get_settings()
    agent_config = INDRA_QUERY_AGENT_CONFIG

    # Initialize LLM
    llm = ChatBedrock(
        model_id=settings.agent_model,
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        model_kwargs={"temperature": agent_config.temperature},
    )

    # Get progress emitter from config (not state - causes pickle errors)
    progress_emitter = config.get("configurable", {}).get("progress_emitter")
    logger.info(f"INDRA agent _indra_agent_node: progress_emitter exists? {progress_emitter is not None}")

    # Get INDRA tools with progress emitter
    indra_tools = create_indra_tools(progress_emitter=progress_emitter)

    # Get handoff tools from config if available
    handoff_tools = config.get("configurable", {}).get("handoff_tools", [])
    all_tools = indra_tools + handoff_tools

    # Create ReAct agent
    agent = create_react_agent(
        model=llm,
        tools=all_tools,
        state_schema=OverallState,
        prompt=agent_config.system_prompt,
    )

    # Run the agent
    result = await agent.ainvoke(state, config)

    # Extract tool results from the agent's messages
    causal_graph = None
    indra_paths = []

    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, ToolMessage):
            # Skip handoff messages
            if "transfer" in msg.content.lower():
                continue

            try:
                parsed = json.loads(msg.content)

                if parsed.get("status") == "success" and "causal_graph" in parsed and not causal_graph:
                    causal_graph = parsed["causal_graph"]
                    logger.info(f"✅ Extracted causal_graph with {len(causal_graph.get('nodes', []))} nodes")

                    # Emit progress: Agent analysis complete (85%)
                    if progress_emitter:
                        async with progress_emitter.step(
                            agent="indra_query_agent",
                            action="Analyzing causal relationships",
                            progress_percent=85,
                            phase="synthesis"
                        ):
                            pass  # Just mark completion

                if parsed.get("status") == "success" and "paths" in parsed and not indra_paths:
                    indra_paths = parsed["paths"]
                    logger.info(f"✅ Extracted {len(indra_paths)} INDRA paths")

            except (json.JSONDecodeError, AttributeError, KeyError):
                continue

    # Build return dict with messages and extracted state
    updates = {"messages": result.get("messages", [])}
    if causal_graph:
        updates["causal_graph"] = causal_graph
    if indra_paths:
        updates["indra_paths"] = indra_paths

        # Generate metadata from indra_paths
        total_evidence = sum(
            sum(edge.get("evidence_count", 0) for edge in path.get("edges", []))
            for path in indra_paths
        )

        from indra_agent.core.models import Metadata
        import time

        # Calculate query time (approximate - just for the INDRA agent portion)
        query_time_ms = 0  # Will be updated by client if needed

        metadata = Metadata(
            query_time_ms=query_time_ms,
            indra_paths_explored=len(indra_paths),
            total_evidence_papers=total_evidence
        )

        updates["metadata"] = metadata.model_dump()
        logger.info(f"✅ Generated metadata: {len(indra_paths)} paths, {total_evidence} evidence papers")

    return updates


async def create_indra_query_agent(handoff_tools=None):
    """Create INDRA query agent with state extraction.

    Args:
        handoff_tools: Optional list of handoff tools for delegation

    Returns:
        RunnableLambda wrapping agent node that returns extracted state
    """
    # Store handoff tools in a closure
    async def indra_agent_with_handoffs(state: OverallState, config: RunnableConfig) -> Dict:
        # Inject handoff tools into config
        if handoff_tools:
            config = config or {}
            if "configurable" not in config:
                config["configurable"] = {}
            config["configurable"]["handoff_tools"] = handoff_tools

        return await _indra_agent_node(state, config)

    # Wrap in RunnableLambda for .ainvoke() compatibility with langgraph_supervisor
    runnable = RunnableLambda(indra_agent_with_handoffs)
    # Set name attribute for langgraph_supervisor
    runnable.name = "indra_query_agent"

    logger.info("INDRA query agent created with state extraction")
    return runnable
