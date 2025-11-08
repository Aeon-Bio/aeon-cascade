# Local Ontology Integration Plan

**Created**: 2025-11-06
**Status**: In Progress (MeSH ingestion complete, integration pending)

---

## Executive Summary

**Goal**: Replace Writer KG with local Memgraph-based ontology for synonym expansion and entity grounding.

**Current Status**:
- ✅ MeSH ingested: 30,924 entities with comprehensive synonyms
- ✅ Database ready: 296,613 total entities across 5 ontologies
- ⏳ Query bugs to fix: Null handling in Cypher
- ⏳ Integration pending: GroundingService still uses Writer KG

**Estimated Time to Complete**: 2-3 hours

---

## Phase 1: Fix Core Query Issues (30 minutes)

### Task 1.1: Fix Memgraph Null Handling

**File**: `indra_agent/services/local_ontology/memgraph_client.py:224`

**Problem**: `startsWith()` receiving null values for `name` field

**Current Code**:
```python
# Line 215-224
query = """
MATCH (e:Entity)
WHERE e.namespace IN $namespaces
  AND e.name STARTS WITH $prefix
RETURN e.id AS id, e.name AS name, e.namespace AS namespace,
       e.definition AS definition, e.synonyms AS synonyms
ORDER BY e.name
LIMIT $limit
"""
```

**Fixed Code**:
```python
query = """
MATCH (e:Entity)
WHERE e.namespace IN $namespaces
  AND e.name IS NOT NULL
  AND toLower(e.name) STARTS WITH toLower($prefix)
RETURN e.id AS id, e.name AS name, e.namespace AS namespace,
       e.definition AS definition, e.synonyms AS synonyms
ORDER BY e.name
LIMIT $limit
"""
```

**Changes**:
1. Add null check: `e.name IS NOT NULL`
2. Make search case-insensitive: `toLower(e.name) STARTS WITH toLower($prefix)`

**Testing**:
```bash
uv run python test_local_ontology_integration.py
# Should pass Test 2, 3, and 5
```

---

### Task 1.2: Verify MeSH Data Quality

**Goal**: Confirm MeSH entities have synonyms populated

**Test Query** (via Memgraph web UI or mgconsole):
```cypher
// Check MESH entities
MATCH (e:Entity)
WHERE e.namespace = 'MESH'
RETURN e.id, e.name, e.synonyms
LIMIT 10;

// Count MESH entities with synonyms
MATCH (e:Entity)
WHERE e.namespace = 'MESH' AND e.synonyms IS NOT NULL
RETURN count(e) as entities_with_synonyms;

// Sample entity with full details
MATCH (e:Entity)
WHERE e.id = 'D052638'  // Particulate Matter
RETURN e;
```

**Expected Results**:
- All 30,924 MESH entities present
- Most entities have synonyms (pipe-separated string: "syn1|syn2|syn3")
- Definitions present for major entities

**If Data Missing**:
- Check CSV file: `output/local_ontology_format/mesh/mesh.csv`
- Verify synonyms column has data
- Re-run ingestion if needed: `uv run python ingest_to_local_ontology.py --namespaces MESH`

---

## Phase 2: Create GroundingService Adapter (30 minutes)

### Task 2.1: Create LocalOntologyAdapter

**File**: `indra_agent/services/local_ontology_adapter.py` (NEW)

**Purpose**: Provide Writer KG-compatible API wrapping LocalHybridStrategy

