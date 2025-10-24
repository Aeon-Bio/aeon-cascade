"""Client wrapper for INDRA causal discovery workflow."""

import asyncio
import logging
from typing import Union

from langchain_core.messages import HumanMessage

from indra_agent.agents.graph import create_causal_discovery_graph
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    CausalDiscoveryResponse,
    CausalGraph,
    ErrorInfo,
    ErrorResponse,
    Metadata,
)
from indra_agent.core.progress import ProgressEmitter

logger = logging.getLogger(__name__)


class INDRAAgentClient:
    """Client for executing INDRA causal discovery workflow."""

    def __init__(self):
        """Initialize INDRA agent client (graph created lazily)."""
        self.graph = None
        logger.info("INDRA agent client created (graph will be initialized on first use)")

    async def _ensure_graph(self, progress_emitter: ProgressEmitter | None = None):
        """Ensure graph is initialized."""
        if self.graph is None:
            # Emit initialization progress
            if progress_emitter:
                async with progress_emitter.step(
                    agent="system",
                    action="Initializing causal discovery agents",
                    progress_percent=1
                ):
                    logger.info("Initializing causal discovery graph")
                    self.graph = await create_causal_discovery_graph()
                    logger.info("Graph initialized successfully")
            else:
                logger.info("Initializing causal discovery graph")
                self.graph = await create_causal_discovery_graph()
                logger.info("Graph initialized successfully")

    async def process_request(
        self,
        request: CausalDiscoveryRequest,
        timeout: float = 30.0,
        progress_emitter: ProgressEmitter | None = None,
    ) -> Union[CausalDiscoveryResponse, ErrorResponse]:
        """Process causal discovery request.

        Args:
            request: Causal discovery request
            timeout: Timeout in seconds (default: 30.0)
            progress_emitter: Optional progress emitter for real-time updates

        Returns:
            CausalDiscoveryResponse or ErrorResponse
        """
        logger.info(f"Processing request: {request.request_id}")

        try:
            # Ensure graph is initialized (with progress tracking)
            await self._ensure_graph(progress_emitter)

            # Prepare initial state with HumanMessage
            user_message = HumanMessage(content=request.query.text)

            initial_state = {
                "messages": [user_message],
                "request_id": request.request_id,
                "user_context": request.user_context.model_dump(),
                "query": request.query.model_dump(),
                "options": request.options.model_dump(),
                "entities": [],
                "source_entities": [],
                "target_entities": [],
                "indra_paths": [],
                "environmental_data": {},
                "causal_graph": {},
                "explanations": [],
                "metadata": {},
                "next_agent": "",
                "current_agent": "",
                "progress_emitter": progress_emitter,  # Pass to agents
            }

            # Run graph with timeout and 50-iteration limit to prevent indefinite hangs
            try:
                final_state = await asyncio.wait_for(
                    self.graph.ainvoke(initial_state, {"recursion_limit": 50}),
                    timeout=timeout
                )

                # Emit final progress: workflow complete (90%)
                if progress_emitter:
                    async with progress_emitter.step(
                        agent="system",
                        action="Finalizing results and generating insights",
                        progress_percent=90
                    ):
                        pass  # Just mark completion

            except asyncio.TimeoutError:
                logger.error(f"Request {request.request_id} timed out after {timeout} seconds")
                return ErrorResponse(
                    request_id=request.request_id,
                    error=ErrorInfo(
                        code="TIMEOUT",
                        message=f"Query timed out after {timeout} seconds",
                        details=None,
                    ),
                )

            # Extract results
            causal_graph_dict = final_state.get("causal_graph", {})
            explanations = final_state.get("explanations", [])
            metadata_dict = final_state.get("metadata", {})
            predictions_dict = final_state.get("predictions", {})

            # Validate we have results
            if not causal_graph_dict or not causal_graph_dict.get("nodes"):
                return ErrorResponse(
                    request_id=request.request_id,
                    error=ErrorInfo(
                        code="NO_CAUSAL_PATH",
                        message="Could not find causal path for the given query",
                        details=None,
                    ),
                )

            # Parse models
            causal_graph = CausalGraph(**causal_graph_dict)
            metadata = Metadata(**metadata_dict)

            # Ensure we have 3-5 explanations
            if len(explanations) < 3:
                explanations.extend(
                    [
                        f"Analysis includes {len(causal_graph.nodes)} biological entities",
                        f"Based on {metadata.total_evidence_papers} scientific papers",
                        f"Causal graph contains {len(causal_graph.edges)} relationships",
                    ]
                )
            explanations = explanations[:5]  # Max 5

            response = CausalDiscoveryResponse(
                request_id=request.request_id,
                causal_graph=causal_graph,
                metadata=metadata,
                explanations=explanations,
                predictions=predictions_dict if predictions_dict else None,
            )

            logger.info(
                f"Request {request.request_id} completed successfully: "
                f"{len(causal_graph.nodes)} nodes, {len(causal_graph.edges)} edges, "
                f"{len(predictions_dict)} predictions" if predictions_dict else f"{len(causal_graph.nodes)} nodes, {len(causal_graph.edges)} edges"
            )

            return response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)

            return ErrorResponse(
                request_id=request.request_id,
                error=ErrorInfo(
                    code="TIMEOUT" if "timeout" in str(e).lower() else "INVALID_REQUEST",
                    message=str(e),
                ),
            )
