# Multi-stage build for INDRA Agent using Chainguard Python images
# Provides minimal attack surface, no CVEs, and distroless runtime
# Optimized for LangGraph + AWS Bedrock deployment

# =============================================================================
# Build Stage: Install dependencies in virtual environment
# =============================================================================
FROM cgr.dev/chainguard/python:latest-dev AS builder

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/app

# Create virtual environment
RUN python -m venv /opt/app/venv

# Copy dependency files
# Note: requirements.txt includes `-e .` which requires pyproject.toml
COPY requirements.txt pyproject.toml ./

# Install dependencies using cache and bind mounts for efficiency
# This approach leverages Docker's BuildKit for faster builds
# Split installation: first install packages, then install local package
RUN --mount=type=cache,target=/root/.cache/pip \
    /opt/app/venv/bin/pip install --upgrade pip setuptools wheel && \
    grep -v "^-e" requirements.txt > requirements-no-editable.txt && \
    /opt/app/venv/bin/pip install --no-cache-dir -r requirements-no-editable.txt

# Copy application code and install as editable package
COPY indra_agent/ ./indra_agent/
RUN /opt/app/venv/bin/pip install --no-cache-dir -e .

# =============================================================================
# Runtime Stage: Minimal distroless image with no shell
# =============================================================================
FROM cgr.dev/chainguard/python:latest AS runner

WORKDIR /opt/app

# Enable unbuffered output for real-time logs
ENV PYTHONUNBUFFERED=1

# Add venv to PATH so Python can find installed packages
ENV PATH="/venv/bin:$PATH"

# AWS Bedrock settings (can be overridden at runtime)
ENV AWS_REGION=us-east-1

# Application settings
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    LOG_LEVEL=INFO

# Copy virtual environment from builder
COPY --from=builder /opt/app/venv /venv

# Copy application source code
COPY indra_agent/ /opt/app/indra_agent/
COPY pyproject.toml /opt/app/

# Expose port 8000 (as configured in settings.py)
EXPOSE 8000

# Health check to ensure service is responsive
# Using Python directly since there's no curl/wget in distroless
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD ["/venv/bin/python", "-c", "import httpx; httpx.get('http://localhost:8000/health', timeout=5.0)"]

# Run FastAPI with uvicorn
# Using python -m uvicorn for better compatibility with venv
ENTRYPOINT ["/venv/bin/python", "-m", "uvicorn", "indra_agent.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
