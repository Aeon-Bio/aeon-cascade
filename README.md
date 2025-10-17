# INDRA Bio-Ontology Agentic System

A LangGraph-based multi-agent system for querying the INDRA bio-ontology to discover causal paths between environmental exposures, molecular mechanisms, and clinical biomarkers.

## Overview

This system receives health queries with user context, queries INDRA for causal paths, resolves biomarkers to molecular mechanisms, and returns structured causal graphs. It's designed for integration with an API gateway that handles user requests.

### Architecture

```
User → API Gateway → FastAPI Server (this system) → LangGraph Multi-Agent System
                                                    ├── Supervisor (orchestration)
                                                    ├── INDRA Agent (bio-ontology queries)
                                                    └── Web Researcher (environmental data)
```

### Key Features

- **LangGraph Supervisor Pattern**: Multi-agent orchestration with supervisor routing
- **AWS Bedrock Integration**: Uses Claude Sonnet 4.5 via AWS Bedrock
- **INDRA Integration**: Queries INDRA bio-ontology with caching for reliability
- **Pre-defined Entity Grounding**: Fast biomarker→INDRA ID mapping
- **Environmental Data**: Fetches pollution and exposure information
- **Genetic Modifiers**: Applies user genetic variants to causal graphs
- **Contract Compliant**: Matches API specification from `agentic-system-spec.md`

## Setup

### Option 1: Docker (Recommended for Production)

**Prerequisites:**
- Docker 20.10+ with BuildKit
- Docker Compose v2.0+
- AWS account with Bedrock access

**Quick Start:**
```bash
# 1. Create .env file with AWS credentials
cp .env.example .env
# Edit .env and add your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# 2. Build and start all services
docker-compose up --build

# 3. Access services
# - INDRA Agent: http://localhost:8000/docs
# - Aeon Gateway: http://localhost:8001/docs

# 4. Verify health
curl http://localhost:8000/health
curl http://localhost:8001/health
```

See **[DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)** for complete deployment guide, including:
- Individual service deployment
- Production configuration
- Kubernetes deployment
- Monitoring and troubleshooting

### Option 2: Local Development

**Prerequisites:**
- Python 3.12+
- AWS account with Bedrock access (for Claude Sonnet 4.5)
- AWS credentials (access key ID and secret access key)

**Installation:**

1. Clone and navigate to hackathon directory:
```bash
cd /path/to/omics-os/hackathon
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Create `.env` file from example:
```bash
cp .env.example .env
```

5. Edit `.env` and add your AWS credentials:
```bash
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-1
```

**Note**: Make sure your AWS account has access to Claude Sonnet 4.5 on Bedrock in the specified region.

## Running the Server

### Development Mode

```bash
# From hackathon directory
python -m indra_agent.main
```

Or with uvicorn directly:
```bash
uvicorn indra_agent.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Endpoint**: `http://localhost:8000/api/v1/causal_discovery`
- **Health Check**: `http://localhost:8000/health`
- **API Docs**: `http://localhost:8000/docs`

## API Usage

### Example Request (Sarah Chen SF→LA Query)

```bash
curl -X POST http://localhost:8000/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-001",
    "user_context": {
      "user_id": "sarah_chen",
      "genetics": {
        "GSTM1": "null",
        "GSTP1": "Val/Val"
      },
      "current_biomarkers": {
        "CRP": 0.7,
        "IL-6": 1.1
      },
      "location_history": [
        {
          "city": "San Francisco",
          "start_date": "2020-01-01",
          "end_date": "2025-08-31",
          "avg_pm25": 7.8
        },
        {
          "city": "Los Angeles",
          "start_date": "2025-09-01",
          "end_date": null,
          "avg_pm25": 34.5
        }
      ]
    },
    "query": {
      "text": "How will LA air quality affect my inflammation?",
      "focus_biomarkers": ["CRP", "IL-6"]
    }
  }'
```

### Expected Response

```json
{
  "request_id": "demo-001",
  "status": "success",
  "causal_graph": {
    "nodes": [
      {
        "id": "PM2.5",
        "type": "environmental",
        "label": "Particulate Matter (PM2.5)",
        "grounding": {"database": "MESH", "identifier": "D052638"}
      },
      {
        "id": "NFKB1",
        "type": "molecular",
        "label": "NF-κB p50",
        "grounding": {"database": "HGNC", "identifier": "7794"}
      },
      {
        "id": "IL6",
        "type": "biomarker",
        "label": "Interleukin-6",
        "grounding": {"database": "HGNC", "identifier": "6018"}
      },
      {
        "id": "CRP",
        "type": "biomarker",
        "label": "C-Reactive Protein",
        "grounding": {"database": "HGNC", "identifier": "2367"}
      }
    ],
    "edges": [
      {
        "source": "PM2.5",
        "target": "NFKB1",
        "relationship": "activates",
        "evidence": {
          "count": 47,
          "confidence": 0.82,
          "sources": ["PMID:12345678", "PMID:23456789"],
          "summary": "PM2.5 activates NFKB1"
        },
        "effect_size": 0.82,
        "temporal_lag_hours": 6
      },
      {
        "source": "NFKB1",
        "target": "IL6",
        "relationship": "increases",
        "evidence": {
          "count": 89,
          "confidence": 0.91,
          "sources": ["PMID:34567891"],
          "summary": "NFKB1 increases IL6"
        },
        "effect_size": 0.91,
        "temporal_lag_hours": 12
      },
      {
        "source": "IL6",
        "target": "CRP",
        "relationship": "increases",
        "evidence": {
          "count": 312,
          "confidence": 0.98,
          "sources": ["PMID:45678901"],
          "summary": "IL6 increases CRP"
        },
        "effect_size": 0.95,
        "temporal_lag_hours": 24
      }
    ],
    "genetic_modifiers": [
      {
        "variant": "GSTM1_null",
        "affected_nodes": ["oxidative_stress"],
        "effect_type": "amplifies",
        "magnitude": 1.3
      }
    ]
  },
  "metadata": {
    "query_time_ms": 1234,
    "indra_paths_explored": 3,
    "total_evidence_papers": 448
  },
  "explanations": [
    "PM2.5 exposure increased 4.4× after moving to Los Angeles (7.8 to 34.5 µg/m³)",
    "Your GSTM1_null variant amplifies the response by 30%",
    "IL6 increases CRP (312 papers, confidence: 0.98)",
    "Causal chain: Particulate Matter (PM2.5) → NF-κB p50 → Interleukin-6 → C-Reactive Protein"
  ]
}
```

