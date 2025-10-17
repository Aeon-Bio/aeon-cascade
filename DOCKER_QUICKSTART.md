# Docker Quick Start - DigitalMe Stack

One-page reference for getting started with the containerized DigitalMe stack.

## ⚡ 30-Second Start

```bash
# 1. Setup
cp .env.example .env
# Edit .env: Add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# 2. Start
docker-compose up --build

# 3. Verify
curl http://localhost:8000/health  # INDRA Agent
curl http://localhost:8001/health  # Aeon Gateway
```

## 📋 Prerequisites Checklist

- [ ] Docker 20.10+ installed
- [ ] Docker Compose v2.0+ installed
- [ ] AWS account with Bedrock access
- [ ] AWS credentials (access key ID and secret)

## 🎯 Essential Commands

### Start/Stop

```bash
# Start all services (build first time)
docker-compose up --build

# Start in background
docker-compose up -d

# Stop services
docker-compose down

# Stop and clean everything
docker-compose down --volumes --rmi all
```

### Monitoring

```bash
# View logs
docker-compose logs -f

# View specific service
docker-compose logs -f indra-agent

# View container status
docker-compose ps

# View resource usage
docker stats
```

### Testing

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health

# API documentation
open http://localhost:8000/docs
open http://localhost:8001/docs

# Test full workflow
curl -X POST http://localhost:8001/api/v1/gateway/query \
  -H "Content-Type: application/json" \
  -d @aeon-gateway/test_query.json
```

## 🔧 Common Tasks

### Rebuild After Code Changes

```bash
# Rebuild specific service
docker-compose build indra-agent

# Rebuild all services
docker-compose build --no-cache

# Rebuild and restart
docker-compose up --build
```

### View Logs

```bash
# All logs
docker-compose logs

# Last 100 lines
docker-compose logs --tail=100

# Follow logs
docker-compose logs -f

# Export logs
docker-compose logs > logs.txt
```

### Update Dependencies

```bash
# Update uv.lock
uv lock --upgrade

# Regenerate requirements.txt
uv export --no-hashes --no-dev > requirements.txt

# Rebuild images
docker-compose build --no-cache
```

## 🐛 Troubleshooting

### Build Fails

```bash
# Clear cache
docker builder prune -a

# Rebuild without cache
docker-compose build --no-cache
```

### Container Won't Start

```bash
# Check logs
docker-compose logs indra-agent

# Common issues:
# - Missing AWS credentials in .env
# - Port 8000/8001 already in use
# - Invalid .env syntax
```

### Services Can't Communicate

```bash
# Check network
docker network inspect digitalme-network

# Ensure AGENTIC_SYSTEM_URL uses service name
# ✅ http://indra-agent:8000
# ❌ http://localhost:8000
```

### Health Check Failing

```bash
# Test manually
docker exec indra-agent /venv/bin/python -c "import httpx; print(httpx.get('http://localhost:8000/health'))"

# Check if service is listening
docker exec indra-agent netstat -tlnp | grep 8000
```

## 📊 Service Ports

| Service | Port | Health Check | API Docs |
|---------|------|--------------|----------|
| INDRA Agent | 8000 | `/health` | `/docs` |
| Aeon Gateway | 8001 | `/health` | `/docs` |

## 🔐 Environment Variables

### Required

```bash
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-1
```

### Optional

```bash
LOG_LEVEL=INFO
IQAIR_API_KEY=your-iqair-api-key
WRITER_API_KEY=your-writer-api-key
AGENT_MODEL=us.anthropic.claude-sonnet-4-5-20250929-v1:0
INDRA_BASE_URL=https://network.indra.bio
```

## 📚 Documentation Links

- **Complete Deployment Guide**: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
- **Integration Summary**: [CHAINGUARD_INTEGRATION_SUMMARY.md](./CHAINGUARD_INTEGRATION_SUMMARY.md)
- **Aeon Gateway Deployment**: [aeon-gateway/docs/CHAINGUARD_DEPLOYMENT.md](./aeon-gateway/docs/CHAINGUARD_DEPLOYMENT.md)

## 🚀 Production Deployment

### Docker Compose

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

### Cloud Run

```bash
gcloud run deploy indra-agent \
  --image gcr.io/your-project/indra-agent:latest \
  --platform managed
```

## 💾 Backup & Restore

### Export Images

```bash
docker save indra-agent:latest | gzip > indra-agent.tar.gz
docker save aeon-gateway:latest | gzip > aeon-gateway.tar.gz
```

### Import Images

```bash
docker load < indra-agent.tar.gz
docker load < aeon-gateway.tar.gz
```

## 🔄 Updates

### Pull Latest Images

```bash
docker-compose pull
docker-compose up -d
```

### Update Base Images

```bash
docker pull cgr.dev/chainguard/python:latest
docker pull cgr.dev/chainguard/python:latest-dev
docker-compose build --pull --no-cache
```

## 📈 Performance Tips

1. **Enable BuildKit caching** (faster builds)
   ```bash
   export DOCKER_BUILDKIT=1
   ```

2. **Use bind mounts for development** (hot reload)
   ```yaml
   volumes:
     - ./indra_agent:/opt/app/indra_agent:ro
   ```

3. **Adjust resource limits** (in docker-compose.yml)
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 2G
   ```

## 🆘 Quick Fixes

| Problem | Solution |
|---------|----------|
| Port in use | Change ports in docker-compose.yml |
| Out of disk space | `docker system prune -a` |
| Build too slow | Enable BuildKit caching |
| Logs too large | `docker-compose logs --tail=100` |
| Container stuck | `docker-compose restart <service>` |
| Network issues | `docker network prune` |

## ✅ Health Check URLs

- INDRA Agent: http://localhost:8000/health
- Aeon Gateway: http://localhost:8001/health
- INDRA Agent Docs: http://localhost:8000/docs
- Aeon Gateway Docs: http://localhost:8001/docs

## 🎓 Learning Resources

- Docker Docs: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- Chainguard Images: https://images.chainguard.dev/
- FastAPI Deployment: https://fastapi.tiangolo.com/deployment/docker/

---

**Need more help?** See [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) for detailed information.
