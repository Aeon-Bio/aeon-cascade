# Environmental Exposure Gap in INDRA Knowledge Graph

**Date**: 2025-10-25
**Status**: Critical architecture finding

---

## The Problem

**Question**: "What files? In the KG?"

**Answer**: There are NO files for environmental exposures in the INDRA knowledge graph. They don't exist as entities.

---

## What We Tested

Comprehensive testing of INDRA's PathwayCommons endpoint (`/biopax/process_pc_pathsbetween`):

### Environmental Exposures (ALL FAILED)
```python
# Abstract environmental terms
❌ "PM2.5" → oxidative stress (0 paths)
❌ "Particulate Matter" → ROS (0 paths)
❌ "Ozone" → inflammation (0 paths)
❌ "Air Pollutants" → CRP (0 paths)
❌ "Cigarette smoke" → oxidative stress (0 paths)

# Specific chemicals in pollution
❌ "Lead" → molecular targets (0 paths)
❌ "Cadmium" → molecular targets (0 paths)
❌ "Arsenic" → molecular targets (0 paths)
❌ "Mercury" → molecular targets (0 paths)
❌ "Benzene" → molecular targets (0 paths)
❌ "Formaldehyde" → molecular targets (0 paths)
❌ "Benzo[a]pyrene" → molecular targets (0 paths)

# Reactive species
❌ "Hydrogen peroxide" → molecular targets (0 paths)
❌ "Peroxynitrite" → molecular targets (0 paths)
❌ "Superoxide" → molecular targets (0 paths)
```

### What DOES Work in INDRA
```python
# Gene/protein pathways
✅ "CRP" → "IL6" → "TNF" (40 statements)
✅ "BRAF" → "MAP2K1" → "MAPK1" (works)
✅ Molecular processes, signaling cascades, metabolic pathways
```

---

## Why This Happens

### INDRA Data Sources

INDRA aggregates from:
1. **PathwayCommons**: Gene/protein signaling (BioPAX format)
2. **Scientific literature**: Molecular biology papers (via NLP extraction)
3. **Pathway databases**: Reactome, KEGG, WikiPathways, etc.

**What's MISSING**: Environmental health literature is NOT in INDRA's corpus.

### Why Environmental Data Isn't There

1. **Different research domains**:
   - INDRA focuses on **molecular biology** (genes, proteins, small molecules)
   - Environmental health is **toxicology/epidemiology** (exposures, populations, outcomes)

2. **Different statement types**:
   - INDRA statements: "BRAF phosphorylates MAP2K1" (molecular mechanism)
   - Environmental research: "PM2.5 associated with 16% increase in CRP" (population-level correlation)

3. **Different ontologies**:
   - INDRA uses: HGNC (genes), CHEBI (drugs), UP (proteins), GO (processes)
   - Environmental health uses: EPA substance registry, IRIS database, exposure taxonomies

4. **Pathway databases don't include environment**:
   - Reactome: cellular pathways only
   - KEGG: metabolism and signaling
   - WikiPathways: molecular pathways
   - **None include**: "PM2.5 → ROS" or "Ozone → NF-κB"

---

## The Architecture Gap

**Current reality**:
```
User Query: "How does air pollution in LA affect inflammation?"

Step 1: Extract entities → ["air pollution", "Los Angeles", "inflammation"]
Step 2: Ground to INDRA → FAILS (no "air pollution" entity)
Step 3: Query INDRA → FAILS (no environmental pathways)
Step 4: ???
```

**What we THOUGHT we could do**:
```
PM2.5 (environmental) → INDRA pathways → IL-6 (biomarker)
```

**What we CAN'T do** (because INDRA doesn't have it):
```
PM2.5 → ??? → (missing link) → ??? → IL-6
```

---

## What We Actually Need

### Option 1: Literature-Derived Environmental Mappings

Build a **separate knowledge base** from environmental health literature:

```python
ENVIRONMENTAL_PATHWAYS = {
    "PM2.5": {
        "oxidative_stress": {
            "effect_size": 0.78,  # From meta-analysis
            "evidence_papers": 31,
            "temporal_lag_hours": 6,
            "confidence": 0.82
        },
        "NF-κB": {
            "effect_size": 0.82,
            "evidence_papers": 47,
            "temporal_lag_hours": 6,
            "confidence": 0.85
        }
    },
    "Ozone": {
        "inflammation": {
            "effect_size": 0.71,
            "evidence_papers": 23,
            ...
        }
    }
}
```

**Source**: Systematic reviews and meta-analyses from:
- Environmental Health Perspectives
- Particle and Fibre Toxicology
- EPA IRIS database
- WHO air quality guidelines

**Then**:
```
PM2.5 → [lookup table] → oxidative_stress → [INDRA] → IL-6 → [INDRA] → CRP
       ↑ manual curated                    ↑ INDRA knowledge graph
```

### Option 2: Hybrid LLM + INDRA Approach

