# Prior Knowledge Integration Strategy: INDRA + MeSH → SCM

**Version**: 1.0
**Last Updated**: October 2025
**Status**: Ready for Implementation

---

## Overview

This document specifies the **comprehensive strategy for integrating prior knowledge from external ontologies (INDRA bio-ontology and MeSH via Writer KG) into Structural Causal Models (SCMs)**. The system must translate qualitative biological relationships into quantitative causal parameters while preserving scientific rigor and traceability.

### Core Challenge

**Input**: Qualitative statements like "PM2.5 activates NF-κB (47 papers, belief=0.82)"

**Output**: Quantitative SCM parameters:
- Edge weight: `W_ij = 0.82` (effect size)
- Temporal lag: `τ_ij = 6 hours`
- Noise variance: `σ²_i = 0.15`

### Design Principles

1. **Evidence-Based**: Every parameter grounded in literature evidence counts and confidence scores
2. **Transparent**: Clear mapping from ontology statement → SCM parameter with full provenance
3. **Robust**: Handle missing data, conflicting evidence, and incomplete pathways gracefully
4. **Validated**: Ensure resulting SCM satisfies mathematical constraints (DAG, stability, identifiability)
5. **Efficient**: <5 seconds for complete graph construction with n=20 nodes

---

## Architecture

```
User Query
    ↓
┌─────────────────────────────────────────────┐
│  PHASE 1: Entity Extraction & Grounding     │
├─────────────────────────────────────────────┤
│  Input: "How does PM2.5 affect CRP?"        │
│  Output: [PM2.5:MESH:D052638, CRP:HGNC:2367]│
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  PHASE 2: MeSH Enrichment (Optional)        │
├─────────────────────────────────────────────┤
│  Input: [PM2.5, CRP]                        │
│  Output: + [NF-κB, IL-6, oxidative stress]  │
│  (Discover related concepts from ontology)  │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  PHASE 3: INDRA Path Discovery              │
├─────────────────────────────────────────────┤
│  Query: paths(PM2.5 → CRP)                  │
│  Returns: [                                 │
│    Path(PM2.5 → NF-κB → IL-6 → CRP),        │
│    Path(PM2.5 → ROS → IL-6 → CRP)           │
│  ]                                          │
│  Each edge: belief, evidence_count, PMIDs   │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  PHASE 4: SCM Parameter Mapping             │
├─────────────────────────────────────────────┤
│  belief=0.82, evidence=47 → W_ij=0.82       │
│  relationship=Activation → τ_ij=6h          │
│  evidence_variance → σ²_i=0.15             │
└─────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────┐
│  PHASE 5: Graph Construction & Validation   │
├─────────────────────────────────────────────┤
│  • Build adjacency matrix W                 │
│  • Check DAG constraint (acyclic)           │
│  • Check stability (spectral radius < 1)    │
│  • Validate parameter ranges                │
└─────────────────────────────────────────────┘
    ↓
Validated SCM Ready for Inference
```

---

## Phase 1: Entity Extraction & Grounding

### 1.1 Entity Types

The system recognizes four entity types:

| Type | Description | Examples | Databases |
|------|-------------|----------|-----------|
| **Environmental** | External exposures | PM2.5, ozone, temperature | MESH (chemicals, pollutants) |
| **Molecular** | Genes, proteins, pathways | NF-κB, TNF-α, p53 | HGNC (genes), GO (processes) |
| **Biomarker** | Clinical measurements | CRP, IL-6, glucose | HGNC (proteins), MESH (clinical) |
| **Genetic** | Genetic variants | GSTM1_null, APOE_ε4 | HGNC (genes) |

### 1.2 Grounding Service

**Purpose**: Map entity names from natural language → database identifiers

**Strategy**:
1. **Pre-cached Mappings** (fast path for common entities)
2. **INDRA Grounding API** (fallback for unknown entities)
3. **Writer KG MeSH Lookup** (for environmental/chemical terms)
4. **Database Priority**: HGNC > MESH > GO > CHEBI

**Implementation**:

