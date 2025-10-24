# Aeon Cascade - Systems Medicine Health Intelligence

A multi-factor health intelligence system that discovers synergistic interventions across multiple conditions using **systems medicine**, powered by INDRA bio-ontology and structural causal models.

## Overview

Aeon Cascade enables evidence-based causal reasoning about health interventions by integrating:
- **INDRA Bio-Ontology**: 3.8M+ literature-backed causal statements
- **Multi-Agent Architecture**: LangGraph workflow with specialized agents
- **Genetic Context**: Personalized analysis with genetic modifiers
- **Environmental Integration**: Pollution exposure and location-based factors
- **Structural Causal Models**: Quantitative intervention predictions

Every causal relationship is backed by peer-reviewed scientific papers with evidence counts and confidence scores.

### Clinical Use Case Example

**Sarah Chen** (34, Software Engineer):
- **Conditions**: Chronic inflammation (CRP: 5.2 mg/L) + Prediabetes (HbA1c: 5.9%)
- **Environment**: High PM2.5 exposure in Los Angeles (35 µg/m³)
- **Challenge**: Two interconnected conditions with shared molecular mechanisms

**Traditional Approach**: Treat inflammation and prediabetes separately → miss synergies

**Systems Medicine Approach**: Identify upstream intervention (reduce PM2.5) that simultaneously:
- ↓ Oxidative stress → ↓ Inflammation (CRP: 5.2 → 4.36 mg/L, -16%)
- ↓ Oxidative stress → ↓ Insulin resistance (HbA1c: 5.9% → 4.77%, -19%)
- **Synergy Score**: 1.34 (34% super-additive benefit from cross-pathway effects)

**Query**: "If Sarah moves from LA to Seattle (PM2.5: 10 µg/m³), how will her inflammation AND metabolic markers respond?"

### Architecture

**Telegram Bot Mode:**
```
User → Telegram → aeon_cascade_frontend (bot.py)
                       ↓
                [Health Query Detection]
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
     Health Query           General Query
            ↓                     ↓
   INDRA Agent (direct)     OpenAI GPT-4
            ↓                     ↓
   Formatted Result         Chat Response
```

**API Mode:**
```
Client → HTTP API / MCP Server → LangGraph Workflow
                                    ├── Supervisor (orchestration)
                                    ├── INDRA Query Agent (bio-ontology)
                                    ├── Web Researcher (environmental data)
                                    └── Graph Builder (causal inference)
```

### Deployment Modes

**1. Telegram Bot (aeon_cascade_frontend)**
- Interactive health assistant via Telegram
- Automatic health query detection
- Integrated with INDRA agent via direct Python imports
- Falls back to OpenAI GPT-4 for general queries
- User health profile storage (genetics, biomarkers, location history)

**2. Standalone API**
- REST API for agent-to-agent communication
- FastAPI with interactive docs (`/docs`)
- MCP server support for Claude Desktop integration
- Direct integration into custom applications

### Key Features

- **Evidence-Based**: Every causal edge backed by scientific papers from INDRA (3.8M+ statements)
- **Personalized Analysis**: Incorporates genetic variants and individual biomarker levels
- **Environmental Context**: Pollution exposure, location history, and exposure deltas
- **Multi-Condition**: Discovers synergistic interventions across interconnected conditions
- **Transparent Evidence**: Paper counts, confidence scores, and PMID references
- **Graph Validation**: Ensures DAG constraints and causal validity

## Setup

### Option 1: Telegram Bot Deployment (Full Health Assistant)

**Prerequisites:**
- Docker 20.10+ with Docker Compose v2.0+
- Telegram Bot Token (from @BotFather)
- OpenAI API Key
- AWS Bedrock access (Claude Sonnet 4.5)
- MongoDB (included in docker-compose)

**Quick Start:**
```bash
# Navigate to Telegram bot directory
cd aeon_cascade_frontend/

# Create config from example
cp config/config.env.example config/config.env

# Edit config/config.env and add:
# - TELEGRAM_TOKEN=your-bot-token
# - OPENAI_API_KEY=your-openai-key
# - AWS_ACCESS_KEY_ID=your-aws-key
# - AWS_SECRET_ACCESS_KEY=your-aws-secret
# - AWS_REGION=us-east-1

# Build and start all services (bot + MongoDB + INDRA agent)
docker-compose --env-file config/config.env up --build

# Bot is now live on Telegram!
# Access MongoDB admin: http://localhost:8081
```

**What's Included:**
- Telegram bot with health query auto-detection
- INDRA agent integration (direct Python imports)
- OpenAI GPT-4 fallback for general queries
- MongoDB for user profiles and health data
- Voice transcription (Whisper)
- Image generation (DALL-E)

**Usage:**
1. Start a chat with your bot on Telegram
2. Ask health questions: "How does pollution affect inflammation?"
3. Bot auto-detects and routes to INDRA agent
4. For general queries, falls back to GPT-4

### Option 2: Standalone API (For Integration)

**Prerequisites:**
- Docker 20.10+ with BuildKit
- AWS account with Bedrock access

**Quick Start:**
```bash
# 1. Create .env file with AWS credentials
cp .env.example .env
# Edit .env and add your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# 2. Build and start API server
docker-compose up --build

# 3. Access API
# - API Documentation: http://localhost:8000/docs
# - Health Check: http://localhost:8000/health

# 4. Verify
curl http://localhost:8000/health
```

### Option 3: Local Development (No Docker)

**Prerequisites:**
- Python 3.11+
- AWS account with Bedrock access (Claude Sonnet 4.5)

**Installation:**

