# Docker Deployment Guide - DigitalMe Stack

Complete guide for deploying the entire DigitalMe stack using secure Chainguard container images.

## 🎯 Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     DigitalMe Stack                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌─────────────────────┐      │
│  │  Aeon Gateway    │ ──────> │   INDRA Agent       │      │
│  │  Port: 8001      │         │   Port: 8000        │      │
│  │  Temporal Model  │         │   LangGraph Agents  │      │
│  └──────────────────┘         └─────────────────────┘      │
│                                          │                   │
│                                          ↓                   │
│                                 ┌────────────────┐          │
│                                 │  AWS Bedrock   │          │
│                                 │  Claude 4.5    │          │
│                                 └────────────────┘          │
│                                          │                   │
│                                          ↓                   │
│                                 ┌────────────────┐          │
│                                 │  INDRA API     │          │
│                                 │  Bio-Ontology  │          │
│                                 └────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Services

1. **INDRA Agent** (Port 8000)
   - LangGraph-based multi-agent system
   - Queries INDRA bio-ontology for causal paths
   - Uses AWS Bedrock (Claude Sonnet 4.5)
   - Image: `indra-agent` (275MB)

2. **Aeon Gateway** (Port 8001)
   - Temporal Bayesian modeling engine
   - Converts causal graphs to predictions
   - Depends on INDRA Agent
   - Image: `aeon-gateway` (252MB)

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+ with BuildKit enabled
- Docker Compose v2.0+
- AWS account with Bedrock access
- AWS credentials (access key ID and secret access key)

### 1. Setup Environment

```bash
cd /path/to/digitalme

# Create .env file
cp .env.example .env

# Edit .env and add your AWS credentials
nano .env
```

Required variables in `.env`:
```bash
# AWS Bedrock (REQUIRED)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-1

# Optional API keys
IQAIR_API_KEY=your-iqair-api-key
WRITER_API_KEY=your-writer-api-key

# Application settings (optional overrides)
LOG_LEVEL=INFO
AGENT_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### 2. Build and Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up --build -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f indra-agent
docker-compose logs -f aeon-gateway
```

### 3. Verify Services

```bash
# Check INDRA Agent
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"indra-causal-discovery","version":"0.1.0"}

# Check Aeon Gateway
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"aeon-gateway","version":"0.1.0"}

# Access API documentation
open http://localhost:8000/docs  # INDRA Agent
open http://localhost:8001/docs  # Aeon Gateway
```

### 4. Stop Services

```bash
# Stop services (preserves containers)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes + images
docker-compose down --volumes --rmi all
```

## 📦 Individual Service Deployment

### INDRA Agent Only

```bash
# Build image
docker build -t indra-agent:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e AWS_REGION=us-east-1 \
  --name indra-agent \
  indra-agent:latest

# Check logs
docker logs -f indra-agent

# Stop
docker stop indra-agent && docker rm indra-agent
```

### Aeon Gateway Only

```bash
# Build image
cd aeon-gateway
docker build -t aeon-gateway:latest .

# Run container (requires INDRA Agent URL)
docker run -d \
  -p 8001:8001 \
  -e AGENTIC_SYSTEM_URL=http://host.docker.internal:8000 \
  --name aeon-gateway \
  aeon-gateway:latest

# Check logs
docker logs -f aeon-gateway

# Stop
docker stop aeon-gateway && docker rm aeon-gateway
```

## 🏗️ Docker Image Details

### INDRA Agent

**Base Images:**
- Builder: `cgr.dev/chainguard/python:latest-dev`
- Runtime: `cgr.dev/chainguard/python:latest`

**Size:** 275MB (vs ~1.2GB for standard Python images)

**Key Dependencies:**
- FastAPI, Uvicorn
- LangGraph, LangChain
- AWS Bedrock (boto3, langchain-aws)
- NumPy, SQLAlchemy

**Build Time:** ~20 seconds (with cache)

**Architecture:**
```dockerfile
# Multi-stage build
FROM cgr.dev/chainguard/python:latest-dev AS builder
  → Install dependencies in venv
  → Install indra_agent package

FROM cgr.dev/chainguard/python:latest AS runner
  → Copy venv from builder
  → Copy application code
  → Run uvicorn
```

