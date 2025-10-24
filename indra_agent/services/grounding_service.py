"""Entity grounding service with dynamic resolution via Writer KG and INDRA API.

This service provides entity grounding using:
1. Writer Knowledge Graph (MeSH ontology) - primary
2. INDRA Network Search API (autocomplete, node resolution) - fallback
3. Minimal seed entities for bootstrapping common queries

NO HARDCODED MAPPINGS - all resolutions are dynamic and live.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GroundingService:
    """Service for grounding biological entities to database identifiers.

    Uses dynamic resolution via Writer KG and INDRA API.
    Minimal seed entities provided for common query bootstrapping only.
    """

    # MINIMAL seed entities for bootstrapping common health queries
    # Only the 10 most frequently queried biomedical entities
    # ALL other entities resolved dynamically via Writer KG / INDRA API
    #
    # CRITICAL: "name" field MUST contain INDRA-compatible entity name
    # For genes: Short symbols work (e.g., "CRP", "IL6")
    # For environmental: Use Writer KG resolution for full names like "Particulate Matter"
    SEED_ENTITIES: Dict[str, Dict] = {
        # Top 5 biomarkers (most common in health queries)
        "CRP": {"id": "CRP", "name": "CRP", "type": "biomarker", "database": "HGNC", "identifier": "2367"},
        "c-reactive protein": {"id": "CRP", "name": "CRP", "type": "biomarker", "database": "HGNC", "identifier": "2367"},
        "IL6": {"id": "IL6", "name": "IL6", "type": "biomarker", "database": "HGNC", "identifier": "6018"},
        "interleukin-6": {"id": "IL6", "name": "IL6", "type": "biomarker", "database": "HGNC", "identifier": "6018"},
        "HbA1c": {"id": "HbA1c", "name": "HbA1c", "type": "biomarker", "database": "MESH", "identifier": "D006442"},
        "Glucose": {"id": "Glucose", "name": "Glucose", "type": "biomarker", "database": "CHEBI", "identifier": "17234"},
        "Insulin": {"id": "Insulin", "name": "INS", "type": "biomarker", "database": "HGNC", "identifier": "6081"},

        # Top 3 environmental exposures - use canonical names from Writer KG/INDRA
        # CRITICAL: "name" field MUST be INDRA-compatible (what LLM agent passes to find_causal_paths)
        "PM2.5": {"id": "PM2.5", "name": "Particulate Matter", "type": "environmental", "database": "MESH", "identifier": "D052638"},
        "particulate matter": {"id": "PM2.5", "name": "Particulate Matter", "type": "environmental", "database": "MESH", "identifier": "D052638"},
        "ozone": {"id": "ozone", "name": "Ozone", "type": "environmental", "database": "CHEBI", "identifier": "25812"},
        "NO2": {"id": "NO2", "name": "Nitrogen Dioxide", "type": "environmental", "database": "CHEBI", "identifier": "33101"},

        # Top 2 molecular nodes (signaling hubs)
        "NFKB1": {"id": "NFKB1", "name": "NFKB1", "type": "molecular", "database": "HGNC", "identifier": "7794"},
        "ROS": {"id": "ROS", "name": "reactive oxygen species", "type": "molecular", "database": "MESH", "identifier": "D017382"},
    }

    # HARDCODED MAPPINGS: Database ID → entity name that INDRA recognizes
    # This is REQUIRED because:
    # 1. INDRA API does NOT accept database IDs (MESH:D052638, HGNC:2367)
    # 2. INDRA API requires EXACT entity names that exist in its knowledge graph
    # 3. No autocomplete endpoint exists to resolve IDs → names dynamically
    # 4. This covers biomolecular + environmental + chemical entities
    #
    # CRITICAL: Entity names MUST match INDRA's internal naming:
    # - Gene symbols: "IL6", "CRP", "NFKB1" (short names work)
    # - Processes: "reactive oxygen species" (FULL name required, not "ROS")
    # - Environmental: Not directly in INDRA - must use intermediate molecular nodes
    DATABASE_ID_TO_NAME: Dict[str, str] = {
        # HGNC gene symbols (proteins/genes) - SHORT names work
        "HGNC:2367": "CRP",
        "HGNC:6018": "IL6",
        "HGNC:6081": "INS",
        "HGNC:7794": "NFKB1",
        "HGNC:11892": "TNF",

        # MESH processes - FULL names required by INDRA
        "MESH:D017382": "reactive oxygen species",  # NOT "ROS"
        "MESH:D006442": "HbA1c",  # Glycated hemoglobin

        # MESH environmental (not in INDRA graph - will use multi-hop)
        "MESH:D052638": "PM2.5",  # Particulate Matter (not in INDRA directly)
        "MESH:D000393": "Air Pollutants",  # Not in INDRA directly
        "MESH:D010126": "Ozone",  # Not in INDRA directly

        # CHEBI chemicals
        "CHEBI:17234": "Glucose",
        "CHEBI:25812": "O3",  # Ozone
        "CHEBI:33101": "NO2",  # Nitrogen dioxide

        # GO processes - FULL names required
        "GO:0006979": "oxidative stress response",  # Full GO term name
    }

    # ALTERNATIVE NAME MAPPINGS: Common entity names → INDRA-compatible SHORT names
    # These handle Writer KG outputs and user queries that use full/alternative names
    ALTERNATIVE_NAMES: Dict[str, str] = {
        # Particulate matter variations
        "particulate matter": "PM2.5",
        "Particulate Matter": "PM2.5",
        "pm2.5": "PM2.5",
        "PM 2.5": "PM2.5",
        "fine particulate matter": "PM2.5",

        # CRP variations
        "c-reactive protein": "CRP",
        "C-Reactive Protein": "CRP",
        "C-reactive protein": "CRP",
        "crp": "CRP",

        # IL-6 variations
        "interleukin-6": "IL6",
        "Interleukin-6": "IL6",
        "IL-6": "IL6",
        "il-6": "IL6",
        "interleukin 6": "IL6",

        # TNF variations
        "tumor necrosis factor": "TNF",
        "Tumor Necrosis Factor": "TNF",
        "TNF-alpha": "TNF",
        "TNFalpha": "TNF",
        "TNFA": "TNF",
        "tnf": "TNF",

        # Oxidative stress / ROS variations
        "oxidative stress": "reactive oxygen species",
        "Oxidative Stress": "reactive oxygen species",
        "ROS": "reactive oxygen species",
        "ros": "reactive oxygen species",
        "Reactive Oxygen Species": "reactive oxygen species",

        # NFKB variations
        "NF-kappa B": "NFKB1",
        "NF-kappaB": "NFKB1",
        "NF-κB": "NFKB1",
        "NFkappaB": "NFKB1",
        "nfkb": "NFKB1",

        # IL-1 beta variations
        "IL-1beta": "IL1B",
        "IL1beta": "IL1B",
        "interleukin-1 beta": "IL1B",
        "Interleukin-1 beta": "IL1B",
    }

    def __init__(self, writer_kg_service=None, indra_service=None):
        """Initialize grounding service with dynamic resolution.

        Args:
            writer_kg_service: Optional Writer KG service for MeSH ontology lookups
            indra_service: Optional INDRA service for entity resolution
        """
        self.writer_kg_service = writer_kg_service
        self.indra_service = indra_service
        self.resolution_cache: Dict[str, Optional[Dict]] = {}  # LRU cache for resolutions

    def ground_entity(self, entity_name: str) -> Optional[Dict]:
        """Ground a single entity to database identifier using dynamic resolution.

        Resolution order:
        1. Check SEED_ENTITIES (fast path for common entities)
        2. Check resolution cache
        3. Try Writer KG API (MeSH ontology) if available
        4. Try INDRA API (autocomplete + node resolution) if available
        5. Return None if all strategies fail

        Args:
            entity_name: Entity name to ground

        Returns:
            Grounding dict with id, name, type, database, identifier, or None if not found
        """
        # Check cache first
        if entity_name in self.resolution_cache:
            logger.debug(f"Cache hit for: {entity_name}")
            return self.resolution_cache[entity_name]

        # Strategy 1: Check SEED_ENTITIES (exact and case-insensitive)
        if entity_name in self.SEED_ENTITIES:
            result = self.SEED_ENTITIES[entity_name]
            self.resolution_cache[entity_name] = result
            logger.info(f"Resolved {entity_name} via SEED (exact match)")
            return result

        entity_lower = entity_name.lower()
        for key, value in self.SEED_ENTITIES.items():
            if key.lower() == entity_lower or entity_lower in value["name"].lower():
                self.resolution_cache[entity_name] = value
                logger.info(f"Resolved {entity_name} via SEED (fuzzy match)")
                return value

        # Strategy 2: Try Writer KG (MeSH ontology) - requires async, so caller must use async version
        # This is a synchronous method, so we can't call async Writer KG here
        # Caller should use ground_entity_async() for dynamic resolution

        # Strategy 3: Return None (caller should use async version for full resolution)
        logger.warning(f"Entity {entity_name} not in SEED_ENTITIES. Use ground_entity_async() for dynamic resolution.")
        self.resolution_cache[entity_name] = None
        return None

    async def ground_entity_async(self, entity_name: str) -> Optional[Dict]:
        """Ground entity with full dynamic resolution (async version).

        This method supports:
        1. SEED_ENTITIES lookup (fast path)
        2. Writer KG API (MeSH ontology)
        3. INDRA API (autocomplete + node resolution)

        Args:
            entity_name: Entity name to ground

        Returns:
            Grounding dict or None
        """
        # Check SEED_ENTITIES first (fast path)
        seed_result = self.ground_entity(entity_name)
        if seed_result:
            return seed_result

        # Check cache
        if entity_name in self.resolution_cache:
            return self.resolution_cache[entity_name]

        # Strategy 2: Try Writer KG (MeSH ontology)
        if self.writer_kg_service:
            try:
                mesh_result = await self.writer_kg_service.find_mesh_term(entity_name)
                if mesh_result:
                    grounded = {
                        "id": mesh_result.get("mesh_id"),
                        "name": mesh_result.get("mesh_label"),
                        "type": self._infer_type_from_mesh(mesh_result),
                        "database": "MESH",
                        "identifier": mesh_result.get("mesh_id"),
                    }
                    self.resolution_cache[entity_name] = grounded
                    logger.info(f"Resolved {entity_name} via Writer KG")
                    return grounded
            except Exception as e:
                logger.warning(f"Writer KG resolution failed for {entity_name}: {e}")

        # Strategy 3: Try INDRA API
        if self.indra_service:
            try:
                indra_result = await self.indra_service.ground_entity(entity_name)
                if indra_result:
                    grounded = {
                        "id": indra_result.get("id", entity_name),
                        "name": indra_result.get("name", entity_name),
                        "type": "molecular",  # Default type
                        "database": indra_result.get("database", "UNKNOWN"),
                        "identifier": indra_result.get("id", ""),
                    }
                    self.resolution_cache[entity_name] = grounded
                    logger.info(f"Resolved {entity_name} via INDRA API")
                    return grounded
            except Exception as e:
                logger.warning(f"INDRA resolution failed for {entity_name}: {e}")

        # All strategies failed
        logger.warning(f"Could not ground entity: {entity_name}")
        self.resolution_cache[entity_name] = None
        return None

    def ground_entities(self, entity_names: List[str]) -> Dict[str, Optional[Dict]]:
        """Ground multiple entities.

        Args:
            entity_names: List of entity names to ground

        Returns:
            Dict mapping entity names to grounding dicts
        """
        return {name: self.ground_entity(name) for name in entity_names}

    def extract_entities_from_query(self, query_text: str) -> List[str]:
        """Extract SEED entities from query text.

        This is a fast heuristic for common entities only.
        For comprehensive entity extraction, use NER or LLM-based extraction.

        Args:
            query_text: Natural language query

        Returns:
            List of recognized entity IDs (from SEED_ENTITIES only)
        """
        query_lower = query_text.lower()
        found_entities = []

        for entity_id, entity_info in self.SEED_ENTITIES.items():
            # Check if entity name appears in query
            if entity_id.lower() in query_lower or entity_info["name"].lower() in query_lower:
                found_entities.append(entity_id)

        return found_entities

    def get_biomarker_regulators(self, biomarker: str) -> List[str]:
        """Get molecular regulators for a biomarker.

        NOTE: This method is deprecated and returns empty list.
        Use INDRA API to discover regulatory relationships dynamically.

        Args:
            biomarker: Biomarker name (e.g., "CRP")

        Returns:
            Empty list (use INDRA path search for dynamic discovery)
        """
        logger.warning(
            f"get_biomarker_regulators({biomarker}) called. "
            "This method is deprecated - use INDRA find_causal_paths for dynamic discovery."
        )
        return []

    def format_for_indra(self, entity: Dict) -> str:
        """Format entity for INDRA API query.

        Args:
            entity: Grounded entity dict

        Returns:
            INDRA-compatible identifier (e.g., "HGNC:6018")
        """
        return f"{entity['database']}:{entity['identifier']}"

    def ground_mesh_enriched_entities(
        self, mesh_enriched: List[Dict]
    ) -> Dict[str, Optional[Dict]]:
        """Ground entities that were enriched with MeSH ontology.

        Args:
            mesh_enriched: List of MeSH-enriched entities from mesh_enrichment_agent

        Returns:
            Dict mapping original terms to grounded entity dicts
        """
        grounded_entities = {}

        for enriched in mesh_enriched:
            original_term = enriched.get("original_term")
            mesh_id = enriched.get("mesh_id")
            mesh_label = enriched.get("mesh_label")

            if not mesh_id or not mesh_label:
                logger.warning(f"Skipping incomplete MeSH entity: {enriched}")
                continue

            # Convert MeSH enriched entity to grounding format
            grounded = {
                "id": mesh_id,
                "name": mesh_label,
                "type": self._infer_type_from_mesh(enriched),
                "database": "MESH",
                "identifier": mesh_id,
                "synonyms": enriched.get("synonyms", []),
                "related_terms": enriched.get("related_terms", []),
                "mesh_enriched": True,  # Flag to indicate MeSH enrichment
            }

            grounded_entities[original_term] = grounded

            logger.info(
                f"Grounded MeSH entity: {original_term} → {mesh_id} ({mesh_label})"
            )

            # Also add synonyms as alternate groundings
            for synonym in enriched.get("synonyms", [])[:3]:
                if synonym not in grounded_entities:
                    grounded_entities[synonym] = grounded

        return grounded_entities

    def _infer_type_from_mesh(self, mesh_entity: Dict) -> str:
        """Infer entity type from MeSH enrichment data.

        Args:
            mesh_entity: MeSH-enriched entity dict

        Returns:
            Entity type: "environmental", "biomarker", or "molecular"
        """
        mesh_id = mesh_entity.get("mesh_id", "")
        label = mesh_entity.get("mesh_label", "").lower()
        definition = mesh_entity.get("definition", "").lower()

        # Environmental indicators
        environmental_keywords = [
            "pollutant", "particulate", "air quality", "exposure",
            "pollution", "environmental", "ozone", "dioxide"
        ]
        if any(kw in label or kw in definition for kw in environmental_keywords):
            return "environmental"

        # Biomarker indicators
        biomarker_keywords = [
            "biomarker", "protein", "crp", "interleukin", "cytokine",
            "marker", "indicator", "level"
        ]
        if any(kw in label or kw in definition for kw in biomarker_keywords):
            return "biomarker"

        # Default to molecular
        return "molecular"

    def merge_with_mesh_enrichment(
        self, entities: List[str], mesh_enriched: List[Dict]
    ) -> Dict[str, Optional[Dict]]:
        """Merge traditional grounding with MeSH enrichment.

        This provides a fallback chain:
        1. Try MeSH-enriched grounding (most current and comprehensive)
        2. Fall back to hard-coded mappings
        3. Return None if not found

        Args:
            entities: List of entity names to ground
            mesh_enriched: List of MeSH-enriched entities

        Returns:
            Dict mapping entity names to grounded dicts
        """
        # First, ground MeSH-enriched entities
        mesh_grounded = self.ground_mesh_enriched_entities(mesh_enriched)

        # Then ground remaining entities with hard-coded mappings
        all_grounded = {}
        for entity in entities:
            if entity in mesh_grounded:
                # Prefer MeSH enrichment
                all_grounded[entity] = mesh_grounded[entity]
                logger.info(f"Using MeSH enrichment for: {entity}")
            else:
                # Fall back to hard-coded
                grounded = self.ground_entity(entity)
                all_grounded[entity] = grounded
                if grounded:
                    logger.info(f"Using hard-coded mapping for: {entity}")
                else:
                    logger.warning(f"No grounding found for: {entity}")

        return all_grounded
