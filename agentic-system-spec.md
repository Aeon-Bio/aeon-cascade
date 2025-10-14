# Agentic System Interface Specification

## For: External Agentic System Developer

**Audience**: Team building the agentic system that queries INDRA
**Purpose**: Define the exact interface contract between your system and our gateway

---

## What You Build

An API endpoint that:
1. Receives health queries with user context
2. Queries INDRA for causal paths
3. Resolves biomarkers to molecular mechanisms
4. Returns structured causal graphs

**You OWN**: INDRA integration, natural language understanding, biomarker resolution
**We OWN**: Temporal modeling, predictions, UI

---

## Required Endpoint

### POST /api/v1/causal_discovery

**URL**: `https://your-domain.com/api/v1/causal_discovery`

**Method**: POST

**Content-Type**: application/json

### Request Format (What We Send You)

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_context": {
    "user_id": "sarah_chen",
    "genetics": {
      "GSTM1": "null",
      "GSTP1": "Val/Val",
      "TNF-alpha": "-308G/A",
      "SOD2": "Ala/Ala"
    },
    "current_biomarkers": {
      "CRP": 0.7,
      "IL-6": 1.1,
      "8-OHdG": 4.2
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
    "intent": "prediction",
    "focus_biomarkers": ["CRP", "IL-6"]
  },
  "options": {
    "max_graph_depth": 4,
    "min_evidence_count": 2,
    "include_interventions": false
  }
}
```

### Response Format (What You Return)

**Success Response** (HTTP 200):

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "success",
  "causal_graph": {
    "nodes": [
      {
        "id": "PM2.5",
        "type": "environmental",
        "label": "Particulate Matter (PM2.5)",
        "grounding": {
          "database": "MESH",
          "identifier": "D052638"
        }
      },
      {
        "id": "NFKB1",
        "type": "molecular",
        "label": "NF-κB p50",
        "grounding": {
          "database": "HGNC",
          "identifier": "7794"
        }
      },
      {
        "id": "IL6",
        "type": "molecular",
        "label": "Interleukin-6",
        "grounding": {
          "database": "HGNC",
          "identifier": "6018"
        }
      },
      {
        "id": "CRP",
        "type": "biomarker",
        "label": "C-Reactive Protein",
        "grounding": {
          "database": "HGNC",
          "identifier": "2367"
        }
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
          "summary": "Particulate matter exposure activates NF-κB signaling pathway"
        },
        "effect_size": 0.65,
        "temporal_lag_hours": 6
      },
      {
        "source": "NFKB1",
        "target": "IL6",
        "relationship": "increases",
        "evidence": {
          "count": 89,
          "confidence": 0.91,
          "sources": ["PMID:34567890"],
          "summary": "NF-κB transcriptionally activates IL-6 gene expression"
        },
        "effect_size": 0.78,
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
          "summary": "IL-6 stimulates hepatocyte CRP synthesis"
        },
        "effect_size": 0.90,
        "temporal_lag_hours": 24
      }
    ],
    "genetic_modifiers": [
      {
        "variant": "GSTM1_null",
        "affected_nodes": ["oxidative_stress"],
        "effect_type": "amplifies",
        "magnitude": 1.3
      },
      {
        "variant": "TNF-alpha_-308G/A",
        "affected_nodes": ["TNF", "IL6"],
        "effect_type": "amplifies",
        "magnitude": 1.2
      }
    ]
  },
  "metadata": {
    "query_time_ms": 1234,
    "indra_paths_explored": 15,
    "total_evidence_papers": 448
  },
  "explanations": [
    "PM2.5 exposure increased 3.4× after moving to LA (34.5 vs 7.8 µg/m³)",
    "Your GSTM1 null variant amplifies oxidative stress response by 30%",
    "PM2.5 activates NF-κB inflammatory signaling (47 papers, confidence: 0.82)",
    "NF-κB drives IL-6 production, which stimulates hepatic CRP synthesis",
    "Expected CRP elevation from 0.7 to ~2.4 mg/L based on environmental change"
  ]
}
```

