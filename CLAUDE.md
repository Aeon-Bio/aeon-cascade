# CLAUDE.md

You are the worlds best hackathon winner.

## Project Overview

**healthOS** is a multi-factor, all-in-one health assistant accessible via Telegram that combines conversational AI with evidence-based health intelligence powered by INDRA bio-ontology.

### Architecture

```
User → Telegram → healthos_bot (bot.py)
                       ↓
                [Health Query Detection]
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
     Health Query           General Query
            ↓                     ↓
   INDRA Agent (direct)     OpenAI GPT-4
   (Bio-ontology)           (Conversational)
            ↓                     ↓
   AWS Bedrock (Claude)     Chat Response
   INDRA Bio-Ontology
            ↓
   Formatted Result
            ↓                     ↓
       Telegram Reply        Telegram Reply
```

### Key Features

✅ **Integrated Health Intelligence**: INDRA agent runs inside bot.py via direct Python imports
✅ **Automatic Detection**: Health keywords trigger INDRA bio-ontology analysis
✅ **Fallback Support**: Falls back to OpenAI if INDRA unavailable or non-health queries
✅ **Single Container**: One Docker container runs both Telegram bot + INDRA agent
✅ **Evidence-Based**: Causal pathways backed by scientific papers from INDRA knowledge graph

## System Components

### 1. healthos_bot (Telegram Interface)
**Location**: `/healthos_bot/`
**Status**: ✅ Production-ready with INDRA integration

**Capabilities**:
- Telegram bot with command handlers (/start, /help, /new, /mode, /search)
- **INDRA health intelligence integration** (NEW)
- OpenAI GPT-4 for general conversational AI
- MongoDB for user profiles, dialog history, usage tracking
- Multiple chat modes (assistant, artist, code helper)
- Voice message transcription (Whisper)
- Image generation (DALL-E) and processing (GPT-4 Vision)
- Web search integration (DuckDuckGo)
- Group chat support with @mention detection

**Technology Stack**:
- python-telegram-bot for Telegram API
- OpenAI API (GPT-4, GPT-4o, DALL-E, Whisper)
- **indra_agent modules (direct Python import)**
- MongoDB for data persistence
- Docker deployment

### 2. indra_agent (Health Intelligence Backend)
**Location**: `/indra_agent/`
**Status**: ✅ Integrated into healthos_bot via direct Python imports

**Capabilities**:
- LangGraph multi-agent system (Supervisor, INDRA Query Agent, Web Researcher)
- AWS Bedrock integration (Claude Sonnet 4.5)
- INDRA bio-ontology integration for causal pathway discovery
- Entity grounding (biomarkers → INDRA database IDs)
- Causal graph construction with evidence and confidence scores
- Genetic modifier application (e.g., GSTM1_null variants)
- Environmental data integration (pollution, exposure tracking)
- Pre-cached INDRA paths for reliability

**Technology Stack**:
- LangGraph for agent orchestration
- AWS Bedrock (Claude Sonnet 4.5)
- INDRA bio-ontology API
- Pydantic for data validation

**Deployment Mode**: Python modules imported directly into healthos_bot/bot.py (NO HTTP API)

## Integration Architecture

### Direct Python Import (No HTTP)

The integration uses **direct Python imports** for performance and simplicity:

```python
# healthos_bot/bot/bot.py

from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    UserContext,
    Query,
    RequestOptions
)

# Initialize client at startup (singleton)
indra_client = INDRAAgentClient()

# Query processing (no HTTP calls)
async def query_indra_health_system(user_id: int, message_text: str):
    request = CausalDiscoveryRequest(
        request_id=str(uuid.uuid4()),
        user_context=UserContext(
            user_id=str(user_id),
            genetics=db.get_user_attribute(user_id, 'health_genetics') or {},
            current_biomarkers=db.get_user_attribute(user_id, 'health_biomarkers') or {},
            location_history=db.get_user_attribute(user_id, 'health_location_history') or []
        ),
        query=Query(text=message_text),
        options=RequestOptions()
    )

    # Direct function call - no HTTP overhead
    response = await indra_client.process_request(request)
    return format_indra_response(response)
```

### Health Query Detection

The bot automatically detects health-related queries:

```python
def is_health_query(message_text: str) -> bool:
    """Detect health-related queries for INDRA routing."""
    health_keywords = [
        'biomarker', 'crp', 'il-6', 'inflammation', 'oxidative stress',
        'pollution', 'pm2.5', 'air quality', 'exposure',
        'gene', 'genetic', 'variant', 'gstm1',
        'health', 'risk', 'causal', 'pathway', 'mechanism',
        'environmental', 'affect', 'impact', 'influence',
        'molecular', 'protein', 'cytokine'
    ]
    return any(keyword in message_text.lower() for keyword in health_keywords)
```

