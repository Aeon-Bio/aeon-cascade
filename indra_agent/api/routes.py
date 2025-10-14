"""FastAPI routes for causal discovery API."""

import logging

from fastapi import APIRouter, HTTPException

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    CausalDiscoveryResponse,
    ErrorResponse,
)

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

        # Log result
        if isinstance(response, CausalDiscoveryResponse):
            logger.info(
                f"Request {request.request_id} succeeded: "
                f"{len(response.causal_graph.nodes)} nodes, "
                f"{len(response.causal_graph.edges)} edges"
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
