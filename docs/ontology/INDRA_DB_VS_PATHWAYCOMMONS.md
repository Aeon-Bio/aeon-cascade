# INDRA DB REST API vs PathwayCommons: Critical Finding

**Date**: 2025-11-01
**Question**: Does INDRA DB REST API contain environmental exposure data that PathwayCommons lacks?
**Answer**: CANNOT DETERMINE - API returns 0 statements for ALL queries (including known molecular pathways)

---

## Background

After discovering that `indranet_service.py` uses a DIFFERENT data source than my previous tests, I needed to verify if INDRA's statement database contains environmental pathways.

**Previous tests** (PathwayCommons):
- Endpoint: `/biopax/process_pc_pathsbetween`
- Result: **0 paths** for all environmental exposures

**Current system** (INDRA DB REST):
- Library: `indra.sources.indra_db_rest`
- Endpoint: `https://db.indra.bio`
- Result: Unknown (requires testing)

---

## Test Execution

### Test Script
`indra_agent/examples/test_indra_db_quick.py`

```python
import os
os.environ['INDRA_DB_REST_URL'] = 'https://db.indra.bio'

import indra.sources.indra_db_rest as idr

# Test 1: PM2.5 → IL-6 (environmental)
processor = idr.get_statements(
    subject="Particulate Matter",
    object="Interleukin-6",
    limit=10,
    timeout=20
)

# Test 2: IL-6 → CRP (control - SHOULD work)
processor = idr.get_statements(
    subject="IL6",
    object="CRP",
    limit=10,
    timeout=20
)
```

### Test Results

```
================================================================================
QUICK INDRA DB TEST: Environmental Pathways
================================================================================

[TEST 1] PM2.5 → IL-6
Result: 0 statements
❌ NO STATEMENTS

[TEST 2] IL-6 → CRP (CONTROL)
Result: 0 statements
❌ CONTROL FAILED (API issue)
```

**Logs**:
```
INFO: [2025-11-01 20:20:36] indra_db_rest.query_processor - Retrieving statements for HasAgent(agent_id="Particulate Matter", namespace="NAME", role="subject", agent_num=None) & HasAgent(agent_id="Interleukin-6", namespace="NAME", role="object", agent_num=None).
INFO: [2025-11-01 20:20:36] indra_db_rest.request_logs - Running 0th request for statements
INFO: [2025-11-01 20:20:36] indra_db_rest.request_logs -   LIMIT: 10
INFO: [2025-11-01 20:20:36] indra_db_rest.request_logs -   OFFSET: 0
[12 seconds pass...]
INFO: [2025-11-01 20:20:48] indra_db_rest.query_processor - Retrieving statements for HasAgent(agent_id="IL6", namespace="NAME", role="subject", agent_num=None) & HasAgent(agent_id="CRP", namespace="NAME", role="object", agent_num=None).
INFO: [2025-11-01 20:20:48] indra_db_rest.request_logs - Running 0th request for statements
INFO: [2025-11-01 20:20:48] indra_db_rest.request_logs -   LIMIT: 10
INFO: [2025-11-01 20:20:48] indra_db_rest.request_logs -   OFFSET: 0
INFO: [2025-11-01 20:21:08] indra_db_rest.query_processor - Leaving request to background thread. Logs may be viewed using the `print_quiet_logs()` method.

Result: 0 statements (for both queries)
```

---

## Analysis

### Critical Observation

**CONTROL TEST FAILED**: IL-6 → CRP is a WELL-DOCUMENTED molecular pathway that should have hundreds of statements in INDRA. The fact that it returned 0 statements indicates:

**Possible explanations**:

1. **API requires authentication**: Public access may be read-only or rate-limited to zero
2. **Query format incorrect**: Agent names might need grounding (HGNC IDs instead of names)
3. **API timeout**: Queries taking 12-20s each, possibly timing out server-side
4. **API downtime**: INDRA DB REST API may be unavailable or broken

### Evidence Analysis

**What works**:
- Library imports successfully
- Queries are sent (logged)
- No exceptions raised
- Response is structured (just empty)

**What doesn't work**:
- ALL queries return 0 statements (including known molecular pathways)
- Even simple, well-documented pathways fail
- No error messages or exceptions

### Comparison with Current Production System

`indranet_service.py` (lines 221-237):
```python
processor = idr.get_statements(
    subject=source,
    object=target,
    limit=200,
    persist=False,
    ev_limit=5,
    sort_by='ev_count',
    timeout=30,
    tries=2
)
logger.info(f"Got {len(processor.statements)} statements: {source} → {target}")
```

