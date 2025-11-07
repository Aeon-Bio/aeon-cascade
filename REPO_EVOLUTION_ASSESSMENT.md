# Repository Evolution Assessment: KG Integration & INDRA Maximization

**Date**: 2025-11-01
**Request**: "examine how our repo has evolved; some time has passed since revisiting this current context. what implications are there on our KG integration of the needed ontologies? how is the workflow navigating the corpus INDRA truly supports? is it actually leveraging indra to the max?"

---

## Executive Summary

**Key Finding**: The repo has DIVERGED from original CTD integration plans. Current system uses **INDRA Python library** for direct database access, NOT the PathwayCommons REST endpoint tested earlier.

**Critical Gap**: Cannot verify if INDRA DB REST API contains environmental data - test queries return 0 statements for ALL queries (including known molecular pathways like IL-6 → CRP).

**Recommendation**: **PROCEED with CTD integration AS PLANNED** until INDRA DB queries are proven to work and contain environmental exposure data.

---

## How the Repo Has Evolved

### 1. From PathwayCommons REST to INDRA Python Library

**Before** (when environmental gap was discovered):
```python
# Used HTTP REST endpoint for PathwayCommons
POST http://api.indra.bio:8000/biopax/process_pc_pathsbetween
{
  "source": "PM2.5",
  "target": "CRP"
}
# Result: 0 paths (PathwayCommons has no environmental exposures)
```

**Now** (`indranet_service.py`, implemented since then):
```python
# Uses INDRA Python library for direct database access
import indra.sources.indra_db_rest as idr

processor = idr.get_statements(
    subject="PM2.5",
    object="CRP",
    limit=200,
    persist=False,
    ev_limit=5,
    sort_by='ev_count',
    timeout=30,
    tries=2
)
statements = processor.statements
```

**Implication**: This is a DIFFERENT data source:
- PathwayCommons: Curated pathway database (BioPAX format)
- INDRA DB REST: Pre-assembled statement database (literature extraction + curation)

**Question**: Does INDRA's statement database contain environmental exposures that PathwayCommons lacks?

**Current Status**: CANNOT DETERMINE (see Section 3)

---

### 2. Ontology Ingestion Framework Built

**Created** (during previous session):
- `scripts/ontology_ingestion/ontology_base.py` - Abstract Factory pattern
- `scripts/ontology_ingestion/parsers.py` - Format-agnostic parsing
- `scripts/ontology_ingestion/converters.py` - Multi-target output
- `scripts/ontology_ingestion/ingest_ctd_environmental.py` - CTD-specific pipeline

**Purpose**: Download and convert external ontologies (CTD, CHEBI, GO) for KG integration

**Status**: Framework built but NOT YET USED in production workflow

**Integration Point**: Designed to populate Writer KG with environmental → molecular mappings from CTD

---

### 3. Current Workflow Architecture

**User Query Flow** (from `indra_query_agent.py`):
```
User Query → LLM Supervisor
           ↓
    Extract Entities → IndraQueryAgent
           ↓
    Call IndraNetService.build_biomarker_network()
           ↓
    idr.get_statements(subject=exposure, object=biomarker)
           ↓
    Build signed NetworkX graph with belief scores
           ↓
    Find MDL-optimal paths using Dijkstra search
           ↓
    Return causal pathways
```

**Key Components**:
1. **`indra_query_agent.py`** (lines 154-159): Calls `indranet_service.build_biomarker_network()`
2. **`indranet_service.py`** (lines 221-237): Queries INDRA DB via Python library
3. **`scm_graph_builder.py`**: Builds structural causal models from INDRA paths

**NO environmental data source integration** - relies entirely on INDRA DB

---

##4. INDRA Corpus Navigation: Are We Maximizing INDRA?

### What INDRA DB Provides (When Working)

**Strengths** (from INDRA documentation):
- 20M+ pre-assembled statements from literature
- Belief scores from Bayesian evidence integration
- Multi-source evidence (Reactome, KEGG, WikiPathways, BioGRID, SignOR, literature NLP)
- Grounding to 10+ ontologies (HGNC, CHEBI, MESH, PUBCHEM, GO, UP, etc.)
- Signed graphs (activation/inhibition)
- Evidence PMIDs for traceability