### Aeon Gateway

**Base Images:**
- Builder: `cgr.dev/chainguard/python:latest-dev`
- Runtime: `cgr.dev/chainguard/python:latest`

**Size:** 252MB

**Key Dependencies:**
- FastAPI, Uvicorn
- NetworkX, Pandas
- NumPy, Pytest

**Build Time:** ~15 seconds (with cache)

## 🔐 Security Features

### Chainguard Advantages

1. **Zero CVEs**: Minimal vulnerability exposure
2. **Distroless Runtime**: No shell, no package manager
3. **Non-Root**: Runs as UID 65532 by default
4. **Minimal Attack Surface**: Only runtime dependencies
5. **Supply Chain Security**: SBOM and provenance included

### Security Best Practices

```yaml
# docker-compose.yml security configuration
services:
  indra-agent:
    security_opt:
      - no-new-privileges:true

    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

### AWS Credentials Management

**Best practices:**

1. **Use environment variables** (for local development)
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
docker-compose up
```

2. **Use .env file** (not committed to git)
```bash
echo ".env" >> .gitignore
```

3. **Use AWS IAM roles** (for production)
   - ECS Task Roles
   - EC2 Instance Profiles
   - Kubernetes Service Accounts

4. **Use secrets management** (for production)
   - AWS Secrets Manager
   - HashiCorp Vault
   - Kubernetes Secrets

## 🚀 Production Deployment

### Docker Compose (Small Scale)

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  indra-agent:
    image: ghcr.io/your-org/indra-agent:v1.0.0
    restart: always
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 1G

  aeon-gateway:
    image: ghcr.io/your-org/aeon-gateway:v1.0.0
    restart: always
    depends_on:
      - indra-agent
```

Run with:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes (Medium to Large Scale)

See `k8s/` directory for complete manifests. Quick example:

```yaml
# k8s/indra-agent-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: indra-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: indra-agent
  template:
    metadata:
      labels:
        app: indra-agent
    spec:
      containers:
      - name: indra-agent
        image: ghcr.io/your-org/indra-agent:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: secret-access-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        securityContext:
          runAsNonRoot: true
          runAsUser: 65532
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
```

Deploy:
```bash
kubectl apply -f k8s/
```

### Cloud Run (Serverless)

**Google Cloud Run:**
```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/your-project/indra-agent:v1.0.0

# Deploy to Cloud Run
gcloud run deploy indra-agent \
  --image gcr.io/your-project/indra-agent:v1.0.0 \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi \
  --cpu 2 \
  --set-env-vars AWS_ACCESS_KEY_ID=your-key,AWS_SECRET_ACCESS_KEY=your-secret
```

**AWS App Runner:**
```bash
# Push to Amazon ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin your-account.dkr.ecr.us-east-1.amazonaws.com

docker tag indra-agent:latest your-account.dkr.ecr.us-east-1.amazonaws.com/indra-agent:v1.0.0
docker push your-account.dkr.ecr.us-east-1.amazonaws.com/indra-agent:v1.0.0

# Deploy via AWS Console or CLI
aws apprunner create-service \
  --service-name indra-agent \
  --source-configuration "{
    \"ImageRepository\": {
      \"ImageIdentifier\": \"your-account.dkr.ecr.us-east-1.amazonaws.com/indra-agent:v1.0.0\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {\"Port\": \"8000\"}
    }
  }"
```

## 🧪 Testing

### Health Checks

```bash
# Test INDRA Agent health
curl http://localhost:8000/health

# Test Aeon Gateway health
curl http://localhost:8001/health

# Test full workflow
curl -X POST http://localhost:8001/api/v1/gateway/query \
  -H "Content-Type: application/json" \
  -d @aeon-gateway/test_query.json
```

### Container Inspection

```bash
# View running containers
docker ps

# Inspect container
docker inspect indra-agent

# View container stats
docker stats

# Execute command in container (limited in distroless)
docker exec indra-agent /venv/bin/python --version

