# INDRA Integration Strategy

## Overview

INDRA (Integrated Network and Dynamical Reasoning Assembler) is a biological knowledge graph developed by Harvard Medical School that aggregates causal mechanisms from scientific literature and databases. We use it as our primary source of mechanistic biological knowledge.

## INDRA Architecture

```
┌─────────────────────────────────────────────────┐
│           INDRA Knowledge Sources               │
│                                                 │
│  • PubMed (literature mining)                   │
│  • PathwayCommons (curated pathways)            │
│  • Reactome (biochemical reactions)             │
│  • SIGNOR (signaling network)                   │
│  • BEL (Biological Expression Language)         │
│  • TRIPS (natural language processing)          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  INDRA Assemblers   │
         │  (Extract, Normalize)│
         └──────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  INDRA Statements   │
         │  (Grounded, Unified)│
         └──────────┬───────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │  network.indra.bio  │
         │  (REST API)         │
         └──────────┬───────────┘
                   │
                   ▼
              Our Gateway
```

## INDRA Statement Types

INDRA represents biological knowledge as **statements** - structured representations of causal relationships.

### Core Statement Types for Aeon

| Statement Type | Description | Example | Relevance |
|---------------|-------------|---------|-----------|
| **Activation** | Agent A activates agent B | PM2.5 activates NFKB1 | High - direct causal effects |
| **Inhibition** | Agent A inhibits agent B | NAC inhibits oxidative_stress | High - interventions |
| **IncreaseAmount** | Agent A increases the amount of B | IL6 increases CRP | High - biomarker production |
| **DecreaseAmount** | Agent A decreases the amount of B | HEPA decreases PM2.5_indoor | High - interventions |
| **Phosphorylation** | Agent A phosphorylates B | MAPK1 phosphorylates RELA | Medium - signaling cascades |
| **Complex** | Agents form a complex | RELA + NFKB1 → NF-κB complex | Medium - pathway structure |
| **RegulateActivity** | Agent A regulates B's activity | GSTM1 regulates detoxification | High - genetic modifiers |

### Statement Structure

```json
{
  "type": "Activation",
  "subj": {
    "name": "PM2.5",
    "db_refs": {
      "MESH": "D052638"
    }
  },
  "obj": {
    "name": "NFKB1",
    "db_refs": {
      "HGNC": "7794",
      "UP": "P19838"
    }
  },
  "evidence": [
    {
      "source_api": "reach",
      "pmid": "28123456",
      "text": "Particulate matter exposure leads to NF-κB activation...",
      "annotations": {
        "species": "9606"  // Human
      }
    },
    {
      "source_api": "trips",
      "pmid": "29234567",
      "text": "Air pollution activates the NF-κB pathway..."
    }
  ],
  "belief": 0.87  // Confidence score based on evidence
}
```

## INDRA REST API Endpoints

Base URL: `https://db.indra.bio`

### 1. Path Search

**Purpose**: Find causal paths between two entities

**Endpoint**: `GET /api/network/path_search`

**Parameters**:
```python
{
  "source": "MESH:D052638",           # PM2.5
  "target": "HGNC:6018",              # IL6
  "max_depth": 4,                     # Maximum path length
  "stmt_filter": [                    # Statement types to include
    "Activation",
    "Inhibition",
    "IncreaseAmount"
  ],
  "k_shortest": 5,                    # Return top 5 paths
  "format": "json"
}
```

**Response**:
```json
{
  "paths": [
    {
      "nodes": [
        {"name": "PM2.5", "id": "MESH:D052638"},
        {"name": "NFKB1", "id": "HGNC:7794"},
        {"name": "IL6", "id": "HGNC:6018"}
      ],
      "edges": [
        {
          "source": "MESH:D052638",
          "target": "HGNC:7794",
          "statements": [
            {/* statement 1 */},
            {/* statement 2 */}
          ],
          "belief": 0.87
        },
        {
          "source": "HGNC:7794",
          "target": "HGNC:6018",
          "statements": [/* ... */],
          "belief": 0.91
        }
      ],
      "path_belief": 0.79  // Combined belief
    }
  ]
}
```