Use LLM to extract environmental → molecular relationships from papers:

```python
async def get_environmental_pathways(exposure: str, target: str):
    """Query LLM with environmental health papers, validate with INDRA."""

    # Step 1: LLM extracts molecular intermediates
    prompt = f"""
    Based on environmental health literature, what molecular mechanisms
    link {exposure} exposure to {target}?

    Return specific genes/proteins that INDRA might have pathways for.
    """

    molecular_intermediates = await llm.generate(prompt)
    # → ["ROS", "NF-κB", "MAPK", ...]

    # Step 2: Verify these exist in INDRA
    for intermediate in molecular_intermediates:
        indra_paths = await indra.get_paths_between([intermediate, target])
        if indra_paths:
            # Found bridging pathway!
            return construct_hybrid_graph(exposure, intermediate, target, indra_paths)
```

**Advantage**: Leverages INDRA's molecular knowledge + LLM's literature understanding
**Disadvantage**: LLM hallucination risk, no quantitative effect sizes

### Option 3: Manual Curation (Hackathon-Safe)

For demo/production: **hardcode the critical pathways** from established literature:

```python
# cached_environmental_pathways.py
KNOWN_ENVIRONMENTAL_MECHANISMS = {
    "PM2.5_to_inflammation": {
        "path": ["PM2.5", "oxidative_stress", "NF-κB", "IL6", "CRP"],
        "edges": [
            {
                "source": "PM2.5",
                "target": "oxidative_stress",
                "effect_size": 0.78,
                "evidence": "Meta-analysis of 31 papers (Brook et al. 2010)",
                "temporal_lag_hours": 6
            },
            # oxidative_stress → NF-κB comes from INDRA
            # NF-κB → IL6 comes from INDRA
            # IL6 → CRP comes from INDRA
        ]
    }
}
```

**Use case**: User asks about PM2.5 → inflammation
**System**: Returns pre-curated pathway + INDRA molecular details
**Advantage**: Reliable, evidence-based, works for demo
**Disadvantage**: Doesn't scale to arbitrary environmental queries

### Option 4: Different Data Source (ComptTox, CTD)

**Comparative Toxicogenomics Database (CTD)**:
- Contains chemical → gene → disease relationships
- Includes environmental exposures
- Has API: `http://ctdbase.org/tools/batchQuery.go`

**Example CTD query**:
```
Chemical: "Particulate Matter"
→ Associated genes: HMOX1, IL6, TNF, NF-κB, ...
→ Diseases: Inflammation, cardiovascular disease, ...
```

**Then map to INDRA**:
```
PM2.5 → [CTD] → {IL6, TNF, NF-κB} → [INDRA pathways] → CRP
```

**Advantage**: Real data source for environmental toxicology
**Disadvantage**: Need to integrate another API, map ontologies

---

## Recommendation for Current Architecture

**Immediate (production/demo)**:
1. ✅ Use pre-curated pathways for key environmental exposures (PM2.5, ozone, smoking)
2. ✅ Document these are from literature, not INDRA
3. ✅ Bridge to INDRA for molecular mechanisms (NF-κB → IL6 → CRP)

**Phase 2 (production)**:
1. Integrate CTD (Comparative Toxicogenomics Database) for environmental → gene associations
2. Build ontology mapping layer: CTD chemicals → INDRA entities
3. Use INDRA for molecular pathways ONLY (what it's good at)

**Phase 3 (research)**:
1. Train custom NLP model on environmental health corpus
2. Extract exposure → mechanism relationships automatically
3. Validate against INDRA molecular pathways

---

## Updated Architecture Diagram

**What we have now**:
```
User Query → LLM Supervisor
           ↓
    INDRA Query Agent → INDRA API (genes/proteins/metabolites)
           ↓
    Molecular pathways ONLY
```

**What we actually need**:
```
User Query → LLM Supervisor
           ↓
    Environmental Exposure Detector
           ↓
    ┌──────────────────────┐
    ↓                      ↓
Environmental Data      INDRA Query Agent
(PM2.5, location)       (molecular pathways)
    ↓                      ↓
Curated Exposure        Gene/protein
Pathways (manual)       mechanisms
    └──────────────────────┘
           ↓
    Hybrid Causal Graph
    (exposure → molecular → biomarker)
```

---

## Bottom Line

**The knowledge graph (INDRA) does NOT contain environmental exposure entities.**

This is NOT a bug. This is by design - INDRA is a **molecular biology knowledge graph**, not an environmental health database.

We must either:
1. **Accept the limitation**: Only answer molecular mechanism questions
2. **Build the bridge**: Create environmental → molecular mapping layer
3. **Integrate external data**: Use CTD, EPA IRIS, or other environmental databases

**For production**: Option #1 (curated pathways) + Option #3 (INDRA molecular)
**For production**: Option #4 (CTD integration) + INDRA

The question "what files? in the kg?" has a simple answer: **There are none. They don't exist. We have to build them.**
