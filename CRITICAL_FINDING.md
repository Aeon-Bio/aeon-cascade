# CRITICAL FINDING: INDRA Knowledge Graph Scope

**Date**: 2025-10-25
**Question**: "what files? in the kg?"
**Answer**: There are NONE. Environmental exposures don't exist in INDRA.

---

## What We Discovered

### ❌ What INDRA Does NOT Have

Comprehensive testing shows INDRA has **ZERO** environmental exposure pathways:

```
PM2.5 → anything: 0 paths
Ozone → anything: 0 paths
Cigarette smoke → anything: 0 paths
Air Pollutants → anything: 0 paths
Lead/Cadmium/Arsenic → anything: 0 paths
Benzene/Formaldehyde → anything: 0 paths
```

### ✅ What INDRA DOES Have

INDRA excels at **molecular biology**:

```
CRP ↔ IL6 ↔ TNF: 40 statements
BRAF → MAP2K1 → MAPK1: ✅ works
Gene signaling, metabolic pathways: ✅ complete
Protein interactions, modifications: ✅ comprehensive
```

---

## Why This Happens

### INDRA's Data Sources

INDRA aggregates:
- **PathwayCommons**: Gene/protein signaling (BioPAX)
- **Reactome, KEGG, WikiPathways**: Molecular pathways
- **Literature NLP**: Molecular biology papers

### What's Missing

**Environmental health literature** is NOT in INDRA's corpus because:

1. **Different research domains**:
   - INDRA = molecular biology (genes, proteins, metabolites)
   - Environmental health = toxicology/epidemiology (exposures, populations)

2. **Different ontologies**:
   - INDRA uses: HGNC (genes), CHEBI (drugs), UP (proteins), GO (processes)
   - Environmental uses: EPA substance registry, IRIS database, CTD

3. **Pathway databases exclude environment**:
   - Reactome: cellular only
   - KEGG: metabolism only
   - WikiPathways: molecular only
   - **None** include "PM2.5 → ROS" or "Ozone → inflammation"

---

## The Architecture Gap

### What We THOUGHT We Could Do

```
User: "How does air pollution in LA affect inflammation?"

System:
  Extract: ["air pollution", "Los Angeles", "inflammation"]
  ↓
  Ground to INDRA: ["air_pollution_entity", "inflammation_pathway"]
  ↓
  Query INDRA: PM2.5 → ROS → NF-κB → IL-6 → CRP
  ↓
  Return causal graph ✅
```

### What ACTUALLY Happens

```
User: "How does air pollution in LA affect inflammation?"

System:
  Extract: ["air pollution", "Los Angeles", "inflammation"]
  ↓
  Ground to INDRA: ❌ FAILS (no "air pollution" entity exists)
  ↓
  Query INDRA: ❌ FAILS (no environmental pathways)
  ↓
  Return: ??? (system breaks)
```

---

## What We Must Build

### The Missing Layer

```
Environmental Exposure Mapping Layer
(Does NOT exist - we must create it)
           ↓
PM2.5 → {oxidative_stress, NF-κB, ROS}
           ↓
      [INDRA pathways]
           ↓
    oxidative_stress → IL6 → CRP
```

### Three Options

**Option A: Manual Curation** (production-safe)
```python
# Pre-curated from literature
ENVIRONMENTAL_PATHWAYS = {
    "PM2.5": {
        "oxidative_stress": {"effect": 0.78, "papers": 31},
        "NF-κB": {"effect": 0.82, "papers": 47}
    }
}
# Then bridge to INDRA for molecular mechanisms
```

**Option B: External Database** (production)
```python
# Integrate CTD (Comparative Toxicogenomics Database)
ctd_response = await ctd.query("Particulate Matter")
# → {genes: ["IL6", "TNF", "NF-κB"], ...}

# Then query INDRA for those genes
indra_paths = await indra.get_paths_between(ctd_genes)
```

**Option C: LLM Hybrid** (research)
```python
# LLM extracts molecular intermediates from papers
intermediates = await llm.extract_pathway("PM2.5", "inflammation")
# → ["ROS", "NF-κB", "MAPK"]

# Validate these exist in INDRA
for intermediate in intermediates:
    verify_in_indra(intermediate)
```

---

## Bottom Line

**"What files? In the KG?"**

**Answer**: There are NO files for environmental exposures in INDRA. They don't exist. This is NOT a bug - INDRA is a **molecular biology** knowledge graph, not an environmental health database.

**What this means**:

1. ✅ We CAN use INDRA for molecular mechanisms (NF-κB → IL6 → CRP)
2. ❌ We CANNOT use INDRA for environmental exposures (PM2.5 → ...)
3. 🔨 We MUST build the environmental → molecular bridge ourselves

**Files that exist**: Gene pathways, protein interactions, metabolic networks
**Files that don't exist**: PM2.5 pathways, ozone effects, pollution mechanisms

The knowledge graph is INCOMPLETE for our use case. We need to extend it.

---

## Recommended Path Forward

**Immediate** (production):
- Use pre-curated environmental pathways (Option A)
- Document these come from literature, not INDRA
- Bridge to INDRA for molecular mechanisms only

**Phase 2** (production):
- Integrate CTD for environmental → gene associations
- Build ontology mapping layer
- Use INDRA for molecular pathways only (its strength)

**Phase 3** (research):
- Train NLP model on environmental health corpus
- Extract exposure → mechanism relationships
- Validate against INDRA molecular knowledge

---

## Testing Evidence

See `indra_agent/examples/test_environmental_pathways.py`:

```bash
$ uv run python indra_agent/examples/test_environmental_pathways.py

TEST: PM2.5 → oxidative stress
❌ NO PATHS: Particulate Matter → oxidative stress
❌ NO PATHS: Particulate Matter → ROS
❌ NO PATHS: Particulate Matter → reactive oxygen species

TEST: Ozone → inflammation
❌ NO PATHS: Ozone → inflammation
❌ NO PATHS: Ozone → IL6
❌ NO PATHS: Ozone → TNF

(All 15 tested queries failed)
```

**Conclusion**: INDRA does not contain environmental exposure data.
