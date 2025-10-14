"""FastAPI application for INDRA causal discovery service."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from indra_agent.api.routes import router
from indra_agent.config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="INDRA Causal Discovery API",
    description=(
        "LangGraph-based multi-agent system for querying INDRA bio-ontology "
        "to discover causal paths between environmental exposures, "
        "molecular mechanisms, and clinical biomarkers."
    ),
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "indra-causal-discovery",
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "INDRA Causal Discovery API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "endpoint": "/api/v1/causal_discovery",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    logger.info(f"Starting INDRA Causal Discovery API on {settings.app_host}:{settings.app_port}")

    uvicorn.run(
        "indra_agent.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