**Our Usage**:
```python
async def find_paths_pm25_to_il6():
    params = {
        "source": "MESH:D052638",
        "target": "HGNC:6018",
        "max_depth": 4,
        "k_shortest": 5
    }

    response = await httpx.get(
        "https://db.indra.bio/api/network/path_search",
        params=params
    )

    paths = response.json()["paths"]

    # Filter high-confidence paths
    return [p for p in paths if p["path_belief"] > 0.7]
```

### 2. Neighborhood Expansion

**Purpose**: Find immediate neighbors of an entity (what does X affect?)

**Endpoint**: `GET /api/network/neighbors`

**Parameters**:
```python
{
  "node": "HGNC:7794",        # NFKB1
  "distance": 1,              # 1-hop neighbors
  "direction": "downstream",  # downstream, upstream, or both
  "stmt_filter": ["Activation", "IncreaseAmount"]
}
```

**Response**:
```json
{
  "nodes": [
    {"name": "IL6", "id": "HGNC:6018", "belief": 0.91},
    {"name": "TNF", "id": "HGNC:11892", "belief": 0.88},
    {"name": "IL1B", "id": "HGNC:5992", "belief": 0.85}
  ],
  "edges": [
    {
      "source": "HGNC:7794",
      "target": "HGNC:6018",
      "statement_count": 89,
      "belief": 0.91
    }
  ]
}
```

**Our Usage**: When user asks "What does NF-κB affect?", or to expand search from known intermediates.

### 3. Statement Search

**Purpose**: Find all statements matching criteria

**Endpoint**: `POST /api/statements/from_agents`

**Parameters**:
```json
{
  "agents": ["NFKB1", "IL6"],
  "stmt_type": ["Activation"],
  "filter_options": {
    "ev_limit": 50,           // Max evidence per statement
    "only_human": true
  }
}
```

**Response**: Array of INDRA statements with full evidence

**Our Usage**: Deep-dive on specific mechanisms, get detailed evidence for UI display.

### 4. Entity Grounding

**Purpose**: Map free-text to grounded database identifiers

**Endpoint**: `POST /api/ground`

**Request**:
```json
{
  "names": ["particulate matter", "PM2.5", "air pollution"]
}
```

**Response**:
```json
{
  "results": [
    {
      "text": "particulate matter",
      "groundings": [
        {"db": "MESH", "id": "D052638", "score": 0.95},
        {"db": "CHEBI", "id": "CHEBI:50699", "score": 0.82}
      ]
    }
  ]
}
```

**Our Usage**: Convert user natural language input to INDRA-compatible identifiers.

## Agent Implementation

### BiomarkerResolver Integration

```python
class BiomarkerResolver:
    """Maps clinical biomarkers to molecular mechanisms"""

    # Curated mappings to INDRA identifiers
    BIOMARKER_TO_INDRA = {
        "CRP": {
            "direct": "HGNC:2367",  # CRP gene
            "regulators": [
                "HGNC:6018",  # IL6 (primary)
                "HGNC:5992",  # IL1B
                "HGNC:11892"  # TNF
            ]
        },
        "IL-6": {
            "direct": "HGNC:6018",
            "regulators": [
                "HGNC:9955",  # RELA
                "HGNC:7794"   # NFKB1
            ]
        },
        "8-OHdG": {
            "process": "GO:0006979",  # oxidative stress
            "regulators": [
                "HGNC:11179",  # SOD1
                "HGNC:7782"    # NFE2L2 (NRF2)
            ]
        }
    }

    def resolve(self, biomarker: str) -> List[str]:
        """Return INDRA identifiers for mechanisms producing biomarker"""
        mapping = self.BIOMARKER_TO_INDRA.get(biomarker, {})

        identifiers = []
        if "direct" in mapping:
            identifiers.append(mapping["direct"])
        identifiers.extend(mapping.get("regulators", []))

        return identifiers
```

### INDRAQueryAgent Implementation

