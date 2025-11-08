# INDRA Ontology Support: Complete Reference

**Date**: 2025-11-01
**Source**: INDRA Documentation (indra.readthedocs.io)

---

## Executive Summary

INDRA supports **30+ database clients** and uses **11 primary grounding namespaces** in a priority-ordered hierarchy. The system can ground to ANY identifiers.org namespace, making it highly extensible.

**Key Finding**: INDRA's grounding system is FAR MORE COMPREHENSIVE than our current implementation uses. We're only scratching the surface.

---

## Primary Grounding Namespaces (Priority Order)

INDRA BioOntology uses this default namespace priority:

```python
['FPLX', 'UPPRO', 'HGNC', 'UP', 'CHEBI', 'GO', 'MESH', 'MIRBASE', 'DOID', 'HP', 'EFO']
```

### Namespace Descriptions

| Namespace | Full Name | Purpose | Priority |
|-----------|-----------|---------|----------|
| **FPLX** | FamPlex | Protein families and complexes | 1 (highest) |
| **UPPRO** | UniProt Proteome | Protein entries | 2 |
| **HGNC** | HUGO Gene Nomenclature Committee | Human gene symbols/IDs | 3 |
| **UP** | UniProt | Protein sequence database | 4 |
| **CHEBI** | Chemical Entities of Biological Interest | Small molecules, drugs | 5 |
| **GO** | Gene Ontology | Biological processes, cellular components, molecular functions | 6 |
| **MESH** | Medical Subject Headings | Diseases, anatomy, chemicals, concepts | 7 |
| **MIRBASE** | miRBase | microRNA identifiers | 8 |
| **DOID** | Disease Ontology | Human disease classification | 9 |
| **HP** | Human Phenotype Ontology | Phenotypic abnormalities | 10 |
| **EFO** | Experimental Factor Ontology | Experimental variables | 11 |

**Additional namespaces** available: CHEMBL, PUBCHEM, HMDB, DRUGBANK, MONDO, IDO, CAS, EGID (Entrez Gene), MGI, RGD, TAXONOMY, EC, LINCS

---

## Complete Database Client List

### Gene/Protein Resources

| Client | Purpose |
|--------|---------|
| **hgnc_client** | Human gene nomenclature, conversions to Ensembl, Entrez, UniProt |
| **uniprot_client** | Protein sequences, annotations, isoforms |
| **mgi_client** | Mouse genes with human ortholog mapping |
| **rgd_client** | Rat genes with human ortholog mapping |

### Chemical/Drug Resources

| Client | Purpose |
|--------|---------|
| **chebi_client** | Chemical entities with cross-refs to PubChem, ChEMBL, HMDB |
| **chembl_client** | Drug-target interactions, pharmacology |
| **pubchem_client** | Chemical compound information |
| **drugbank_client** | Drug information, cross-database mappings |
| **hmdb_client** | Human metabolome (endogenous metabolites) |
| **cas_client** | Chemical Abstracts Service registry |

### Biological Ontologies

| Client | Purpose |
|--------|---------|
| **go_client** | Gene Ontology (BP, CC, MF) |
| **mesh_client** | Medical Subject Headings, disease classification |
| **mondo_client** | Disease ontology (integrates DOID, OMIM, Orphanet) |
| **hp_client** | Human Phenotype Ontology |
| **efo_client** | Experimental factors, diseases, anatomy |
| **doid_client** | Disease Ontology |
| **ido_client** | Infectious Disease Ontology |

### Specialized Resources

| Client | Purpose |
|--------|---------|
| **cbio_client** | cBioPortal cancer genomics (mutations, CNV) |
| **ndex_client** | Network Data Exchange (biological networks) |
| **mirbase_client** | microRNA identifiers |
| **taxonomy_client** | Organism classification (NCBI Taxonomy) |
| **ec_code_client** | Enzyme classification |
| **lincs_client** | Library of Integrated Network-Based Cellular Signatures |

### Infrastructure

| Client | Purpose |
|--------|---------|
| **identifiers_org** | Maps namespaces, generates URLs for identifiers.org |
| **bioregistry_client** | Namespace info from bioregistry.io |