**Question**: Does the production system actually GET statements, or does it also return empty?

**Need to verify**: Check production logs to see if `indranet_service.py` successfully retrieves statements in practice.

---

## Implications for CTD Integration

### Scenario A: INDRA DB API is working (my queries are wrong)

If the API works when queried correctly:
- Need to determine proper agent name format (grounding IDs?)
- Retest with corrected query format
- THEN assess if environmental data exists

**Action**: Examine how `indra_query_agent.py` calls `indranet_service.py` in production:
- Do they use agent names or HGNC IDs?
- Check logs for successful statement retrieval
- Test with exact same parameters as production

### Scenario B: INDRA DB API requires authentication

If API requires API key for non-empty responses:
- Need to obtain `INDRA_DB_REST_API_KEY`
- Configure in environment
- Retest queries

**Action**: Check INDRA documentation for public vs authenticated access

### Scenario C: INDRA DB API is down/broken

If API is unavailable:
- Production system would be failing too
- Check if cached responses are being used instead
- CTD integration becomes CRITICAL (can't rely on broken API)

**Action**: Test production system to see if it's working

### Scenario D: Agent name format is wrong

INDRA uses grounded agent names. "Particulate Matter" might need to be:
- MESH ID: "D052638" (from our grounding service)
- Full grounding: "Particulate Matter@MESH:D052638"

**Action**: Test with grounded IDs instead of names

---

## Next Steps (Prioritized)

### IMMEDIATE: Test with grounded IDs

```python
# Instead of:
idr.get_statements(subject="Particulate Matter", object="Interleukin-6")

# Try:
idr.get_statements(subject="MESH:D052638", object="HGNC:5973")
# OR
idr.get_statements(subject="Particulate Matter@MESH", object="IL6@HGNC")
```

### NEXT: Check production logs

```bash
# Search for indranet_service.py logs showing successful statement retrieval
grep "Got.*statements" logs/production.log | head -20
```

### THEN: Review INDRA Python library docs

Check `indra.sources.indra_db_rest` documentation for:
- Agent name format requirements
- Authentication requirements
- Known issues/limitations

### FINALLY: Decision on CTD integration

**IF** INDRA DB contains environmental data:
- CTD integration may be redundant
- Focus on optimizing INDRA queries

**IF** INDRA DB does NOT contain environmental data:
- CTD integration is CRITICAL
- Proceed with ontology ingestion framework

---

## Bottom Line

**Current status**: CANNOT determine if INDRA DB contains environmental exposure data because:
1. Test queries return 0 statements for ALL queries (including control)
2. Control test (IL-6 → CRP) should work but doesn't
3. Unclear if issue is query format, authentication, or API availability

**Recommendation**: **DO NOT ABANDON CTD INTEGRATION** until we verify INDRA DB actually works and contains environmental data.

**Evidence required**:
1. ✅ Successful query returning non-zero statements (even for molecular pathways)
2. ✅ Confirmation of correct agent name format
3. ❓ Test environmental queries with correct format
4. ❓ Compare results to PathwayCommons

**Conservative approach**: Proceed with CTD integration AS PLANNED since:
- INDRA DB queries currently failing
- PathwayCommons confirmed NO environmental data
- CTD provides reliable environmental → gene data
- Risk of INDRA dependency too high

---

## Code Changes Needed

**IF we fix INDRA DB queries**:
1. Update `test_indra_db_environmental.py` with correct agent format
2. Rerun comprehensive environmental pathway tests
3. Document which data source has which pathways
4. Update architecture docs accordingly

**IF INDRA DB doesn't have environmental data**:
1. Keep CTD integration as primary environmental data source
2. Use INDRA DB for molecular pathways only (its strength)
3. Build hybrid system: CTD (environmental) + INDRA (molecular)
4. Document clear separation of concerns

---

## Testing TODOs

- [ ] Test with HGNC/MESH IDs instead of names
- [ ] Check INDRA Python library documentation
- [ ] Review production logs for successful queries
- [ ] Test with different agent name formats
- [ ] Verify API authentication requirements
- [ ] Compare responses to PathwayCommons
- [ ] Document working query format
- [ ] Retest environmental pathways with correct format

---

## References

- INDRA DB REST API: https://db.indra.bio
- INDRA Python docs: https://indra.readthedocs.io/en/latest/modules/sources/indra_db_rest/index.html
- Current production code: `indra_agent/services/indranet_service.py`
- Test script: `indra_agent/examples/test_indra_db_quick.py`