```python
from typing import Optional, Dict, List
from dataclasses import dataclass
import httpx

@dataclass
class GroundedEntity:
    """Entity with database grounding."""
    name: str
    database: str  # HGNC, MESH, GO, CHEBI
    identifier: str
    confidence: float  # 0-1
    entity_type: str  # environmental, molecular, biomarker, genetic

class GroundingService:
    """Ground entity names to database identifiers."""

    # Pre-cached common entities (fast path)
    ENTITY_CACHE = {
        # Biomarkers
        "CRP": {"db": "HGNC", "id": "2367", "type": "biomarker", "confidence": 1.0},
        "IL-6": {"db": "HGNC", "id": "6018", "type": "biomarker", "confidence": 1.0},
        "IL6": {"db": "HGNC", "id": "6018", "type": "biomarker", "confidence": 1.0},
        "TNF-alpha": {"db": "HGNC", "id": "11892", "type": "biomarker", "confidence": 1.0},
        "8-OHdG": {"db": "MESH", "id": "D015794", "type": "biomarker", "confidence": 1.0},

        # Environmental
        "PM2.5": {"db": "MESH", "id": "D052638", "type": "environmental", "confidence": 1.0},
        "particulate matter": {"db": "MESH", "id": "D052638", "type": "environmental", "confidence": 1.0},
        "ozone": {"db": "MESH", "id": "D010126", "type": "environmental", "confidence": 1.0},
        "NO2": {"db": "MESH", "id": "D009585", "type": "environmental", "confidence": 1.0},

        # Molecular
        "NF-kappaB": {"db": "HGNC", "id": "7794", "type": "molecular", "confidence": 1.0},
        "NF-κB": {"db": "HGNC", "id": "7794", "type": "molecular", "confidence": 1.0},
        "NFKB1": {"db": "HGNC", "id": "7794", "type": "molecular", "confidence": 1.0},
        "p53": {"db": "HGNC", "id": "11998", "type": "molecular", "confidence": 1.0},
        "TP53": {"db": "HGNC", "id": "11998", "type": "molecular", "confidence": 1.0},

        # Processes
        "oxidative stress": {"db": "GO", "id": "0006979", "type": "molecular", "confidence": 0.9},
        "inflammation": {"db": "GO", "id": "0006954", "type": "molecular", "confidence": 0.9},
        "apoptosis": {"db": "GO", "id": "0006915", "type": "molecular", "confidence": 0.9},
    }

    def __init__(self, indra_base_url: str = "https://grounding.indra.bio"):
        self.indra_base_url = indra_base_url
        self.client = httpx.AsyncClient(timeout=10.0)

    async def ground(self, entity_name: str) -> Optional[GroundedEntity]:
        """Ground entity to database identifier."""
        # Normalize name
        normalized = entity_name.strip().lower()

        # Fast path: check cache
        if normalized in self.ENTITY_CACHE:
            cached = self.ENTITY_CACHE[normalized]
            return GroundedEntity(
                name=entity_name,
                database=cached["db"],
                identifier=cached["id"],
                confidence=cached["confidence"],
                entity_type=cached["type"]
            )

        # Slow path: query INDRA grounding API
        try:
            response = await self.client.get(
                f"{self.indra_base_url}/ground",
                params={"text": entity_name}
            )
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            # Take highest scoring grounding
            best = max(data, key=lambda x: x.get("score", 0))

            entity_type = self._infer_type(best["db"], best["id"])

            return GroundedEntity(
                name=entity_name,
                database=best["db"],
                identifier=best["id"],
                confidence=best.get("score", 0.5),
                entity_type=entity_type
            )

        except Exception as e:
            print(f"Grounding failed for {entity_name}: {e}")
            return None

    def _infer_type(self, database: str, identifier: str) -> str:
        """Infer entity type from database."""
        if database == "MESH":
            # MESH contains both chemicals (environmental) and clinical terms
            # Heuristic: D052638 (PM2.5) is environmental, D015794 (8-OHdG) is biomarker
            if identifier.startswith("D052") or identifier.startswith("D010"):
                return "environmental"
            else:
                return "biomarker"
        elif database == "HGNC":
            return "molecular"  # genes/proteins
        elif database == "GO":
            return "molecular"  # biological processes
        elif database == "CHEBI":
            return "environmental"  # chemicals
        else:
            return "molecular"  # default

    async def ground_batch(self, entity_names: List[str]) -> List[Optional[GroundedEntity]]:
        """Ground multiple entities in parallel."""
        import asyncio
        tasks = [self.ground(name) for name in entity_names]
        return await asyncio.gather(*tasks)
```

### 1.3 Entity Extraction from Query

**LLM-based extraction** via Supervisor agent:

```python
# From agent_config.py
ENTITY_EXTRACTION_PROMPT = """
Extract biological entities from the user query. Return a JSON list with:
- entity_name: natural language name
- entity_role: "exposure" | "outcome" | "mediator" | "modifier"

Query: {query}

Respond ONLY with JSON array. Example:
[
  {"entity_name": "PM2.5", "entity_role": "exposure"},
  {"entity_name": "CRP", "entity_role": "outcome"},
  {"entity_name": "NF-κB", "entity_role": "mediator"}
]
"""
```

**Expected Output** for "How does PM2.5 affect CRP?":
```json
[
  {"entity_name": "PM2.5", "entity_role": "exposure"},
  {"entity_name": "CRP", "entity_role": "outcome"}
]
```

---

## Phase 2: MeSH Enrichment (Optional)

### 2.1 Purpose

**Problem**: User queries often omit intermediate biological entities:
- Query: "How does pollution affect inflammation?"
- Missing: NF-κB, IL-6, TNF-α (critical mediators)

**Solution**: Use MeSH ontology to discover related concepts automatically.

### 2.2 Writer KG MeSH Integration

**Writer KG** provides structured MeSH ontology as knowledge graph:
- 30,000+ MeSH terms
- Hierarchical relationships (broader/narrower)
- Cross-references to biological concepts

**Query Strategy**:
```graphql
query GetRelatedConcepts {
  search(query: "PM2.5") {
    results {
      node {
        name
        ... on MeSHDescriptor {
          treeNumbers
          relatedConcepts(first: 10) {
            edges {
              node {
                name
                semanticType
              }
            }
          }
        }
      }
    }
  }
}
```

**Example Output**:
```json
{
  "PM2.5": {
    "related": [
      "Air Pollutants",
      "Oxidative Stress",
      "Inflammation Mediators",
      "Reactive Oxygen Species"
    ]
  }
}
```

### 2.3 Enrichment Strategy