```bash
# 1. Install indra_agent package (editable mode)
pip install -e .

# 2. For Telegram bot: install additional dependencies
cd aeon_cascade_frontend/
pip install -r requirements.txt
cd ..

# 3. Create .env file
cp .env.example .env

# 4. Edit .env and add credentials:
# AWS_ACCESS_KEY_ID=your-key
# AWS_SECRET_ACCESS_KEY=your-secret
# AWS_REGION=us-east-1
#
# For Telegram bot, also edit aeon_cascade_frontend/config/config.env:
# TELEGRAM_TOKEN=your-bot-token
# OPENAI_API_KEY=your-openai-key
```

**Note**: Your AWS account must have access to `us.anthropic.claude-sonnet-4-5-20250129-v1:0` on Bedrock.

## Running Locally

### Telegram Bot Mode

```bash
cd aeon_cascade_frontend/
python bot/bot.py
```

The bot will:
- Connect to Telegram
- Auto-detect health queries → route to INDRA agent
- Handle general queries → route to OpenAI GPT-4
- Store user context in MongoDB (start MongoDB separately if needed)

### API Server Mode

```bash
# From project root
python -m indra_agent.main
```

Or with uvicorn:
```bash
uvicorn indra_agent.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Endpoint**: `http://localhost:8000/api/v1/causal_discovery`
- **Health Check**: `http://localhost:8000/health`
- **Interactive Docs**: `http://localhost:8000/docs`

### MCP Server Mode (Claude Desktop Integration)

```bash
# Add to Claude Desktop config (~/.config/claude/claude_desktop_config.json):
{
  "mcpServers": {
    "aeon_cascade": {
      "command": "python",
      "args": ["-m", "indra_agent.mcp_server"],
      "cwd": "/path/to/digitalme"
    }
  }
}

# Restart Claude Desktop to activate
```

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
digitalme/
├── indra_agent/                    # Health intelligence backend
│   ├── agents/                     # LangGraph multi-agent system
│   │   ├── supervisor.py           # Orchestration agent
│   │   ├── indra_query_agent.py    # INDRA bio-ontology queries
│   │   ├── web_researcher.py       # Environmental data
│   │   ├── mesh_enrichment_agent.py# MeSH ontology enrichment
│   │   ├── state.py                # State definitions
│   │   └── graph.py                # LangGraph workflow
│   ├── api/
│   │   └── routes.py               # FastAPI endpoints
│   ├── config/
│   │   ├── settings.py             # Environment config
│   │   ├── agent_config.py         # Agent prompts & configs
│   │   └── cached_responses.py     # Pre-cached INDRA paths
│   ├── core/
│   │   ├── client.py               # Main client interface
│   │   ├── models.py               # Pydantic models (API contract)
│   │   └── progress.py             # Progress tracking
│   ├── services/                   # Stateless services
│   │   ├── grounding_service.py    # Entity → INDRA ID mapping
│   │   ├── indra_service.py        # INDRA API wrapper
│   │   ├── graph_builder.py        # Causal graph construction
│   │   ├── web_data_service.py     # Pollution/environmental data
│   │   └── writer_kg_service.py    # Writer KG integration
│   ├── main.py                     # FastAPI app entry point
│   └── mcp_server.py               # MCP server for Claude Desktop
├── aeon_cascade_frontend/                   # Telegram bot interface
│   ├── bot/
│   │   ├── bot.py                  # Main bot (imports indra_agent)
│   │   ├── config.py               # Configuration loader
│   │   ├── database.py             # MongoDB abstraction
│   │   └── openai_utils.py         # OpenAI API utilities
│   ├── config/
│   │   ├── config.yml              # Bot settings
│   │   ├── config.env              # Environment variables
│   │   ├── chat_modes.yml          # Bot personalities
│   │   └── models.yml              # OpenAI model configs
│   ├── Dockerfile                  # Docker build (multi-context)
│   └── docker-compose.yml          # Bot + MongoDB deployment
├── tests/                          # Test suite
├── pyproject.toml                  # Python package config
├── .env.example                    # Environment template
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

## API Contract

The system provides a standardized causal graph API with:

✅ **Effect Sizes**: Values ∈ [0, 1] for Monte Carlo simulation compatibility
✅ **Temporal Lags**: Non-negative hours for causal ordering
✅ **Node Types**: `environmental` | `molecular` | `biomarker` | `genetic`
✅ **Relationship Types**: `activates` | `inhibits` | `increases` | `decreases`
✅ **Evidence**: PMID references, paper counts, confidence scores
✅ **Genetic Context**: Modifiers with affected nodes and magnitude
✅ **Explanations**: 3-5 concise insights (<200 chars each)

See API documentation at `/docs` endpoint for full specification.

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

## Technology Stack

- **LangGraph**: Multi-agent workflow orchestration
- **AWS Bedrock**: Claude Sonnet 4.5 for entity extraction and synthesis
- **INDRA Bio-Ontology**: 3.8M+ curated causal statements from literature
- **FastAPI**: REST API framework
- **Pydantic**: Data validation and API contracts
- **Telegram Bot API**: User interface (bot mode)
- **OpenAI API**: GPT-4 fallback, Whisper, DALL-E (bot mode)
- **MongoDB**: User profile and health data storage (bot mode)
- **Docker**: Containerized deployment

## Contributing

This is a research prototype. For production use:
1. Implement proper authentication and authorization
2. Add rate limiting and request validation
3. Set up monitoring and logging infrastructure
4. Configure backup and disaster recovery for user health data
5. Ensure HIPAA compliance if handling protected health information

## License

MIT License - See LICENSE file for details