**Code**:
```python
"""Adapter to integrate LocalHybridStrategy with GroundingService.

This provides a Writer KG-compatible interface for the local ontology.
"""

import logging
from typing import Dict, List, Optional

from indra_agent.services.local_ontology import LocalHybridStrategy

logger = logging.getLogger(__name__)


class LocalOntologyAdapter:
    """Writer KG-compatible adapter for LocalHybridStrategy.

    This class wraps LocalHybridStrategy to provide the same API
    that GroundingService expects from WriterKGService.
    """

    def __init__(self):
        """Initialize local ontology strategy."""
        self.strategy = LocalHybridStrategy()
        self._initialized = False

    async def initialize(self):
        """Initialize connection to local ontology."""
        if not self._initialized:
            await self.strategy.initialize()
            self._initialized = True
            logger.info("LocalOntologyAdapter initialized")

    async def find_mesh_term(self, query: str) -> Optional[Dict]:
        """Find MeSH term matching query (Writer KG-compatible API).

        Args:
            query: Search term (e.g., "PM2.5", "oxidative stress")

        Returns:
            Dict with keys:
                - mesh_id: MeSH ID (e.g., "D052638")
                - mesh_label: Canonical name
                - synonyms: List of synonym strings

            None if no match found

        Example:
            >>> result = await adapter.find_mesh_term("PM2.5")
            >>> result
            {
                'mesh_id': 'D052638',
                'mesh_label': 'Particulate Matter',
                'synonyms': ['PM2.5', 'fine particulate matter', 'PM 2.5']
            }
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Search for MESH entities matching query
            results = await self.strategy.autocomplete_entity(
                prefix=query,
                limit=1,
                namespaces=["MESH"]
            )

            if not results:
                logger.debug(f"No MESH term found for: {query}")
                return None

            entity = results[0]

            # Get full metadata with synonyms
            entity_id = f"{entity['database']}:{entity['id']}"
            metadata = await self.strategy.get_entity_metadata(entity_id)

            if not metadata:
                logger.warning(f"Metadata not found for MESH entity: {entity_id}")
                return None

            # Parse synonyms (stored as pipe-separated string)
            synonyms_str = metadata.get('synonyms', '')
            synonyms = [s.strip() for s in synonyms_str.split('|') if s.strip()] if synonyms_str else []

            return {
                'mesh_id': entity['id'],  # e.g., "D052638"
                'mesh_label': metadata.get('name', entity['name']),
                'synonyms': synonyms
            }

        except Exception as e:
            logger.error(f"Error finding MESH term for '{query}': {e}")
            return None

    async def close(self):
        """Close connections to local ontology."""
        if self._initialized:
            await self.strategy.close()
            self._initialized = False
            logger.info("LocalOntologyAdapter closed")
```

**Testing**:
```python
# Test script: test_local_ontology_adapter.py
import asyncio
from indra_agent.services.local_ontology_adapter import LocalOntologyAdapter

async def test():
    adapter = LocalOntologyAdapter()
    await adapter.initialize()

    # Test PM2.5 lookup
    result = await adapter.find_mesh_term("PM2.5")
    print(f"Query: PM2.5")
    print(f"Result: {result}")
    print(f"Synonyms ({len(result['synonyms'])}): {result['synonyms'][:5]}")

    # Test oxidative stress
    result = await adapter.find_mesh_term("oxidative stress")
    print(f"\nQuery: oxidative stress")
    print(f"Result: {result}")

    await adapter.close()

asyncio.run(test())
```

---

### Task 2.2: Update GroundingService

**File**: `indra_agent/services/grounding_service.py`

**Changes**:

1. **Import LocalOntologyAdapter** (line 13):
```python
from typing import Dict, List, Optional, Set

from indra_agent.services.local_ontology_adapter import LocalOntologyAdapter

logger = logging.getLogger(__name__)
```

2. **Update __init__** (line 48-55):
```python
def __init__(self, local_ontology: Optional[LocalOntologyAdapter] = None):
    """Initialize with local ontology for MeSH synonym expansion.

    Args:
        local_ontology: LocalOntologyAdapter for MeSH ontology lookups
    """
    self.local_ontology = local_ontology
    self.cache: Dict[str, List[str]] = {}
```

