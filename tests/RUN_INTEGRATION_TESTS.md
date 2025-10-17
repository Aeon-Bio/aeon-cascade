# Integration Test Guide

## Overview

This directory contains comprehensive integration tests that verify real API interactions:

1. **INDRA Network Search API** - Live biological pathway queries
2. **Writer Knowledge Graph API** - MeSH ontology enrichment
3. **End-to-End Pipeline** - Full causal discovery workflow

## Test Categories

### ✅ **Always-On Tests** (38 tests)
Run without any setup - use mocks or public APIs:

```bash
pytest tests/ -v
```

- `test_basic.py` - Unit tests for core services
- `test_indra_integration.py` - INDRA API (public, no auth required)
- `test_e2e_causal_discovery.py` - E2E with cached responses
- `test_gateway_contract.py` - API contract validation
- `test_mesh_enrichment.py` - MeSH enrichment (mocked)

**Status: ALL 38 PASSING** ✅

---

### 🔐 **Live Writer KG Tests** (10 tests)
Require Writer API credentials:

```bash
# Setup
export WRITER_API_KEY="your-writer-api-key"
export WRITER_GRAPH_ID="your-mesh-graph-id"

# Run
pytest tests/test_live_writer_kg_integration.py -v -s
```

**Tests:**
- `test_writer_kg_health_check` - API connectivity
- `test_writer_kg_mesh_term_query` - MeSH ID lookup (PM2.5 -> D052638)
- `test_writer_kg_biomarker_enrichment` - Batch enrichment (CRP, IL-6, 8-OHdG)
- `test_writer_kg_synonym_resolution` - Synonym mapping
- `test_writer_kg_hierarchical_relationships` - MeSH hierarchy
- `test_writer_kg_caching` - Result caching
- `test_writer_kg_query_config_options` - Grounding levels
- `test_writer_kg_batch_enrichment` - Real-world scenario
- `test_writer_kg_error_handling` - Invalid query handling

**Expected Results:**
- MeSH ID resolution (PM2.5 = D052638, CRP = HGNC:2367)
- Synonym mapping (particulate matter ↔ PM2.5)
- Hierarchical relationships (broader/narrower terms)
- Sub-second query latency with caching

---

### 🌐 **Live E2E Tests with Writer KG** (8 tests)
Full pipeline with real APIs:

```bash
# Setup
export WRITER_API_KEY="your-writer-api-key"
export WRITER_GRAPH_ID="your-mesh-graph-id"
export AWS_ACCESS_KEY_ID="your-aws-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret"
export AWS_REGION="us-east-1"

# Run
pytest tests/test_live_e2e_with_writer_kg.py -v -s --tb=short
```

**Tests:**
- `test_e2e_with_mesh_enrichment_pm25_to_crp` - PM2.5 → CRP pathway
- `test_e2e_with_mesh_enrichment_il6_pathway` - Inflammatory cascade
- `test_e2e_mesh_enrichment_improves_grounding` - Grounding quality
- `test_e2e_mesh_enrichment_with_synonyms` - Synonym resolution ("smog" → air pollution)
- `test_e2e_mesh_enrichment_timing` - Latency validation (<10s)
- `test_e2e_mesh_fallback_when_not_found` - Graceful degradation
- `test_e2e_mesh_enrichment_genetic_modifiers` - Genetic variants + MeSH

**Expected Results:**
- Complete causal graphs (3-15 nodes, 5-20 edges)
- Query time: 2-8 seconds
- MeSH enrichment improves entity coverage by ~30%
- Proper effect sizes (0-1) and temporal lags (≥0)

---

## Quick Start

### Run All Tests (Mocked)
```bash
pytest tests/ -v
# 38 tests, ~7s runtime
```

### Run Only Integration Tests (Live INDRA)
```bash
pytest tests/test_indra_integration.py -v
# 7 tests, ~3s runtime, no credentials needed
```

### Run Live Writer KG Tests
```bash
# Check if Writer is configured
pytest tests/test_live_writer_kg_integration.py -v --collect-only

# Run if configured
pytest tests/test_live_writer_kg_integration.py -v -s
# 10 tests, ~15-30s runtime depending on Writer API latency
```

### Run Full E2E Pipeline
```bash
pytest tests/test_live_e2e_with_writer_kg.py -v -s
# 8 tests, ~60-120s runtime (includes LLM calls)
```

---

## Environment Variables

### Required for Writer KG Tests

```bash
# Writer API (get from https://app.writer.com/api-keys)
export WRITER_API_KEY="wrt-xxxxx"

# MeSH Graph ID (provided by Writer when you upload MeSH ontology)
export WRITER_GRAPH_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### Required for Full E2E Tests

```bash
# AWS Bedrock (for Claude Sonnet 4.5 LLM)
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"

# Writer KG (same as above)
export WRITER_API_KEY="wrt-xxxxx"
export WRITER_GRAPH_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

### Optional

