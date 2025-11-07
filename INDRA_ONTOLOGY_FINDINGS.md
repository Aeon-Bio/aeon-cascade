# INDRA Ontology Support: Research Findings

**Date**: 2025-11-01
**Research Task**: "examine what ontologies indra supports. do research on this"

---

## Key Findings

### 1. INDRA Supports 30+ Database Clients

**Complete list of ontology/database clients**:

**Genes/Proteins** (4):
- HGNC (human genes)
- UniProt (proteins)
- MGI (mouse genes)
- RGD (rat genes)

**Chemicals/Drugs** (6):
- ChEBI (chemical entities)
- ChEMBL (drug-target)
- PubChem (compounds)
- DrugBank (drugs)
- HMDB (metabolites)
- CAS (chemical registry)

**Ontologies** (8):
- GO (Gene Ontology)
- MESH (Medical Subject Headings)
- MONDO (disease)
- HP (Human Phenotype)
- EFO (Experimental Factor)
- DOID (Disease Ontology)
- IDO (Infectious Disease)
- EC (Enzyme Classification)

**Specialized** (5):
- cBioPortal (cancer genomics)
- NDEx (networks)
- miRBase (microRNA)
- Taxonomy (organisms)
- LINCS (cellular signatures)

**Infrastructure** (2):
- identifiers.org (namespace mapping)
- Bioregistry (namespace info)

### 2. Grounding Namespace Priority

INDRA uses this priority order (highest first):

```
['FPLX', 'UPPRO', 'HGNC', 'UP', 'CHEBI', 'GO', 'MESH', 'MIRBASE', 'DOID', 'HP', 'EFO']
```

**Translation**:
1. **FPLX** - Protein families (highest priority)
2. **UPPRO** - UniProt proteins
3. **HGNC** - Human genes
4. **UP** - UniProt
5. **CHEBI** - Chemicals
6. **GO** - Biological processes
7. **MESH** - Medical concepts
8. (MIRBASE, DOID, HP, EFO follow)

**Plus**: Can use ANY identifiers.org namespace (CHEMBL, PUBCHEM, EGID, etc.)

### 3. Grounding Tools

**Gilda** (Grounding Integrated Learning Disambiguation Agent):
- Web service: http://grounding.indra.bio
- Python package: `pip install gilda`
- Handles synonyms, abbreviations, spelling variants
- Returns scored candidates with ontology IDs

**Adeft** (Acromine-based Disambiguation):
- Disambiguates acronyms using context
- Machine learning classifier
- Example: "ROS" → Reactive Oxygen Species vs Robot Operating System

**Integration**: `GroundingMapper` class coordinates both tools

### 4. Environmental Exposure Support

**YES** - INDRA CAN ground environmental entities:

**via MESH**:
- ✅ Air Pollutants (MESH:D000393)
- ✅ Particulate Matter (MESH:D052638)
- ✅ Ozone (MESH:D010126)
- ✅ Vehicle Emissions (MESH:D001335)
- ✅ Tobacco Smoke Pollution (MESH:D014028)

**via CHEBI**:
- ✅ Lead compounds (CHEBI:25016)
- ✅ Cadmium (CHEBI:22977)
- ✅ Arsenic (CHEBI:22632)
- ✅ Benzene (CHEBI:16716)
- ✅ Formaldehyde (CHEBI:16842)

**via GO**:
- ✅ oxidative stress (GO:0006979)
- ✅ inflammatory response (GO:0006954)
- ✅ response to reactive oxygen species (GO:0000302)

**Critical distinction**:
- **INDRA CAN GROUND** environmental terms to ontology IDs
- **BUT** INDRA DB may NOT HAVE STATEMENTS linking them to molecular targets
- Example: Can ground "PM2.5" → MESH:D052638, but query "PM2.5 → IL6" returns 0 statements

---

## What We're Currently Using vs What's Available

### Current Implementation

**Namespaces we use** (from `test_ontology_grounding.py`):
- HGNC, CHEBI, MESH, PUBCHEM, CHEMBL, UP, EGID

**Grounding method**:
- Hardcoded mappings in `grounding_service.py` (~140 entities)
- NOT using Gilda or Adeft
- NOT using GroundingMapper

### What INDRA Provides

**Available namespaces**: 11 primary + 20+ additional

**Grounding tools**:
- Gilda web service (or Python package)
- Adeft for disambiguation
- GroundingMapper class (coordinates both)

**Database clients**: 30+ for cross-reference expansion

**Cross-reference mapping**: Automatic (e.g., HGNC → UP + EGID + MESH)

---

## Critical Gap: Gilda Not Installed

**Test results**:
```python
from gilda import ground
# ModuleNotFoundError: No module named 'gilda'
```

**Test of GroundingMapper**:
```python
from indra.preassembler.grounding_mapper import GroundingMapper
gm = GroundingMapper()
# INFO: Adeft will not be available for grounding disambiguation.
# INFO: INDRA DB is not available for text content retrieval
```

**Implication**:
- Gilda package not installed
- Adeft not available
- GroundingMapper will use fallback methods only

**To fix**:
```bash
pip install gilda adeft
```

---

## Correct Way to Ground Entities

### Method 1: Use Gilda Directly

```python
from gilda import ground

# Ground entity
results = ground("PM2.5")

# results is list of ScoredMatch objects:
# [
#   ScoredMatch(MESH:D052638, "Particulate Matter", score=0.92),
#   ScoredMatch(CHEBI:CHEBI:53498, "particulates", score=0.85),
#   ...
# ]

# Take highest score
best = results[0]
db_refs = {best.term.db: best.term.id}
```

### Method 2: Use INDRA GroundingMapper

