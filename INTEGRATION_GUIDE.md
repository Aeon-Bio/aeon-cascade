# healthOS Integration Guide

## Overview

The healthOS Telegram bot now includes **direct Python integration** with the INDRA agent for health intelligence queries. When users ask health-related questions, the bot automatically routes them to the INDRA bio-ontology system for evidence-based causal pathway analysis.

## Architecture

```
User → Telegram → healthos_bot/bot.py
                       ↓
                  [Health Query Detection]
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
     Health Query           General Query
            ↓                     ↓
    INDRA Agent (direct)    OpenAI GPT-4
    (Bio-ontology)          (Conversational)
            ↓                     ↓
    Formatted Result        Chat Response
            ↓                     ↓
        Telegram Reply      Telegram Reply
```

## Key Features

✅ **Direct Python Import**: No HTTP overhead - indra_agent runs in same process
✅ **Automatic Detection**: Health keywords trigger INDRA analysis
✅ **Fallback Support**: Falls back to OpenAI if INDRA unavailable
✅ **Rich Formatting**: Telegram-optimized display with causal pathways
✅ **Single Container**: One Docker container runs both systems

## Setup Instructions

### 1. Configure AWS Bedrock Credentials

Edit `healthos_bot/config/config.env` and add your AWS credentials:

```bash
# AWS Bedrock Configuration (for INDRA health intelligence agent)
AWS_ACCESS_KEY_ID=your-actual-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-actual-aws-secret-access-key
AWS_REGION=us-east-1
```

### 2. Build and Run with Docker

```bash
cd healthos_bot/

# Build and start all services
docker-compose --env-file config/config.env up --build
```

The bot will automatically:
- Install both healthos_bot and indra_agent dependencies
- Initialize INDRA client at startup
- Detect health queries and route to INDRA

### 3. Test Health Queries

Send health-related messages to the bot:

**Example Queries:**
- "How does PM2.5 pollution affect CRP biomarkers?"
- "What's the causal pathway between air quality and inflammation?"
- "Explain the relationship between oxidative stress and IL-6"
- "How do genetic variants like GSTM1 affect pollution impact?"

**Trigger Keywords:**
The bot detects health queries using keywords: `biomarker`, `crp`, `il-6`, `inflammation`, `pollution`, `pm2.5`, `genetic`, `health`, `causal`, `pathway`, `environmental`, etc.

## Health Query Response Format

When INDRA processes a health query, users receive:

```
🧬 Health Intelligence Report

📊 Key Insights:
1. [Evidence-based insight about environmental exposure]
2. [Genetic context if applicable]
3. [Highest evidence causal relationship]

🔬 Causal Analysis:
• X biological entities identified
• Y causal relationships found
• Based on Z scientific papers
• Analysis time: Nms

🔗 Top Causal Pathways:
  PM2.5 ⬆️ IL-6
  Evidence: 47 papers, Effect: 0.82, Lag: 12h

  IL-6 ⬆️ CRP
  Evidence: 312 papers, Effect: 0.98, Lag: 6h

🧬 Genetic Factors:
  ⬆️ GSTM1_null: amplifies effect by 1.3x

💡 This analysis uses INDRA bio-ontology for evidence-based causal pathways.
```

## User Health Data Management

Users can store personal health context in MongoDB:

```python
# Store user genetics
db.set_user_attribute(user_id, 'health_genetics', {
    'GSTM1': 'null',
    'CYP1A1': 'T/T'
})

# Store current biomarkers
db.set_user_attribute(user_id, 'health_biomarkers', {
    'CRP': 5.2,  # mg/L
    'IL-6': 3.8   # pg/mL
})

# Store location history
db.set_user_attribute(user_id, 'health_location_history', [
    {
        'city': 'San Francisco',
        'start_date': '2024-01-01',
        'end_date': '2024-06-01',
        'avg_pm25': 12.5
    }
])
```

This context is automatically included in INDRA queries for personalized analysis.

## Development Mode (Local Testing)

For local development without Docker:

```bash
# Install both projects in editable mode
cd healthos_bot/
pip install -r requirements.txt
pip install -e ../

cd ../
pip install -e .

# Run bot directly
cd healthos_bot/
python3 bot/bot.py
```

## Integration Points

### bot.py Integration

```python
# healthos_bot/bot/bot.py (lines 37-51)

# Import indra_agent modules
from indra_agent.core.client import INDRAAgentClient
from indra_agent.core.models import (
    CausalDiscoveryRequest,
    UserContext,
    Query,
    LocationHistory,
    RequestOptions
)

# Initialize client (singleton)
indra_client = INDRAAgentClient()
```