3. **Update get_all_synonyms** (line 90-110):
```python
# Query local ontology for MeSH synonyms
if self.local_ontology:
    try:
        mesh_result = await self.local_ontology.find_mesh_term(entity)
        if mesh_result:
            # Add canonical MeSH label
            synonyms.add(mesh_result["mesh_label"])
            synonyms.add(mesh_result["mesh_label"].lower())

            # Add MeSH ID (INDRA might accept it)
            mesh_id = mesh_result["mesh_id"]
            synonyms.add(f"MESH:{mesh_id}")
            synonyms.add(mesh_id)

            # Add all MeSH synonyms
            for syn in mesh_result.get("synonyms", []):
                synonyms.add(syn)
                synonyms.add(syn.lower())

            logger.debug(f"Local ontology found {len(synonyms)} synonyms for {entity}")
    except Exception as e:
        logger.warning(f"Local ontology lookup failed for {entity}: {e}")
```

4. **Update get_canonical** (line 147-153):
```python
if self.local_ontology:
    try:
        mesh_result = await self.local_ontology.find_mesh_term(entity)
        if mesh_result:
            return mesh_result["mesh_label"]
    except Exception as e:
        logger.debug(f"Local ontology lookup failed for {entity}: {e}")
```

5. **Update get_mesh_id** (line 167-176):
```python
if not self.local_ontology:
    return None

try:
    mesh_result = await self.local_ontology.find_mesh_term(entity)
    if mesh_result:
        return mesh_result["mesh_id"]
except Exception as e:
    logger.debug(f"Local ontology lookup failed for {entity}: {e}")
```

---

## Phase 3: Update Agent Initialization (15 minutes)

### Task 3.1: Update INDRAAgentClient

**File**: `indra_agent/core/client.py`

**Changes**:

1. **Import LocalOntologyAdapter** (top of file):
```python
from indra_agent.services.local_ontology_adapter import LocalOntologyAdapter
from indra_agent.services.grounding_service import GroundingService
```

2. **Initialize LocalOntologyAdapter** (in `__init__`):
```python
class INDRAAgentClient:
    def __init__(self):
        self.local_ontology = LocalOntologyAdapter()
        self.grounding_service = GroundingService(local_ontology=self.local_ontology)
        # ... rest of initialization
```

3. **Initialize connections** (in `initialize` or first query):
```python
async def initialize(self):
    """Initialize all services."""
    await self.local_ontology.initialize()
    logger.info("INDRA agent client initialized")
```

4. **Cleanup** (in `close` or destructor):
```python
async def close(self):
    """Close all connections."""
    await self.local_ontology.close()
```

---

### Task 3.2: Update Supervisor Agent

**File**: `indra_agent/agents/supervisor.py`

**Changes**:

1. **Pass grounding_service to state**:
```python
# In build_graph() or wherever state is initialized
state = OverallState(
    request=request,
    grounding_service=self.grounding_service,  # Add this
    # ... rest of state
)
```

2. **Ensure grounding_service available to INDRA Query Agent**:
```python
# In INDRA Query Agent node
grounding_service = state.get("grounding_service")
if grounding_service:
    synonyms = await grounding_service.get_all_synonyms(entity)
```

---

## Phase 4: End-to-End Testing (1 hour)

### Test 4.1: Unit Test - Synonym Expansion

**File**: `tests/test_local_ontology_integration.py`

```python
async def test_synonym_expansion():
    """Test that local ontology expands PM2.5 to all synonyms."""
    adapter = LocalOntologyAdapter()
    await adapter.initialize()

    grounding = GroundingService(local_ontology=adapter)

    synonyms = await grounding.get_all_synonyms("PM2.5")

    # Check we got lots of synonyms
    assert len(synonyms) >= 10, f"Expected >=10 synonyms, got {len(synonyms)}"

    # Check key synonyms present
    assert "Particulate Matter" in synonyms
    assert "fine particulate matter" in synonyms or "Fine Particulate Matter" in synonyms
    assert "MESH:D052638" in synonyms or "D052638" in synonyms

    print(f"✓ Synonym expansion working: {len(synonyms)} synonyms for PM2.5")
    print(f"  Sample: {list(synonyms)[:10]}")

    await adapter.close()
```

