"""Entity synonym resolution for exhaustive INDRA graph search.

Purpose: Give the agent ALL ways to refer to an entity so it can:
1. Query INDRA with every synonym combination
2. Discover latent causal intermediates
3. Construct emergent pathway structures

NOT a "grounding service" - this is a SYNONYM EXPANSION service.
The agent needs to search exhaustively to let structure emerge.
"""

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class GroundingService:
    """Expand entity names to ALL synonyms for exhaustive INDRA search.

    The agent's job is to discover causal paths by querying INDRA with
    every possible name variant. Molecular intermediates EMERGE from
    graph structure, not from hardcoded mappings.
    """

    # ONLY for INDRA API name translation (when INDRA uses different names)
    # NOT for grounding - for resolving what NAME to pass to INDRA DB
    INDRA_NAME_VARIANTS = {
        # INDRA uses short gene symbols
        "c-reactive protein": ["CRP"],
        "interleukin-6": ["IL6", "IL-6"],
        "interleukin 6": ["IL6", "IL-6"],
        "tumor necrosis factor": ["TNF", "TNF-alpha"],

        # INDRA uses full names for processes
        "ros": ["reactive oxygen species"],
        "oxidative stress": ["reactive oxygen species", "oxidative stress response"],

        # INDRA environmental variations (if they exist)
        "pm2.5": ["Particulate Matter", "PM2.5", "particulates"],
        "particulate matter": ["Particulate Matter", "PM2.5"],

        # NF-κB variations
        "nf-kappa-b": ["NFKB1", "NF-kappaB", "NF-kB"],
        "nfkb": ["NFKB1"],
    }

    def __init__(self, local_ontology=None, use_gilda: bool = True):
        """Initialize with optional Gilda grounding.

        Args:
            local_ontology: LocalOntologyAdapter for MeSH ontology lookups (DEPRECATED - causes imprecise matches)
            use_gilda: If True, use Gilda for precise entity grounding (RECOMMENDED)
        """
        self.local_ontology = local_ontology
        self.use_gilda = use_gilda
        self.cache: Dict[str, List[str]] = {}

        # Lazy-import Gilda to avoid import errors if not installed
        self._gilda = None
        if use_gilda:
            try:
                import gilda
                self._gilda = gilda
                logger.info("Gilda grounding enabled (INDRA's official grounding service)")
            except ImportError:
                logger.warning("Gilda not installed - falling back to INDRA name variants only")
                logger.warning("Install with: pip install gilda")

    async def get_all_synonyms(self, entity: str) -> List[str]:
        """Get ALL ways to refer to this entity for INDRA search.

        This is the core method the agent uses to search exhaustively.

        Sources:
        1. Original name (as-is, lowercase, uppercase)
        2. Local ontology MeSH synonyms (Memgraph)
        3. INDRA-specific name variants
        4. Database IDs (MESH:D052638, HGNC:2367)

        Args:
            entity: Entity name from user query or LLM extraction

        Returns:
            List of all synonym variants to query INDRA with

        Example:
            >>> await get_all_synonyms("PM2.5")
            ["PM2.5", "pm2.5", "Particulate Matter", "particulate matter",
             "particulates", "fine particulate matter", "MESH:D052638"]
        """
        if entity in self.cache:
            return self.cache[entity]

        synonyms: Set[str] = set()

        # Add original name variants
        synonyms.add(entity)
        synonyms.add(entity.lower())
        synonyms.add(entity.upper())

        # Use Gilda for precise entity grounding (INDRA's official grounding service)
        if self.use_gilda and self._gilda:
            try:
                # Gilda.ground() returns list of ScoredMatch objects
                # ScoredMatch has attributes: term (with .entry_name, .db, .id), score, text
                results = self._gilda.ground(entity)

                if results:
                    # Take top 3 grounding results (high confidence matches)
                    for result in results[:3]:
                        # Add term entry name
                        synonyms.add(result.term.entry_name)

                        # Add the matched text variant
                        if hasattr(result, 'text'):
                            synonyms.add(result.text)

                        # Add database IDs (INDRA accepts namespace:ID format)
                        db = result.term.db
                        db_id = result.term.id

                        if db == 'CHEBI':
                            synonyms.add(f"CHEBI:{db_id}")
                            # Don't add double prefix - Gilda already includes it
                        elif db == 'HGNC':
                            synonyms.add(f"HGNC:{db_id}")
                        elif db == 'GO':
                            synonyms.add(f"GO:{db_id}")
                        elif db == 'MESH':
                            synonyms.add(f"MESH:{db_id}")
                        elif db == 'UP':  # UniProt
                            synonyms.add(f"UP:{db_id}")

                    logger.debug(f"Gilda found {len(results)} grounding results for '{entity}' (using top 3)")
            except Exception as e:
                logger.warning(f"Gilda grounding failed for {entity}: {e}")

        # Add INDRA-specific variants
        entity_lower = entity.lower()
        if entity_lower in self.INDRA_NAME_VARIANTS:
            synonyms.update(self.INDRA_NAME_VARIANTS[entity_lower])

        # Add common abbreviation expansions
        # (e.g., "IL-6" → "IL6", "NF-κB" → "NFKB1")
        if "-" in entity:
            synonyms.add(entity.replace("-", ""))
        if " " in entity:
            synonyms.add(entity.replace(" ", ""))

        result = sorted(list(synonyms))
        self.cache[entity] = result

        grounding_source = "Gilda" if (self.use_gilda and self._gilda) else "INDRA variants only"
        logger.info(f"Expanded '{entity}' → {len(result)} synonyms via {grounding_source}")
        return result

    async def get_canonical(self, entity: str) -> str:
        """Get ONE canonical name for display to user.

        Priority:
        1. Local ontology MeSH label (authoritative)
        2. Original entity name (as provided)

        Args:
            entity: Entity name

        Returns:
            Canonical name for user display

        Example:
            >>> await get_canonical("pm2.5")
            "Particulate Matter"
        """
        if self.local_ontology:
            try:
                mesh_result = await self.local_ontology.find_mesh_term(entity)
                if mesh_result:
                    return mesh_result["mesh_label"]
            except Exception as e:
                logger.debug(f"Local ontology lookup failed for {entity}: {e}")

        # Fallback: return original name
        return entity

    async def get_mesh_id(self, entity: str) -> Optional[str]:
        """Get MeSH ID for entity (for CTD integration).

        Args:
            entity: Entity name

        Returns:
            MeSH ID (e.g., "D052638") or None
        """
        if not self.local_ontology:
            return None

        try:
            mesh_result = await self.local_ontology.find_mesh_term(entity)
            if mesh_result:
                return mesh_result["mesh_id"]
        except Exception as e:
            logger.debug(f"Local ontology lookup failed for {entity}: {e}")

        return None

    def clear_cache(self):
        """Clear synonym cache."""
        self.cache.clear()
        logger.info("Synonym cache cleared")