**Trigger Examples**:
- "How does PM2.5 pollution affect CRP biomarkers?"
- "What's the causal pathway between air quality and inflammation?"
- "Explain the relationship between oxidative stress and IL-6"
- "How do genetic variants like GSTM1 affect health?"

### Message Flow

```python
async def message_handle_fn():
    # Check if health query
    if _message and is_health_query(_message) and INDRA_AVAILABLE:
        # Route to INDRA agent
        indra_result = await query_indra_health_system(user_id, _message)

        if indra_result['success']:
            # Display INDRA response
            await update.message.reply_text(indra_result['response'], parse_mode=ParseMode.HTML)
            return

    # Fall through to OpenAI for non-health or failed queries
    chatgpt_instance = openai_utils.ChatGPT(model=current_model)
    # ... existing OpenAI logic
```

## Setup and Deployment

### 1. Configure Credentials

Edit `healthos_bot/config/config.env`:

```bash
# Telegram & OpenAI
TELEGRAM_TOKEN=your-telegram-bot-token
OPENAI_API_KEY=your-openai-api-key

# MongoDB
MONGODB_PORT=27017

# AWS Bedrock (for INDRA health intelligence)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-1

# Optional
INDRA_BASE_URL=https://db.indra.bio
IQAIR_API_KEY=your-iqair-api-key-optional
```

Edit `healthos_bot/config/config.yml`:

```yaml
telegram_token: ${TELEGRAM_TOKEN}
openai_api_key: ${OPENAI_API_KEY}
allowed_telegram_usernames: []  # Empty = allow all users
```

### 2. Production Deployment (Docker - Recommended)

```bash
cd healthos_bot/

# Build and run all services
docker-compose --env-file config/config.env up --build
```

**What happens:**
1. Docker builds from parent directory context to access both healthos_bot/ and indra_agent/
2. Installs healthos_bot dependencies (requirements.txt)
3. Installs indra_agent dependencies (pyproject.toml)
4. Copies indra_agent to `/opt/indra_agent` for editable install
5. Runs bot.py which imports indra_agent modules
6. Single container runs: Telegram bot + INDRA agents + OpenAI chat + MongoDB

