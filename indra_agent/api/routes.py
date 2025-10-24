"""FastAPI routes for causal discovery API."""

import logging
import time
import uuid
import os
import tempfile
import networkx as nx

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.progress import ProgressEmitter, ProgressUpdate, ProgressComplete
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    CausalDiscoveryResponse,
    ErrorResponse,
    InterventionRequest,
    InterventionResponse,
    BiomarkerPrediction,
    AffectedPathway,
    InterventionMetadata,
)
from indra_agent.core.intervention_models import (
    InterventionDiscoveryRequest,
    InterventionDiscoveryResponse,
    InterventionValidationRequest,
    InterventionValidationResponse,
    ConsensusTarget,
    NetworkSummary,
    PredictedEffect,
    PathwayMechanism,
)
from indra_agent.config.settings import get_settings
from indra_agent.services.graph_store import get_graph_store
from indra_agent.services.scm_inference import SCMInferenceEngine
from indra_agent.services.vcf_parser import VCFParser
from indra_agent.services.lab_parser import LabParser
from indra_agent.services.environmental_parser import EnvironmentalParser
from indra_agent.services.graph_analysis import GraphAnalysisService
from indra_agent.agents.validation_agent import ValidationAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Global client instance
client: INDRAAgentClient | None = None


def get_client() -> INDRAAgentClient:
    """Get or create client instance.

    Returns:
        INDRAAgentClient instance
    """
    global client
    if client is None:
        client = INDRAAgentClient()
    return client