**Error Response** (HTTP 200 with status="error"):

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "error": {
    "code": "NO_CAUSAL_PATH",
    "message": "Could not find causal path from PM2.5 to CRP within depth 4",
    "details": {
      "attempted_sources": ["PM2.5", "PM10", "ozone"],
      "attempted_targets": ["CRP", "IL-6"],
      "paths_found": 0,
      "max_depth_reached": true
    }
  },
  "partial_result": null
}
```

---

## Field Specifications

### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string (UUID) | Yes | Unique request identifier (echo back in response) |
| `user_context.user_id` | string | Yes | User identifier |
| `user_context.genetics` | object | Yes | Map of gene → variant (e.g., "GSTM1": "null") |
| `user_context.current_biomarkers` | object | Yes | Map of biomarker → value (e.g., "CRP": 0.7) |
| `user_context.location_history` | array | Yes | List of {city, start_date, end_date, avg_pm25} |
| `query.text` | string | Yes | Natural language query |
| `query.intent` | string | No | Hint: "prediction" \| "explanation" \| "intervention" |
| `query.focus_biomarkers` | array | No | Specific biomarkers to include |
| `options.max_graph_depth` | int | No | Max path length (default: 4) |
| `options.min_evidence_count` | int | No | Min papers per edge (default: 2) |

### Response Fields (Success)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string | Yes | Echo request_id |
| `status` | string | Yes | Must be "success" or "error" |
| `causal_graph.nodes` | array | Yes | List of nodes in graph |
| `causal_graph.nodes[].id` | string | Yes | Unique node identifier |
| `causal_graph.nodes[].type` | string | Yes | "environmental" \| "molecular" \| "biomarker" \| "genetic" |
| `causal_graph.nodes[].label` | string | Yes | Human-readable name |
| `causal_graph.nodes[].grounding.database` | string | Yes | "MESH" \| "HGNC" \| "CHEBI" \| "GO" |
| `causal_graph.nodes[].grounding.identifier` | string | Yes | Database-specific ID |
| `causal_graph.edges` | array | Yes | List of causal relationships |
| `causal_graph.edges[].source` | string | Yes | Source node ID |
| `causal_graph.edges[].target` | string | Yes | Target node ID |
| `causal_graph.edges[].relationship` | string | Yes | "activates" \| "inhibits" \| "increases" \| "decreases" |
| `causal_graph.edges[].evidence.count` | int | Yes | Number of supporting papers |
| `causal_graph.edges[].evidence.confidence` | float | Yes | 0-1 confidence score |
| `causal_graph.edges[].evidence.sources` | array | Yes | List of PMIDs |
| `causal_graph.edges[].evidence.summary` | string | Yes | One-sentence explanation |
| `causal_graph.edges[].effect_size` | float | Yes | **0-1** normalized effect strength |
| `causal_graph.edges[].temporal_lag_hours` | int | Yes | **≥0** hours from cause to effect |
| `causal_graph.genetic_modifiers` | array | Yes | Genetic variants that modulate paths |
| `metadata.query_time_ms` | int | Yes | Processing time |
| `explanations` | array | Yes | Human-readable explanations (3-5 items) |

### Response Fields (Error)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string | Yes | Echo request_id |
| `status` | string | Yes | Must be "error" |
| `error.code` | string | Yes | "NO_CAUSAL_PATH" \| "TIMEOUT" \| "INVALID_REQUEST" |
| `error.message` | string | Yes | Human-readable error |
| `error.details` | object | No | Additional context |

---

## Critical Constraints

### MUST SATISFY

1. **Effect Size Range**: `0 ≤ effect_size ≤ 1`
   - 0 = no effect
   - 1 = deterministic effect
   - We use this for Monte Carlo simulation weights

2. **Temporal Lag Non-Negative**: `temporal_lag_hours ≥ 0`
   - We use this for time-sliced modeling
   - Negative lag = causality violation

3. **Status Values**: Only "success" or "error"
   - We validate with Pydantic
   - Other values will cause ValidationError

4. **Node Types**: Only "environmental", "molecular", "biomarker", "genetic"
   - We use type for visualization colors
   - Other values will render incorrectly

5. **Relationship Types**: Only "activates", "inhibits", "increases", "decreases"
   - We interpret for causal direction
   - Other values ignored

### SHOULD SATISFY

1. **Response Time**: Aim for < 2 seconds
   - We timeout at 5 seconds
   - Show loading spinner in UI

2. **Explanations**: 3-5 items, each < 200 characters
   - We display verbatim in UI
   - More than 5 clutters interface

3. **Evidence Count**: Higher = better
   - We use for edge thickness visualization
   - Single-paper edges shown as dashed lines

---

## Example Query Scenarios

### Scenario 1: SF→LA Inflammation (Demo Query)

**Request**:
```json
{
  "request_id": "demo-001",
  "user_context": {
    "user_id": "sarah_chen",
    "genetics": {"GSTM1": "null", "GSTP1": "Val/Val"},
    "current_biomarkers": {"CRP": 0.7, "IL-6": 1.1},
    "location_history": [
      {"city": "San Francisco", "avg_pm25": 7.8},
      {"city": "Los Angeles", "avg_pm25": 34.5}
    ]
  },
  "query": {
    "text": "How will LA air quality affect my inflammation?",
    "focus_biomarkers": ["CRP", "IL-6"]
  }
}
```

**Expected Response**:
- Graph includes: PM2.5 → [intermediates] → IL6 → CRP
- Genetic modifier: GSTM1_null → oxidative_stress (magnitude ~1.3)
- Explanations mention 3.4× PM2.5 increase
- Evidence counts: IL6→CRP should have 200+ papers (well-studied)

### Scenario 2: Generic Query (Fallback)

**Request**:
```json
{
  "request_id": "generic-001",
  "user_context": {
    "user_id": "test_user",
    "genetics": {},
    "current_biomarkers": {},
    "location_history": []
  },
  "query": {
    "text": "Tell me about inflammation"
  }
}
```

**Expected Response**:
- Return empty or generic graph
- Explanations note insufficient context
- Still return status="success" (not an error)

### Scenario 3: No Path Found

**Request**:
```json
{
  "query": {
    "text": "How does coffee affect my eye color?"
  }
}
```

**Expected Response**:
```json
{
  "status": "error",
  "error": {
    "code": "NO_CAUSAL_PATH",
    "message": "No causal relationship found between coffee and eye color"
  }
}
```

---

## INDRA Integration Guidelines

### Recommended Workflow

1. **Parse Query**:
   - Extract entities (PM2.5, CRP, IL-6)
   - Identify environmental vs biomarker terms

2. **Ground Entities**:
   ```python
   # Use INDRA grounding service
   POST https://db.indra.bio/api/ground
   {
     "names": ["particulate matter", "PM2.5", "C-reactive protein"]
   }
   # Returns: [{"db": "MESH", "id": "D052638"}, ...]
   ```

3. **Query Path Search**:
   ```python
   GET https://db.indra.bio/api/network/path_search
   ?source=MESH:D052638
   &target=HGNC:2367
   &max_depth=4
   ```

4. **Extract Evidence**:
   - Count statements per edge
   - Compute INDRA belief scores
   - Map to our `effect_size` (0-1 range)

5. **Apply Genetic Context**:
   - If user has GSTM1 null, boost oxidative_stress edges
   - Add genetic_modifiers array

6. **Generate Explanations**:
   - Start with environmental delta (e.g., "PM2.5 increased 3.4×")
   - Mention genetic variants
   - Summarize causal chain

### Estimating Effect Size

INDRA provides `belief` scores (0-1). Map to `effect_size`:

```python
def indra_belief_to_effect_size(belief, evidence_count):
    # Baseline from belief
    effect = belief * 0.8

    # Boost for high evidence
    if evidence_count > 50:
        effect += 0.1
    elif evidence_count > 100:
        effect += 0.15

    # Cap at 0.95 (avoid determinism)
    return min(effect, 0.95)
