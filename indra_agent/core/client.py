"""Client wrapper for INDRA causal discovery workflow."""

import logging
from typing import Union

from indra_agent.agents.graph import create_causal_discovery_graph
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    CausalDiscoveryResponse,
    CausalGraph,
    ErrorInfo,
    ErrorResponse,
    Metadata,
)

logger = logging.getLogger(__name__)


class INDRAAgentClient:
    """Client for executing INDRA causal discovery workflow."""

    def __init__(self):
        """Initialize INDRA agent client."""
        self.graph = create_causal_discovery_graph()
        logger.info("INDRA agent client initialized")

    async def process_request(
        self, request: CausalDiscoveryRequest
    ) -> Union[CausalDiscoveryResponse, ErrorResponse]:
        """Process causal discovery request.

        Args:
            request: Causal discovery request

        Returns:
            CausalDiscoveryResponse or ErrorResponse
        """
        logger.info(f"Processing request: {request.request_id}")

        try:
            # Prepare initial state
            initial_state = {
                "messages": [],
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
            }

            # Run graph
            final_state = await self.graph.ainvoke(initial_state)

            # Extract results
            causal_graph_dict = final_state.get("causal_graph", {})
            explanations = final_state.get("explanations", [])
            metadata_dict = final_state.get("metadata", {})

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
            )

            logger.info(
                f"Request {request.request_id} completed successfully: "
                f"{len(causal_graph.nodes)} nodes, {len(causal_graph.edges)} edges"
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