---

### Test 4.2: Integration Test - Full Query

**File**: `tests/test_agent_with_local_ontology.py`

```python
async def test_full_query_with_local_ontology():
    """Test complete query flow using local ontology."""
    from indra_agent.core.client import INDRAAgentClient
    from indra_agent.core.models import (
        CausalDiscoveryRequest,
        UserContext,
        Query,
        RequestOptions
    )

    client = INDRAAgentClient()
    await client.initialize()

    # Test query: "How does PM2.5 affect CRP?"
    request = CausalDiscoveryRequest(
        request_id="test-001",
        user_context=UserContext(
            user_id="test-user",
            genetics={},
            current_biomarkers={},
            location_history=[]
        ),
        query=Query(text="How does PM2.5 pollution affect CRP biomarkers?"),
        options=RequestOptions()
    )

    response = await client.process_request(request)

    # Verify response
    assert response.status == "success"
    assert len(response.graph.nodes) > 0, "Should find at least some nodes"

    # Check that PM2.5 was expanded to synonyms
    # (This would show up in logs as multiple INDRA queries)

    print(f"✓ Full query succeeded")
    print(f"  Found {len(response.graph.nodes)} nodes")
    print(f"  Found {len(response.graph.edges)} edges")

    await client.close()
```

---

### Test 4.3: Performance Benchmark

**Goal**: Verify local ontology is faster than Writer KG

**Expected Results**:
- Synonym expansion: <100ms (was ~300ms with Writer KG)
- Full query: <5s total (including INDRA API calls)

**Test**:
```python
import time

async def benchmark_synonym_expansion():
    adapter = LocalOntologyAdapter()
    await adapter.initialize()

    grounding = GroundingService(local_ontology=adapter)

    # Warm up
    await grounding.get_all_synonyms("PM2.5")

    # Benchmark
    start = time.time()
    for _ in range(10):
        await grounding.get_all_synonyms("PM2.5")
    elapsed = time.time() - start

    avg_time = (elapsed / 10) * 1000  # Convert to ms

    print(f"Average synonym expansion time: {avg_time:.1f}ms")
    assert avg_time < 100, f"Too slow: {avg_time}ms (expected <100ms)"

    await adapter.close()
```

---

## Phase 5: Cleanup and Documentation (30 minutes)

### Task 5.1: Remove Writer KG References

**Files to Update**:

1. **Remove WriterKGService import from GroundingService**:
   - Delete: `indra_agent/services/writer_kg_service.py`
   - Remove references in other files

2. **Remove Writer KG environment variables**:
   - `.env`: Remove `WRITER_API_KEY`, `WRITER_GRAPH_ID`
   - Update `.env.example` with local ontology settings

3. **Update Settings**:
   - `indra_agent/config/settings.py`: Remove Writer KG settings

4. **Search for remaining references**:
```bash
cd /Users/noot/Documents/digitalme
grep -r "writer_kg" --include="*.py" .
grep -r "WriterKG" --include="*.py" .
```

---

### Task 5.2: Update Documentation

**Files to Update**:

1. **KG_INTEGRATION_PLAN.md**:
```markdown
**Status**: ✅ **COMPLETE** - Writer KG fully replaced

## Integration Status

✅ **LocalOntologyAdapter** - Production ready
✅ **GroundingService** - Using local ontology
✅ **Agents** - Integrated with local ontology
✅ **Tests** - All passing
✅ **Performance** - 3-5x faster than Writer KG

## Final Statistics

| Ontology | Entities | Status |
|----------|----------|--------|
| FPLX | 579 | ✅ Complete |
| GO | 12,182 | ✅ Complete |
| CHEBI | 218,261 | ✅ Complete |
| HGNC | 34,667 | ⚠️ Stubs |
| **MESH** | **30,924** | ✅ **Complete** |
| **TOTAL** | **296,613** | ✅ **Production** |
```