**Scope** (from prior testing):
- ✅ Gene/protein signaling pathways (INDRA's strength)
- ✅ Metabolic pathways
- ✅ Drug-target interactions
- ❌ Environmental exposures (NOT in PathwayCommons)
- ❓ Environmental exposures (Unknown if in INDRA DB statement database)

### How We're Currently Using INDRA

**✅ DOING WELL**:
1. **Direct Python library access** (faster than HTTP REST)
   - `indra.sources.indra_db_rest.get_statements()` - direct database query
   - No HTTP serialization overhead
   - Async execution via `asyncio.to_thread()`

2. **Caching optimizations** (`indranet_service.py` lines 84-115)
   - LRU cache with max 50 queries (~50 MB)
   - Cache hit avoids redundant INDRA queries
   - Automatic eviction prevents memory leaks

3. **Pre-assembled statements** (lines 167-170)
   - INDRA DB statements already pre-assembled
   - Skip duplicate preassembly step
   - Just filter by belief threshold

4. **Signed graphs** (lines 250-283)
   - Uses `IndraNetAssembler` for signed graphs
   - Preserves activation/inhibition semantics
   - Belief scores on edges

5. **MDL-based pathfinding** (`mdl_weight.py`)
   - Minimum Description Length for optimal paths
   - Penalizes complexity, rewards evidence
   - Finds mechanistically plausible chains

**❌ NOT MAXIMIZING INDRA**:

1. **No multi-source queries**
   - Current: Single `subject → object` query
   - Missing: Neighborhood expansion (get ALL interactions for a node)
   - INDRA supports: `agents=[...]` parameter for multi-node queries

2. **No ontology-based expansion**
   - Current: Query with exact entity names
   - Missing: Query with ontology synonyms (e.g., "IL-6" + "Interleukin-6" + "IL6")
   - INDRA supports: Grounded entity search

3. **No temporal modeling**
   - Current: Static graph (no time dimension)
   - Missing: Statement timing info (phosphorylation = fast, transcription = slow)
   - INDRA supports: Statement types can infer temporal dynamics

4. **No confidence intervals**
   - Current: Point estimates for belief scores
   - Missing: Uncertainty quantification from evidence counts
   - INDRA supports: Evidence count → confidence via binomial distribution

5. **No source prioritization**
   - Current: All evidence sources weighted equally
   - Missing: Prioritize high-quality sources (Reactome > text mining)
   - INDRA supports: Source-level metadata in evidence

---

## KG Integration: What's Missing for Environmental Queries

### Gap Analysis

**User queries like**:
> "How does air pollution in Los Angeles affect inflammation?"

**Require data sources that span**:
1. ✅ Molecular pathways: IL-6 → CRP (INDRA has this)
2. ❌ Environmental exposures: PM2.5 → IL-6 (INDRA PathwayCommons doesn't have this)
3. ❓ Environmental exposures: PM2.5 → IL-6 (INDRA DB status UNKNOWN)
4. ❌ Location → exposure levels: Los Angeles → PM2.5 = 35 µg/m³ (need Air Quality API)
5. ❌ Reference ranges: CRP > 3 mg/L = high risk (need clinical reference DB)

### Current Coverage

| Data Need | Source | Status |
|-----------|--------|--------|
| Molecular pathways (genes/proteins) | INDRA DB | ✅ Working (assumed) |
| Environmental → molecular | INDRA DB? | ❓ UNKNOWN |
| Environmental → molecular | CTD | ⏳ Framework ready, not integrated |
| Location → exposure | Air Quality API | ⚠️ Optional (IQAir) |
| Biomarker references | Clinical DB | ❌ Hardcoded comments |
| Genetic modifiers | ClinVar/gnomAD | ⏳ Framework exists, not integrated |
| Temporal dynamics | INDRA statement types | ⏳ Partial (TEMPORAL_LAG_MAP) |

---

## Critical Testing Gap: INDRA DB Environmental Data

### Test Conducted

**File**: `indra_agent/examples/test_indra_db_quick.py`

**Query Format** (same as production code):
```python
import indra.sources.indra_db_rest as idr

processor = idr.get_statements(
    subject="Particulate Matter",
    object="Interleukin-6",
    limit=10,
    timeout=20
)
```

**Result**: **0 statements** for ALL queries

**Control Test**:
```python
processor = idr.get_statements(
    subject="IL6",
    object="CRP",
    limit=10,
    timeout=20
)
```

**Result**: **0 statements** (SHOULD have found hundreds!)

### Interpretation

**Possible explanations**:
1. **API requires authentication** - public access returns empty
2. **Agent name format wrong** - need HGNC IDs instead of names?
3. **API timeout** - queries taking 12-20s, timing out server-side
4. **API broken/unavailable** - INDRA DB REST may be down

**Implication**: **Cannot determine if INDRA DB has environmental data** until we:
1. Fix query format (try HGNC/MESH IDs)
2. Get API authentication working
3. Verify production system actually retrieves statements

---

## Implications for CTD Integration

### Scenario Matrix

| INDRA DB Status | Environmental Data | CTD Integration Decision |
|----------------|-------------------|------------------------|
| Working + Has environmental | ✅ | OPTIONAL (redundant with INDRA) |
| Working + NO environmental | ❌ | **CRITICAL** (only source) |
| Broken (current state) | ❓ | **PROCEED** (can't rely on broken API) |

### Conservative Recommendation

**PROCEED with CTD integration AS PLANNED** because:

1. **INDRA DB queries currently failing** (0 statements for known pathways)
2. **PathwayCommons confirmed NO environmental data** (previous testing)
3. **CTD provides reliable environmental → gene data** (proven resource)
4. **Risk mitigation**: Don't depend on unverified data source
5. **Hybrid approach**: CTD (environmental) + INDRA (molecular) is architecturally sound

### Integration Architecture (Recommended)

```
User Query: "How does PM2.5 pollution affect CRP?"

Step 1: CTD Query (environmental → molecular)
  PM2.5 → [CTD] → {IL6, TNF, NF-κB, HMOX1, ...}
  Result: List of genes affected by PM2.5

Step 2: INDRA Query (molecular → biomarker)
  IL6 → [INDRA DB] → CRP
  NF-κB → [INDRA DB] → IL6 → CRP
  Result: Molecular pathways with belief scores

Step 3: Merge Graphs
  PM2.5 → IL6 → CRP (combined chain)
  Evidence: CTD (PM2.5→IL6) + INDRA (IL6→CRP)
  Belief: CTD confidence × INDRA belief

Step 4: Return Causal Graph
  Nodes: [PM2.5, IL6, CRP]
  Edges: [(PM2.5, IL6, 0.82), (IL6, CRP, 0.98)]
  Evidence: PMIDs from both sources
```

**Benefits**:
- ✅ Separates concerns (environmental vs molecular)
- ✅ Uses each data source's strength
- ✅ Clear evidence provenance (CTD vs INDRA)
- ✅ Fallback if one source fails

---

## Maximizing INDRA: Specific Improvements

### 1. Multi-Node Neighborhood Queries

**Current** (single pair):
```python
stmts = await idr.get_statements(subject="PM2.5", object="CRP")
```

**Improved** (neighborhood expansion):
```python
# Get ALL interactions involving PM2.5
pm25_stmts = await idr.get_statements(agents=["PM2.5"], limit=500)

# Get ALL interactions involving CRP
crp_stmts = await idr.get_statements(agents=["CRP"], limit=500)

# Merge and find connecting paths
```

**Benefit**: Discovers indirect paths via intermediates

---

### 2. Ontology Synonym Expansion

**Current** (exact name only):
```python
stmts = await idr.get_statements(subject="IL-6", object="CRP")
```

**Improved** (query all synonyms):
```python
# From ontology resolver
il6_synonyms = ["IL-6", "Interleukin-6", "IL6", "HGNC:5973"]

all_stmts = []
for syn in il6_synonyms:
    stmts = await idr.get_statements(subject=syn, object="CRP")
    all_stmts.extend(stmts)

# Deduplicate via grounding
```

**Benefit**: Catches statements with different entity name variants

---

### 3. Temporal Dynamics from Statement Types

**Current** (static graph):
```python
# No temporal information
graph = assembler.make_model(graph_type="signed")
```

**Improved** (add temporal metadata):
```python
# Map statement types to temporal lags
STMT_TYPE_TO_LAG = {
    "Phosphorylation": 1,  # hours
    "Activation": 6,
    "IncreaseAmount": 12,
    "Translocation": 0.5,
}

for stmt in statements:
    lag = STMT_TYPE_TO_LAG.get(type(stmt).__name__, 6)
    # Add to edge metadata
    graph[source][target]["temporal_lag_hours"] = lag
```

**Benefit**: Predicts response timelines for interventions

---

### 4. Evidence-Based Confidence Intervals

**Current** (point estimates):
```python
belief = stmt.belief  # e.g., 0.82
```

**Improved** (uncertainty quantification):
```python
import scipy.stats as stats

def compute_confidence_interval(belief: float, evidence_count: int) -> Tuple[float, float]:
    """Binomial confidence interval for belief score."""
    # belief ~ evidence_count positive evidence / total attempts
    # Use Wilson score interval (better for small samples)
    ci_lower, ci_upper = stats.beta.interval(
        alpha=0.95,
        a=belief * evidence_count + 1,
        b=(1 - belief) * evidence_count + 1
    )
    return (ci_lower, ci_upper)

# Usage
belief_ci = compute_confidence_interval(stmt.belief, len(stmt.evidence))
# (0.78, 0.89) - 95% confidence interval
```

**Benefit**: Quantifies uncertainty for clinical decision support

---

### 5. Source Prioritization

**Current** (all evidence equal):
```python
# Belief score averages all sources
belief = stmt.belief
```

**Improved** (weight by source quality):
```python
SOURCE_WEIGHTS = {
    "reactome": 1.0,  # Highest quality (curated)
    "kegg": 0.9,
    "signor": 0.9,
    "reach": 0.6,  # Text mining (lower confidence)
    "rlimsp": 0.5,
}

def compute_weighted_belief(stmt):
    """Weight evidence by source quality."""
    weighted_score = 0
    total_weight = 0

    for ev in stmt.evidence:
        source = ev.source_api
        weight = SOURCE_WEIGHTS.get(source, 0.7)
        weighted_score += weight * (1 if ev.pmid else 0.5)
        total_weight += weight

    return weighted_score / total_weight if total_weight > 0 else stmt.belief

# Usage
belief_weighted = compute_weighted_belief(stmt)
```

**Benefit**: Prioritizes high-quality curated sources over noisy text mining

---

## Action Plan: Next Steps

### IMMEDIATE (Fix INDRA DB queries)

1. **Test with grounded IDs** instead of names:
   ```python
   # Test: IL-6 → CRP with HGNC IDs
   processor = idr.get_statements(
       subject="HGNC:5973",  # IL-6
       object="HGNC:2367",   # CRP
       limit=10
   )
   ```

2. **Check production logs** for successful statement retrieval:
   ```bash
   grep "Got.*statements" logs/* | grep -v "Got 0 statements"
   ```

3. **Review INDRA Python library docs** for agent name format requirements

### SHORT-TERM (Verify environmental data)

4. **IF INDRA DB works**:
   - Retest environmental queries with correct format
   - Document which pathways INDRA DB contains
   - Compare to CTD coverage

5. **IF INDRA DB doesn't have environmental data**:
   - Integrate CTD as primary environmental source
   - Use INDRA for molecular pathways only
   - Build hybrid architecture (CTD + INDRA)

### MEDIUM-TERM (Maximize INDRA)

6. **Implement neighborhood expansion** (multi-node queries)
7. **Add ontology synonym resolution** (query all name variants)
8. **Extract temporal dynamics** (from statement types)
9. **Compute confidence intervals** (from evidence counts)
10. **Prioritize high-quality sources** (weight by curation level)

---

## Bottom Line

**Are we leveraging INDRA to the max?** **NO** - significant optimizations available:
- Missing: Neighborhood expansion, synonym resolution, temporal modeling, uncertainty quantification, source prioritization

**Is the workflow navigating INDRA's corpus correctly?** **UNKNOWN** - test queries currently failing, need to verify:
- Correct agent name format
- API authentication requirements
- Production system actually working

**What are the implications for KG integration?** **PROCEED with CTD** until INDRA DB proven to work AND contain environmental data:
- Conservative approach: Don't depend on unverified source
- Hybrid architecture: CTD (environmental) + INDRA (molecular)
- Clear separation of concerns

**Key Risk**: If we abandon CTD integration and INDRA DB doesn't have environmental data, we'll have NO data source for environmental queries.

**Recommendation**: **Build CTD integration AS PLANNED**, then optimize INDRA usage with improvements listed above.
