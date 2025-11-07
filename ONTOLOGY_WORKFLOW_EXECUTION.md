# Ontology Integration Workflow: Concrete Execution Flow

**Date**: 2025-11-01
**Purpose**: Map exactly how ontologies flow through the system from Writer KG → CTD → INDRA → Markov boundary

---

## The Complete Data Flow

```
User Query: "How does PM2.5 affect inflammation in someone with high glucose?"
     ↓
[1] Writer KG (Graph-RAG)
     ↓
[2] CTD Network Builder (Topology Discovery)
     ↓
[3] FPLX Aggregation (Family-Level Grouping)
     ↓
[4] Markov Boundary Selection (Parsimony)
     ↓
[5] INDRA Validation (Mechanistic Evidence)
     ↓
[6] Bayesian Inference (Causal Effects)
     ↓
Response: "PM2.5 + Glucose → MAPK/NFkappaB → IL6 → CRP (synergy score: 1.34)"
```

---

## Step-by-Step Execution

### Step 1: Writer KG Query (Graph-RAG Entity Extraction)

**Input**: User query text
**Output**: Grounded entities with MESH IDs

**Code Path**: `indra_agent/services/writer_kg_service.py`

```python
async def query(self, question: str) -> Dict:
    """Query Writer KG for entity grounding + pathway hints."""

    # Graph-RAG query
    response = await self.client.post(
        f"/graphs/{GRAPH_ID}/question",
        json={
            "question": question,
            "subqueries": True  # Enable multi-hop reasoning
        }
    )

    # Extract entities from answer
    entities = self._extract_entities(response["answer"])

    return {
        "entities": entities,  # e.g., [{"name": "PM2.5", "mesh_id": "D052638"}, ...]
        "pathway_hints": response.get("citations", []),  # Graph edges mentioned
        "answer": response["answer"]
    }

def _extract_entities(self, answer: str) -> List[Dict]:
    """Parse MESH IDs from graph-RAG answer.

    Example answer: "PM2.5 (MESH:D052638) affects genes including IL6..."
    """
    pattern = r'(\w+(?:\s+\w+)*)\s*\(MESH:([A-Z0-9]+)\)'
    matches = re.findall(pattern, answer)

    return [
        {"name": name, "mesh_id": mesh_id, "type": "environmental"}
        for name, mesh_id in matches
    ]
```

**Example Output**:
```python
{
  "entities": [
    {"name": "PM2.5", "mesh_id": "D052638", "type": "environmental"},
    {"name": "Glucose", "mesh_id": "D005947", "type": "environmental"},
    {"name": "inflammation", "mesh_id": "D007249", "type": "process"}
  ],
  "pathway_hints": ["PM2.5 → IL6", "Glucose → AKT1"],
  "answer": "PM2.5 (MESH:D052638) and Glucose (MESH:D005947) both affect inflammatory pathways..."
}
```

**Key Point**: Writer KG provides MESH IDs which map directly to CTD chemical IDs.

---

### Step 2: CTD Network Query (Topology Discovery)

**Input**: MESH IDs from Writer KG
**Output**: Convergent gene nodes

**Code Path**: `indra_agent/services/ctd_network_builder.py`

```python
# Initialize with CTD relationships CSV
ctd_builder = CTDNetworkBuilder(
    ctd_relationships_path="output/ctd_environmental_exposures_relationships.csv"
)

# Load network into memory (NetworkX graph)
ctd_builder.load_network(min_evidence=2)

# Find genes affected by multiple exposures
exposure_mesh_ids = ["D052638", "D005947"]  # From Writer KG

convergent_genes = ctd_builder.find_convergent_targets(
    exposure_nodes=exposure_mesh_ids,
    min_convergence=2  # Both exposures must affect this gene
)
```

**Example Output**:
```python
[
  {
    "gene_symbol": "MAPK1",
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 156  # 89 (PM2.5) + 67 (Glucose)
  },
  {
    "gene_symbol": "MAPK3",
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 134
  },
  {
    "gene_symbol": "IL6",
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 78
  },
  {
    "gene_symbol": "NFKB1",
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 67
  },
  # ... 1,937 total convergent genes
]
```

**Key Point**: We now have gene-level convergence, but 1,937 genes is too many for Markov boundary.

---

### Step 3: FPLX Aggregation (Family-Level Grouping)

**Input**: Convergent genes from CTD
**Output**: Protein families with member genes

**Code Path**: NEW - `indra_agent/services/fplx_aggregator.py` (needs to be created)