2. **CLAUDE.md**: Update integration section

3. **README.md**: Add quick start for local ontology

---

## Phase 6: Deployment Checklist

### Pre-Deployment Verification

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Performance benchmarks meet SLA (<100ms synonym expansion)
- [ ] No Writer KG references remaining
- [ ] Documentation updated
- [ ] Memgraph running and accessible

### Deployment Steps

1. **Ensure Memgraph is running**:
```bash
docker ps | grep memgraph
# Should show memgraph container running on port 7687
```

2. **Verify data is loaded**:
```bash
# Connect to Memgraph
mgconsole --host localhost --port 7687

# Check entity counts
MATCH (e:Entity) RETURN e.namespace, count(e) AS count;
# Should show: MESH: 30924, GO: 12182, CHEBI: 218261, etc.
```

3. **Run full test suite**:
```bash
cd /Users/noot/Documents/digitalme
uv run pytest tests/test_local_ontology_integration.py -v
uv run pytest tests/test_agent_with_local_ontology.py -v
```

4. **Start agent system**:
```bash
# If using FastAPI
uv run python -m indra_agent.main

# If using Telegram bot
cd aeon_cascade_frontend
docker-compose up
```

5. **Monitor logs for errors**:
```bash
# Check for "Local ontology" messages
docker logs chatgpt_telegram_bot | grep "ontology"

# Verify no "Writer KG" messages
docker logs chatgpt_telegram_bot | grep "Writer"
# Should return nothing
```

---

## Success Criteria

✅ **Functional**:
- [ ] Synonym expansion returns >10 synonyms for common terms (PM2.5, CRP, etc.)
- [ ] Full queries complete successfully
- [ ] No errors in logs related to ontology lookups

✅ **Performance**:
- [ ] Synonym expansion <100ms (avg)
- [ ] Full query <5s total
- [ ] 3-5x faster than Writer KG baseline

✅ **Quality**:
- [ ] All tests passing
- [ ] No Writer KG references in codebase
- [ ] Documentation updated and accurate

---

## Rollback Plan

If issues arise:

1. **Revert GroundingService**:
   - Keep Writer KG service as fallback
   - Add flag: `use_local_ontology = False`

2. **Quick Fix**:
```python
# In GroundingService.__init__
self.use_local = False  # Disable local ontology
self.writer_kg = writer_kg_service  # Re-enable Writer KG
```

3. **Restart services** with Writer KG enabled

---

## Timeline Estimate

| Phase | Tasks | Time | Status |
|-------|-------|------|--------|
| **Phase 1** | Fix query bugs, verify data | 30 min | ⏳ Pending |
| **Phase 2** | Create adapter, update GroundingService | 30 min | ⏳ Pending |
| **Phase 3** | Update agent initialization | 15 min | ⏳ Pending |
| **Phase 4** | End-to-end testing | 1 hour | ⏳ Pending |
| **Phase 5** | Cleanup and documentation | 30 min | ⏳ Pending |
| **Phase 6** | Deployment and verification | 15 min | ⏳ Pending |
| **TOTAL** | | **3 hours** | |

---

## Notes

- **Memgraph must be running** for integration to work
- **LightRAG is disabled** (API incompatibility) - semantic search uses Memgraph fallback
- **Zero cost** - local ontology is free (vs Writer KG commercial pricing)
- **Faster queries** - 3-5x performance improvement
- **More ontologies** - 5 ontologies vs 1 with Writer KG

---

## Contact / Questions

For questions about this integration:
- Check `LOCAL_ONTOLOGY_INTEGRATION_PLAN.md` (this file)
- See `KG_INTEGRATION_PLAN.md` for architecture details
- Review `CLAUDE.md` for agent system integration

---

**Last Updated**: 2025-11-06
**Next Review**: After Phase 4 completion