### Health Query Detection (line 111-133)

```python
def is_health_query(message_text: str) -> bool:
    """Detect health-related queries for INDRA routing."""
    health_keywords = [
        'biomarker', 'crp', 'il-6', 'inflammation',
        'pollution', 'pm2.5', 'genetic', 'health', ...
    ]
    return any(keyword in message_text.lower() for keyword in health_keywords)
```

### INDRA Query Function (line 136-201)

```python
async def query_indra_health_system(user_id: int, message_text: str) -> dict:
    """Query INDRA agent directly (no HTTP)."""
    # Build user context from DB
    user_context = UserContext(
        user_id=str(user_id),
        genetics=db.get_user_attribute(user_id, 'health_genetics') or {},
        current_biomarkers=db.get_user_attribute(user_id, 'health_biomarkers') or {},
        location_history=db.get_user_attribute(user_id, 'health_location_history') or []
    )

    # Create request
    request = CausalDiscoveryRequest(
        request_id=str(uuid.uuid4()),
        user_context=user_context,
        query=Query(text=message_text),
        options=RequestOptions()
    )

    # Call INDRA directly (no HTTP)
    response = await indra_client.process_request(request)

    return {'success': True, 'response': format_indra_response(response), 'graph': response}
```

### Message Handler Integration (line 827-880)

The message handler now checks for health queries before routing to OpenAI:

```python
async def message_handle_fn():
    # Check if health query
    if _message and is_health_query(_message) and INDRA_AVAILABLE:
        logger.info(f"Health query detected from user {user_id}")

        # Query INDRA system
        indra_result = await query_indra_health_system(user_id, _message)

        if indra_result['success']:
            # Use INDRA response
            await update.message.reply_text(indra_result['response'], parse_mode=ParseMode.HTML)
            return

    # Fall through to OpenAI for non-health or failed queries
    chatgpt_instance = openai_utils.ChatGPT(model=current_model)
    # ... existing OpenAI logic
```

## Troubleshooting

### INDRA Agent Not Available

**Symptom**: Bot logs `INDRA agent not available: No module named 'indra_agent'`

**Solution**: Ensure Dockerfile properly installs indra_agent:
```bash
docker-compose down
docker-compose --env-file config/config.env up --build
```

### AWS Bedrock Access Denied

**Symptom**: `Error querying INDRA system: AccessDeniedException`

**Solution**:
1. Verify AWS credentials in `config/config.env`
2. Ensure AWS account has Bedrock access
3. Confirm Claude Sonnet 4.5 is available in your region (us-east-1)

### Health Queries Not Detected

**Symptom**: Health questions go to OpenAI instead of INDRA

**Solution**: Check if query contains health keywords. Add more keywords to `is_health_query()` in bot.py:111

### INDRA Falls Back to OpenAI

**Symptom**: `Health system error: ... Using general AI instead.`

**Solution**: Check INDRA agent logs for specific errors. Common issues:
- INDRA API timeout (cached responses will be used)
- Invalid entity grounding
- AWS Bedrock rate limits

## Performance Notes

- **INDRA Query Time**: 2-5 seconds (includes LLM calls to AWS Bedrock)
- **OpenAI Fallback**: Automatic if INDRA fails or unavailable
- **No HTTP Overhead**: Direct function calls within same Python process
- **Caching**: Pre-cached INDRA responses for common queries (PM2.5 → CRP, etc.)

## Next Steps

1. **Add User Commands**: `/health_profile` to manage genetics/biomarkers
2. **Proactive Monitoring**: Alert users when biomarkers change
3. **Location Integration**: Auto-detect pollution exposure from Telegram location
4. **Multi-modal Input**: Parse lab report images with GPT-4 Vision

## Architecture Benefits

✅ **Simplicity**: One service, one deployment, one health check
✅ **Performance**: Microsecond function calls vs millisecond HTTP requests
✅ **Reliability**: Shared AWS Bedrock client, connection pooling
✅ **Debugging**: Single process, unified logging, Python debugger works
✅ **Cost**: No separate service infrastructure costs

## Files Modified

1. `healthos_bot/bot/bot.py`: Added INDRA integration (lines 37-880)
2. `healthos_bot/Dockerfile`: Install indra_agent dependencies
3. `healthos_bot/docker-compose.yml`: Add AWS environment variables
4. `healthos_bot/config/config.env`: AWS Bedrock credentials template

---

For more details, see the main project documentation in `/CLAUDE.md`
