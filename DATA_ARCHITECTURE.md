# Data Architecture: Knowledge Graph Integration

**Date**: 2025-10-25
**Status**: Design - defining what we actually need

---

## The Actual Problem

We need to answer queries like:
- "How does air pollution in Los Angeles affect inflammation?"
- "What happens if I move from LA to Seattle?"
- "How does my GSTM1_null variant modify oxidative stress response?"

These queries span MULTIPLE data sources that must integrate:

---

## Data Sources Required

### 1. INDRA Bio-Ontology (Causal Mechanisms)
**What it provides**:
- Molecular mechanisms: PM2.5 → ROS → NF-κB → IL-6 → CRP
- Complete ontology grounding: HGNC, CHEBI, MESH, GO, PUBCHEM, etc.
- Belief scores (literature evidence)
- Statement types (Activation, Inhibition, IncreaseAmount, etc.)

**What it does NOT provide**:
- Environmental exposure data (PM2.5 levels in LA vs Seattle)
- Genetic variant data (what is GSTM1_null? how common?)
- Biomarker reference ranges (what CRP level is "high"?)
- Temporal dynamics (how long does it take?)

**API**: `http://api.indra.bio:8000`

**Grounding format**:
```python
{
  "name": "chlorpyrifos",
  "db_refs": {
    "CHEBI": "CHEBI:34631",
    "MESH": "D004390",
    "PUBCHEM": "2730",
    "CHEMBL": "CHEMBL463210"
  }
}
```

---

### 2. Environmental Exposure Data
**What we need**:
- Air quality: PM2.5, PM10, O3, NO2 by location
- Historical averages (not just current)
- Geographic aggregation (city-level, zip-level)

**Potential sources**:
- IQAir API (current + forecast, limited historical)
- EPA AirNow (US only, current + limited historical)
- OpenAQ (global, historical, open source)
- NOAA/NASA satellite data (research-grade, complex)

**Current status**: Using IQAir (optional, not critical path)

**Integration point**: Map location → exposure levels → INDRA entities
```python
# User query: "air pollution in Los Angeles"
location = "Los Angeles, CA"
exposure_data = get_air_quality(location)
# → {"PM2.5": 35, "O3": 65, "NO2": 20}

# Map to INDRA-compatible entities
# PM2.5 → INDRA already has "Particulate Matter" (from pathways)
# But does INDRA have PM2.5 → ROS pathways?
# Or do we need intermediate mapping: PM2.5 → oxidative stress → ROS?
```

**CRITICAL QUESTION**: Does INDRA have environmental → molecular pathways?
- If YES: We can query directly
- If NO: We need to model exposure → biomarker relationships separately

---

### 3. Genetic Variant Data
**What we need**:
- Variant → function mapping (GSTM1_null → no glutathione conjugation)
- Variant → pathway effects (GSTM1_null → 1.3× oxidative stress)
- Population frequencies (how common is this variant?)

**Potential sources**:
- ClinVar (clinical variants, pathogenicity)
- gnomAD (population frequencies)
- PharmGKB (pharmacogenomics, drug-gene interactions)
- DisGeNET (gene-disease associations)

**Current status**: Hardcoded in `cached_responses.py`

**Integration point**: Map variant → INDRA pathway modifiers
```python
# User has GSTM1_null variant
variant = "GSTM1_null"

# Does INDRA know about GSTM1?
# → Yes, GSTM1 is a gene (HGNC:4436)

# Does INDRA know GSTM1 → oxidative stress pathways?
# → Need to check

# How do we model "null variant" → "loss of function"?
# → This is a META-level operation on the graph
```

---

### 4. Biomarker Reference Ranges
**What we need**:
- Normal ranges (CRP: <1 mg/L = low risk, 1-3 = moderate, >3 = high)
- Clinical thresholds (HbA1c: <5.7% = normal, 5.7-6.4% = prediabetes, ≥6.5% = diabetes)
- Age/sex stratification

**Potential sources**:
- Lab reference databases (LabCorp, Quest)
- Clinical guidelines (ADA for diabetes, AHA for cardiovascular)
- Research literature (meta-analyses of population distributions)

**Current status**: Hardcoded comments in code

**Integration point**: Interpret INDRA predictions
```python
# INDRA predicts: PM2.5 reduction → CRP: 5.2 → 4.3 mg/L
# Without reference ranges, this is meaningless to user

# With reference ranges:
# CRP 5.2 mg/L = HIGH RISK (>3)
# CRP 4.3 mg/L = MODERATE RISK (1-3)
# → Clinical interpretation: "moves from high to moderate risk"
```

---

### 5. Temporal Dynamics (Pharmacokinetics/Pharmacodynamics)
**What we need**:
- Time to effect (exposure → biomarker lag)
- Half-lives (how long does effect persist?)
- Steady-state dynamics

**Potential sources**:
- INDRA statement types → temporal categories (Phosphorylation = 1h, IncreaseAmount = 12h)
- PK/PD databases for drugs
- Research literature for environmental exposures

