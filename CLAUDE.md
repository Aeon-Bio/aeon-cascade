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
  -d '{
    "request_id": "test-123",
    "user_context": {"user_id": "test", "genetics": {}, "current_biomarkers": {}, "location_history": []},
    "query": {"text": "How does PM2.5 affect CRP?"},
    "options": {"max_graph_depth": 4, "min_evidence_count": 2}
  }'
```

## Key Benefits

✅ **Performance**: Function calls are microseconds vs milliseconds for HTTP
✅ **Simplicity**: One service, one deployment, one health check
✅ **Shared Resources**: Common AWS Bedrock client, MongoDB connection, caching
✅ **Easier Debugging**: Single process, unified logging, Python debugger works
✅ **Hackathon-Friendly**: Faster development, fewer moving parts
✅ **Evidence-Based**: All health insights backed by peer-reviewed research

## Architecture Benefits

### Why Direct Python Imports?

**Chosen over HTTP/REST API because:**
- ❌ HTTP adds unnecessary complexity for monolithic Python application
- ❌ HTTP serialization/deserialization overhead
- ❌ Network latency between containers
- ❌ Two services to deploy, monitor, and debug
- ❌ Connection pool management complexity

**Direct imports provide:**
- ✅ Microsecond function calls vs millisecond HTTP requests
- ✅ Single service deployment (one container, one health check)
- ✅ Shared AWS Bedrock client and connection pooling
- ✅ Unified logging and debugging (Python debugger works)
- ✅ No infrastructure costs for separate service

## Documentation

- **INTEGRATION_GUIDE.md**: Comprehensive integration documentation
- **DOCKER_FIXES_SUMMARY.md**: Docker build context fixes and details
- **agentic-system-spec.md**: INDRA API contract specification

---

**Status**: ✅ Production-ready integration
**Deployment**: ✅ Single-command Docker deployment
**Architecture**: ✅ Direct Python imports (no HTTP)
**Health Intelligence**: ✅ INDRA bio-ontology integrated
**Hackathon-Ready**: ✅ Fast, simple, fewer moving parts