---

## Grounding Disambiguation Tools

INDRA uses **two machine-learning tools** for context-aware entity grounding:

### 1. Gilda (Grounding Integrated Learning and Disambiguation Agent)

**Purpose**: Map entity names to grounded ontology identifiers

**Features**:
- Web service API: http://grounding.indra.bio
- Local Python package available
- Context-aware disambiguation using evidence text
- Supports synonyms, abbreviations, spelling variations
- Returns scored grounding candidates

**Integration**: `indra.preassembler.grounding_mapper.GroundingMapper` uses Gilda for automated grounding

### 2. Adeft (Acromine-based Disambiguation of Entities From Text)

**Purpose**: Disambiguate ambiguous acronyms and abbreviations

**Features**:
- Analyzes evidence context (full papers, abstracts, or sentences)
- Machine learning classifier trained on usage patterns
- Handles domain-specific terminology
- Returns confidence scores

**Example**: "ROS" could be:
- Reactive Oxygen Species (biology)
- Robot Operating System (robotics)
- Return on Sales (finance)

Adeft uses context to choose correct meaning.

---

## How INDRA Grounding Works

### Grounding Workflow

```
Raw Entity Name (e.g., "PM2.5", "IL-6", "oxidative stress")
        ↓
    Gilda Grounding Service
    - Query with name + context
    - Get scored candidates
        ↓
    Score candidates:
    - "IL-6" → HGNC:5973 (score: 0.95)
    - "IL-6" → UP:P05231 (score: 0.90)
    - "IL-6" → MESH:D015850 (score: 0.85)
        ↓
    Apply namespace priority:
    - HGNC (priority 3) > UP (priority 4) > MESH (priority 7)
    - Select: HGNC:5973
        ↓
    Standardize name:
    - Use HGNC symbol: "IL6"
        ↓
    Cross-reference mapping:
    - Add UP, EGID, MESH IDs from HGNC record
        ↓
    Final db_refs:
    {
        "HGNC": "5973",
        "UP": "P05231",
        "EGID": "3569",
        "MESH": "D015850"
    }
```

### Standardization Functions

```python
from indra.ontology.standardize import (
    get_standard_agent,      # Create standardized agent
    get_standard_name,       # Get standardized name
    standardize_agent_name,  # Update agent name
    standardize_db_refs,     # Normalize db_refs dict
    standardize_name_db_refs # Get both name and refs
)

# Example usage
from indra.statements import Agent

# Create agent with name only
agent = Agent("PM2.5")

# Standardize with Gilda
from indra.preassembler import grounding_mapper
gm = grounding_mapper.GroundingMapper()
gm.map_agents([agent])

# Result:
# agent.db_refs = {"MESH": "D052638", "CHEBI": "CHEBI:53498"}
# agent.name = "Particulate Matter"
```

---

## What Our Implementation Currently Uses

### Current Coverage (from our code)

**Testing** (`test_ontology_grounding.py`):
```python
# We check for these namespaces:
- HGNC (genes)
- CHEBI (chemicals)
- MESH (general)
- PUBCHEM (chemicals)
- CHEMBL (drugs)
- UP (proteins)
- EGID (Entrez Gene)
```

**Grounding Service** (`grounding_service.py`):
```python
# Hardcoded entities (~140 lines)
SEED_ENTITIES = {
    "PM2.5": {"MESH": "D052638"},
    "CRP": {"HGNC": "2367"},
    ...
}

# NOT using Gilda or INDRA's grounding tools!
```

### What We're MISSING

1. **Gilda integration** - No automated grounding for arbitrary entity names
2. **Adeft disambiguation** - No context-aware acronym resolution
3. **Cross-reference expansion** - Not using HGNC → UP/EGID mappings
4. **Ontology clients** - Not leveraging 30+ database clients
5. **Priority-based selection** - Not using namespace hierarchy
6. **Synonym expansion** - Not querying all name variants

---

## INDRA's Environmental Exposure Support

### Question: Does INDRA support environmental entities?

**Answer**: **PARTIALLY** - depends on namespace