# View container filesystem
docker run --rm -it --entrypoint /bin/sh cgr.dev/chainguard/python:latest-dev
```

### Performance Testing

```bash
# Install Apache Bench
brew install apache-bench  # macOS

# Load test INDRA Agent
ab -n 1000 -c 10 http://localhost:8000/health

# Load test with POST request
ab -n 100 -c 5 -p test_payload.json -T application/json \
  http://localhost:8001/api/v1/gateway/query
```

## 📊 Monitoring

### Container Logs

```bash
# View logs (follow mode)
docker-compose logs -f

# View logs with timestamps
docker-compose logs -f -t

# View last 100 lines
docker-compose logs --tail=100

# Export logs to file
docker-compose logs > logs.txt
```

### Metrics Collection

**Prometheus + Grafana:**

```yaml
# Add to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  prometheus-data:
  grafana-data:
```

## 🐛 Troubleshooting

### Build Issues

**Problem:** `ERROR: failed to solve: failed to compute cache key`

**Solution:**
```bash
# Clear BuildKit cache
docker builder prune -a

# Rebuild without cache
docker-compose build --no-cache
```

**Problem:** `pip: command not found` in builder stage

**Solution:** Ensure you're using `cgr.dev/chainguard/python:latest-dev` (not `latest`) in builder stage.

### Runtime Issues

**Problem:** Container exits immediately

**Solution:**
```bash
# Check logs
docker logs indra-agent

# Common issues:
# 1. Missing AWS credentials
# 2. Port already in use
# 3. Invalid configuration
```

**Problem:** Health check failing

**Solution:**
```bash
# Check if service is responding
docker exec indra-agent /venv/bin/python -c "import httpx; print(httpx.get('http://localhost:8000/health'))"

# Check if port is accessible
curl -v http://localhost:8000/health

# Check container network
docker inspect indra-agent | grep IPAddress
```

**Problem:** Cannot connect to AWS Bedrock

**Solution:**
```bash
# Verify credentials
docker exec indra-agent env | grep AWS

# Test boto3 connection
docker exec indra-agent /venv/bin/python -c "import boto3; print(boto3.client('bedrock-runtime', region_name='us-east-1').list_foundation_models())"
```

### Network Issues

**Problem:** Aeon Gateway cannot reach INDRA Agent

**Solution:**
```bash
# Check if both services are on same network
docker network inspect digitalme-network

# Test connectivity from aeon-gateway to indra-agent
docker exec aeon-gateway /venv/bin/python -c "import httpx; print(httpx.get('http://indra-agent:8000/health'))"

# Use correct hostname (service name in docker-compose)
# ✅ AGENTIC_SYSTEM_URL=http://indra-agent:8000
# ❌ AGENTIC_SYSTEM_URL=http://localhost:8000
```

## 📚 Additional Resources

- **Chainguard Images**: https://images.chainguard.dev/directory/image/python/overview
- **Docker Best Practices**: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
- **FastAPI Deployment**: https://fastapi.tiangolo.com/deployment/docker/
- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/

## 🔄 CI/CD Integration

### GitHub Actions

See `.github/workflows/docker-build.yml` in each service for complete examples.

Key steps:
1. Build images with BuildKit
2. Run security scans (Trivy, Grype)
3. Run health checks
4. Push to container registry
5. Generate SBOM

### GitLab CI

```yaml
# .gitlab-ci.yml
build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

scan:
  stage: test
  image: aquasec/trivy:latest
  script:
    - trivy image $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA

deploy:
  stage: deploy
  script:
    - kubectl set image deployment/indra-agent indra-agent=$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

## 📝 Changelog

### v1.0.0 (October 2025)
- ✅ Initial Chainguard integration
- ✅ Multi-stage builds for both services
- ✅ Docker Compose orchestration
- ✅ Security hardening (non-root, no-new-privileges)
- ✅ Health checks and resource limits
- ✅ Complete documentation

---

**Last Updated:** October 17, 2025
**Tested On:** Docker 24.0.6, macOS ARM64
**Status:** ✅ Production Ready