## Project Structure

```
hackathon/
├── indra_agent/
│   ├── agents/              # LangGraph agents
│   │   ├── supervisor.py    # Orchestration agent
│   │   ├── indra_query_agent.py  # INDRA bio-ontology queries
│   │   ├── web_researcher.py     # Environmental data
│   │   ├── state.py         # State definitions
│   │   └── graph.py         # LangGraph workflow
│   ├── api/
│   │   └── routes.py        # FastAPI endpoints
│   ├── config/
│   │   ├── settings.py      # Environment config
│   │   ├── agent_config.py  # Agent configurations
│   │   └── cached_responses.py  # Pre-cached INDRA paths
│   ├── core/
│   │   ├── client.py        # LangGraph client wrapper
│   │   ├── models.py        # Pydantic models
│   │   └── state_manager.py # State management
│   ├── services/            # Stateless services
│   │   ├── grounding_service.py  # Entity grounding
│   │   ├── indra_service.py      # INDRA API wrapper
│   │   ├── graph_builder.py      # Causal graph construction
│   │   └── web_data_service.py   # Pollution data
│   └── main.py              # FastAPI app entry point
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
# Format with black
black indra_agent/

# Lint with ruff
ruff check indra_agent/
```

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS access key ID | - |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret access key | - |
| `AWS_REGION` | Yes | AWS region for Bedrock | `us-east-1` |
| `IQAIR_API_KEY` | No | IQAir API for real-time pollution | - |
| `APP_HOST` | No | Server host | `0.0.0.0` |
| `APP_PORT` | No | Server port | `8000` |
| `LOG_LEVEL` | No | Logging level | `INFO` |
| `INDRA_BASE_URL` | No | INDRA API base URL | `https://db.indra.bio` |
| `AGENT_MODEL` | No | AWS Bedrock model ID | `us.anthropic.claude-sonnet-4-5-20250129-v1:0` |

### Pre-cached INDRA Paths

For demo reliability, key causal paths are pre-cached in `config/cached_responses.py`:
- PM2.5 → IL-6 (via NF-κB)
- IL-6 → CRP (well-studied, 300+ papers)
- PM2.5 → oxidative stress

The system will fallback to these if the live INDRA API is unavailable.

## System Design

### LangGraph Workflow

1. **Supervisor** receives request and routes to specialist agents
2. **INDRA Query Agent**:
   - Extracts entities from query
   - Grounds entities to INDRA identifiers
   - Queries INDRA for causal paths
   - Builds causal graph with evidence
3. **Web Researcher**:
   - Fetches environmental data
   - Calculates exposure deltas
4. **Supervisor** synthesizes results and generates explanations

### Entity Grounding

Pre-defined mappings for fast entity resolution:
- **Biomarkers**: CRP, IL-6, 8-OHdG
- **Environmental**: PM2.5, ozone, NO2
- **Molecular**: NF-κB, TNF-α, IL-1β, ROS
- **Processes**: oxidative stress, inflammation

### Effect Size Calculation

Effect size is calculated from INDRA belief scores:
```
effect_size = min(belief * 0.8 + evidence_boost, 0.95)
```

Where evidence_boost is based on paper count:
- 100+ papers: +0.15
- 50-99 papers: +0.10
- 20-49 papers: +0.05

### Temporal Lag Estimation

Temporal lag is estimated by mechanism type:
- Phosphorylation: 1 hour
- Complex formation: 2 hours
- Transcriptional activation: 6 hours
- Protein synthesis: 12 hours

## API Contract Compliance

This system implements the specification from `/Users/tyo/GITHUB/digitalme/agentic-system-spec.md`:

✅ Effect sizes ∈ [0, 1]
✅ Temporal lags ≥ 0
✅ Node types: environmental, molecular, biomarker, genetic
✅ Relationship types: activates, inhibits, increases, decreases
✅ Evidence with PMIDs and confidence
✅ Genetic modifiers applied
✅ 3-5 explanations (< 200 chars each)

## Troubleshooting

### "No module named 'indra_agent'"

Make sure you installed the package:
```bash
pip install -e .
```

### AWS Credentials Issues

1. **"AWS credentials not found"**: Create a `.env` file with your credentials:
```bash
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
```

2. **"Could not connect to the endpoint"**: Ensure you have Bedrock access enabled in your AWS account

3. **"Model not found"**: Make sure Claude Sonnet 4.5 is available in your AWS region. The model ID is: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

### Port 8000 already in use

Change the port in `.env`:
```bash
APP_PORT=8001
```

## License

This project is part of the omics-os monorepo.

## Contact

For questions or issues, see the main omics-os repository.