**MESH namespace includes**:
- ✅ "Air Pollutants" (MESH:D000393)
- ✅ "Particulate Matter" (MESH:D052638)
- ✅ "Ozone" (MESH:D010126)
- ✅ "Vehicle Emissions" (MESH:D001335)
- ✅ "Tobacco Smoke Pollution" (MESH:D014028)

**CHEBI namespace includes**:
- ✅ Lead compounds (CHEBI:25016)
- ✅ Cadmium compounds (CHEBI:22977)
- ✅ Arsenic compounds (CHEBI:22632)
- ✅ Benzene (CHEBI:16716)
- ✅ Formaldehyde (CHEBI:16842)

**GO namespace includes**:
- ✅ "oxidative stress" (GO:0006979)
- ✅ "inflammatory response" (GO:0006954)
- ✅ "response to reactive oxygen species" (GO:0000302)

### Implication for Environmental Queries

**INDRA CAN ground environmental entities** via:
1. **MESH** for general environmental exposures (air pollutants, particulate matter)
2. **CHEBI** for specific chemicals (heavy metals, organic compounds)
3. **GO** for biological processes (oxidative stress, inflammation)

**BUT**: INDRA may NOT have **causal statements** linking environmental entities to molecular targets.

**Example**:
```python
# INDRA can ground this:
"PM2.5" → MESH:D052638 (Particulate Matter)

# But may not have statements:
"Particulate Matter" → "IL6" (0 results in our tests)

# Versus molecular pathways work:
"IL6" → "CRP" (should have hundreds of statements)
```

---

## Recommendations for Our Implementation

### IMMEDIATE: Test with Proper Grounding

Instead of:
```python
processor = idr.get_statements(
    subject="Particulate Matter",  # Ungrounded name
    object="Interleukin-6"         # Ungrounded name
)
```

Try:
```python
from indra.preassembler import grounding_mapper
from indra.statements import Agent

# Create agents
pm25_agent = Agent("PM2.5")
il6_agent = Agent("IL-6")

# Ground with Gilda
gm = grounding_mapper.GroundingMapper()
gm.map_agents([pm25_agent, il6_agent])

# Query with grounded entities
processor = idr.get_statements(
    subject=pm25_agent.name,  # Now standardized
    object=il6_agent.name
)

# OR use db_refs directly
processor = idr.get_statements_by_hash(
    subject_hash=pm25_agent.get_hash(),
    object_hash=il6_agent.get_hash()
)
```

### SHORT-TERM: Replace Hardcoded Grounding Service

**Current** (`grounding_service.py`):
```python
# 140 lines of hardcoded entities
SEED_ENTITIES = {...}
DATABASE_ID_TO_NAME = {...}
ALTERNATIVE_NAMES = {...}
```

**Recommended** (use Gilda):
```python
from indra.preassembler.grounding_mapper import GroundingMapper

class GildaGroundingService:
    def __init__(self):
        self.gm = GroundingMapper()

    async def ground_entity(self, name: str, context: str = None):
        """Ground entity using Gilda + INDRA ontology."""
        agent = Agent(name)
        self.gm.map_agents([agent], context=context)
        return {
            "name": agent.name,
            "db_refs": agent.db_refs
        }
```

### MEDIUM-TERM: Leverage All INDRA Ontologies

**Use case**: Environmental exposure queries

**Strategy**:
1. **Ground exposures via MESH**: PM2.5 → MESH:D052638
2. **Ground chemicals via CHEBI**: Lead → CHEBI:25016
3. **Ground processes via GO**: oxidative stress → GO:0006979
4. **Query INDRA DB** with grounded entities
5. **Fallback to CTD** if INDRA has no statements

**Hybrid architecture**:
```
User Query: "PM2.5 affects inflammation"
    ↓
Ground entities (Gilda):
  PM2.5 → MESH:D052638
  inflammation → GO:0006954
    ↓
Query INDRA DB:
  MESH:D052638 → GO:0006954
    ↓
IF statements found:
  Use INDRA pathways
ELSE:
  Query CTD:
    PM2.5 → {IL6, TNF, NF-κB}
  Query INDRA:
    IL6 → CRP (molecular pathways)
  Merge graphs
```