**Conservative Enrichment** (MVP):
1. For each extracted entity, query Writer KG for related concepts
2. Filter to entities with strong semantic links (1-2 hops)
3. Prioritize entities that appear in INDRA paths (validate with path search)
4. Limit enrichment to 3-5 additional entities (avoid graph explosion)

**Implementation**:

```python
class MeSHEnrichmentService:
    """Discover related concepts from MeSH ontology via Writer KG."""

    def __init__(self, writer_api_key: str, writer_graph_id: str):
        self.api_key = writer_api_key
        self.graph_id = writer_graph_id
        self.client = httpx.AsyncClient(
            base_url="https://api.writer.com/v1/graphs",
            headers={"Authorization": f"Bearer {writer_api_key}"},
            timeout=15.0
        )

    async def enrich(
        self,
        seed_entities: List[GroundedEntity],
        max_additional: int = 5
    ) -> List[GroundedEntity]:
        """Discover related entities from MeSH ontology."""
        enriched = []

        for entity in seed_entities:
            # Query Writer KG for related concepts
            query = f"""
            {{
              search(query: "{entity.name}") {{
                results {{
                  node {{
                    name
                    ... on Entity {{
                      relatedNodes(first: 10) {{
                        edges {{
                          node {{
                            name
                            properties
                          }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            """

            try:
                response = await self.client.post(
                    f"/{self.graph_id}/query",
                    json={"query": query}
                )
                response.raise_for_status()
                data = response.json()

                # Extract related entities
                results = data.get("data", {}).get("search", {}).get("results", [])
                for result in results[:max_additional]:
                    node = result.get("node", {})
                    related_nodes = node.get("relatedNodes", {}).get("edges", [])

                    for edge in related_nodes:
                        related = edge.get("node", {})
                        related_name = related.get("name")

                        if related_name and related_name not in [e.name for e in seed_entities]:
                            # Attempt to ground the related entity
                            grounded = await grounding_service.ground(related_name)
                            if grounded:
                                enriched.append(grounded)

            except Exception as e:
                print(f"MeSH enrichment failed for {entity.name}: {e}")
                continue

        return enriched[:max_additional]
```

---

## Phase 3: INDRA Path Discovery

### 3.1 INDRA Bio-Ontology Overview

**INDRA** (Integrated Network and Dynamical Reasoning Assembler):
- 3.8M+ mechanistic statements from literature
- Covers: genes, proteins, chemicals, biological processes
- Statement types: Activation, Inhibition, Phosphorylation, IncreaseAmount, Complex
- Each statement: belief score (0-1), evidence count, PMIDs

**API Endpoints**:
- `POST /assembly/paths` - Find paths between entities
- `POST /assembly/statements` - Get statements for entity
- `POST /grounding` - Ground entity names

### 3.2 Path Search Strategy

**Multi-Strategy Approach**:

1. **Direct Path Search** (primary):
   - Query: `paths(source → target, max_depth=3)`
   - Returns: Shortest paths with intermediate nodes
   - Fast (< 2s), high precision

2. **Neighborhood Expansion** (fallback):
   - Query: `statements(entity=source, depth=2)`
   - Manually traverse graph to find target
   - Slower (< 5s), higher recall

3. **Reverse Path Search** (bidirectional):
   - Query: `paths(target ← source)` (reverse edges)
   - Useful for inhibitory relationships
   - Combine with forward paths

**Implementation**:

```python
from typing import List, Dict, Optional
from dataclasses import dataclass
import httpx

@dataclass
class INDRAStatement:
    """Single causal statement from INDRA."""
    source: GroundedEntity
    target: GroundedEntity
    relationship: str  # Activation, Inhibition, IncreaseAmount, etc.
    belief: float  # 0-1
    evidence_count: int
    pmids: List[str]

@dataclass
class INDRAPath:
    """Path from source to target."""
    nodes: List[GroundedEntity]
    edges: List[INDRAStatement]
    total_belief: float  # Product of edge beliefs
    total_evidence: int  # Sum of evidence counts

class INDRAService:
    """Query INDRA bio-ontology for causal pathways."""

    def __init__(self, base_url: str = "https://db.indra.bio"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def find_paths(
        self,
        source: GroundedEntity,
        target: GroundedEntity,
        max_depth: int = 3,
        max_paths: int = 5
    ) -> List[INDRAPath]:
        """Find causal paths from source to target."""
        # Strategy 1: Direct path search
        try:
            paths = await self._direct_path_search(source, target, max_depth)
            if paths:
                return paths[:max_paths]
        except Exception as e:
            print(f"Direct path search failed: {e}")

        # Strategy 2: Neighborhood expansion (fallback)
        try:
            paths = await self._neighborhood_expansion(source, target, max_depth)
            if paths:
                return paths[:max_paths]
        except Exception as e:
            print(f"Neighborhood expansion failed: {e}")

        return []

    async def _direct_path_search(
        self,
        source: GroundedEntity,
        target: GroundedEntity,
        max_depth: int
    ) -> List[INDRAPath]:
        """Direct API call to find paths."""
        payload = {
            "source": f"{source.database}:{source.identifier}",
            "target": f"{target.database}:{target.identifier}",
            "max_depth": max_depth,
            "stmt_filter": ["Activation", "Inhibition", "IncreaseAmount", "DecreaseAmount"],
            "weighted": True,  # Use belief scores for weighting
            "k_shortest": 5    # Return top 5 paths
        }

        response = await self.client.post(
            f"{self.base_url}/assembly/paths",
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        paths = []
        for path_data in data.get("paths", []):
            path = self._parse_path(path_data)
            if path:
                paths.append(path)

        return paths

    def _parse_path(self, path_data: Dict) -> Optional[INDRAPath]:
        """Parse INDRA path response into INDRAPath object."""
        nodes_raw = path_data.get("nodes", [])
        edges_raw = path_data.get("edges", [])

        if not nodes_raw or not edges_raw:
            return None

        # Parse nodes
        nodes = []
        for node_raw in nodes_raw:
            entity = GroundedEntity(
                name=node_raw.get("name", "Unknown"),
                database=node_raw.get("db", "HGNC"),
                identifier=node_raw.get("id", ""),
                confidence=1.0,
                entity_type="molecular"  # Default
            )
            nodes.append(entity)

        # Parse edges
        edges = []
        total_belief = 1.0
        total_evidence = 0

        for edge_raw in edges_raw:
            stmt_type = edge_raw.get("stmt_type", "Activation")
            belief = edge_raw.get("belief", 0.5)
            evidence = edge_raw.get("evidence_count", 1)
            pmids = edge_raw.get("pmids", [])

            # Map INDRA statement type to relationship
            relationship = self._map_statement_type(stmt_type)

            statement = INDRAStatement(
                source=nodes[edge_raw["source_idx"]],
                target=nodes[edge_raw["target_idx"]],
                relationship=relationship,
                belief=belief,
                evidence_count=evidence,
                pmids=pmids[:5]  # Limit to 5 PMIDs
            )

            edges.append(statement)
            total_belief *= belief
            total_evidence += evidence

        return INDRAPath(
            nodes=nodes,
            edges=edges,
            total_belief=total_belief,
            total_evidence=total_evidence
        )

    def _map_statement_type(self, stmt_type: str) -> str:
        """Map INDRA statement type to API relationship type."""
        mapping = {
            "Activation": "activates",
            "Inhibition": "inhibits",
            "IncreaseAmount": "increases",
            "DecreaseAmount": "decreases",
            "Phosphorylation": "activates",  # Simplification
            "Dephosphorylation": "inhibits",
            "Complex": "binds"
        }
        return mapping.get(stmt_type, "increases")

    async def _neighborhood_expansion(
        self,
        source: GroundedEntity,
        target: GroundedEntity,
        max_depth: int
    ) -> List[INDRAPath]:
        """Fallback: manually traverse graph from source."""
        # Step 1: Get all statements for source
        source_stmts = await self._get_statements(source, depth=1)

        # Step 2: Expand to depth 2
        intermediate_nodes = [stmt.target for stmt in source_stmts]
        paths = []

        for intermediate in intermediate_nodes:
            # Check if intermediate connects to target
            target_stmts = await self._get_statements(intermediate, depth=1)

            for stmt in target_stmts:
                if stmt.target.identifier == target.identifier:
                    # Found path: source → intermediate → target
                    path = INDRAPath(
                        nodes=[source, intermediate, target],
                        edges=[
                            source_stmts[0],  # source → intermediate
                            stmt               # intermediate → target
                        ],
                        total_belief=source_stmts[0].belief * stmt.belief,
                        total_evidence=source_stmts[0].evidence_count + stmt.evidence_count
                    )
                    paths.append(path)

        return paths

    async def _get_statements(
        self,
        entity: GroundedEntity,
        depth: int = 1
    ) -> List[INDRAStatement]:
        """Get all statements involving entity."""
        payload = {
            "subject": f"{entity.database}:{entity.identifier}",
            "stmt_type": ["Activation", "Inhibition", "IncreaseAmount", "DecreaseAmount"],
            "evidence_limit": 100
        }

        response = await self.client.post(
            f"{self.base_url}/statements/from_agents",
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        statements = []
        for stmt_raw in data.get("statements", []):
            # Parse statement (similar to _parse_path)
            statement = self._parse_statement(stmt_raw, entity)
            if statement:
                statements.append(statement)

        return statements

    def _parse_statement(self, stmt_raw: Dict, source: GroundedEntity) -> Optional[INDRAStatement]:
        """Parse individual INDRA statement."""
        # Extract target entity
        obj = stmt_raw.get("obj", {})
        target = GroundedEntity(
            name=obj.get("name", "Unknown"),
            database=obj.get("db", "HGNC"),
            identifier=obj.get("id", ""),
            confidence=1.0,
            entity_type="molecular"
        )

        relationship = self._map_statement_type(stmt_raw.get("type", "Activation"))
        belief = stmt_raw.get("belief", 0.5)
        evidence_count = len(stmt_raw.get("evidence", []))
        pmids = [ev.get("pmid") for ev in stmt_raw.get("evidence", []) if ev.get("pmid")]

        return INDRAStatement(
            source=source,
            target=target,
            relationship=relationship,
            belief=belief,
            evidence_count=evidence_count,
            pmids=pmids[:5]
        )
```

### 3.3 Path Ranking

**Ranking Formula**:
```
score = 0.4 * evidence_weight + 0.3 * belief_weight + 0.3 * path_length_penalty

evidence_weight = log(1 + total_evidence) / log(1 + 500)  # Normalize to [0,1]
belief_weight = total_belief  # Already [0,1]
path_length_penalty = 1 / len(path.nodes)  # Prefer shorter paths
```