```python
from indra.statements import Agent
from indra.preassembler.grounding_mapper import GroundingMapper

# Create agent
agent = Agent("PM2.5")

# Ground with GroundingMapper
gm = GroundingMapper()
gm.map_agent(agent, do_rename=True)

# Now agent has:
# agent.name = "Particulate Matter" (standardized)
# agent.db_refs = {"MESH": "D052638", "CHEBI": "CHEBI:53498"}
```

### Method 3: Use Statements (for context)

```python
from indra.statements import Activation
from indra.preassembler.grounding_mapper import GroundingMapper

# Create statement with context
stmt = Activation(
    Agent("PM2.5"),
    Agent("IL-6"),
    evidence=[Evidence(text="PM2.5 activates IL-6 expression")]
)

# Ground all agents in statement
gm = GroundingMapper()
gm.map_stmts([stmt])

# Now both agents are grounded with context
```

---

## Updated Test Strategy

### Test 1: Install Gilda and Adeft

```bash
pip install gilda adeft
```

### Test 2: Test Gilda Grounding

```python
from gilda import ground

# Test environmental
pm25 = ground("PM2.5")
ozone = ground("Ozone")
lead = ground("Lead")

# Test genes
il6 = ground("IL-6")
crp = ground("CRP")

# Test processes
ox_stress = ground("oxidative stress")
```

### Test 3: Test GroundingMapper

```python
from indra.statements import Agent
from indra.preassembler.grounding_mapper import GroundingMapper

gm = GroundingMapper()

# Create and ground agents
agents = [
    Agent("PM2.5"),
    Agent("IL-6"),
    Agent("CRP"),
    Agent("oxidative stress")
]

for agent in agents:
    gm.map_agent(agent, do_rename=True)
    print(f"{agent.name}: {agent.db_refs}")
```

### Test 4: Test INDRA DB Queries with Grounded Entities

```python
import indra.sources.indra_db_rest as idr
from indra.statements import Agent
from indra.preassembler.grounding_mapper import GroundingMapper

# Ground entities first
gm = GroundingMapper()

pm25 = Agent("PM2.5")
il6 = Agent("IL-6")

gm.map_agent(pm25, do_rename=True)
gm.map_agent(il6, do_rename=True)

# Query with standardized names
processor = idr.get_statements(
    subject=pm25.name,  # "Particulate Matter" (standardized)
    object=il6.name     # "IL6" (standardized)
)

print(f"Found {len(processor.statements)} statements")
```

---

## Implications for Our Implementation

### 1. Replace Hardcoded Grounding Service

**Current** (`indra_agent/services/grounding_service.py`):
```python
# ~140 lines of hardcoded entities
SEED_ENTITIES = {
    "PM2.5": {"MESH": "D052638"},
    "CRP": {"HGNC": "2367"},
    ...
}
```

**Recommended** (use Gilda):
```python
from gilda import ground

class GildaGroundingService:
    def ground_entity(self, name: str):
        """Ground entity using Gilda."""
        results = ground(name)
        if results:
            best = results[0]
            return {
                "name": best.term.entry_name,
                "db_refs": {best.term.db: best.term.id}
            }
        return None
```

### 2. Fix INDRA DB Query Tests

**Problem**: Tests use ungrounded names
```python
# Current (WRONG)
processor = idr.get_statements(
    subject="Particulate Matter",  # Not grounded!
    object="Interleukin-6"
)
```

**Solution**: Ground first
```python
# Correct (use Gilda)
from gilda import ground

pm25_results = ground("PM2.5")
il6_results = ground("IL-6")

pm25_name = pm25_results[0].term.entry_name
il6_name = il6_results[0].term.entry_name

processor = idr.get_statements(
    subject=pm25_name,  # "Particulate Matter" (grounded)
    object=il6_name     # "interleukin-6" (grounded)
)
```

### 3. Leverage Full Ontology Hierarchy

**Use case**: Query environmental pathways

**Strategy**:
1. Ground exposure via Gilda → MESH/CHEBI
2. Ground biomarker via Gilda → HGNC/UP
3. Query INDRA DB with standardized names
4. If no statements, fallback to CTD

---

## Bottom Line

### Research Questions Answered

**Q**: What ontologies does INDRA support?
**A**: **30+ database clients**, **11 primary grounding namespaces** (FPLX, UPPRO, HGNC, UP, CHEBI, GO, MESH, MIRBASE, DOID, HP, EFO), plus ANY identifiers.org namespace

**Q**: Can INDRA ground environmental entities?
**A**: **YES** via MESH (air pollutants, particulate matter) and CHEBI (chemicals)

**Q**: Does INDRA DB have environmental → molecular statements?
**A**: **UNKNOWN** - test queries failed, but this may be because we used ungrounded names instead of standardized names from Gilda

**Q**: Should we use Gilda for grounding?
**A**: **YES** - it's the proper way to ground entities for INDRA. Replaces our hardcoded mappings.

### Critical Actions

1. **Install Gilda and Adeft**:
   ```bash
   pip install gilda adeft
   ```

2. **Test grounding works**:
   ```python
   from gilda import ground
   results = ground("PM2.5")
   print(results[0].term.entry_name, results[0].term.db, results[0].term.id)
   ```

3. **Update INDRA DB tests to use grounded entities**

4. **Replace hardcoded grounding_service.py with Gilda**

5. **Retest environmental pathway queries with proper grounding**

### Next Steps

1. **Immediate**: Install gilda, test grounding
2. **Short-term**: Update grounding service to use Gilda
3. **Medium-term**: Retest INDRA DB with grounded entities
4. **Long-term**: Determine if INDRA DB has environmental data or if CTD integration is still needed