```python
class INDRAQueryAgent:
    BASE_URL = "https://db.indra.bio"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.cache = {}  # Cache responses for hackathon

    async def find_causal_paths(
        self,
        exposures: List[str],      # ["MESH:D052638"]
        mechanisms: List[str],     # ["HGNC:6018", "HGNC:9955"]
        max_depth: int = 4
    ) -> List[CausalPath]:
        """
        Multi-strategy path discovery:
        1. Direct paths: exposure → mechanism
        2. Neighborhood expansion: exposure → X → mechanism
        """

        all_paths = []

        # Strategy 1: Direct path search
        for exposure in exposures:
            for mechanism in mechanisms:
                paths = await self._query_path_search(
                    source=exposure,
                    target=mechanism,
                    max_depth=max_depth
                )
                all_paths.extend(paths)

        # Strategy 2: Expand from exposures first
        neighbors = await self._get_neighbors(exposures)

        # Then search neighbors → mechanisms
        for neighbor in neighbors:
            for mechanism in mechanisms:
                paths = await self._query_path_search(
                    source=neighbor,
                    target=mechanism,
                    max_depth=max_depth - 1
                )
                all_paths.extend(paths)

        # Deduplicate and rank
        return self._rank_paths(all_paths)

    async def _query_path_search(
        self,
        source: str,
        target: str,
        max_depth: int
    ) -> List[CausalPath]:
        """Query INDRA path search endpoint"""

        cache_key = f"{source}_{target}_{max_depth}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/api/network/path_search",
                params={
                    "source": source,
                    "target": target,
                    "max_depth": max_depth,
                    "k_shortest": 5,
                    "stmt_filter": [
                        "Activation",
                        "Inhibition",
                        "IncreaseAmount",
                        "DecreaseAmount"
                    ]
                }
            )

            response.raise_for_status()
            data = response.json()

            paths = self._parse_paths(data, source, target)
            self.cache[cache_key] = paths

            return paths

        except httpx.HTTPError as e:
            logger.error(f"INDRA query failed: {e}")
            return []

    def _parse_paths(
        self,
        data: Dict,
        source: str,
        target: str
    ) -> List[CausalPath]:
        """Convert INDRA response to CausalPath objects"""

        paths = []

        for path_data in data.get("paths", []):
            nodes = [n["name"] for n in path_data.get("nodes", [])]
            edges = path_data.get("edges", [])

            # Aggregate evidence
            total_evidence = sum(
                len(edge.get("statements", []))
                for edge in edges
            )

            avg_belief = (
                sum(edge.get("belief", 0.5) for edge in edges) /
                len(edges) if edges else 0
            )

            # Extract all statements
            all_statements = []
            for edge in edges:
                all_statements.extend(edge.get("statements", []))

            paths.append(CausalPath(
                source=source,
                target=target,
                path=nodes,
                statements=all_statements,
                evidence_count=total_evidence,
                avg_confidence=avg_belief,
                path_length=len(nodes)
            ))

        return paths

    async def _get_neighbors(
        self,
        entities: List[str],
        distance: int = 1
    ) -> List[str]:
        """Get downstream neighbors of entities"""

        neighbors = set()

        for entity in entities:
            try:
                response = await self.client.get(
                    f"{self.BASE_URL}/api/network/neighbors",
                    params={
                        "node": entity,
                        "distance": distance,
                        "direction": "downstream"
                    }
                )

                data = response.json()
                neighbor_nodes = [
                    n["id"] for n in data.get("nodes", [])
                    if n.get("belief", 0) > 0.6
                ]
                neighbors.update(neighbor_nodes)

            except httpx.HTTPError as e:
                logger.error(f"Neighbor query failed: {e}")

        return list(neighbors)

    def _rank_paths(self, paths: List[CausalPath]) -> List[CausalPath]:
        """Rank paths by composite score"""

        def score_path(path: CausalPath) -> float:
            # Normalize components
            evidence_score = min(path.evidence_count / 20.0, 1.0)
            confidence_score = path.avg_confidence
            length_score = 1.0 / path.path_length

            # Weighted combination
            return (
                0.4 * evidence_score +
                0.3 * confidence_score +
                0.3 * length_score
            )

        paths.sort(key=score_path, reverse=True)
        return paths
```

## Entity Grounding Strategy

### Environmental Exposures

| Common Name | INDRA Identifier | Database |
|------------|------------------|----------|
| PM2.5, Particulate Matter | MESH:D052638 | MESH |
| Ozone, O₃ | CHEBI:25812 | CHEBI |
| NO₂, Nitrogen Dioxide | CHEBI:33101 | CHEBI |
| Lead, Pb | CHEBI:25016 | CHEBI |
| Benzene | CHEBI:16716 | CHEBI |