```python
class FPLXAggregator:
    """Aggregate genes to protein families using INDRA's FamPlex ontology."""

    # FPLX mappings (from INDRA's famplex repository)
    FAMILY_MEMBERS = {
        "MAPK": ["MAPK1", "MAPK3", "MAPK8", "MAPK9", "MAPK14", "MAPK11"],
        "NFkappaB": ["NFKB1", "NFKB2", "RELA", "REL", "RELB"],
        "AKT": ["AKT1", "AKT2", "AKT3"],
        "TNF": ["TNF"],  # Single-member family
        "IL6": ["IL6"],  # Single-member family
    }

    def aggregate_to_families(
        self,
        convergent_genes: List[Dict]
    ) -> List[Dict]:
        """Group genes into families, preserving evidence."""

        families = {}
        ungrouped = []

        for gene_data in convergent_genes:
            gene = gene_data["gene_symbol"]

            # Find which family this gene belongs to
            family_name = self._find_family(gene)

            if family_name:
                # Add to family
                if family_name not in families:
                    families[family_name] = {
                        "family": family_name,
                        "members": [],
                        "affected_by": set(gene_data["affected_by"]),
                        "total_evidence": 0
                    }

                families[family_name]["members"].append(gene)
                families[family_name]["affected_by"].update(gene_data["affected_by"])
                families[family_name]["total_evidence"] += gene_data["total_evidence"]
            else:
                # Keep as ungrouped gene
                ungrouped.append(gene_data)

        # Convert families to list
        family_list = [
            {
                "family": name,
                "members": data["members"],
                "affected_by": list(data["affected_by"]),
                "convergence_degree": len(data["affected_by"]),
                "total_evidence": data["total_evidence"],
                "is_family": True
            }
            for name, data in families.items()
        ]

        # Mark ungrouped genes
        for gene_data in ungrouped:
            gene_data["is_family"] = False

        return family_list + ungrouped

    def _find_family(self, gene: str) -> Optional[str]:
        """Find which family a gene belongs to."""
        for family, members in self.FAMILY_MEMBERS.items():
            if gene in members:
                return family
        return None
```

**Usage**:
```python
aggregator = FPLXAggregator()
families = aggregator.aggregate_to_families(convergent_genes)
```

**Example Output**:
```python
[
  {
    "family": "MAPK",
    "members": ["MAPK1", "MAPK3", "MAPK14"],
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 290,  # Sum of all MAPK members
    "is_family": True
  },
  {
    "family": "NFkappaB",
    "members": ["NFKB1"],  # Only NFKB1 was in convergent genes
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 67,
    "is_family": True
  },
  {
    "gene_symbol": "IL6",  # No family, keep as gene
    "affected_by": ["D052638", "D005947"],
    "convergence_degree": 2,
    "total_evidence": 78,
    "is_family": False
  },
  # ... ~100 families/genes total (vs 1,937 genes)
]
```

**Key Point**: Dimensional reduction from 1,937 → ~100 nodes.

---

### Step 4: Markov Boundary Selection (Parsimony Filter)

**Input**: Families + genes from FPLX aggregation
**Output**: Minimal Markov boundary (8-12 hubs)

**Code Path**: NEW - `indra_agent/services/markov_boundary_selector.py`

```python
class MarkovBoundarySelector:
    """Select minimal set of latent nodes that d-separate observations."""

    def select_boundary(
        self,
        candidates: List[Dict],  # Families/genes from FPLX
        observations: List[str],  # Biomarkers user cares about
        min_evidence: int = 50,
        top_n: int = 20
    ) -> List[Dict]:
        """Select Markov boundary using greedy d-separation algorithm.

        Strategy:
        1. Rank candidates by total_evidence (literature support)
        2. Keep only nodes that connect to observed biomarkers
        3. Remove redundant nodes (d-separation check)
        4. Return minimal set
        """

        # Filter by evidence threshold
        high_evidence = [
            c for c in candidates
            if c["total_evidence"] >= min_evidence
        ]

        # Sort by evidence (highest first)
        high_evidence.sort(key=lambda x: x["total_evidence"], reverse=True)

        # Take top N
        boundary_candidates = high_evidence[:top_n]

        # TODO: Add d-separation check (requires graph structure)
        # For now, return top N by evidence

        logger.info(
            f"Markov boundary: {len(boundary_candidates)} nodes "
            f"(from {len(candidates)} candidates)"
        )

        return boundary_candidates
```

**Usage**:
```python
selector = MarkovBoundarySelector()

markov_boundary = selector.select_boundary(
    candidates=families,
    observations=["CRP", "IL6", "HbA1c"],  # User's biomarkers
    min_evidence=50,
    top_n=12
)
```