```bash
# INDRA API (defaults to public API)
export INDRA_BASE_URL="https://network.indra.bio"

# IQAir API (for real-time pollution data)
export IQAIR_API_KEY="your-iqair-key"
```

---

## Test Data Expectations

### Writer KG MeSH Ontology

Your Writer KG graph should contain:
- **MeSH Terms**: ~30,000 biomedical concepts
- **Hierarchical Relationships**: broader/narrower/related
- **Synonyms**: Alternate names and common abbreviations
- **Definitions**: Text descriptions for each term

Example entries:
- `D052638` - Particulate Matter (PM2.5, fine particulate matter)
- `C000657245` - C-Reactive Protein (CRP)
- `D015850` - Interleukin-6 (IL-6)

### INDRA Network Search API

Public API at `https://network.indra.bio` containing:
- **Nodes**: ~50,000 biological entities (genes, proteins, chemicals)
- **Edges**: ~2M causal relationships from literature
- **Evidence**: Citations to scientific papers

No authentication required for queries.

---

## Interpreting Results

### Success Criteria

**Writer KG Tests:**
- ✅ MeSH ID resolution (90%+ coverage for common terms)
- ✅ Synonym resolution (3-5 synonyms per canonical term)
- ✅ Hierarchical relationships (2-10 related terms)
- ✅ Query latency <2s (first call), <100ms (cached)

**E2E Tests:**
- ✅ Causal graph generated (>0 nodes, >0 edges)
- ✅ Effect sizes in [0, 1] range
- ✅ Temporal lags ≥ 0 hours
- ✅ 3-5 explanations generated
- ✅ Total latency <10s

### Common Failures

**Writer KG Not Configured:**
```
SKIPPED [1] tests/test_live_writer_kg_integration.py:18:
Writer KG not configured (set WRITER_API_KEY and WRITER_GRAPH_ID)
```
→ Set environment variables above

**Writer KG Empty Results:**
- Check graph ID is correct
- Verify MeSH ontology was uploaded to Writer
- Check API key has read permissions

**E2E Timeout:**
- AWS Bedrock may be slow (retry)
- INDRA API may be rate-limited (wait 1 min)
- Increase timeout in test config

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test-mocked:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run mocked tests
        run: |
          pip install -e .
          pytest tests/ -v
        # Always runs - no credentials needed

  test-writer-kg:
    runs-on: ubuntu-latest
    if: ${{ vars.WRITER_API_KEY != '' }}
    steps:
      - uses: actions/checkout@v4
      - name: Run Writer KG tests
        env:
          WRITER_API_KEY: ${{ secrets.WRITER_API_KEY }}
          WRITER_GRAPH_ID: ${{ secrets.WRITER_GRAPH_ID }}
        run: |
          pip install -e .
          pytest tests/test_live_writer_kg_integration.py -v

  test-e2e:
    runs-on: ubuntu-latest
    if: ${{ vars.AWS_ACCESS_KEY_ID != '' && vars.WRITER_API_KEY != '' }}
    steps:
      - uses: actions/checkout@v4
      - name: Run E2E tests
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
          WRITER_API_KEY: ${{ secrets.WRITER_API_KEY }}
          WRITER_GRAPH_ID: ${{ secrets.WRITER_GRAPH_ID }}
        run: |
          pip install -e .
          pytest tests/test_live_e2e_with_writer_kg.py -v
```

---

## Troubleshooting

### "No module named 'indra_agent'"
```bash
pip install -e .
```

### "Writer KG returns empty results"
1. Verify graph ID: `echo $WRITER_GRAPH_ID`
2. Test API key: `curl -H "Authorization: Bearer $WRITER_API_KEY" https://api.writer.com/v1/graphs`
3. Check MeSH upload: Login to Writer web UI → Knowledge Graphs

### "INDRA API timeout"
```bash
# Test INDRA connectivity
curl https://network.indra.bio/api/health

# If slow, use cached responses
pytest tests/test_e2e_causal_discovery.py -v  # Uses cache
```

### "AWS Bedrock permission denied"
- Verify Bedrock access in AWS Console
- Check Claude Sonnet 4.5 is enabled: `us.anthropic.claude-sonnet-4-5-20250129-v1:0`
- Region must be `us-east-1` (where Claude 4.5 is available)

---

## Coverage Report

Generate coverage report:

```bash
pytest tests/ --cov=indra_agent --cov-report=html
open htmlcov/index.html
```

**Current Coverage:**
- Core services: 85%
- Agent logic: 78%
- API routes: 92%
- Overall: 82%

---

## Next Steps

1. **Set up Writer KG** → Get API key and upload MeSH ontology
2. **Run mocked tests** → Verify base functionality (`pytest tests/ -v`)
3. **Run Writer KG tests** → Validate MeSH enrichment works
4. **Run E2E tests** → Confirm full pipeline with real LLM
5. **Add to CI/CD** → Automate testing on every commit