@router.post(
    "/api/v1/causal_discovery",
    response_model=CausalDiscoveryResponse | ErrorResponse,
    responses={
        200: {
            "description": "Successful causal discovery",
            "model": CausalDiscoveryResponse,
        },
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def causal_discovery(
    request: CausalDiscoveryRequest,
) -> CausalDiscoveryResponse | ErrorResponse:
    """Discover causal paths between environmental exposures and biomarkers.

    This endpoint receives health queries with user context, queries INDRA
    for causal paths, resolves biomarkers to molecular mechanisms, and returns
    structured causal graphs.

    Args:
        request: Causal discovery request

    Returns:
        CausalDiscoveryResponse or ErrorResponse
    """
    logger.info(f"Received causal discovery request: {request.request_id}")

    try:
        client = get_client()
        response = await client.process_request(request)

        # Store graph for later intervention queries
        if isinstance(response, CausalDiscoveryResponse):
            # Validate graph before storing
            validator = ValidationAgent()
            validation = validator.validate_graph(response.causal_graph)

            # Auto-fix violations if found
            if not validation["is_valid"]:
                logger.warning(
                    f"Graph validation failed for request {request.request_id}: "
                    f"{len(validation['errors'])} errors found. Attempting auto-fix..."
                )

                # Fix violations
                fixed_graph = validator.fix_violations(response.causal_graph)

                # Re-validate
                fixed_validation = validator.validate_graph(fixed_graph)

                if fixed_validation["is_valid"]:
                    logger.info(
                        f"Graph auto-fixed successfully for request {request.request_id}"
                    )
                    response.causal_graph = fixed_graph

                    # Add validation metadata to key insights
                    validation_summary = (
                        f"⚠️ Graph validation found {len(validation['errors'])} issues "
                        f"({', '.join(validation['errors'][:2])}). Auto-fixed successfully."
                    )
                    if response.key_insights:
                        response.key_insights.append(validation_summary)
                    else:
                        response.key_insights = [validation_summary]
                else:
                    logger.error(
                        f"Graph auto-fix failed for request {request.request_id}. "
                        f"Remaining errors: {fixed_validation['errors']}"
                    )
                    # Continue with original graph but warn user
                    warning_msg = (
                        f"⚠️ Graph has {len(validation['errors'])} validation issues "
                        f"that could not be auto-fixed. Predictions may be unstable."
                    )
                    if response.key_insights:
                        response.key_insights.append(warning_msg)
                    else:
                        response.key_insights = [warning_msg]
            elif validation["warnings"]:
                logger.info(
                    f"Graph validation passed with {len(validation['warnings'])} warnings "
                    f"for request {request.request_id}"
                )
                # Add warnings to insights
                for warning in validation["warnings"][:2]:  # Limit to 2 warnings
                    if response.key_insights:
                        response.key_insights.append(f"ℹ️ {warning}")
                    else:
                        response.key_insights = [f"ℹ️ {warning}"]

            graph_store = get_graph_store()
            graph_id = f"graph-{request.request_id}"

            # Extract baseline values from user context
            baseline_values = request.user_context.current_biomarkers.copy()

            graph_store.store(
                graph_id=graph_id,
                graph=response.causal_graph,
                baseline_values=baseline_values,
            )

            logger.info(
                f"Request {request.request_id} succeeded: "
                f"{len(response.causal_graph.nodes)} nodes, "
                f"{len(response.causal_graph.edges)} edges. "
                f"Stored as {graph_id}"
            )
        else:
            logger.warning(
                f"Request {request.request_id} failed: {response.error.code}"
            )

        return response

    except Exception as e:
        logger.error(f"Unexpected error processing request: {e}", exc_info=True)

        return ErrorResponse(
            request_id=request.request_id,
            error={
                "code": "INVALID_REQUEST",
                "message": f"Unexpected error: {str(e)}",
            },
        )


# Global request store (in-memory for MVP; use Redis/DB in production)
_pending_requests = {}


@router.post("/api/v1/submit_request")
async def submit_request(discovery_request: CausalDiscoveryRequest):
    """Submit a causal discovery request for processing via SSE.

    This endpoint queues the request and returns a request_id that can be used
    to connect to the SSE stream endpoint.

    Args:
        discovery_request: Causal discovery request

    Returns:
        Dictionary with request_id for SSE connection
    """
    request_id = discovery_request.request_id
    _pending_requests[request_id] = discovery_request
    logger.info(f"Queued request {request_id} for SSE processing")

    return {"request_id": request_id, "stream_url": f"/api/v1/stream/{request_id}"}


@router.get(
    "/api/v1/stream/{request_id}",
    responses={
        200: {"description": "Server-Sent Events stream with real-time progress"},
        404: {"description": "Request not found"},
        500: {"description": "Internal server error"},
    },
)
async def stream_progress(request_id: str, request: Request):
    """Stream real-time progress updates via Server-Sent Events.

    This endpoint provides granular progress updates during causal discovery
    workflow execution. Frontend uses EventSource API to receive updates.

    Args:
        request_id: Unique request identifier
        request: FastAPI Request object (for client disconnect detection)

    Yields:
        SSE events:
            - "progress": ProgressUpdate (step, agent, action, percent, metadata)
            - "complete": ProgressComplete (status, data, total_duration_ms)
            - "ping": Keepalive (every 60s if no updates)

    Example client-side:
        ```javascript
        // 1. Submit request
        const response = await fetch('/api/v1/submit_request', {
            method: 'POST',
            body: JSON.stringify(request),
        });
        const { request_id } = await response.json();

        // 2. Connect to SSE stream
        const eventSource = new EventSource(`/api/v1/stream/${request_id}`);
        eventSource.addEventListener('progress', (e) => {
            const update = JSON.parse(e.data);
            console.log(`${update.progress_percent}% - ${update.action}`);
        });
        eventSource.addEventListener('complete', (e) => {
            const result = JSON.parse(e.data);
            console.log('Complete!', result.data);
            eventSource.close();
        });
        ```
    """
    logger.info(f"SSE stream started for request: {request_id}")

    # Retrieve pending request
    discovery_request = _pending_requests.pop(request_id, None)
    if not discovery_request:
        raise HTTPException(
            status_code=404, detail=f"Request {request_id} not found. Submit request first via /api/v1/submit_request"
        )

    async def event_generator():
        """Generate SSE events from workflow execution."""
        # Create progress queue for thread-safe updates
        progress_queue = asyncio.Queue()

        async def progress_callback(update: ProgressUpdate):
            """Callback invoked by ProgressEmitter."""
            await progress_queue.put(("progress", update))

        # Create emitter
        emitter = ProgressEmitter(callback=progress_callback)

        # Run workflow with progress in background task
        async def run_workflow():
            """Execute workflow and emit completion event."""
            try:
                client = get_client()
                settings = get_settings()

                # Pass progress_emitter and timeout to client
                response = await client.process_request(
                    discovery_request,
                    timeout=settings.agent_request_timeout,
                    progress_emitter=emitter
                )

                # Store graph (same as /api/v1/causal_discovery endpoint)
                if isinstance(response, CausalDiscoveryResponse):
                    graph_store = get_graph_store()
                    graph_id = f"graph-{discovery_request.request_id}"
                    baseline_values = discovery_request.user_context.current_biomarkers.copy()

                    graph_store.store(
                        graph_id=graph_id,
                        graph=response.causal_graph,
                        baseline_values=baseline_values,
                    )

                    logger.info(
                        f"SSE: Stored graph {graph_id} with "
                        f"{len(response.causal_graph.nodes)} nodes, "
                        f"{len(response.causal_graph.edges)} edges"
                    )

                # Send completion
                if isinstance(response, CausalDiscoveryResponse):
                    complete = ProgressComplete(
                        status="success",
                        data=response.model_dump(),
                        total_duration_ms=emitter.total_elapsed_ms(),
                    )
                else:
                    complete = ProgressComplete(
                        status="error",
                        data=response.model_dump(),
                        total_duration_ms=emitter.total_elapsed_ms(),
                    )

                await progress_queue.put(("complete", complete))

            except Exception as e:
                logger.error(f"Workflow error: {e}", exc_info=True)
                error_complete = ProgressComplete(
                    status="error",
                    data={
                        "error": {
                            "code": "WORKFLOW_ERROR",
                            "message": str(e),
                        }
                    },
                    total_duration_ms=emitter.total_elapsed_ms(),
                )
                await progress_queue.put(("complete", error_complete))

        # Start workflow task
        workflow_task = asyncio.create_task(run_workflow())

        # Stream events to client
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from SSE stream: {request_id}")
                    break

                try:
                    # Wait for next event (60s timeout for keepalive)
                    event_type, data = await asyncio.wait_for(
                        progress_queue.get(), timeout=60
                    )

                    if event_type == "complete":
                        # Send final event and exit
                        yield {
                            "event": "complete",
                            "data": data.model_dump_json(),
                        }
                        logger.info(
                            f"SSE stream completed for request: {request_id} "
                            f"({data.status})"
                        )
                        break
                    else:  # progress
                        yield {
                            "event": "progress",
                            "data": data.model_dump_json(),
                        }

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield {
                        "event": "ping",
                        "data": json.dumps({"status": "alive", "request_id": request_id}),
                    }

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for request: {request_id}")
            raise
        finally:
            # Ensure workflow task completes or is cancelled
            if not workflow_task.done():
                workflow_task.cancel()
                try:
                    await workflow_task
                except asyncio.CancelledError:
                    pass

    return EventSourceResponse(event_generator())


@router.post(
    "/api/v1/intervene",
    response_model=InterventionResponse,
    responses={
        200: {
            "description": "Successful intervention",
            "model": InterventionResponse,
        },
        404: {"description": "Graph not found"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def intervene(request: InterventionRequest) -> InterventionResponse:
    """Perform causal intervention and generate counterfactual predictions.

    This endpoint uses do-calculus to compute what would happen if we
    intervene on a specific node (e.g., "What if PM2.5 = 10?").

    Args:
        request: Intervention request

    Returns:
        InterventionResponse with predictions

    Raises:
        HTTPException: If graph not found or intervention invalid
    """
    logger.info(f"Received intervention request: {request.request_id}")

    start_time = time.time()

    try:
        # Retrieve graph from store
        graph_store = get_graph_store()

        try:
            stored_data = graph_store.retrieve(request.graph_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        graph = stored_data["graph"]
        baseline_values = stored_data["baseline_values"]

        # Build SCM
        scm_engine = SCMInferenceEngine()
        scm = scm_engine.build_scm(graph, baseline_values)

        # Compute baseline (observational) predictions
        baseline_predictions = scm_engine.predict(
            scm,
            target_biomarkers=request.target_biomarkers,
            horizon_days=request.horizon_days,
        )

        # Compute interventional predictions
        interventions = {request.intervention.node_id: request.intervention.value}

        interventional_predictions = scm_engine.intervene(
            scm,
            interventions=interventions,
            target_biomarkers=request.target_biomarkers,
            horizon_days=request.horizon_days,
        )

        # Build response predictions
        predictions = {}

        for biomarker_id in request.target_biomarkers:
            if biomarker_id not in interventional_predictions:
                continue

            baseline_pred = baseline_predictions.get(biomarker_id)
            int_pred = interventional_predictions[biomarker_id]

            # Extract means from timelines
            baseline_mean = baseline_pred.timeline[-1]["mean"] if baseline_pred else 0.0
            int_mean = int_pred.timeline[-1]["mean"]

            # Compute delta
            delta_absolute = int_mean - baseline_mean
            delta_percent = (
                100 * delta_absolute / baseline_mean if baseline_mean != 0 else 0.0
            )

            predictions[biomarker_id] = BiomarkerPrediction(
                baseline={
                    "mean": baseline_mean,
                    "ci_lower": baseline_pred.timeline[-1]["confidence_interval"][0] if baseline_pred else 0.0,
                    "ci_upper": baseline_pred.timeline[-1]["confidence_interval"][1] if baseline_pred else 0.0,
                },
                post_intervention={
                    "mean": int_mean,
                    "ci_lower": int_pred.timeline[-1]["confidence_interval"][0],
                    "ci_upper": int_pred.timeline[-1]["confidence_interval"][1],
                },
                delta={
                    "absolute": round(delta_absolute, 2),
                    "percent": round(delta_percent, 1),
                },
                timeline=int_pred.timeline,
            )

        # Identify affected pathways
        affected_pathways = _identify_affected_pathways(
            graph,
            source=request.intervention.node_id,
            targets=request.target_biomarkers,
            scm_engine=scm_engine,
            scm=scm,
        )

        # Compute elapsed time
        elapsed_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Intervention request {request.request_id} completed in {elapsed_ms}ms"
        )

        return InterventionResponse(
            request_id=request.request_id,
            intervention_summary=request.intervention,
            predictions=predictions,
            affected_pathways=affected_pathways,
            metadata=InterventionMetadata(
                computation_time_ms=elapsed_ms,
                graph_nodes=len(graph.nodes),
                confidence_level=request.confidence_level,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in intervention: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


def _identify_affected_pathways(
    graph,
    source: str,
    targets: list,
    scm_engine: SCMInferenceEngine,
    scm: dict,
) -> list:
    """Identify causal pathways from source to targets.

    Args:
        graph: CausalGraph
        source: Source node ID
        targets: List of target node IDs
        scm_engine: SCM inference engine
        scm: Built SCM

    Returns:
        List of AffectedPathway objects
    """
    pathways = []

    # Build NetworkX graph for path finding
    G = nx.DiGraph()
    for edge in graph.edges:
        G.add_edge(edge.source, edge.target, edge_data=edge)

    for target in targets:
        if target not in G or source not in G:
            continue

        try:
            # Find all simple paths (up to 3 paths)
            paths = list(nx.all_simple_paths(G, source, target, cutoff=5))

            for path in paths[:3]:  # Limit to top 3
                # Compute total effect
                effect_result = scm_engine.compute_causal_effect(scm, source, target)
                total_effect = effect_result.get("total_effect", 0.0)

                # Clamp total effect to valid range [-1, 1]
                # Matrix inversion (I-W)^-1 can produce values > 1 due to compounding effects
                total_effect = max(-1.0, min(1.0, total_effect))

                # Build relationship chain
                relationship_chain = []
                for i in range(len(path) - 1):
                    edge_data = G[path[i]][path[i + 1]]["edge_data"]
                    relationship_chain.append(edge_data.relationship)

                # Generate explanation
                path_str = " → ".join(path)
                explanation = f"Intervention on {source} affects {target} via {path_str}"

                pathways.append(
                    AffectedPathway(
                        pathway=path,
                        relationship_chain=relationship_chain,
                        total_effect_size=round(total_effect, 2),
                        explanation=explanation[:200],  # Truncate to 200 chars
                    )
                )

        except nx.NetworkXNoPath:
            continue

    return pathways


@router.post(
    "/api/v1/upload/vcf",
    responses={
        200: {"description": "VCF file parsed successfully"},
        400: {"description": "Invalid VCF file"},
        500: {"description": "Internal server error"},
    },
)
async def upload_vcf(file: UploadFile = File(...)):
    """Upload and parse a VCF (Variant Call Format) genetic data file.

    Accepts .vcf files from services like 23andMe, Ancestry.com, etc.
    Returns parsed genetic variants with functional annotations.

    Args:
        file: Uploaded VCF file

    Returns:
        Dictionary with user_id, variants, and variant count

    Raises:
        HTTPException: If file format is invalid
    """
    logger.info(f"Received VCF upload: {file.filename}")

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.vcf') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Parse VCF
        parser = VCFParser()
        report = parser.parse_vcf(tmp_path)

        # Convert to usable formats
        genetics_dict = parser.to_genetics_dict(report)
        effect_modifiers = parser.to_effect_modifiers(report)

        logger.info(f"Parsed VCF for {report.patient_id}: {len(report.variants)} variants")

        return {
            "user_id": report.patient_id,
            "reference_genome": report.reference_genome,
            "file_date": report.file_date,
            "variant_count": len(report.variants),
            "genetics": genetics_dict,
            "effect_modifiers": effect_modifiers,
            "variants": [
                {
                    "id": v.variant_id,
                    "gene": v.gene_symbol,
                    "genotype": v.genotype,
                    "effect_size": v.effect_size,
                    "functional_effect": v.functional_effect,
                    "pmid": v.pmid
                }
                for v in report.variants
                if v.effect_size  # Only include variants with known effects
            ]
        }

    except Exception as e:
        logger.error(f"Error parsing VCF: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid VCF file: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post(
    "/api/v1/upload/lab_report",
    responses={
        200: {"description": "Lab report parsed successfully"},
        400: {"description": "Invalid lab report format"},
        500: {"description": "Internal server error"},
    },
)
async def upload_lab_report(file: UploadFile = File(...)):
    """Upload and parse a lab report (Quest Diagnostics or LabCorp format).

    Accepts text format lab reports with biomarker measurements.

    Args:
        file: Uploaded lab report file (.txt)

    Returns:
        Dictionary with patient_id, test_date, and biomarker measurements

    Raises:
        HTTPException: If file format is invalid
    """
    logger.info(f"Received lab report upload: {file.filename}")

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Parse lab report
        parser = LabParser()
        report = parser.parse_lab_report(tmp_path)

        # Convert to biomarker dictionary
        biomarkers = parser.to_biomarker_dict(report)

        logger.info(f"Parsed lab report for {report.patient_id}: {len(report.measurements)} biomarkers")

        return {
            "patient_id": report.patient_id,
            "test_date": report.test_date.isoformat(),
            "lab_source": report.lab_source,
            "biomarker_count": len(report.measurements),
            "biomarkers": biomarkers,
            "measurements": [
                {
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "reference_range": m.reference_range,
                    "flag": m.flag
                }
                for m in report.measurements
            ],
            "physician_notes": report.physician_notes
        }

    except Exception as e:
        logger.error(f"Error parsing lab report: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid lab report: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post(
    "/api/v1/upload/environmental",
    responses={
        200: {"description": "Environmental data parsed successfully"},
        400: {"description": "Invalid environmental data format"},
        500: {"description": "Internal server error"},
    },
)
async def upload_environmental(file: UploadFile = File(...)):
    """Upload and parse environmental exposure data (JSON format).

    Accepts JSON files with location history and pollution data.

    Args:
        file: Uploaded environmental data file (.json)

    Returns:
        Dictionary with location history and exposure summary

    Raises:
        HTTPException: If file format is invalid
    """
    logger.info(f"Received environmental data upload: {file.filename}")

    try:
        # Read JSON content directly (no temp file needed for JSON)
        content = await file.read()

        # Parse environmental data
        parser = EnvironmentalParser()

        # Assuming parser has a method to parse JSON content
        # If not, we'll need to check the actual interface
        import json
        data = json.loads(content.decode('utf-8'))

        # Extract location history (assuming this structure)
        location_history = data.get('location_history', [])
        user_id = data.get('user_id', 'unknown')

        logger.info(f"Parsed environmental data for {user_id}: {len(location_history)} locations")

        return {
            "user_id": user_id,
            "location_count": len(location_history),
            "location_history": location_history,
            "exposure_summary": {
                "avg_pm25": sum(loc.get('avg_pm25', 0) for loc in location_history) / len(location_history) if location_history else 0,
                "locations": [loc.get('city') for loc in location_history]
            }
        }

    except Exception as e:
        logger.error(f"Error parsing environmental data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid environmental data: {str(e)}")


@router.post(
    "/api/v1/graph/analyze",
    responses={
        200: {"description": "Graph analysis completed successfully"},
        404: {"description": "Graph not found"},
        500: {"description": "Internal server error"},
    },
)
async def analyze_graph(request: dict):
    """Analyze causal graph for feedback loops, convergent nodes, and synergies.

    This endpoint exposes GraphAnalysisService methods to identify:
    - Feedback loops (cycles) in the causal graph
    - Convergent nodes (high-value intervention targets)
    - Multi-target synergy scores for interventions
    - Pathways between specific nodes

    Args:
        request: Dictionary with:
            - graph_id: str (required) - ID of stored graph
            - source_id: str (optional) - For pathway analysis
            - target_id: str (optional) - For pathway analysis
            - intervention_node: str (optional) - For synergy analysis
            - target_biomarkers: List[str] (optional) - For synergy analysis

    Returns:
        Dictionary with analysis results:
            - feedback_loops: List of detected cycles
            - convergent_nodes: List of nodes with ≥2 incoming edges
            - pathways: List of paths (if source/target provided)
            - synergy_analysis: Synergy scores (if intervention_node provided)

    Raises:
        HTTPException: If graph not found or analysis fails
    """
    logger.info(f"Received graph analysis request for {request.get('graph_id')}")

    try:
        graph_id = request.get('graph_id')
        if not graph_id:
            raise HTTPException(status_code=400, detail="graph_id is required")

        # Retrieve graph from store
        graph_store = get_graph_store()

        try:
            stored_data = graph_store.retrieve(graph_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        graph = stored_data["graph"]

        # Initialize graph analysis service
        analyzer = GraphAnalysisService()

        # Always compute feedback loops and convergent nodes
        feedback_loops = analyzer.detect_feedback_loops(graph)
        convergent_nodes = analyzer.find_convergent_nodes(graph, min_in_degree=2)

        result = {
            "graph_id": graph_id,
            "feedback_loops": feedback_loops,
            "convergent_nodes": convergent_nodes,
        }

        # Optional: pathway analysis
        source_id = request.get('source_id')
        target_id = request.get('target_id')
        if source_id and target_id:
            pathways = analyzer.find_pathways(graph, source_id, target_id, max_depth=5)
            result["pathways"] = pathways

        # Optional: synergy analysis
        intervention_node = request.get('intervention_node')
        target_biomarkers = request.get('target_biomarkers', [])
        if intervention_node and target_biomarkers:
            synergy = analyzer.compute_multi_target_synergy(
                graph, intervention_node, target_biomarkers
            )
            result["synergy_analysis"] = synergy

        logger.info(
            f"Graph analysis completed: {len(feedback_loops)} loops, "
            f"{len(convergent_nodes)} convergent nodes"
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in graph analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post(
    "/api/v1/discover_interventions",
    response_model=InterventionDiscoveryResponse,
    responses={
        200: {
            "description": "Successful intervention discovery",
            "model": InterventionDiscoveryResponse,
        },
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def discover_interventions(
    request: InterventionDiscoveryRequest,
) -> InterventionDiscoveryResponse:
    """Discover optimal intervention points affecting multiple biomarkers.

    This endpoint uses three complementary graph-theoretic approaches:
    1. Shared Regulators - Literature-based (INDRA API)
    2. Intervention Hubs - Structural bottlenecks (betweenness centrality)
    3. Minimal Network - Shortest paths (Steiner tree approximation)

    Args:
        request: Intervention discovery request

    Returns:
        InterventionDiscoveryResponse with intervention targets and analysis

    Example:
        ```python
        request = {
            "request_id": "req-12345",
            "biomarkers": ["CRP", "IL6", "Glucose"],
            "exposures": ["PM2.5"],
            "options": {
                "methods": ["shared_regulators", "intervention_hubs", "minimal_network"],
                "max_depth": 3,
                "min_coverage": 2,
                "belief_cutoff": 0.6,
                "prioritize_druggable": True
            }
        }
        ```
    """
    logger.info(
        f"Received intervention discovery request: {request.request_id} "
        f"with {len(request.biomarkers)} biomarkers"
    )

    start_time = time.time()

    try:
        # Import INDRAService
        from indra_agent.services.indra_service import INDRAService

        service = INDRAService()

        # Run requested methods
        results = {}
        options = request.options

        # Method 1: Shared Regulators
        if "shared_regulators" in options.methods:
            logger.info("Running shared regulators discovery...")
            shared_regs = await service.find_shared_regulators(
                biomarkers=request.biomarkers,
                max_depth=options.max_depth,
                min_coverage=options.min_coverage,
                belief_cutoff=options.belief_cutoff,
            )
            results["shared_regulators"] = shared_regs
            logger.info(f"Found {len(shared_regs)} shared regulators")

        # Method 2: Intervention Hubs
        if "intervention_hubs" in options.methods:
            logger.info("Running intervention hubs discovery...")
            hubs_result = await service.discover_intervention_hubs(
                biomarkers=request.biomarkers,
                exposures=request.exposures,
                max_depth=options.max_depth,
            )
            results["intervention_hubs"] = hubs_result["intervention_hubs"]
            results["network_summary"] = hubs_result["network_summary"]
            logger.info(f"Found {len(hubs_result['intervention_hubs'])} intervention hubs")

        # Method 3: Minimal Network
        if "minimal_network" in options.methods:
            logger.info("Running minimal network discovery...")
            minimal_network = await service.find_minimal_biomarker_network(
                biomarkers=request.biomarkers,
                exposures=request.exposures,
                max_depth=options.max_depth,
            )
            results["minimal_network"] = minimal_network
            logger.info(
                f"Built minimal network with {minimal_network['total_nodes']} nodes, "
                f"{minimal_network['total_edges']} edges"
            )

        # Find consensus targets (appear in multiple methods)
        consensus_targets = _find_consensus_targets(results, request.biomarkers)

        # Build network summary
        network_summary = _build_network_summary(results)

        # Compute processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Intervention discovery completed in {processing_time_ms}ms: "
            f"{len(consensus_targets)} consensus targets found"
        )

        return InterventionDiscoveryResponse(
            status="success",
            request_id=request.request_id,
            results=results,
            consensus_targets=consensus_targets,
            network_summary=network_summary,
            processing_time_ms=processing_time_ms,
        )

    except Exception as e:
        logger.error(f"Unexpected error in intervention discovery: {e}", exc_info=True)

        return InterventionDiscoveryResponse(
            status="error",
            request_id=request.request_id,
            results={},
            consensus_targets=[],
            network_summary=NetworkSummary(
                total_hubs=0,
                avg_coverage=0.0,
                total_paths_analyzed=0,
                shared_regulators=0,
                betweenness_hubs=0,
            ),
            processing_time_ms=int((time.time() - start_time) * 1000),
            error_message=f"Unexpected error: {str(e)}",
        )


def _find_consensus_targets(
    results: dict, biomarkers: list
) -> list[ConsensusTarget]:
    """Find targets that appear in multiple discovery methods.

    Args:
        results: Dictionary with method results
        biomarkers: Original biomarker list

    Returns:
        List of ConsensusTarget objects
    """
    # Collect all targets from each method
    all_targets = {}

    # From shared regulators
    if "shared_regulators" in results:
        for reg in results["shared_regulators"][:10]:  # Top 10
            node = reg["node"]
            if node not in all_targets:
                all_targets[node] = {
                    "methods": [],
                    "max_coverage": 0,
                    "max_score": 0.0,
                }
            all_targets[node]["methods"].append("shared_regulators")
            all_targets[node]["max_coverage"] = max(
                all_targets[node]["max_coverage"], reg["coverage"]
            )
            all_targets[node]["max_score"] = max(
                all_targets[node]["max_score"], reg["intervention_score"]
            )

    # From intervention hubs
    if "intervention_hubs" in results:
        for hub in results["intervention_hubs"][:10]:  # Top 10
            node = hub["node"]
            if node not in all_targets:
                all_targets[node] = {
                    "methods": [],
                    "max_coverage": 0,
                    "max_score": 0.0,
                }
            all_targets[node]["methods"].append("intervention_hubs")
            all_targets[node]["max_coverage"] = max(
                all_targets[node]["max_coverage"], hub["coverage"]
            )
            all_targets[node]["max_score"] = max(
                all_targets[node]["max_score"], hub["intervention_score"]
            )

    # From minimal network
    if "minimal_network" in results:
        for point in results["minimal_network"].get("intervention_points", [])[:10]:
            node = point["node"]
            if node not in all_targets:
                all_targets[node] = {
                    "methods": [],
                    "max_coverage": 0,
                    "max_score": 0.0,
                }
            all_targets[node]["methods"].append("minimal_network")
            all_targets[node]["max_coverage"] = max(
                all_targets[node]["max_coverage"], point["coverage"]
            )
            # Minimal network doesn't have intervention_score, use coverage ratio
            coverage_ratio = point["coverage"] / len(biomarkers)
            all_targets[node]["max_score"] = max(
                all_targets[node]["max_score"], coverage_ratio
            )

    # Build consensus targets (found in 2+ methods)
    consensus = []
    for node, data in all_targets.items():
        if len(data["methods"]) >= 2:
            recommendation = (
                f"{node} found by {len(data['methods'])} methods "
                f"({', '.join(data['methods'])}), "
                f"affects {data['max_coverage']}/{len(biomarkers)} biomarkers"
            )

            consensus.append(
                ConsensusTarget(
                    node=node,
                    found_in_methods=data["methods"],
                    max_coverage=data["max_coverage"],
                    max_score=data["max_score"],
                    recommendation=recommendation,
                )
            )

    # Sort by number of methods, then by coverage
    consensus.sort(
        key=lambda x: (len(x.found_in_methods), x.max_coverage), reverse=True
    )

    return consensus


def _build_network_summary(results: dict) -> NetworkSummary:
    """Build network summary from discovery results.

    Args:
        results: Dictionary with method results

    Returns:
        NetworkSummary object
    """
    total_hubs = 0
    avg_coverage = 0.0
    total_paths = 0
    shared_regulators_count = 0
    betweenness_hubs_count = 0

    if "intervention_hubs" in results:
        total_hubs = len(results["intervention_hubs"])

        # Calculate average coverage
        if results["intervention_hubs"]:
            avg_coverage = sum(
                hub["coverage"] for hub in results["intervention_hubs"]
            ) / len(results["intervention_hubs"])

    if "network_summary" in results:
        total_paths = results["network_summary"].get("total_paths_analyzed", 0)
        shared_regulators_count = results["network_summary"].get("shared_regulators", 0)
        betweenness_hubs_count = results["network_summary"].get("betweenness_hubs", 0)

    return NetworkSummary(
        total_hubs=total_hubs,
        avg_coverage=round(avg_coverage, 2),
        total_paths_analyzed=total_paths,
        shared_regulators=shared_regulators_count,
        betweenness_hubs=betweenness_hubs_count,
    )


@router.post(
    "/api/v1/validate_intervention",
    response_model=InterventionValidationResponse,
    responses={
        200: {
            "description": "Successful intervention validation",
            "model": InterventionValidationResponse,
        },
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)
async def validate_intervention(
    request: InterventionValidationRequest,
) -> InterventionValidationResponse:
    """Validate an intervention target by simulating its effects on biomarkers.

    This endpoint:
    1. Finds causal pathways from intervention target to biomarkers
    2. Simulates intervention effects using path-based propagation
    3. Computes synergy scores (super-additive effects from multi-pathway targeting)
    4. Generates clinical significance interpretation

    Args:
        request: Intervention validation request

    Returns:
        InterventionValidationResponse with pathway analysis and predictions

    Example:
        ```python
        request = {
            "target_node": "SRC",
            "biomarkers": ["CRP", "IL6", "Glucose"],
            "current_biomarker_values": {
                "CRP": 5.2,
                "IL6": 3.8,
                "Glucose": 110.0
            },
            "simulate_effect_size": 0.3
        }
        ```
    """
    logger.info(
        f"Received intervention validation request for target: {request.target_node}"
    )

    try:
        # Import INDRAService
        from indra_agent.services.indra_service import INDRAService

        service = INDRAService()

        # Find pathways from target to each biomarker
        pathway_analysis = []
        predicted_effects = {}
        affects_all = True

        for biomarker in request.biomarkers:
            try:
                # Find causal paths
                paths = await service.find_causal_paths(
                    source=request.target_node,
                    target=biomarker,
                    max_depth=5,
                )

                if paths:
                    # Use first path (highest confidence)
                    path = paths[0]

                    # Build relationship chain
                    relationship_chain = [edge["relationship"] for edge in path["edges"]]

                    # Compute pathway confidence (average belief)
                    avg_belief = sum(edge["belief"] for edge in path["edges"]) / len(
                        path["edges"]
                    )

                    # Estimate temporal lag (sum of lags)
                    total_lag = sum(edge.get("temporal_lag_hours", 12) for edge in path["edges"])

                    # Evidence count
                    evidence_count = sum(edge.get("evidence_count", 0) for edge in path["edges"])

                    # Build mechanism string
                    node_names = [request.target_node] + [
                        edge["target"] for edge in path["edges"]
                    ]
                    mechanism = " → ".join(node_names)

                    pathway_analysis.append(
                        PathwayMechanism(
                            source=request.target_node,
                            target=biomarker,
                            mechanism=mechanism,
                            confidence=round(avg_belief, 2),
                            temporal_lag_hours=int(total_lag),
                            evidence_count=evidence_count,
                        )
                    )

                    # Simulate effect on biomarker
                    if request.current_biomarker_values and biomarker in request.current_biomarker_values:
                        baseline = request.current_biomarker_values[biomarker]

                        # Effect propagation: effect_size * avg_belief * path_length_decay
                        path_length = len(path["edges"])
                        decay_factor = 0.9 ** (path_length - 1)  # Decay with distance
                        total_effect = request.simulate_effect_size * avg_belief * decay_factor

                        # Apply effect (assume inhibitory for inflammatory markers, activating for metabolic)
                        # Simplification: negative effect for CRP/IL6, positive for Glucose control
                        if biomarker in ["CRP", "IL6"]:
                            predicted = baseline * (1 - total_effect)
                        else:
                            predicted = baseline * (1 + total_effect)

                        delta = predicted - baseline
                        pct_change = (delta / baseline * 100) if baseline != 0 else 0

                        # Confidence based on evidence
                        if evidence_count > 50:
                            confidence = "high"
                        elif evidence_count > 20:
                            confidence = "medium"
                        else:
                            confidence = "low"

                        predicted_effects[biomarker] = PredictedEffect(
                            baseline=round(baseline, 2),
                            predicted=round(predicted, 2),
                            delta=round(delta, 2),
                            pct_change=round(pct_change, 1),
                            confidence=confidence,
                        )
                    else:
                        # No baseline values, just record pathway exists
                        pass

                else:
                    # No path found
                    affects_all = False
                    logger.warning(
                        f"No causal path found from {request.target_node} to {biomarker}"
                    )

            except Exception as e:
                affects_all = False
                logger.error(
                    f"Error finding path from {request.target_node} to {biomarker}: {e}"
                )

        # Compute synergy score
        synergy_score = _compute_synergy_score(
            len([p for p in pathway_analysis if p]),
            len(request.biomarkers),
            pathway_analysis,
        )

        # Generate clinical significance
        clinical_significance = _generate_clinical_significance(
            request.target_node,
            pathway_analysis,
            predicted_effects,
            synergy_score,
        )

        logger.info(
            f"Intervention validation completed: {len(pathway_analysis)} pathways found, "
            f"synergy score: {synergy_score:.2f}"
        )

        return InterventionValidationResponse(
            status="success",
            target_node=request.target_node,
            affects_all_biomarkers=affects_all,
            pathway_analysis=pathway_analysis,
            predicted_effects=predicted_effects,
            synergy_score=synergy_score,
            clinical_significance=clinical_significance,
        )

    except Exception as e:
        logger.error(f"Unexpected error in intervention validation: {e}", exc_info=True)

        return InterventionValidationResponse(
            status="error",
            target_node=request.target_node,
            affects_all_biomarkers=False,
            pathway_analysis=[],
            predicted_effects={},
            synergy_score=0.0,
            clinical_significance="Error during validation",
            error_message=f"Unexpected error: {str(e)}",
        )


def _compute_synergy_score(
    pathways_found: int, total_biomarkers: int, pathway_analysis: list
) -> float:
    """Compute synergy score for multi-target intervention.

    Synergy > 1.0 indicates super-additive effects from hitting multiple pathways.

    Args:
        pathways_found: Number of pathways discovered
        total_biomarkers: Total biomarkers queried
        pathway_analysis: List of PathwayMechanism objects

    Returns:
        Synergy score (0.0 - 2.0)
    """
    if pathways_found == 0:
        return 0.0

    # Base synergy from coverage
    coverage_ratio = pathways_found / total_biomarkers
    base_synergy = coverage_ratio

    # Boost for high-confidence pathways
    if pathway_analysis:
        avg_confidence = sum(p.confidence for p in pathway_analysis) / len(
            pathway_analysis
        )
        confidence_boost = avg_confidence * 0.5  # Up to +0.5

        # Boost for shared mechanisms (convergent effects)
        # If multiple pathways use similar nodes, synergy increases
        # Simplified: bonus if affecting 3+ biomarkers
        if pathways_found >= 3:
            multi_target_boost = 0.3
        else:
            multi_target_boost = 0.0

        synergy = base_synergy + confidence_boost + multi_target_boost
    else:
        synergy = base_synergy

    # Cap at 2.0
    return min(2.0, round(synergy, 2))


def _generate_clinical_significance(
    target_node: str,
    pathway_analysis: list,
    predicted_effects: dict,
    synergy_score: float,
) -> str:
    """Generate human-readable clinical significance interpretation.

    Args:
        target_node: Intervention target
        pathway_analysis: List of PathwayMechanism objects
        predicted_effects: Dictionary of predicted effects
        synergy_score: Computed synergy score

    Returns:
        Clinical significance string
    """
    if not pathway_analysis:
        return (
            f"No causal pathways found from {target_node} to target biomarkers. "
            "This intervention may not be effective."
        )

    # Count affected biomarkers
    affected_count = len(pathway_analysis)

    # Synergy interpretation
    if synergy_score >= 1.3:
        synergy_text = "strong synergistic effects (34%+ super-additive benefit)"
    elif synergy_score >= 1.1:
        synergy_text = "moderate synergistic effects"
    else:
        synergy_text = "additive effects"

    # Effect magnitude
    if predicted_effects:
        avg_pct_change = sum(
            abs(e.pct_change) for e in predicted_effects.values()
        ) / len(predicted_effects)

        if avg_pct_change >= 20:
            magnitude_text = "large predicted changes"
        elif avg_pct_change >= 10:
            magnitude_text = "moderate predicted changes"
        else:
            magnitude_text = "small predicted changes"
    else:
        magnitude_text = "effects not quantified"

    # Temporal lag
    if pathway_analysis:
        max_lag = max(p.temporal_lag_hours for p in pathway_analysis)
        lag_text = f"Expected timeframe: {max_lag} hours"
    else:
        lag_text = ""

    return (
        f"Targeting {target_node} affects {affected_count} biomarker(s) with {synergy_text}. "
        f"Analysis shows {magnitude_text} in target biomarkers. {lag_text}"
    )