**Example Output**:
```python
[
  {"family": "MAPK", "members": ["MAPK1", "MAPK3", "MAPK14"], "total_evidence": 290},
  {"gene_symbol": "IL6", "total_evidence": 78},
  {"family": "NFkappaB", "members": ["NFKB1"], "total_evidence": 67},
  {"family": "AKT", "members": ["AKT1", "AKT2"], "total_evidence": 156},
  # ... 8 more nodes
  # Total: 12 latent hubs
]
```

**Key Point**: Final Markov boundary is **12 nodes** (vs 1,937 genes or 100 families).

---

### Step 5: INDRA Validation (Mechanistic Evidence)

**Input**: Markov boundary nodes
**Output**: Validated edges with molecular mechanisms

**Code Path**: `indra_agent/services/indra_service.py`

```python
async def validate_markov_boundary(
    self,
    boundary_nodes: List[Dict],
    target_biomarkers: List[str]
) -> CausalGraph:
    """Query INDRA to validate boundary → biomarker edges.

    For each boundary node:
    1. If it's a family, query INDRA with family name (FPLX namespace)
    2. If it's a gene, query INDRA with gene symbol (HGNC namespace)
    3. Keep only edges with belief > 0.7
    """

    validated_edges = []

    for node in boundary_nodes:
        if node.get("is_family"):
            # Query at family level
            source = node["family"]
            namespace = "FPLX"
        else:
            # Query at gene level
            source = node["gene_symbol"]
            namespace = "HGNC"

        for biomarker in target_biomarkers:
            # Query INDRA
            statements = await self.get_statements(
                subject=source,
                object=biomarker,
                max_statements=10
            )

            if statements and statements[0].belief > 0.7:
                validated_edges.append({
                    "source": source,
                    "target": biomarker,
                    "belief": statements[0].belief,
                    "evidence_count": len(statements[0].evidence),
                    "stmt_type": statements[0].stmt_type
                })

    return self._build_graph(boundary_nodes, validated_edges)
```

**Example INDRA Query** (family-level):
```python
# Query: "MAPK" family → "IL6"
await indra_service.get_statements(
    subject="MAPK",  # Family name
    object="IL6"
)

# INDRA internally expands to:
# - MAPK1 → IL6
# - MAPK3 → IL6
# - MAPK14 → IL6
# And aggregates evidence across all members
```

**Example Output**:
```python
[
  Statement(
    subject="MAPK",  # Family
    object="IL6",
    stmt_type="IncreaseAmount",
    belief=0.87,  # Aggregated across MAPK1/3/14
    evidence=[...312 papers...]
  )
]
```

**Key Point**: INDRA natively supports FPLX queries - it automatically aggregates evidence across family members.

---

### Step 6: Build Final Causal Graph

**Input**: Validated edges from INDRA
**Output**: CausalGraph for Bayesian inference

**Code Path**: `indra_agent/services/graph_builder.py`

```python
def build_foliated_graph(
    exposures: List[Dict],      # From Writer KG
    markov_boundary: List[Dict], # From Markov selector
    validated_edges: List[Dict], # From INDRA
    genetics: Dict              # User's genetic variants
) -> CausalGraph:
    """Build complete causal graph with foliation structure.

    Layers:
    1. Exposures (observed)
    2. Markov boundary (latent)
    3. Biomarkers (observed)
    4. Outcomes (observed)
    5. Genetics (observed modifiers)
    """

    nodes = []
    edges = []

    # Layer 1: Exposures
    for exp in exposures:
        nodes.append(Node(
            id=exp["mesh_id"],
            label=exp["name"],
            type="environmental"
        ))

    # Layer 2: Markov boundary (latent hubs)
    for hub in markov_boundary:
        if hub.get("is_family"):
            node_id = hub["family"]  # FPLX family name
            node_type = "protein_family"
        else:
            node_id = hub["gene_symbol"]
            node_type = "molecular"

        nodes.append(Node(
            id=node_id,
            label=node_id,
            type=node_type
        ))

    # Add edges from CTD (exposure → boundary)
    for hub in markov_boundary:
        for exposure_id in hub["affected_by"]:
            edges.append(Edge(
                source=exposure_id,
                target=hub.get("family") or hub["gene_symbol"],
                relationship="affects",
                effect_size=min(0.5 + hub["total_evidence"]/200, 0.95),
                evidence_count=hub["total_evidence"]
            ))

    # Add edges from INDRA (boundary → biomarkers)
    for edge_data in validated_edges:
        edges.append(Edge(
            source=edge_data["source"],
            target=edge_data["target"],
            relationship=edge_data["stmt_type"],
            effect_size=edge_data["belief"],
            confidence=edge_data["belief"],
            evidence_count=edge_data["evidence_count"]
        ))

    # Layer 5: Genetic modifiers
    if "GSTM1" in genetics and genetics["GSTM1"] == "null":
        # Add modifier edge: GSTM1_null amplifies oxidative stress
        edges.append(Edge(
            source="GSTM1_null",
            target="ROS",  # If ROS is in Markov boundary
            relationship="amplifies",
            effect_size=1.3  # 30% amplification
        ))

    return CausalGraph(nodes=nodes, edges=edges)
```