**Services Started:**
- `chatgpt_telegram_bot`: Main bot with INDRA integration
- `mongo`: MongoDB database
- `mongo_express`: Database admin UI (http://localhost:8081)

### 3. Development Mode (Local Python)

```bash
# Install both projects
pip install -e .
cd healthos_bot/
pip install -r requirements.txt

# Run bot directly
python3 bot/bot.py
```

## Docker Build Details

### Build Context Structure

The Docker setup uses **parent directory context** to access both projects:

```yaml
# healthos_bot/docker-compose.yml
services:
  chatgpt_telegram_bot:
    build:
      context: ".."                      # Parent directory (digitalme/)
      dockerfile: healthos_bot/Dockerfile
```

```dockerfile
# healthos_bot/Dockerfile
FROM cgr.dev/chainguard-private/python:3.11-dev

# Install healthos_bot dependencies
COPY healthos_bot/requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

# Copy and install indra_agent (permanent location for editable install)
COPY indra_agent /opt/indra_agent
COPY pyproject.toml /opt/pyproject.toml
RUN cd /opt && pip3 install -e .

# Copy healthos_bot code
COPY healthos_bot /code
WORKDIR /code

CMD ["bash"]
```

**Container Filesystem:**
```
/opt/indra_agent/          # Permanent copy for editable install
├── agents/
├── core/
└── services/

/code/                     # Working directory
├── bot/bot.py            # Imports: from indra_agent.core.client import ...
├── config/
└── requirements.txt
```

## Usage Examples

### Health Queries (Triggers INDRA)

**User:** "How does PM2.5 pollution affect CRP biomarkers?"

**Bot Response:**
```
🧬 Health Intelligence Report

📊 Key Insights:
1. PM2.5 exposure increases inflammatory biomarkers through oxidative stress pathways
2. Causal chain: PM2.5 → NF-κB activation → IL-6 elevation → CRP increase
3. Based on 312 peer-reviewed scientific papers

🔬 Causal Analysis:
• 5 biological entities identified
• 4 causal relationships found
• Based on 312 scientific papers
• Analysis time: 2847ms

🔗 Top Causal Pathways:
  PM2.5 ⬆️ NF-κB
  Evidence: 47 papers, Effect: 0.82, Lag: 6h

  NF-κB ⬆️ IL-6
  Evidence: 89 papers, Effect: 0.87, Lag: 12h

  IL-6 ⬆️ CRP
  Evidence: 312 papers, Effect: 0.98, Lag: 6h

💡 This analysis uses INDRA bio-ontology for evidence-based causal pathways.
```

### General Queries (Uses OpenAI)

**User:** "What's the weather like in San Francisco?"

**Bot Response:** [Standard ChatGPT response using OpenAI]

## Configuration Files

### healthos_bot Configuration

- **config/config.yml**: Main bot settings (tokens, allowed users, features)
- **config/config.env**: Environment variables (AWS credentials, MongoDB, etc.)
- **config/chat_modes.yml**: Bot personality definitions
- **config/models.yml**: OpenAI model configurations

### indra_agent Configuration

- **indra_agent/config/agent_config.py**: Agent prompts and system instructions
- **indra_agent/config/cached_responses.py**: Pre-cached INDRA paths for reliability
- AWS credentials in `healthos_bot/config/config.env` (shared)

## User Health Data Management

Users can store personal health context in MongoDB for personalized analysis:

```python
# Store user genetics
db.set_user_attribute(user_id, 'health_genetics', {
    'GSTM1': 'null',
    'CYP1A1': 'T/T'
})

# Store current biomarkers
db.set_user_attribute(user_id, 'health_biomarkers', {
    'CRP': 5.2,  # mg/L
    'IL-6': 3.8  # pg/mL
})

# Store location history (for environmental exposure analysis)
db.set_user_attribute(user_id, 'health_location_history', [
    {
        'city': 'San Francisco',
        'start_date': '2024-01-01',
        'end_date': '2024-06-01',
        'avg_pm25': 12.5
    }
])
```

This context is automatically included in INDRA queries for personalized health insights.

## Technical Implementation

### Integration Points

**File**: `healthos_bot/bot/bot.py`

**Lines 37-51**: Import INDRA modules
```python
from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (...)
```

**Lines 60-68**: Initialize INDRA client singleton
```python
indra_client = INDRAAgentClient()
```

**Lines 111-133**: Health query detection function
```python
def is_health_query(message_text: str) -> bool:
```

**Lines 136-201**: INDRA query processing function
```python
async def query_indra_health_system(user_id: int, message_text: str):
```

**Lines 204-272**: Result formatting for Telegram
```python
def format_indra_response(response) -> str:
```

**Lines 827-880**: Message handler integration
```python
if _message and is_health_query(_message) and INDRA_AVAILABLE:
    indra_result = await query_indra_health_system(user_id, _message)
```

### INDRA Agent Workflow

1. **Entity Extraction**: Supervisor extracts biomarkers and exposures from query
2. **Entity Grounding**: Map entities to INDRA database IDs (HGNC, MESH, GO, CHEBI)
3. **Path Discovery**: Query INDRA API for causal pathways
4. **Graph Construction**: Build causal graph with evidence and confidence scores
5. **Result Synthesis**: Generate human-readable explanations
6. **Telegram Formatting**: Format for HTML display in Telegram

### Performance Characteristics

- **Health Query Time**: 2-5 seconds (includes AWS Bedrock LLM calls)
- **OpenAI Fallback**: Automatic if INDRA fails or unavailable
- **No HTTP Overhead**: Direct function calls (microseconds vs milliseconds)
- **Caching**: Pre-cached INDRA responses for common queries

## Project Structure

```
digitalme/
├── pyproject.toml                  # Root project config for indra_agent
├── indra_agent/                    # Health intelligence backend
│   ├── agents/                     # LangGraph agents
│   │   ├── supervisor.py           # Orchestration
│   │   ├── indra_query_agent.py    # INDRA queries
│   │   ├── web_researcher.py       # Environmental data
│   │   ├── state.py                # State management
│   │   └── graph.py                # Workflow definition
│   ├── core/
│   │   ├── client.py               # Main client interface
│   │   └── models.py               # Pydantic models
│   ├── services/
│   │   ├── grounding_service.py    # Entity grounding
│   │   ├── indra_service.py        # INDRA API wrapper
│   │   └── graph_builder.py        # Graph construction
│   └── config/
│       ├── agent_config.py         # Agent prompts
│       └── cached_responses.py     # Pre-cached paths
└── healthos_bot/                   # Telegram bot
    ├── bot/
    │   ├── bot.py                  # Main bot (imports indra_agent)
    │   ├── config.py               # Configuration loader
    │   ├── database.py             # MongoDB abstraction
    │   └── openai_utils.py         # OpenAI utilities
    ├── config/
    │   ├── config.yml              # Bot settings
    │   ├── config.env              # Environment variables
    │   ├── chat_modes.yml          # Bot personalities
    │   └── models.yml              # OpenAI models
    ├── Dockerfile                  # Docker build
    └── docker-compose.yml          # Docker orchestration
```

## Troubleshooting

### "Module not found: indra_agent"

**Cause**: Editable install failed or Docker build context incorrect

**Check**:
```bash
docker exec chatgpt_telegram_bot ls /opt/indra_agent
# Should see: agents/, core/, services/
```

**Fix**: Rebuild with correct build context:
```bash
cd healthos_bot/
docker-compose down
docker-compose --env-file config/config.env up --build
```

### AWS Bedrock Access Denied

**Cause**: Missing or invalid AWS credentials

**Fix**: Add correct credentials to `healthos_bot/config/config.env`:
```bash
AWS_ACCESS_KEY_ID=your-real-key
AWS_SECRET_ACCESS_KEY=your-real-secret
AWS_REGION=us-east-1
```

Verify AWS Bedrock access and Claude Sonnet 4.5 availability in your region.

### Health Queries Not Detected

**Cause**: Query doesn't contain health keywords

**Check**: Message includes: `biomarker`, `crp`, `pollution`, `genetic`, `health`, etc.

**Fix**: Add more keywords to `is_health_query()` in `bot.py:111`

### INDRA Falls Back to OpenAI

**Cause**: INDRA query failed or timed out

**Check logs**:
```bash
docker logs chatgpt_telegram_bot | grep "INDRA"
```

**Common issues**:
- INDRA API timeout (cached responses used automatically)
- Invalid entity grounding
- AWS Bedrock rate limits

### Bot Logs

**Check INDRA initialization:**
```bash
docker logs chatgpt_telegram_bot | grep "INDRA"
```

**Expected output:**
```
INDRA agent modules imported successfully
INDRA agent client initialized
```

**Health query detection:**
```
Health query detected from user 12345: How does PM2.5...
Calling INDRA agent for user 12345
```

## Testing

### Test Health Integration

```bash
# Start bot
cd healthos_bot/
docker-compose --env-file config/config.env up

# Send test message to bot via Telegram
# "How does pollution affect inflammation?"

# Check logs
docker logs chatgpt_telegram_bot -f
```

### Test INDRA Agent Standalone (Development)

```bash
cd ..
pip install -e .

# Run FastAPI server
python -m indra_agent.main

# Open browser
open http://localhost:8000/docs

# Test causal discovery endpoint
curl -X POST http://localhost:8000/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_request.json
```

## High-Level Architecture

### LangGraph Multi-Agent System

The system uses a **supervisor pattern** where a central orchestrator routes work to specialist agents:

```
User Request → FastAPI → LangGraph Workflow
                         ├─ Supervisor (orchestration)
                         ├─ INDRA Query Agent (bio-ontology)
                         └─ Web Researcher (environmental data)
```

**Workflow execution** (`indra_agent/agents/graph.py`):
1. Supervisor receives request and extracts entities
2. Routes to Web Researcher (if location data present) or INDRA Agent (otherwise)
3. INDRA Agent queries INDRA API, builds causal graph
4. Web Researcher fetches pollution data, calculates exposure deltas
5. Supervisor synthesizes results, generates explanations

**State management** (`indra_agent/agents/state.py`):
- Shared `OverallState` TypedDict passed between all agents
- Contains: request context, extracted entities, agent results, routing info
- Each agent updates state, supervisor decides next routing

### INDRA Integration Strategy

**Entity Grounding** (`indra_agent/services/grounding_service.py`):
- Pre-defined mappings for common entities (CRP → HGNC:2367, PM2.5 → MESH:D052638)
- Fallback to INDRA grounding API for unknown entities
- Database priority: HGNC (genes) > MESH (chemicals) > GO (processes) > CHEBI

**Path Discovery** (`indra_agent/services/indra_service.py`):
- Multi-strategy: direct path search + neighborhood expansion
- Ranks paths by: evidence count (40%), belief score (30%), path length (30%)
- Caches responses in `config/cached_responses.py` for demo reliability

**Graph Construction** (`indra_agent/services/graph_builder.py`):
- Converts INDRA paths to API-compliant causal graphs
- Effect size: `min(belief * 0.8 + evidence_boost, 0.95)` where boost depends on paper count
- Temporal lag: mapped by statement type (Phosphorylation: 1h, IncreaseAmount: 12h, etc.)

### API Contract Compliance

**Critical constraints** (see `agentic-system-spec.md`):
- `effect_size` MUST be ∈ [0, 1] (used for Monte Carlo weights)
- `temporal_lag_hours` MUST be ≥ 0 (causality violation otherwise)
- Node types MUST be: "environmental" | "molecular" | "biomarker" | "genetic"
- Relationship types MUST be: "activates" | "inhibits" | "increases" | "decreases"

**Genetic modifiers**:
- Applied via `config/cached_responses.py::get_genetic_modifier()`
- Only included if affected nodes present in graph
- Examples: GSTM1_null amplifies oxidative_stress by 1.3×

## Key Configuration Files

### Environment Variables (.env)
Required:
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`: Bedrock access
- Model: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

Optional:
- `IQAIR_API_KEY`: Real-time pollution data
- `INDRA_BASE_URL`: Default https://db.indra.bio
- `APP_PORT`: Default 8000

### Agent Prompts (config/agent_config.py)
- Supervisor: Orchestration, entity extraction, explanation generation
- INDRA Agent: Entity grounding, path search, graph building
- Web Researcher: Pollution data, exposure deltas

All agents use temperature=0.0 for deterministic output.

## Important Implementation Details

### Temporal Lag Estimation
Based on biological mechanism type (see `TEMPORAL_LAG_MAP` in `graph_builder.py`):
- Fast signaling (Phosphorylation): 1 hour
- Protein binding (Complex): 2 hours
- Transcription factor (Activation): 6 hours
- Gene expression (IncreaseAmount): 12 hours

### Effect Size Calculation
Combines INDRA belief score with evidence count:
```python
effect = belief * 0.8
if evidence_count > 100: effect += 0.15
elif evidence_count > 50: effect += 0.10
elif evidence_count > 20: effect += 0.05
return min(effect, 0.95)  # Cap to avoid determinism
```

### Pre-cached Responses
For hackathon reliability, key paths are cached:
- PM2.5 → IL-6 (via NF-κB): 47 papers, belief 0.82
- IL-6 → CRP: 312 papers, belief 0.98
- PM2.5 → oxidative stress: 31 papers, belief 0.78

Fallback to cache if INDRA API unavailable.

### Node Type Inference
Heuristic-based (`_infer_node_type` in `graph_builder.py`):
- MESH database OR known exposures → "environmental"
- GO database OR known processes → "molecular"
- Known clinical markers (CRP, IL-6, 8-OHdG) → "biomarker"
- Default → "molecular"

## Troubleshooting

### "No module named 'indra_agent'"
Install in editable mode: `pip install -e .`

### AWS Bedrock access issues
1. Check credentials in `.env`
2. Verify Bedrock access in your AWS account
3. Confirm Claude Sonnet 4.5 available in region (us-east-1 recommended)
4. Model ID: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`

### INDRA API timeouts
System automatically falls back to cached responses. Check logs for "using cache" warnings.

### Port 8000 in use
Set `APP_PORT=8001` in `.env` or use `uvicorn indra_agent.main:app --port 8001`

## Project Structure Notes

**Service layer** (`indra_agent/services/`): Stateless services for INDRA API, grounding, graph building, web data. These are called by agents but contain no LLM logic.

**Agent layer** (`indra_agent/agents/`): LangGraph agents with AWS Bedrock LLMs. Each agent has system prompt in `config/agent_config.py`.

**Core layer** (`indra_agent/core/`): Pydantic models matching API specification, client wrappers, state management.

**API layer** (`indra_agent/api/`): FastAPI routes that invoke LangGraph workflow.

## API Response Format

Always return status="success" even if no paths found (empty graph). Only return status="error" for:
- `NO_CAUSAL_PATH`: Query nonsensical (e.g., "coffee affects eye color")
- `TIMEOUT`: Processing took >5 seconds
- `INVALID_REQUEST`: Missing required fields

Explanations must be 3-5 items, each <200 characters. Priority order:
1. Environmental delta (if location history present)
2. Genetic context (if variants affect graph)
3. Highest evidence edge
4. Causal chain summary
5. Expected outcome

## Testing Strategy

**Unit tests**: Test individual services (grounding, graph builder, etc.)
**Integration tests**: Test full workflow with cached INDRA responses
**Contract tests**: Validate response against API specification (effect_size range, temporal_lag ≥ 0, etc.)

Use pytest fixtures in `tests/fixtures/` for sample requests/responses.
