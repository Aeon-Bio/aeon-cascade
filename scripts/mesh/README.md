# MeSH → Writer Knowledge Graph Pipeline

Automated pipeline to download MeSH 2025 ontology, convert to CSV, and upload to Writer Knowledge Graph for semantic biomedical entity grounding.

## Overview

This pipeline:
1. **Downloads** MeSH 2025 RDF N-Triples from NLM (~500-800MB compressed)
2. **Converts** RDF to structured CSV format
3. **Uploads** to Writer Knowledge Graph for semantic search

## Prerequisites

```bash
# Install dependencies
pip install rdflib httpx python-dotenv

# Set Writer API key
export WRITER_API_KEY="your_api_key_here"
# Or add to .env file in project root
```

## Usage

### Option 1: Curated Subset (Recommended for MVP)

Convert ~1,000 metabolic/environmental/inflammatory terms:

```bash
# Step 1: Download MeSH RDF
python 01_download_mesh.py

# Step 2: Convert to CSV (curated mode)
python 02_convert_to_csv.py --curated

# Step 3: Upload to Writer
python 03_upload_to_writer.py
```

**Output size**: ~300-500 KB total

**Coverage**:
- Environmental exposures (PM2.5, ozone, air pollutants)
- Metabolic markers (glucose, insulin, HbA1c, adiponectin)
- Inflammatory markers (CRP, IL-6, TNF-α)
- Oxidative stress (ROS, glutathione, antioxidants)
- Diseases (diabetes, metabolic syndrome, CVD)
- Molecular mechanisms (NF-κB, insulin signaling)

### Option 2: Full MeSH Ontology

Convert all 30,956 descriptors + relationships:

```bash
python 01_download_mesh.py
python 02_convert_to_csv.py --full  # Takes 10-20 minutes
python 03_upload_to_writer.py
```

**Output size**: ~305 MB total

## Output Files

After conversion, CSV files are created in `data/csv/`:

- **mesh_terms.csv**: Core descriptors with labels and definitions
  ```csv
  mesh_id,label,definition,uri
  D052638,Particulate Matter,"Particles of any solid substance...",http://...
  D002097,C-Reactive Protein,"A plasma protein that circulates...",http://...
  ```

- **mesh_relationships.csv**: Hierarchical relationships
  ```csv
  source,target,relationship,description
  D052638,D000393,broader_than,D000393 is broader than D052638
  ```

- **mesh_synonyms.csv**: Alternative terms
  ```csv
  mesh_id,synonym,type
  D052638,PM2.5,alternative
  D052638,Fine Particulate Matter,alternative
  ```

## Writer Knowledge Graph Integration

Once uploaded, query the Knowledge Graph from Python:

```python
from indra_agent.services.mesh_service import MeSHService

mesh = MeSHService()

# Search for entity
results = await mesh.search_mesh_terms("particulate matter", limit=5)
# Returns: [{"mesh_id": "D052638", "label": "Particulate Matter", ...}]

# Get hierarchy
hierarchy = await mesh.get_mesh_hierarchy("D052638")
# Returns: {"broader": ["D000393"], "narrower": [...]}
```

## File Size Summary

| Mode | Terms | Relationships | Total Size | Time |
|------|-------|---------------|------------|------|
| **Curated** | ~1,000 | ~200 | **300-500 KB** | 2-5 min |
| **Full** | 30,956 | ~15,000 | **305 MB** | 15-30 min |

## Troubleshooting

**Download fails**:
```bash
# Check NLM server status
curl -I https://nlmpubs.nlm.nih.gov/projects/mesh/rdf/2025/mesh2025.nt.gz

# Use alternative mirror (if available)
# Update MESH_URL in 01_download_mesh.py
```

**Conversion memory error**:
```bash
# For full MeSH, ensure 8GB+ RAM available
# Or use curated mode instead
python 02_convert_to_csv.py --curated
```

**Upload fails**:
```bash
# Verify API key
echo $WRITER_API_KEY

# Check file size limits (Writer max: depends on plan)
ls -lh data/csv/

# Upload files individually if needed
```

## Architecture

```
┌─────────────────────┐
│  NLM MeSH RDF       │
│  (mesh2025.nt.gz)   │  01_download_mesh.py
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  RDF Graph          │
│  (rdflib parsing)   │  02_convert_to_csv.py
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  CSV Files          │
│  - Terms            │
│  - Relationships    │  03_upload_to_writer.py
│  - Synonyms         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Writer Knowledge   │
│  Graph (API)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  indra_agent        │
│  Entity Grounding   │
└─────────────────────┘
```

## Next Steps

After successful upload:

1. **Wait for indexing**: Writer KG takes 5-10 minutes to index CSV data
2. **Test queries**: Use Writer API or SDK to query MeSH terms
3. **Integrate with indra_agent**: Update `mesh_service.py` to use Writer KG
4. **Monitor performance**: Track query latency and accuracy

## References

- [MeSH RDF Documentation](https://hhs.github.io/meshrdf/)
- [MeSH Download Site](https://www.nlm.nih.gov/databases/download/mesh.html)
- [Writer Knowledge Graph API](https://dev.writer.com/api-guides/knowledge-graph)
- [Writer File Upload API](https://dev.writer.com/api-reference/file-api/upload-files)

## License

MeSH data is public domain (provided by National Library of Medicine).

Scripts in this directory: MIT License