**Current status**: Hardcoded `TEMPORAL_LAG_MAP` in `graph_builder.py`

**Integration point**: Predict response timeline
```python
# User moves from LA to Seattle
# When will biomarkers change?

# PM2.5 → ROS (6h)
# ROS → NF-κB (1h)
# NF-κB → IL-6 (12h)
# IL-6 → CRP (6h)
# Total: ~25 hours for CRP to start changing

# But what about steady-state?
# Need half-life of CRP (19 hours) to model full response
```

---

## Integration Architecture

### Current Approach (Partial)
```
User Query → LLM Supervisor
           ↓
    Extract Entities → Grounding Service (HARDCODED)
           ↓
    INDRA Query Agent → INDRA API
           ↓
    Build Causal Graph
           ↓
    ??? (missing data integrations) ???
           ↓
    Response
```

### What We Actually Need
```
User Query → LLM Supervisor
           ↓
    Extract Entities → Multi-Source Grounding:
                       - INDRA (chemicals, genes, processes)
                       - Location → Air Quality API
                       - Genetic variants → ClinVar/gnomAD
                       - Biomarkers → Reference Range DB
           ↓
    INDRA Query Agent → Build Causal Graph (from INDRA)
           ↓
    Environmental Agent → Map Location → Exposure Levels
           ↓
    Genetic Modifier Agent → Apply Variant Effects to Graph
           ↓
    Effect Propagation → Compute Biomarker Changes
           ↓
    Clinical Interpretation → Compare to Reference Ranges
           ↓
    Temporal Model → Predict Response Timeline
           ↓
    Response (with evidence, uncertainty, clinical context)
```

---

## Critical Questions to Answer

### Q1: Does INDRA have environmental → molecular pathways?
**Test Results** (2025-10-25):
```python
# Tested queries:
# - PM2.5 → oxidative stress: ❌ NO PATHS
# - Ozone → inflammation: ❌ NO PATHS
# - Cigarette smoke → ROS: ❌ NO PATHS
# - Air Pollutants → CRP: ❌ NO PATHS
# - Lead/Cadmium/Arsenic → molecular targets: ❌ NO PATHS
```

**CRITICAL FINDING**:
INDRA's `/biopax/process_pc_pathsbetween` endpoint uses **PathwayCommons** data, which contains:
- ✅ Gene/protein signaling pathways
- ✅ Metabolic pathways
- ❌ NO environmental exposures (PM2.5, ozone, cigarette smoke)
- ❌ NO heavy metals or organic pollutants as entities

**Implication**: We MUST build a **separate exposure modeling layer** that maps:
```
Location → Environmental Data API → Exposure Levels → CTD KG → INDRA Molecular Entities
                                                        ↑
                                              SOLUTION: CTD integration!
```

**✅ SOLUTION IMPLEMENTED** (2025-10-25):

**CTD (Comparative Toxicogenomics Database)** provides environmental → molecular pathways:
- PM2.5 → {IL6, TNF, NF-κB, HMOX1, ...}
- Ozone → {SOD2, HMOX1, inflammation genes}
- Lead → {oxidative stress genes}
- Cigarette smoke → {ROS-related genes}

**Architecture**:
```python
# New multi-ontology ingestion framework (scripts/ontology_ingestion/)
# Uses Abstract Factory pattern for ontology-agnostic ingestion

# Step 1: Download CTD
python ingest_ctd_environmental.py --download

# Step 2: Upload to Writer KG (separate from INDRA KG)

# Step 3: Query BOTH KGs:
#   - CTD KG: PM2.5 → IL6 (environmental → molecular)
#   - INDRA KG: IL6 → CRP (molecular → biomarker)
#   - Merge: PM2.5 → IL6 → CRP (complete chain)
```

See `ONTOLOGY_INGESTION_FRAMEWORK.md` for full implementation details.

**Other Options** (not chosen):
1. ~~Literature-derived mappings~~: Too manual, doesn't scale
2. ~~Hybrid LLM model~~: Hallucination risk, no quantitative data
3. ~~Manual curation~~: Limited coverage, maintenance burden
4. ~~Different INDRA endpoint~~: Tested - no environmental data exists

### Q2: How do we map user locations to INDRA entities?
**Options**:
1. **Direct mapping**: "Los Angeles" → PM2.5 level → INDRA "Particulate Matter" entity
2. **Intermediate abstraction**: "Los Angeles" → "high pollution" → generic oxidative stress
3. **Multi-pollutant**: "Los Angeles" → {PM2.5, O3, NO2} → multiple INDRA pathways → aggregate effects

### Q3: How do we model genetic variants as graph modifiers?
**Options**:
1. **Edge weight modifiers**: GSTM1_null → ROS edge gets 1.3× multiplier
2. **Virtual nodes**: Add "GSTM1 (functional)" vs "GSTM1 (null)" nodes
3. **Counterfactual graphs**: Build two graphs (with/without variant), compare

### Q4: Where do ontology mappings happen?
**Current mess**:
- Grounding service: Hardcoded entity names
- Network builder v1: Hardcoded name extraction
- Network builder v2: Uses INDRA db_refs (better, but incomplete)