---

## Testing Implications

### Current Test Status

**Problem**: Tests use ungrounded names
```python
# test_indra_db_quick.py
processor = idr.get_statements(
    subject="Particulate Matter",  # Not grounded!
    object="Interleukin-6"         # Not grounded!
)
# Result: 0 statements
```

**Why this fails**:
1. INDRA DB may require grounded entities (MESH IDs, not names)
2. Entity names must match INDRA's standardized forms exactly
3. No context for disambiguation

### Updated Test Strategy

**Test 1**: Verify grounding works
```python
from indra.preassembler.grounding_mapper import GroundingMapper

gm = GroundingMapper()

# Test grounding
pm25 = Agent("PM2.5")
gm.map_agents([pm25])

print(f"Grounded: {pm25.name}")
print(f"db_refs: {pm25.db_refs}")

# Expected:
# Grounded: Particulate Matter
# db_refs: {"MESH": "D052638", "CHEBI": "CHEBI:53498"}
```

**Test 2**: Query with grounded entities
```python
# Use standardized names from grounding
processor = idr.get_statements(
    subject=pm25.name,  # "Particulate Matter" (standardized)
    object="IL6"        # Use HGNC symbol
)
```

**Test 3**: Try namespace-specific queries
```python
# If MESH ID doesn't work, try HGNC for genes
il6_agent = Agent("IL-6")
gm.map_agents([il6_agent])

# Query with HGNC ID
processor = idr.get_statements(
    subject="Particulate Matter",
    object=il6_agent.db_refs.get("HGNC")  # Use ID, not name
)
```

---

## Action Items

### 1. Create Grounding Test Script

File: `indra_agent/examples/test_gilda_grounding.py`

**Purpose**: Verify Gilda integration works

**Tests**:
- Ground environmental entities (PM2.5, Ozone, Lead)
- Ground genes (IL-6, CRP, TNF)
- Ground processes (oxidative stress, inflammation)
- Verify db_refs populated correctly
- Verify namespace priorities work

### 2. Update INDRA DB Query Tests

File: `indra_agent/examples/test_indra_db_environmental.py`

**Changes**:
- Use Gilda to ground entities BEFORE querying
- Try multiple query formats (name, MESH ID, HGNC ID)
- Test with standardized names
- Add control tests with known molecular pathways

### 3. Replace Hardcoded Grounding Service

File: `indra_agent/services/grounding_service.py`

**Strategy**:
- Deprecate hardcoded SEED_ENTITIES
- Integrate GroundingMapper from INDRA
- Use Gilda for automated grounding
- Cache grounding results to avoid redundant API calls
- Document ontology priorities

### 4. Document INDRA Ontology Coverage

File: `indra_agent/docs/ontology_coverage.md`

**Contents**:
- List all 11 primary namespaces
- Document namespace priorities
- Provide examples of grounded entities
- Explain when to use each namespace
- Show cross-reference mappings

---

## Bottom Line

**Are we leveraging INDRA's ontologies to the max?** **NO**

**Current state**:
- Using 7 namespaces manually (HGNC, CHEBI, MESH, PUBCHEM, CHEMBL, UP, EGID)
- Hardcoding ~140 entity groundings
- NOT using Gilda or Adeft for automated grounding
- NOT using 30+ INDRA database clients
- NOT using namespace priority hierarchy
- NOT expanding cross-references automatically

**INDRA provides**:
- 11 primary namespaces + 20+ additional
- Gilda for automated grounding
- Adeft for disambiguation
- 30+ database clients
- Cross-reference expansion
- Standardization functions

**Recommendation**:
1. **IMMEDIATE**: Test INDRA DB queries with Gilda-grounded entities
2. **SHORT-TERM**: Replace hardcoded grounding with GroundingMapper
3. **MEDIUM-TERM**: Leverage full ontology hierarchy for environmental queries
4. **LONG-TERM**: Integrate CTD as fallback when INDRA lacks environmental statements

**Key insight**: INDRA CAN ground environmental entities (via MESH, CHEBI, GO), but may NOT have causal statements linking them to molecular targets. This is why CTD integration remains critical.
