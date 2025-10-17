#!/bin/bash

# Documentation Cleanup Script
# Consolidates documentation from aeon-gateway/docs to root /docs directory

set -e  # Exit on error

echo "🧹 Starting documentation cleanup..."

# Step 1: Copy architecture docs
echo "📁 Copying architecture docs..."
cp aeon-gateway/docs/architecture/boundaries-and-contracts.md docs/architecture/
cp aeon-gateway/docs/architecture/technology-stack.md docs/architecture/

# Step 2: Copy API specs
echo "📁 Copying API specs..."
cp aeon-gateway/docs/api/agentic-system-spec.md docs/api/
cp aeon-gateway/docs/api/ui-integration-spec.md docs/api/

# Step 3: Consolidate INDRA integration docs
echo "📁 Consolidating INDRA integration docs..."
cp aeon-gateway/docs/external-apis/indra-integration-guide.md docs/api/indra-integration.md

# Step 4: Copy deployment docs
echo "📁 Copying deployment docs..."
cp aeon-gateway/docs/deployment/local-development.md docs/deployment/

# Step 5: Copy requirements docs
echo "📁 Copying requirements docs..."
cp aeon-gateway/docs/requirements/demo-scenario.md docs/requirements/
cp aeon-gateway/docs/requirements/product-requirements.md docs/requirements/

# Step 6: Delete root-level duplicates
echo "🗑️  Deleting root-level duplicates..."
rm -f agentic-system-spec.md
rm -f indra-integration.md

# Step 7: Delete aeon-gateway duplicates
echo "🗑️  Deleting aeon-gateway duplicates..."
rm -f aeon-gateway/docs/api/indra-integration.md

# Step 8: Create root docs README
echo "📝 Creating root docs README..."
cat > docs/README.md << 'EOF'
# INDRA Bio-Ontology Agentic System Documentation

## Architecture

Two-service architecture for personalized health predictions:

1. **indra_agent** (port 8000)
   - Queries INDRA bio-ontology
   - Generates causal graphs
   - Resolves biomarkers to mechanisms
   - See: [architecture/indra-agent.md](architecture/indra-agent.md)

2. **aeon-gateway** (port 8001)
   - Temporal Bayesian modeling
   - Biomarker predictions
   - UI integration
   - See: [architecture/aeon-gateway.md](architecture/aeon-gateway.md)

## Quick Start

```bash
# Terminal 1: Start indra_agent
cd indra_agent
python -m indra_agent.main

# Terminal 2: Start aeon-gateway
cd aeon-gateway
export AGENTIC_SYSTEM_URL=http://localhost:8000
uvicorn src.main:app --reload --port 8001

# Terminal 3: Test integration
curl -X POST http://localhost:8001/api/v1/gateway/query \
  -H "Content-Type: application/json" \
  -d @docs/requirements/demo-scenario.json
```

See [deployment/local-development.md](deployment/local-development.md) for detailed setup.

## API Contracts

### For Agentic System Developers
- **Spec**: [api/agentic-system-spec.md](api/agentic-system-spec.md)
- **Endpoint**: `POST /api/v1/causal_discovery`
- **Responsibility**: INDRA queries, causal graph generation

### For UI Developers
- **Spec**: [api/ui-integration-spec.md](api/ui-integration-spec.md)
- **Endpoint**: `POST /api/v1/gateway/query`
- **Responsibility**: Temporal predictions, timeline data

### INDRA Integration
- **Guide**: [api/indra-integration.md](api/indra-integration.md)
- **Current**: Uses network.indra.bio for entity grounding
- **Strategy**: Pre-cached paths for demo reliability

## System Overview

```
┌─────────────┐
│   Frontend  │
│   (React)   │
└──────┬──────┘
       │ HTTP/JSON
┌──────▼──────────┐
│  aeon-gateway   │  Temporal modeling, predictions
│  (Port 8001)    │
└──────┬──────────┘
       │ HTTP/JSON
┌──────▼──────────┐
│  indra_agent    │  INDRA queries, causal graphs
│  (Port 8000)    │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  INDRA Network  │  Bio-ontology database
│  Search API     │
└─────────────────┘
```

## Documentation Structure

