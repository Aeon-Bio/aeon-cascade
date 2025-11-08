"""Memgraph Graph Database Client.

Provides async interface to Memgraph for graph queries and path finding.
Uses Bolt protocol via neo4j-driver (Memgraph is Cypher-compatible).
"""

import logging
from typing import Dict, List, Optional, Set

try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    AsyncDriver = None

logger = logging.getLogger(__name__)


class MemgraphClient:
    """Async client for Memgraph graph database.

    Uses Neo4j driver (compatible with Memgraph's Bolt protocol).
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "",
        password: str = "",
        database: str = "memgraph"
    ):
        """Initialize Memgraph client.

        Args:
            uri: Bolt URI (default: bolt://localhost:7687)
            username: Auth username (empty for no auth)
            password: Auth password
            database: Database name (default: memgraph)
        """
        if not NEO4J_AVAILABLE:
            raise ImportError("neo4j driver not installed. Run: pip install neo4j")

        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver: Optional[AsyncDriver] = None

    async def connect(self):
        """Establish connection to Memgraph."""
        if self.driver:
            return

        auth = (self.username, self.password) if self.username else None
        self.driver = AsyncGraphDatabase.driver(self.uri, auth=auth)
        await self.verify_connectivity()
        logger.info(f"Connected to Memgraph at {self.uri}")

    async def verify_connectivity(self):
        """Verify connection to Memgraph."""
        async with self.driver.session(database=self.database) as session:
            result = await session.run("RETURN 1 AS num")
            record = await result.single()
            assert record["num"] == 1

    async def close(self):
        """Close connection to Memgraph."""
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def execute(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute Cypher query and return results.

        Args:
            query: Cypher query string
            params: Query parameters

        Returns:
            List of result records as dicts
        """
        if not self.driver:
            await self.connect()

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, params or {})
            records = await result.data()
            return records

    # ==================== Entity Operations ====================

    async def create_entity(
        self,
        entity_id: str,
        name: str,
        namespace: str,
        definition: Optional[str] = None,
        synonyms: Optional[List[str]] = None,
        xrefs: Optional[Dict[str, str]] = None
    ):
        """Create ontology entity node.

        Args:
            entity_id: Unique ID (e.g., "mesh:D052638")
            name: Entity name
            namespace: Database namespace (MESH, HGNC, GO, etc.)
            definition: Optional definition text
            synonyms: Optional list of synonyms
            xrefs: Optional cross-references to other databases
        """
        query = """
        MERGE (e:Entity {id: $id})
        SET e.name = $name,
            e.namespace = $namespace,
            e.definition = $definition,
            e.synonyms = $synonyms,
            e.xrefs = $xrefs
        RETURN e
        """
        await self.execute(query, {
            "id": entity_id,
            "name": name,
            "namespace": namespace,
            "definition": definition or "",
            "synonyms": synonyms or [],
            "xrefs": xrefs or {}
        })

    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        stmt_type: str,
        belief: float,
        evidence_count: int = 1,
        pmids: Optional[List[str]] = None
    ):
        """Create causal relationship between entities.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            stmt_type: Statement type (e.g., "Activation", "Phosphorylation")
            belief: INDRA belief score [0, 1]
            evidence_count: Number of supporting papers
            pmids: Optional list of PubMed IDs
        """
        query = """
        MATCH (source:Entity {id: $source_id})
        MERGE (target:Entity {id: $target_id})
        ON CREATE SET target.name = $target_id, target.namespace = split($target_id, ':')[0]
        MERGE (source)-[r:CAUSAL]->(target)
        SET r.stmt_type = $stmt_type,
            r.belief = $belief,
            r.evidence_count = $evidence_count,
            r.pmids = $pmids
        RETURN r
        """
        await self.execute(query, {
            "source_id": source_id,
            "target_id": target_id,
            "stmt_type": stmt_type,
            "belief": belief,
            "evidence_count": evidence_count,
            "pmids": pmids or []
        })

    async def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID.

        Args:
            entity_id: Entity ID (e.g., "mesh:D052638")

        Returns:
            Entity dict or None if not found
        """
        query = "MATCH (e:Entity {id: $id}) RETURN e"
        results = await self.execute(query, {"id": entity_id})
        if results:
            return results[0]["e"]
        return None

    # ==================== Search Operations ====================

    async def search_entities(
        self,
        prefix: str,
        limit: int = 10,
        namespaces: Optional[List[str]] = None
    ) -> List[Dict]:
        """Fuzzy search for entities by name prefix.

        Args:
            prefix: Text prefix to search
            limit: Maximum results
            namespaces: Optional namespace filter

        Returns:
            List of matching entities
        """
        # Case-insensitive search with null handling
        prefix_lower = prefix.lower()

        if namespaces:
            query = """
            MATCH (e:Entity)
            WHERE e.namespace IN $namespaces
              AND e.name IS NOT NULL
              AND (toLower(e.name) CONTAINS $prefix_lower OR
                   toLower(e.name) STARTS WITH $prefix_lower OR
                   ANY(syn IN e.synonyms WHERE syn IS NOT NULL AND (toLower(syn) CONTAINS $prefix_lower OR toLower(syn) STARTS WITH $prefix_lower)))
            RETURN e
            ORDER BY CASE
                WHEN toLower(e.name) = $prefix_lower THEN 0
                WHEN toLower(e.name) STARTS WITH $prefix_lower THEN 1
                ELSE 2
            END, e.name
            LIMIT $limit
            """
            params = {"prefix_lower": prefix_lower, "namespaces": namespaces, "limit": limit}
        else:
            query = """
            MATCH (e:Entity)
            WHERE e.name IS NOT NULL
              AND (toLower(e.name) CONTAINS $prefix_lower OR
                   toLower(e.name) STARTS WITH $prefix_lower OR
                   ANY(syn IN e.synonyms WHERE syn IS NOT NULL AND (toLower(syn) CONTAINS $prefix_lower OR toLower(syn) STARTS WITH $prefix_lower)))
            RETURN e
            ORDER BY CASE
                WHEN toLower(e.name) = $prefix_lower THEN 0
                WHEN toLower(e.name) STARTS WITH $prefix_lower THEN 1
                ELSE 2
            END, e.name
            LIMIT $limit
            """
            params = {"prefix_lower": prefix_lower, "limit": limit}

        results = await self.execute(query, params)
        return [r["e"] for r in results]

    # ==================== Path Finding ====================

    async def find_shortest_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3,
        allowed_namespaces: Optional[Set[str]] = None
    ) -> List[List[Dict]]:
        """Find shortest causal paths from source to target.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            max_depth: Maximum path length
            allowed_namespaces: Optional allowed intermediate namespaces

        Returns:
            List of paths, where each path is list of relationship dicts
        """
        if allowed_namespaces:
            # Filter intermediate nodes by namespace
            query = f"""
            MATCH path = (source:Entity {{id: $source_id}})-[r:CAUSAL*1..{max_depth}]->(target:Entity {{id: $target_id}})
            WHERE ALL(node IN nodes(path)[1..-1] WHERE node.namespace IN $namespaces)
            RETURN relationships(path) as rels,
                   [rel in relationships(path) | rel.belief] as beliefs
            ORDER BY size(rels), avg(beliefs) DESC
            LIMIT 10
            """
            params = {
                "source_id": source_id,
                "target_id": target_id,
                "namespaces": list(allowed_namespaces)
            }
        else:
            query = f"""
            MATCH path = (source:Entity {{id: $source_id}})-[r:CAUSAL*1..{max_depth}]->(target:Entity {{id: $target_id}})
            RETURN relationships(path) as rels,
                   [rel in relationships(path) | rel.belief] as beliefs
            ORDER BY size(rels), avg(beliefs) DESC
            LIMIT 10
            """
            params = {"source_id": source_id, "target_id": target_id}

        results = await self.execute(query, params)
        paths = []
        for record in results:
            path = []
            for rel in record["rels"]:
                path.append({
                    "type": rel["type"],
                    "belief": rel["belief"],
                    "evidence_count": rel.get("evidence_count", 1),
                    "pmids": rel.get("pmids", [])
                })
            paths.append(path)
        return paths

    async def find_shared_regulators(
        self,
        biomarker_ids: List[str],
        min_belief: float = 0.5,
        max_depth: int = 2
    ) -> List[Dict]:
        """Find common upstream regulators of multiple biomarkers.

        Args:
            biomarker_ids: List of target entity IDs
            min_belief: Minimum belief threshold
            max_depth: Maximum distance from regulator to biomarkers

        Returns:
            List of regulator entities with target counts
        """
        query = f"""
        MATCH (regulator:Entity)-[r:CAUSAL*1..{max_depth}]->(biomarker:Entity)
        WHERE biomarker.id IN $biomarker_ids AND
              ALL(rel IN r WHERE rel.belief >= $min_belief)
        WITH regulator, collect(DISTINCT biomarker.id) as targets
        WHERE size(targets) >= 2
        RETURN regulator, targets, size(targets) as target_count
        ORDER BY target_count DESC, regulator.name
        LIMIT 20
        """
        results = await self.execute(query, {
            "biomarker_ids": biomarker_ids,
            "min_belief": min_belief
        })

        regulators = []
        for record in results:
            reg = record["regulator"]
            regulators.append({
                "id": reg["id"],
                "name": reg["name"],
                "namespace": reg["namespace"],
                "targets": record["targets"],
                "target_count": record["target_count"]
            })
        return regulators

    async def get_neighbors(
        self,
        entity_id: str,
        direction: str = "out",
        limit: int = 20
    ) -> List[Dict]:
        """Get neighboring entities (interactors).

        Args:
            entity_id: Entity ID
            direction: "out" (outgoing), "in" (incoming), or "both"
            limit: Maximum neighbors

        Returns:
            List of neighbor entities with relationship info
        """
        if direction == "out":
            query = """
            MATCH (e:Entity {id: $entity_id})-[r:CAUSAL]->(neighbor:Entity)
            RETURN neighbor, r
            ORDER BY r.belief DESC
            LIMIT $limit
            """
        elif direction == "in":
            query = """
            MATCH (e:Entity {id: $entity_id})<-[r:CAUSAL]-(neighbor:Entity)
            RETURN neighbor, r
            ORDER BY r.belief DESC
            LIMIT $limit
            """
        else:  # both
            query = """
            MATCH (e:Entity {id: $entity_id})-[r:CAUSAL]-(neighbor:Entity)
            RETURN neighbor, r
            ORDER BY r.belief DESC
            LIMIT $limit
            """

        results = await self.execute(query, {"entity_id": entity_id, "limit": limit})
        neighbors = []
        for record in results:
            neighbor = record["neighbor"]
            rel = record["r"]
            neighbors.append({
                "id": neighbor["id"],
                "name": neighbor["name"],
                "namespace": neighbor["namespace"],
                "stmt_type": rel["type"],
                "belief": rel["belief"],
                "evidence_count": rel.get("evidence_count", 1)
            })
        return neighbors

    # ==================== Admin Operations ====================

    async def create_indexes(self):
        """Create indexes for performance."""
        queries = [
            "CREATE INDEX ON :Entity(id);",
            "CREATE INDEX ON :Entity(name);",
            "CREATE INDEX ON :Entity(namespace);"
        ]
        for query in queries:
            try:
                await self.execute(query)
                logger.info(f"Created index: {query}")
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {e}")

    async def clear_database(self):
        """Delete all nodes and relationships. USE WITH CAUTION."""
        await self.execute("MATCH (n) DETACH DELETE n")
        logger.warning("Database cleared!")

    async def get_stats(self) -> Dict:
        """Get database statistics.

        Returns:
            Dict with node counts, relationship counts, etc.
        """
        queries = {
            "total_entities": "MATCH (n:Entity) RETURN count(n) as count",
            "total_relationships": "MATCH ()-[r:CAUSAL]->() RETURN count(r) as count",
            "namespaces": "MATCH (n:Entity) RETURN DISTINCT n.namespace as namespace, count(n) as count ORDER BY count DESC"
        }

        stats = {}
        stats["total_entities"] = (await self.execute(queries["total_entities"]))[0]["count"]
        stats["total_relationships"] = (await self.execute(queries["total_relationships"]))[0]["count"]

        namespace_results = await self.execute(queries["namespaces"])
        stats["namespaces"] = {r["namespace"]: r["count"] for r in namespace_results}

        return stats
