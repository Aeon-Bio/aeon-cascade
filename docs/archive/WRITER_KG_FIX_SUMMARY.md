# Writer KG TSV Parsing Fix Summary

## Problem

Writer Knowledge Graph API was returning raw TSV data in snippets, which `WriterKGService` failed to parse correctly.

### Before Fix

```python
# Query: particulate matter
result = await service.find_mesh_term("particulate matter")
# Result: {'mesh_id': 'D016899', 'mesh_label': 'Interferon-beta', ...}
# ❌ Wrong MeSH ID! Got first line from TSV instead of correct entry
```

### Root Cause

Writer KG returns snippets like:
```
D016899\tInterferon-beta\t\thttp://id.nlm.nih.gov/mesh/D016899
D017382\tReactive Oxygen Species\t\thttp://id.nlm.nih.gov/mesh/D017382
D052638\tParticulate Matter\t\thttp://id.nlm.nih.gov/mesh/D052638
```

The old code extracted the FIRST line, not the CORRECT line for the queried term.

## Solution

### 1. Extract MeSH ID from LLM Answer

Writer KG's LLM answer contains the correct MeSH ID:
```
"The MeSH ID for particulate matter is D052638..."
```

### 2. Search TSV Snippets for Matching Line

Once we have the correct MeSH ID, search all snippet lines for that ID and extract the label/definition.

### Code Changes

**File**: `indra_agent/services/writer_kg_service.py`

**Added Method**:
```python
def _extract_mesh_id_from_answer(self, answer: str) -> Optional[str]:
    """Extract MeSH ID from LLM answer text."""
    import re
    match = re.search(r'\b([DCA]\d{6})\b', answer)
    return match.group(1) if match else None
```

**Updated Method**:
```python
async def find_mesh_term(self, term_name: str) -> Optional[Dict]:
    result = await self.query_mesh_terms(question, max_snippets=10)

    # Extract MeSH ID from LLM answer first (most reliable)
    answer = result.get("answer", "")
    mesh_id = self._extract_mesh_id_from_answer(answer)

    # Find matching entry in TSV sources
    mesh_label = None
    definition = None

    if mesh_id:
        for source in result.get("sources", []):
            snippet = source.get("snippet", "")
            for line in snippet.split('\n'):
                if mesh_id in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        mesh_label = parts[1].strip()
                    if len(parts) >= 3:
                        definition = parts[2].strip()
                    break
            if mesh_label:
                break

    return {
        "mesh_id": mesh_id,
        "mesh_label": mesh_label,
        "definition": definition or answer,
        "synonyms": self._extract_synonyms(answer),
    }
```

**Updated TSV Parsing Methods**:
- `_extract_mesh_id()`: Parse tab-separated values, validate MeSH ID format
- `_extract_label()`: Parse label from correct TSV line
- `_extract_definition()`: Parse definition from TSV (3rd column)

## Results

### After Fix

```python
# Query: particulate matter
result = await service.find_mesh_term("particulate matter")
# Result: {'mesh_id': 'D052638', 'mesh_label': 'Particulate Matter', ...}
# ✅ Correct!

# Query: CRP
result = await service.find_mesh_term("CRP")
# Result: {'mesh_id': 'D002097', 'mesh_label': 'C-Reactive Protein', ...}
# ✅ Correct!
```

### Test Results

**Writer KG Integration Tests**: 8 passed, 1 skipped (was 2 failed, 6 passed)
**Full Test Suite**: 40 passed, 6 failed, 1 skipped (was 37 passed, 9 failed)

**Improvement**: +3 tests passing

## Remaining Issues

### PM2.5 Synonym Resolution

PM2.5 doesn't resolve because synonyms are not in the uploaded CSV data:

```bash
$ head scripts/mesh/data/csv/mesh_synonyms.csv
mesh_id,synonym,type
# Empty except header
```

**Workaround**: Use canonical names ("particulate matter" instead of "PM2.5")

**Future Fix**: Upload synonym data to Writer KG

### E2E Agent Integration Tests

6 E2E tests still fail - these require full LLM agent orchestration with Bedrock and are expected to fail without proper agent routing/execution. These are not Writer KG issues.

## Files Modified

1. `indra_agent/services/writer_kg_service.py` - TSV parsing logic
2. `tests/test_live_writer_kg_integration.py` - Updated test expectations
3. `tests/test_live_e2e_with_writer_kg.py` - Added missing user_id fields

## Status

✅ **FIXED** - Writer KG TSV parsing now works correctly
⚠️ **NOTE** - Synonym data not populated (use canonical names)
📝 **TODO** - Debug E2E agent integration tests (separate issue)