```

### Estimating Temporal Lag

```python
def estimate_temporal_lag(statement_type):
    lags = {
        "Phosphorylation": 1,      # Fast signaling
        "Complex": 2,              # Protein binding
        "Activation": 6,           # Transcription factor
        "IncreaseAmount": 12,      # Gene expression
        "default": 6
    }
    return lags.get(statement_type, lags["default"])
```

---

## Testing

### Contract Test (We Provide)

We will provide a contract test suite you can run:

```bash
# Install
pip install aeon-gateway-contract-tests

# Run against your endpoint
aeon-contract-test https://your-domain.com/api/v1/causal_discovery

# Output
✓ Response has required fields
✓ Effect sizes in range [0, 1]
✓ Temporal lags non-negative
✓ Node types valid
✓ Pydantic validation passes
```

### Example Request for Testing

```bash
curl -X POST https://your-domain.com/api/v1/causal_discovery \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "test-123",
    "user_context": {
      "user_id": "test_user",
      "genetics": {"GSTM1": "null"},
      "current_biomarkers": {"CRP": 0.7},
      "location_history": [{"city": "Los Angeles", "avg_pm25": 34.5}]
    },
    "query": {
      "text": "How will LA affect my inflammation?",
      "focus_biomarkers": ["CRP"]
    }
  }'
```

### Minimum Viable Response (For Testing)

```json
{
  "request_id": "test-123",
  "status": "success",
  "causal_graph": {
    "nodes": [
      {"id": "PM2.5", "type": "environmental", "label": "PM2.5", "grounding": {"database": "MESH", "identifier": "D052638"}},
      {"id": "CRP", "type": "biomarker", "label": "CRP", "grounding": {"database": "HGNC", "identifier": "2367"}}
    ],
    "edges": [
      {
        "source": "PM2.5",
        "target": "CRP",
        "relationship": "increases",
        "evidence": {"count": 10, "confidence": 0.7, "sources": ["PMID:12345678"], "summary": "PM2.5 increases CRP"},
        "effect_size": 0.5,
        "temporal_lag_hours": 24
      }
    ],
    "genetic_modifiers": []
  },
  "metadata": {"query_time_ms": 100},
  "explanations": ["Test response"]
}
```

---

## Communication

**Questions**: [email/slack channel]

**Issue Reporting**: [github issues link]

**API Health**: We'll monitor your `/health` endpoint (please implement)

**SLA**: Target 99% uptime (we have fallback to cached responses)

---

## Versioning

Current version: **v1**

Breaking changes will be released as v2 with 30-day deprecation notice.

Non-breaking additions (new optional fields) can be added to v1.

---

## Success Criteria

Before integration:
- ✅ Contract tests pass
- ✅ Sarah's SF→LA query returns graph with PM2.5→IL6→CRP
- ✅ Response time < 2 seconds (p95)
- ✅ Effect sizes all in [0, 1]
- ✅ Temporal lags all ≥ 0

This is the contract. Build to this spec, and we integrate seamlessly.
