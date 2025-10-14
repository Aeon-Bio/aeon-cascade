"""Entity grounding service with pre-defined biological entity mappings.

This service maps biomarker names, environmental exposures, and molecular entities
to their corresponding database identifiers (MESH, HGNC, GO, CHEBI).
"""

from typing import Dict, List, Optional, Tuple


class GroundingService:
    """Service for grounding biological entities to database identifiers."""

    # Pre-defined biomarker mappings
    BIOMARKER_MAPPINGS: Dict[str, Dict] = {
        "CRP": {
            "id": "CRP",
            "name": "C-Reactive Protein",
            "type": "biomarker",
            "database": "HGNC",
            "identifier": "2367",
            "regulators": ["IL6", "IL1B", "TNF"],
        },
        "IL-6": {
            "id": "IL6",
            "name": "Interleukin-6",
            "type": "biomarker",
            "database": "HGNC",
            "identifier": "6018",
            "regulators": ["NFKB1", "RELA"],
        },
        "IL6": {  # Alias
            "id": "IL6",
            "name": "Interleukin-6",
            "type": "biomarker",
            "database": "HGNC",
            "identifier": "6018",
            "regulators": ["NFKB1", "RELA"],
        },
        "8-OHdG": {
            "id": "8-OHdG",
            "name": "8-Hydroxy-2-deoxyguanosine",
            "type": "biomarker",
            "database": "CHEBI",
            "identifier": "40304",
            "process": "oxidative_stress",
        },
    }

    # Environmental exposures
    ENVIRONMENTAL_MAPPINGS: Dict[str, Dict] = {
        "PM2.5": {
            "id": "PM2.5",
            "name": "Particulate Matter (PM2.5)",
            "type": "environmental",
            "database": "MESH",
            "identifier": "D052638",
        },
        "PM10": {
            "id": "PM10",
            "name": "Particulate Matter (PM10)",
            "type": "environmental",
            "database": "MESH",
            "identifier": "D052638",
        },
        "ozone": {
            "id": "ozone",
            "name": "Ozone",
            "type": "environmental",
            "database": "CHEBI",
            "identifier": "25812",
        },
        "NO2": {
            "id": "NO2",
            "name": "Nitrogen Dioxide",
            "type": "environmental",
            "database": "CHEBI",
            "identifier": "33101",
        },
    }

    # Molecular entities
    MOLECULAR_MAPPINGS: Dict[str, Dict] = {
        "NFKB1": {
            "id": "NFKB1",
            "name": "NF-κB p50",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "7794",
        },
        "RELA": {
            "id": "RELA",
            "name": "NF-κB p65 (RELA)",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "9955",
        },
        "IL6": {
            "id": "IL6",
            "name": "Interleukin-6",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "6018",
        },
        "TNF": {
            "id": "TNF",
            "name": "TNF-α",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "11892",
        },
        "IL1B": {
            "id": "IL1B",
            "name": "IL-1β",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "5992",
        },
        "NFE2L2": {
            "id": "NFE2L2",
            "name": "NRF2 (NFE2L2)",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "7782",
        },
        "SOD1": {
            "id": "SOD1",
            "name": "Superoxide Dismutase 1",
            "type": "molecular",
            "database": "HGNC",
            "identifier": "11179",
        },
        "ROS": {
            "id": "ROS",
            "name": "Reactive Oxygen Species",
            "type": "molecular",
            "database": "MESH",
            "identifier": "D017382",
        },
    }

    # Biological processes
    PROCESS_MAPPINGS: Dict[str, Dict] = {
        "oxidative_stress": {
            "id": "oxidative_stress",
            "name": "Oxidative Stress",
            "type": "molecular",
            "database": "GO",
            "identifier": "0006979",
        },
        "inflammation": {
            "id": "inflammation",
            "name": "Inflammation",
            "type": "molecular",
            "database": "GO",
            "identifier": "0006954",
        },
    }

    def __init__(self):
        """Initialize grounding service."""
        # Combine all mappings
        self.all_mappings = {
            **self.BIOMARKER_MAPPINGS,
            **self.ENVIRONMENTAL_MAPPINGS,
            **self.MOLECULAR_MAPPINGS,
            **self.PROCESS_MAPPINGS,
        }

    def ground_entity(self, entity_name: str) -> Optional[Dict]:
        """Ground a single entity to database identifier.

        Args:
            entity_name: Entity name to ground

        Returns:
            Grounding dict with id, name, type, database, identifier, or None if not found
        """
        # Try exact match
        if entity_name in self.all_mappings:
            return self.all_mappings[entity_name]

        # Try case-insensitive match
        entity_lower = entity_name.lower()
        for key, value in self.all_mappings.items():
            if key.lower() == entity_lower:
                return value

        # Try partial match on name
        for key, value in self.all_mappings.items():
            if entity_lower in value["name"].lower():
                return value

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
        """Extract known entities from query text.

        Args:
            query_text: Natural language query

        Returns:
            List of recognized entity IDs
        """
        query_lower = query_text.lower()
        found_entities = []

        for entity_id, entity_info in self.all_mappings.items():
            # Check if entity name appears in query
            if entity_id.lower() in query_lower or entity_info["name"].lower() in query_lower:
                found_entities.append(entity_id)

        return found_entities

    def get_biomarker_regulators(self, biomarker: str) -> List[str]:
        """Get molecular regulators for a biomarker.

        Args:
            biomarker: Biomarker name (e.g., "CRP")

        Returns:
            List of regulator entity IDs
        """
        if biomarker in self.BIOMARKER_MAPPINGS:
            return self.BIOMARKER_MAPPINGS[biomarker].get("regulators", [])
        return []

    def format_for_indra(self, entity: Dict) -> str:
        """Format entity for INDRA API query.

        Args:
            entity: Grounded entity dict

        Returns:
            INDRA-compatible identifier (e.g., "HGNC:6018")
        """
        return f"{entity['database']}:{entity['identifier']}"