**Implementation**:

```python
def rank_paths(paths: List[INDRAPath]) -> List[INDRAPath]:
    """Rank paths by evidence, belief, and length."""
    import math

    scored_paths = []
    for path in paths:
        evidence_weight = math.log(1 + path.total_evidence) / math.log(1 + 500)
        belief_weight = path.total_belief
        length_penalty = 1 / len(path.nodes)

        score = 0.4 * evidence_weight + 0.3 * belief_weight + 0.3 * length_penalty

        scored_paths.append((score, path))

    # Sort by score descending
    scored_paths.sort(key=lambda x: x[0], reverse=True)

    return [path for score, path in scored_paths]
```

---

## Phase 4: SCM Parameter Mapping

### 4.1 Effect Size Calculation

**Formula** (from mathematical-foundation.md):
```
W_ij = min(α · belief + β · log(1 + evidence_count), W_max)

where:
  α = 0.6          (weight on belief score)
  β = 0.1          (weight on evidence accumulation)
  W_max = 0.95     (stability cap)
```

**Rationale**:
- **Belief score**: INDRA's machine learning estimate of statement correctness
- **Evidence count**: More papers → higher confidence
- **Logarithmic scaling**: Diminishing returns after ~100 papers
- **Cap at 0.95**: Ensures (I - W) remains invertible (spectral radius < 1)

**Implementation**:

```python
import math

class ParameterMapper:
    """Map INDRA statements to SCM parameters."""

    ALPHA = 0.6      # Weight on belief
    BETA = 0.1       # Weight on evidence
    W_MAX = 0.95     # Stability cap

    def calculate_effect_size(
        self,
        belief: float,
        evidence_count: int,
        relationship: str
    ) -> float:
        """Calculate effect size from INDRA statement."""
        if not 0 <= belief <= 1:
            raise ValueError(f"Belief must be ∈ [0,1], got {belief}")

        base_effect = self.ALPHA * belief
        evidence_bonus = self.BETA * math.log(1 + evidence_count)
        effect_size = min(base_effect + evidence_bonus, self.W_MAX)

        # Handle inhibitory relationships (negative weight)
        if relationship in ["inhibits", "decreases"]:
            effect_size = -effect_size

        return effect_size
```

**Example Calculations**:

| Belief | Evidence | Formula | Effect Size |
|--------|----------|---------|-------------|
| 0.82 | 47 | min(0.6×0.82 + 0.1×log(48), 0.95) | **0.88** |
| 0.91 | 312 | min(0.6×0.91 + 0.1×log(313), 0.95) | **0.95** (capped) |
| 0.65 | 12 | min(0.6×0.65 + 0.1×log(13), 0.95) | **0.64** |

### 4.2 Temporal Lag Estimation

**Strategy**: Map INDRA statement type → biological timescale

**TEMPORAL_LAG_MAP**:

| Statement Type | Biological Mechanism | Lag (hours) |
|----------------|----------------------|-------------|
| Phosphorylation | Fast signaling cascade | 1 |
| Dephosphorylation | Signal termination | 1 |
| Complex | Protein-protein binding | 2 |
| Activation (TF) | Transcription factor binding | 6 |
| IncreaseAmount | Gene expression + translation | 12 |
| DecreaseAmount | Protein degradation | 8 |
| Inhibition | Depends on mechanism | 6 (default) |

**Implementation**:

```python
class ParameterMapper:
    TEMPORAL_LAG_MAP = {
        "Phosphorylation": 1,
        "Dephosphorylation": 1,
        "Complex": 2,
        "Activation": 6,
        "IncreaseAmount": 12,
        "DecreaseAmount": 8,
        "Inhibition": 6
    }

    def estimate_temporal_lag(self, statement_type: str) -> int:
        """Estimate temporal lag in hours from statement type."""
        return self.TEMPORAL_LAG_MAP.get(statement_type, 6)  # Default 6h
```

**Refinement (Post-Hackathon)**:
- Use experimental data (e.g., Gene Expression Omnibus timeseries)
- Train regression model: `lag = f(statement_type, cell_type, tissue)`
- Incorporate regulatory delays (e.g., mRNA half-life)

### 4.3 Noise Variance Estimation

**Purpose**: Quantify uncertainty in causal effect (σ²_i in SCM)

**Strategy**: Inverse relationship with evidence quality
```
σ²_i = σ²_base × (1 - belief) × (1 + 1/√evidence_count)

where:
  σ²_base = 0.1  (baseline measurement noise)
```

**Rationale**:
- Low belief → high variance
- Few papers → high variance
- √ scaling: Diminishing reduction with more evidence

**Implementation**:

```python
class ParameterMapper:
    SIGMA_BASE = 0.1  # Baseline noise variance

    def estimate_noise_variance(self, belief: float, evidence_count: int) -> float:
        """Estimate noise variance from evidence quality."""
        import math

        uncertainty_factor = (1 - belief) * (1 + 1 / math.sqrt(evidence_count))
        sigma_squared = self.SIGMA_BASE * uncertainty_factor

        return max(sigma_squared, 0.01)  # Floor at 0.01
```

**Example Calculations**:

| Belief | Evidence | Formula | σ² |
|--------|----------|---------|-----|
| 0.90 | 100 | 0.1 × (1-0.90) × (1+1/10) | **0.011** |
| 0.70 | 10 | 0.1 × (1-0.70) × (1+1/√10) | **0.039** |
| 0.50 | 3 | 0.1 × (1-0.50) × (1+1/√3) | **0.079** |

---

## Phase 5: Graph Construction & Validation

### 5.1 Graph Builder Service

**Purpose**: Assemble validated causal graph from INDRA paths

**Algorithm**:
1. Merge paths (union of all discovered edges)
2. Deduplicate nodes (by database:identifier)
3. Resolve conflicting edges (choose highest evidence)
4. Build adjacency matrix W
5. Validate constraints (DAG, stability, parameter ranges)

**Implementation**:

```python
import networkx as nx
import numpy as np
from typing import List, Dict

class GraphBuilderService:
    """Assemble causal graph from INDRA paths."""

    def __init__(self, parameter_mapper: ParameterMapper):
        self.param_mapper = parameter_mapper

    def build_graph(self, paths: List[INDRAPath]) -> CausalGraph:
        """Build causal graph from paths."""
        # Step 1: Collect all unique nodes
        nodes_dict = {}
        for path in paths:
            for node in path.nodes:
                key = f"{node.database}:{node.identifier}"
                if key not in nodes_dict:
                    nodes_dict[key] = node

        # Step 2: Collect all edges (merge duplicates)
        edges_dict = {}
        for path in paths:
            for edge in path.edges:
                source_key = f"{edge.source.database}:{edge.source.identifier}"
                target_key = f"{edge.target.database}:{edge.target.identifier}"
                edge_key = (source_key, target_key)

                # If duplicate, keep edge with higher evidence
                if edge_key in edges_dict:
                    existing = edges_dict[edge_key]
                    if edge.evidence_count > existing.evidence_count:
                        edges_dict[edge_key] = edge
                else:
                    edges_dict[edge_key] = edge

        # Step 3: Build CausalGraph object
        nodes = []
        for key, entity in nodes_dict.items():
            node = CausalNode(
                id=entity.name,
                type=entity.entity_type,
                label=entity.name,
                grounding={
                    "database": entity.database,
                    "identifier": entity.identifier
                }
            )
            nodes.append(node)

        edges = []
        for (source_key, target_key), statement in edges_dict.items():
            # Calculate SCM parameters
            effect_size = self.param_mapper.calculate_effect_size(
                statement.belief,
                statement.evidence_count,
                statement.relationship
            )

            temporal_lag = self.param_mapper.estimate_temporal_lag(
                statement.relationship
            )

            edge = CausalEdge(
                source=statement.source.name,
                target=statement.target.name,
                relationship=statement.relationship,
                effect_size=effect_size,
                temporal_lag_hours=temporal_lag,
                evidence={
                    "count": statement.evidence_count,
                    "confidence": statement.belief,
                    "sources": statement.pmids,
                    "summary": f"{statement.source.name} {statement.relationship} {statement.target.name}"
                }
            )
            edges.append(edge)

        # Step 4: Validate graph
        graph = CausalGraph(nodes=nodes, edges=edges)
        self._validate_graph(graph)

        return graph

    def _validate_graph(self, graph: CausalGraph) -> None:
        """Validate graph satisfies all constraints."""
        # Constraint 1: DAG (acyclic)
        G = nx.DiGraph()
        for edge in graph.edges:
            G.add_edge(edge.source, edge.target)

        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("Graph contains cycles (not a DAG)")

        # Constraint 2: Effect sizes ∈ [-1, 1]
        for edge in graph.edges:
            if not -1 <= edge.effect_size <= 1:
                raise ValueError(f"Effect size {edge.effect_size} out of range [-1,1]")

        # Constraint 3: Temporal lags ≥ 0
        for edge in graph.edges:
            if edge.temporal_lag_hours < 0:
                raise ValueError(f"Temporal lag {edge.temporal_lag_hours} must be ≥ 0")

        # Constraint 4: Stability (spectral radius < 1)
        W = self._build_weight_matrix(graph)
        eigenvalues = np.linalg.eigvals(W)
        spectral_radius = np.max(np.abs(eigenvalues))

        if spectral_radius >= 1.0:
            raise ValueError(f"Unstable graph (spectral radius {spectral_radius:.3f} ≥ 1)")

    def _build_weight_matrix(self, graph: CausalGraph) -> np.ndarray:
        """Build weight matrix W for stability check."""
        n = len(graph.nodes)
        node_to_idx = {node.id: i for i, node in enumerate(graph.nodes)}

        W = np.zeros((n, n))
        for edge in graph.edges:
            i = node_to_idx[edge.target]
            j = node_to_idx[edge.source]
            W[i, j] = edge.effect_size

        return W
```

### 5.2 Conflict Resolution

**Problem**: Multiple paths may contain conflicting information about the same edge.

**Example**:
- Path 1: PM2.5 → NF-κB (belief=0.82, evidence=47)
- Path 2: PM2.5 → NF-κB (belief=0.75, evidence=31)

**Resolution Strategy**:
1. **Prefer higher evidence count** (more papers = higher confidence)
2. If evidence tied, prefer higher belief score
3. If both tied, take average

**Implementation**:

```python
def resolve_conflict(statements: List[INDRAStatement]) -> INDRAStatement:
    """Resolve conflicting statements for same edge."""
    if len(statements) == 1:
        return statements[0]

    # Sort by evidence count (descending), then belief (descending)
    sorted_stmts = sorted(
        statements,
        key=lambda s: (s.evidence_count, s.belief),
        reverse=True
    )

    # Return highest-ranked statement
    return sorted_stmts[0]
```

### 5.3 Genetic Modifiers

**Purpose**: Apply user-specific genetic variants as edge modifiers

**Mechanism**:
- Genetic variant → amplifies/attenuates specific causal edges
- Example: `GSTM1_null` increases susceptibility to oxidative stress

**Implementation**:

```python
class GraphBuilderService:
    GENETIC_MODIFIERS = {
        "GSTM1_null": {
            "affected_edges": [("PM2.5", "oxidative_stress"), ("oxidative_stress", "IL6")],
            "effect_type": "amplifies",
            "magnitude": 1.3  # 30% amplification
        },
        "GSTP1_Val_Val": {
            "affected_edges": [("PM2.5", "oxidative_stress")],
            "effect_type": "amplifies",
            "magnitude": 1.2
        },
        "APOE_e4": {
            "affected_edges": [("inflammation", "neurodegeneration")],
            "effect_type": "amplifies",
            "magnitude": 1.5
        }
    }

    def apply_genetic_modifiers(
        self,
        graph: CausalGraph,
        genetics: Dict[str, str]
    ) -> CausalGraph:
        """Apply user-specific genetic modifiers to graph."""
        modified_graph = graph.copy()

        for variant_name, genotype in genetics.items():
            # Check if variant has modifier
            if variant_name not in self.GENETIC_MODIFIERS:
                continue

            modifier = self.GENETIC_MODIFIERS[variant_name]

            # Apply to affected edges
            for source, target in modifier["affected_edges"]:
                for edge in modified_graph.edges:
                    if edge.source == source and edge.target == target:
                        # Modify effect size
                        if modifier["effect_type"] == "amplifies":
                            edge.effect_size *= modifier["magnitude"]
                        elif modifier["effect_type"] == "attenuates":
                            edge.effect_size /= modifier["magnitude"]

                        # Cap at W_MAX
                        edge.effect_size = min(edge.effect_size, 0.95)

        return modified_graph
```

---

## Caching & Offline Mode

### 6.1 Pre-cached INDRA Paths

**Purpose**: Ensure hackathon demo reliability (avoid INDRA API downtime)

**Strategy**: Pre-cache common causal pathways in `config/cached_responses.py`

**Implementation**:

```python
# config/cached_responses.py

CACHED_INDRA_PATHS = {
    ("PM2.5", "IL6"): {
        "paths": [
            {
                "nodes": ["PM2.5", "NFKB1", "IL6"],
                "edges": [
                    {
                        "source": "PM2.5",
                        "target": "NFKB1",
                        "relationship": "activates",
                        "belief": 0.82,
                        "evidence_count": 47,
                        "pmids": ["PMID:12345678", "PMID:23456789"]
                    },
                    {
                        "source": "NFKB1",
                        "target": "IL6",
                        "relationship": "increases",
                        "belief": 0.87,
                        "evidence_count": 89,
                        "pmids": ["PMID:34567891"]
                    }
                ]
            }
        ]
    },
    ("IL6", "CRP"): {
        "paths": [
            {
                "nodes": ["IL6", "CRP"],
                "edges": [
                    {
                        "source": "IL6",
                        "target": "CRP",
                        "relationship": "increases",
                        "belief": 0.98,
                        "evidence_count": 312,
                        "pmids": ["PMID:45678901"]
                    }
                ]
            }
        ]
    }
}

def get_cached_path(source: str, target: str) -> Optional[Dict]:
    """Retrieve pre-cached INDRA path."""
    return CACHED_INDRA_PATHS.get((source, target))
```

**Fallback Logic**:
```python
async def find_paths_with_cache(source, target):
    # Try live API first
    try:
        paths = await indra_service.find_paths(source, target)
        if paths:
            return paths
    except:
        pass

    # Fallback to cache
    cached = get_cached_path(source.name, target.name)
    if cached:
        return parse_cached_path(cached)

    # No path found
    return []
```

### 6.2 Cost Monitoring

**Problem**: AWS Bedrock LLM calls can be expensive

**Solution**: Track token usage and cost per request

**Implementation**:

```python
class CostMonitor:
    """Track AWS Bedrock costs."""

    # Pricing as of Jan 2025 (us-east-1)
    COST_PER_INPUT_TOKEN = 0.000003   # $3 per 1M tokens
    COST_PER_OUTPUT_TOKEN = 0.000015  # $15 per 1M tokens

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def record_usage(self, input_tokens: int, output_tokens: int):
        """Record token usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_total_cost(self) -> float:
        """Calculate total cost in USD."""
        input_cost = self.total_input_tokens * self.COST_PER_INPUT_TOKEN
        output_cost = self.total_output_tokens * self.COST_PER_OUTPUT_TOKEN
        return input_cost + output_cost

    def log_summary(self):
        """Log cost summary."""
        total_cost = self.get_total_cost()
        print(f"Total tokens: {self.total_input_tokens + self.total_output_tokens:,}")
        print(f"Total cost: ${total_cost:.4f}")
```

---

## Error Handling

### 7.1 Error Types