### Molecular Entities

| Gene/Protein | INDRA Identifier | Database |
|-------------|------------------|----------|
| NF-κB p65 (RELA) | HGNC:9955 | HGNC |
| NF-κB p50 (NFKB1) | HGNC:7794 | HGNC |
| IL-6 | HGNC:6018 | HGNC |
| TNF-α | HGNC:11892 | HGNC |
| IL-1β | HGNC:5992 | HGNC |
| NRF2 (NFE2L2) | HGNC:7782 | HGNC |
| SOD1 | HGNC:11179 | HGNC |

### Biological Processes

| Process | INDRA Identifier | Database |
|---------|------------------|----------|
| Oxidative Stress | GO:0006979 | GO |
| Inflammation | GO:0006954 | GO |
| Apoptosis | GO:0006915 | GO |
| Cell Proliferation | GO:0008283 | GO |

## Caching Strategy (Hackathon)

For the 2.5-hour hackathon, we'll pre-cache key queries to ensure demo reliability:

```python
# Pre-cache critical paths
CACHED_INDRA_RESPONSES = {
    "PM25_to_IL6": {
        "paths": [
            {
                "nodes": ["PM2.5", "NFKB1", "IL6"],
                "evidence_count": 47,
                "belief": 0.82,
                "statements": [/* ... */]
            },
            {
                "nodes": ["PM2.5", "oxidative_stress", "RELA", "IL6"],
                "evidence_count": 23,
                "belief": 0.75,
                "statements": [/* ... */]
            }
        ]
    },
    "PM25_to_oxidative_stress": {
        "paths": [
            {
                "nodes": ["PM2.5", "ROS", "oxidative_stress"],
                "evidence_count": 31,
                "belief": 0.78
            }
        ]
    },
    "IL6_to_CRP": {
        "paths": [
            {
                "nodes": ["IL6", "hepatocyte_signaling", "CRP"],
                "evidence_count": 312,
                "belief": 0.98
            }
        ]
    }
}

# Fallback to cache if API unavailable
async def query_with_fallback(source, target):
    cache_key = f"{source}_to_{target}"

    try:
        # Try real API
        return await indra_agent.query_path_search(source, target)
    except Exception as e:
        logger.warning(f"INDRA API failed, using cache: {e}")
        return CACHED_INDRA_RESPONSES.get(cache_key, [])
```

## Error Handling

```python
class INDRAError(Exception):
    """Base exception for INDRA-related errors"""
    pass

class INDRAConnectionError(INDRAError):
    """INDRA API is unreachable"""
    pass

class INDRANoPathError(INDRAError):
    """No causal path found between entities"""
    pass

async def safe_indra_query(source, target):
    """Wrapper with retry logic and graceful degradation"""

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            return await indra_agent.query_path_search(source, target)

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
                continue
            else:
                raise INDRAConnectionError("INDRA API timeout after retries")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise INDRANoPathError(f"No path found: {source} → {target}")
            else:
                raise INDRAError(f"INDRA API error: {e}")
```

## Rate Limiting

INDRA doesn't publish rate limits, but we'll be conservative:

```python
from asyncio import Semaphore

class RateLimitedINDRAClient:
    def __init__(self, max_concurrent=5, requests_per_minute=30):
        self.semaphore = Semaphore(max_concurrent)
        self.rate_limiter = TokenBucket(requests_per_minute, 60)

    async def query(self, *args, **kwargs):
        async with self.semaphore:
            await self.rate_limiter.acquire()
            return await self._do_query(*args, **kwargs)
```

## Future Enhancements (Post-Hackathon)

1. **Local INDRA Instance**: Deploy our own INDRA database for sub-second queries
2. **Multi-Source Integration**: Combine INDRA with OpenTargets, STRING, DISEASES
3. **Active Learning**: Flag low-confidence paths for expert curation
4. **Custom Statement Extraction**: Run our own text mining on recent papers
5. **Graph Embeddings**: Use INDRA network structure for similarity search

## Resources

- **INDRA Documentation**: https://indra.readthedocs.io
- **Network API**: https://network.indra.bio
- **GitHub**: https://github.com/sorgerlab/indra
- **Paper**: Gyori et al. "From word models to executable models of signaling networks using automated assembly" (Molecular Systems Biology, 2017)