```
docs/
├── README.md                          # This file
├── architecture/
│   ├── system-overview.md            # High-level architecture
│   ├── boundaries-and-contracts.md   # Interface contracts
│   ├── technology-stack.md           # Tech choices
│   ├── indra-agent.md                # indra_agent details
│   └── aeon-gateway.md               # aeon-gateway details
├── api/
│   ├── agentic-system-spec.md        # Contract for indra_agent
│   ├── ui-integration-spec.md        # Contract for UI
│   └── indra-integration.md          # INDRA API usage
├── deployment/
│   ├── local-development.md          # Local setup
│   └── production.md                 # Production deployment
└── requirements/
    ├── demo-scenario.md              # Demo data & script
    └── product-requirements.md       # Product vision
```

## Contributing

See individual service READMEs:
- [indra_agent/README.md](../indra_agent/README.md)
- [aeon-gateway/README.md](../aeon-gateway/README.md)
EOF

# Step 9: Create service-specific architecture docs
echo "📝 Creating service-specific architecture docs..."
cat > docs/architecture/indra-agent.md << 'EOF'
# INDRA Agent Architecture

## Overview

LangGraph-based multi-agent system for querying INDRA bio-ontology.

## Responsibility

- Parse health queries
- Ground entities to INDRA identifiers
- Query INDRA for causal paths
- Build structured causal graphs
- Return evidence-backed relationships

## Implementation

See [/indra_agent/README.md](../../indra_agent/README.md) for details.

## API Contract

Implements: [api/agentic-system-spec.md](../api/agentic-system-spec.md)

**Endpoint**: `POST /api/v1/causal_discovery`

**Port**: 8000 (default)

## Key Components

- **Supervisor Agent**: Orchestrates workflow
- **INDRA Query Agent**: Queries bio-ontology
- **Web Researcher**: Fetches environmental data
- **Grounding Service**: Entity resolution
- **Graph Builder**: Constructs causal graphs

## INDRA Integration

Uses Network Search API (network.indra.bio):
- Entity grounding via autocomplete
- Node resolution
- Cross-reference lookup

Falls back to pre-cached responses for path search (Network Search API doesn't support path queries).

See [api/indra-integration.md](../api/indra-integration.md) for details.
EOF

cat > docs/architecture/aeon-gateway.md << 'EOF'
# Aeon Gateway Architecture

## Overview

Temporal Bayesian modeling service for personalized health predictions.

## Responsibility

- Accept queries from UI
- Forward to indra_agent for causal graphs
- Build temporal models (NetworkX + Monte Carlo)
- Generate biomarker predictions
- Return timeline data with confidence intervals

## Implementation

See [/aeon-gateway/README.md](../../aeon-gateway/README.md) for details.

## API Contract

Implements: [api/ui-integration-spec.md](../api/ui-integration-spec.md)

**Endpoint**: `POST /api/v1/gateway/query`

**Port**: 8001 (recommended, default 8000)

## Key Components

- **FastAPI Layer**: API endpoints, validation
- **Temporal Model Engine**: NetworkX graph + Monte Carlo simulation
- **Agentic Client**: HTTP client for indra_agent
- **Mock System**: Fallback for testing

## Integration

Calls indra_agent at `$AGENTIC_SYSTEM_URL` (default: http://localhost:8000)

Falls back to MockAgenticSystem if URL not set.
EOF

# Step 10: Create .env.example for aeon-gateway
echo "📝 Creating .env.example for aeon-gateway..."
cat > aeon-gateway/.env.example << 'EOF'
# Aeon Gateway Configuration

# Agentic System Integration
AGENTIC_SYSTEM_URL=http://localhost:8000  # indra_agent endpoint

# Server Configuration
APP_HOST=0.0.0.0
APP_PORT=8001  # Use 8001 to avoid conflict with indra_agent (8000)

# Logging
LOG_LEVEL=INFO
EOF

echo "✅ Documentation cleanup complete!"
echo ""
echo "Next steps:"
echo "1. Review the changes: git status"
echo "2. Test both services:"
echo "   - Terminal 1: cd indra_agent && python -m indra_agent.main"
echo "   - Terminal 2: cd aeon-gateway && export AGENTIC_SYSTEM_URL=http://localhost:8000 && uvicorn src.main:app --reload --port 8001"
echo "3. Commit changes: git add docs/ indra_agent/ aeon-gateway/ && git commit -m 'docs: consolidate documentation'"