| Error | Cause | Recovery Strategy |
|-------|-------|-------------------|
| **GROUNDING_FAILED** | Entity not in any database | Use fuzzy matching, ask user for clarification |
| **NO_INDRA_PATH** | No causal connection found | Expand search depth, try reverse path |
| **MESH_TIMEOUT** | Writer KG API timeout | Skip enrichment, proceed with seed entities |
| **INVALID_GRAPH** | Validation failed (cycle, unstable) | Remove problematic edges, re-validate |
| **API_RATE_LIMIT** | INDRA/AWS rate limit hit | Exponential backoff, fallback to cache |

### 7.2 Graceful Degradation

**Strategy**: Provide partial results when possible

**Example**:
```json
{
  "status": "partial_success",
  "warnings": [
    "Could not ground entity 'PM10' (using PM2.5 instead)",
    "MESH enrichment timed out (skipped)"
  ],
  "causal_graph": { ... }
}
```

---

## Performance Targets

### 8.1 Latency Breakdown (n=20 nodes)

| Phase | Target (p95) | Notes |
|-------|-------------|-------|
| Entity Extraction | < 500ms | LLM call |
| Entity Grounding | < 200ms | Cached for common entities |
| MeSH Enrichment | < 1000ms | Optional, can skip |
| INDRA Path Discovery | < 3000ms | External API, cache common paths |
| Parameter Mapping | < 50ms | Pure computation |
| Graph Validation | < 100ms | Matrix operations |
| **TOTAL** | **< 5000ms** | **End-to-end** |

### 8.2 Optimization Strategies

1. **Parallel API Calls**: Query INDRA for multiple paths concurrently
2. **Aggressive Caching**: Cache grounding, paths, graphs with 1-hour TTL
3. **Lazy Enrichment**: Skip MeSH enrichment if >3 entities already found
4. **Early Termination**: Stop path search after finding 3 high-quality paths

---

## Testing Strategy

### 9.1 Unit Tests

```python
def test_effect_size_calculation():
    mapper = ParameterMapper()
    effect = mapper.calculate_effect_size(belief=0.82, evidence_count=47, relationship="activates")
    assert 0.8 < effect < 0.95

def test_temporal_lag_estimation():
    mapper = ParameterMapper()
    lag = mapper.estimate_temporal_lag("Phosphorylation")
    assert lag == 1

def test_dag_validation():
    # Create cyclic graph
    graph = create_cyclic_test_graph()
    builder = GraphBuilderService(ParameterMapper())

    with pytest.raises(ValueError, match="contains cycles"):
        builder._validate_graph(graph)
```

### 9.2 Integration Tests

```python
@pytest.mark.asyncio
async def test_full_pipeline():
    # Input: PM2.5 affects CRP
    query = "How does PM2.5 pollution affect CRP biomarkers?"

    # Phase 1: Extract entities
    entities = await supervisor.extract_entities(query)
    assert len(entities) >= 2

    # Phase 2: Ground entities
    grounded = await grounding_service.ground_batch(entities)
    assert all(e is not None for e in grounded)

    # Phase 3: Find paths
    paths = await indra_service.find_paths(grounded[0], grounded[1])
    assert len(paths) > 0

    # Phase 4: Build graph
    graph = builder.build_graph(paths)
    assert len(graph.nodes) >= 3
    assert len(graph.edges) >= 2

    # Phase 5: Validate
    builder._validate_graph(graph)  # Should not raise
```

---

## Post-Hackathon Enhancements

### 10.1 MeSH Enrichment Agent (Week 2)

**Goal**: Automatically discover relevant intermediate entities

**Approach**:
- Semantic similarity search in Writer KG
- Filter by biological relevance (scoring heuristic)
- Validate via INDRA path existence

### 10.2 Bayesian Parameter Estimation (Month 1)

**Goal**: Learn effect sizes from observational data

**Approach**:
- Fit Linear Gaussian SCM to user health timeseries
- Posterior distribution: p(W, Σ | data, graph_structure)
- Combine with INDRA priors (hybrid approach)

### 10.3 Multi-Timescale DBN (Month 2)

**Goal**: Handle feedback loops (inflammation ↔ oxidative stress)

**Approach**:
- Discrete-time Bayesian Network with multiple timescales
- Fast processes (hours): inflammation mediators
- Slow processes (days): tissue remodeling
- Separate graphs per timescale, combine via message passing

### 10.4 Active Learning for Edge Discovery (Month 3)

**Goal**: Identify missing edges from data

**Approach**:
- Residual analysis: identify unexplained correlations
- Query INDRA for candidate edges
- Bayesian model comparison (with vs without edge)

---

## References

**INDRA**:
- Gyori et al. (2017) - "From word models to executable models of signaling networks"
- INDRA API: https://network.indra.bio

**MeSH Ontology**:
- NLM Medical Subject Headings: https://www.nlm.nih.gov/mesh
- Writer KG: https://writer.com/product/knowledge-graph

**SCM Theory**:
- Pearl (2009) - *Causality: Models, Reasoning, and Inference*
- Peters et al. (2017) - *Elements of Causal Inference*

**Effect Size Estimation**:
- Hoyer et al. (2009) - "Nonlinear causal discovery with additive noise models"
- Zheng et al. (2018) - "DAGs with NO TEARS"

---

**End of Knowledge Integration Strategy**