**What we actually need**:
```python
# User says: "air pollution"
# → Map to WHAT in INDRA?
#   - "Particulate Matter" (MESH:D052638)?
#   - "Air Pollutants" (MESH:D000393)?
#   - Specific chemicals (PM2.5, O3, NO2)?

# INDRA provides db_refs, but we need:
# - User term → canonical INDRA entity name
# - This is NOT hardcoding - this is a LOOKUP TABLE from ontologies
```

---

## What We Should Build (Actually)

### 1. Ontology Resolution Service
**Not hardcoded mappings. Not invented. Actual ontology lookups.**

```python
class OntologyResolver:
    """Resolve user terms to INDRA-compatible entities using ontologies.

    Sources:
    - INDRA grounding API (if it exists)
    - UMLS Metathesaurus (maps between ontologies)
    - BioPortal API (ontology search)
    - Writer KG (MeSH ontology we already have)
    """

    async def resolve(self, user_term: str) -> List[INDRAEntity]:
        # Try INDRA's own grounding
        # Try UMLS mapping
        # Try Writer KG MeSH
        # Return candidates with confidence scores
```

### 2. Environmental Data Integration
```python
class EnvironmentalDataService:
    """Map locations to exposure levels to INDRA entities."""

    async def get_exposures(self, location: str) -> Dict[str, float]:
        # Query air quality APIs
        # Return exposure levels

    async def map_to_indra_entities(self, exposures: Dict) -> List[INDRAEntity]:
        # PM2.5 → "Particulate Matter" entity
        # O3 → "Ozone" entity
        # Use ontology resolver to ensure INDRA compatibility
```

### 3. Genetic Variant Integration
```python
class GeneticVariantService:
    """Map variants to pathway modifiers."""

    async def get_variant_effects(self, variant: str) -> VariantEffect:
        # Query ClinVar, gnomAD, PharmGKB
        # Determine affected pathways
        # Return modifier coefficients with evidence
```

### 4. Clinical Reference Service
```python
class ClinicalReferenceService:
    """Biomarker reference ranges and clinical interpretation."""

    def get_reference_range(self, biomarker: str) -> ReferenceRange:
        # Return normal/abnormal thresholds
        # Age/sex stratification if available

    def interpret(self, biomarker: str, value: float) -> ClinicalInterpretation:
        # "High risk", "Moderate risk", "Normal", etc.
```

---

## Immediate Action Items

### ✅ COMPLETED: Environmental Pathway Testing (2025-10-25)

**Result**: INDRA does NOT have environmental → molecular pathways.
- See `ENVIRONMENTAL_EXPOSURE_GAP.md` for full analysis
- INDRA is molecular biology only (genes, proteins, metabolites)
- Environmental exposures (PM2.5, ozone) are NOT entities in knowledge graph

**Implication**: We MUST build environmental exposure mapping layer separately.

---

### NEXT ACTIONS (Prioritized)

1. **DECIDE**: Environmental exposure strategy
   - **Option A** (production-safe): Pre-curated pathways from literature
   - **Option B** (production): Integrate CTD (Comparative Toxicogenomics Database)
   - **Option C** (hybrid): LLM extracts intermediates, validate with INDRA

2. **FIX**: Network builder v1 to preserve db_refs
   - ❌ DELETE: `indra_network_builder_v2.py` (wrong pattern)
   - ✅ FIX: `indra_network_builder.py` to use complete ontology grounding
   - Change `_extract_agent()` to return `(name, db_refs)` tuple
   - Preserve ALL db_refs in node attributes

3. **DELETE**: Hardcoded mappings in grounding_service.py
   - Lines 31-51: Remove SEED_ENTITIES (~50 hardcoded entities)
   - Lines 64-88: Remove DATABASE_ID_TO_NAME (~30 hardcoded mappings)
   - Lines 92-140: Remove ALTERNATIVE_NAMES (~50 hardcoded aliases)
   - Replace with: ontology API calls OR document why seed entities needed

4. **BUILD**: Environmental exposure service (if Option A or B chosen)
   ```python
   class EnvironmentalExposureService:
       """Map environmental exposures to INDRA molecular entities."""

       async def get_molecular_intermediates(
           self, exposure: str
       ) -> List[Tuple[str, float]]:
           """PM2.5 → [("oxidative_stress", 0.78), ("NF-κB", 0.82)]"""
   ```

5. **INTEGRATE**: Multi-source knowledge graph
   - Environmental layer (new) → INDRA layer (exists) → Biomarker layer
   - Each layer uses proper ontology grounding (no hardcoding)
   - Clear API boundaries between layers

---

## Bottom Line

We're building a **multi-source knowledge graph integration**.

INDRA is ONE source (causal mechanisms). We need AT LEAST 4 more:
1. Environmental exposure data
2. Genetic variant databases
3. Clinical reference ranges
4. Temporal/PK-PD dynamics

Stop creating v2 files. Fix the architecture to integrate these properly.