**Final Graph Structure**:
```
Exposures (2) → Markov Boundary (12) → Biomarkers (3) → Outcomes (2)
                      ↑
                Genetics (1) modifiers

Total nodes: 20
Total edges: ~30
```

---

## Complete Workflow Integration

**Main Entry Point**: `indra_agent/core/client.py`

```python
async def process_causal_discovery_request(
    self,
    request: CausalDiscoveryRequest
) -> CausalDiscoveryResponse:
    """End-to-end causal discovery with ontology integration."""

    # Step 1: Writer KG query
    kg_result = await self.writer_kg.query(request.query.text)
    exposures = kg_result["entities"]

    # Step 2: CTD topology discovery
    ctd_builder = CTDNetworkBuilder(CTD_RELATIONSHIPS_PATH)
    ctd_builder.load_network()

    exposure_ids = [e["mesh_id"] for e in exposures]
    convergent_genes = ctd_builder.find_convergent_targets(
        exposure_nodes=exposure_ids,
        min_convergence=2
    )

    # Step 3: FPLX aggregation
    fplx_aggregator = FPLXAggregator()
    families = fplx_aggregator.aggregate_to_families(convergent_genes)

    # Step 4: Markov boundary selection
    boundary_selector = MarkovBoundarySelector()
    markov_boundary = boundary_selector.select_boundary(
        candidates=families,
        observations=request.user_context.current_biomarkers.keys(),
        top_n=12
    )

    # Step 5: INDRA validation
    validated_edges = await self.indra.validate_markov_boundary(
        boundary_nodes=markov_boundary,
        target_biomarkers=list(request.user_context.current_biomarkers.keys())
    )

    # Step 6: Build causal graph
    graph = build_foliated_graph(
        exposures=exposures,
        markov_boundary=markov_boundary,
        validated_edges=validated_edges,
        genetics=request.user_context.genetics
    )

    # Step 7: Bayesian inference (existing code)
    predictions = await self.scm_inference.predict(graph, ...)

    return CausalDiscoveryResponse(
        graph=graph,
        predictions=predictions,
        explanations=self._generate_explanations(graph, predictions)
    )
```

---

## What We Need to Build

### New Components

1. **`fplx_aggregator.py`** ✅ Design complete, needs implementation
   - Load FPLX family mappings from INDRA
   - Aggregate genes → families with evidence summation

2. **`markov_boundary_selector.py`** ✅ Design complete, needs implementation
   - Greedy selection by evidence
   - Eventually: d-separation check

3. **FPLX data in Writer KG** ⚠️ Need to add
   - Download FPLX ontology from INDRA repository
   - Convert to CSV: `family_id,family_name,member_genes`
   - Upload to Writer KG

### Modified Components

4. **`indra_service.py`** - Add family-level queries
   - Already supports FPLX namespace
   - Just need to pass `namespace="FPLX"` for families

5. **`graph_builder.py`** - Handle protein families as nodes
   - Add `type="protein_family"` node type
   - Preserve family membership in metadata

---

## Bottom Line: The Workflow IS Feasible

**Data Sources Already In Place**:
- ✅ Writer KG (MeSH + CTD)
- ✅ CTD Network Builder (gene-level topology)
- ✅ INDRA service (molecular validation)

**Missing Pieces** (2-3 files):
1. FPLX aggregator (~150 lines)
2. Markov boundary selector (~100 lines)
3. FPLX ontology in Writer KG (download + upload)

**Execution Time** (per query):
- Writer KG: 2-5s
- CTD network load: <1s (in-memory graph)
- FPLX aggregation: <0.1s (dict lookups)
- Markov selection: <0.1s (sort + filter)
- INDRA validation: 2-3s per edge × 12 nodes = 30s
- **Total: ~40s** (acceptable for systems medicine analysis)

The workflow is **linear** and **tractable**. Each step reduces dimensionality:
- 1,937 genes → 100 families → 12 Markov hubs → validated causal graph
