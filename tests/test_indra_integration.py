"""Integration tests for INDRA Network Search API.

Tests actual API calls to verify our implementation matches the OpenAPI schema.
"""

import pytest
import httpx
from indra_agent.services.indra_service import INDRAService


@pytest.mark.asyncio
async def test_indra_health_check():
    """Test INDRA API health endpoint."""
    service = INDRAService()
    try:
        is_healthy = await service.health_check()
        assert is_healthy, "INDRA API should be healthy"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_indra_autocomplete():
    """Test INDRA autocomplete endpoint."""
    service = INDRAService()
    try:
        # Test autocomplete for CRP
        matches = await service.autocomplete_entity("CRP", limit=5)
        assert len(matches) > 0, "Should find matches for CRP"

        # Verify response structure
        first_match = matches[0]
        assert "name" in first_match
        assert "database" in first_match
        assert "id" in first_match

        # CRP should match HGNC
        crp_match = next((m for m in matches if m["database"] == "HGNC"), None)
        assert crp_match is not None, "Should find HGNC entry for CRP"
        assert crp_match["id"] == "2367", "CRP should be HGNC:2367"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_indra_node_resolution():
    """Test INDRA node resolution endpoints."""
    service = INDRAService()
    try:
        # Test node-name-in-graph
        node = await service.resolve_node_by_name("CRP")
        assert node is not None, "Should find CRP node"
        assert node.get("namespace") == "HGNC"
        assert node.get("identifier") == "2367"

        # Test with invalid node
        invalid = await service.resolve_node_by_name("NOTAREALNODE123")
        assert invalid is None, "Should return None for invalid node"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_indra_query_endpoint():
    """Test INDRA /query endpoint with actual API call.

    This tests the core path search functionality.
    """
    service = INDRAService()
    try:
        # Query for simple path: IL6 -> CRP (well-studied relationship)
        paths = await service.find_causal_paths(
            source="IL6",
            target="CRP",
            max_depth=2,
            use_cache=False  # Force live API call
        )

        if len(paths) == 0:
            pytest.skip("INDRA API returned no paths (may be temporary)")

        # Verify path structure
        assert len(paths) > 0, "Should find at least one path"
        path = paths[0]

        # Check nodes
        assert "nodes" in path
        assert len(path["nodes"]) >= 2, "Path should have at least 2 nodes"

        # Verify node structure
        for node in path["nodes"]:
            assert "id" in node
            assert "name" in node
            assert "grounding" in node
            assert "db" in node["grounding"]
            assert "id" in node["grounding"]

        # Check edges
        assert "edges" in path
        assert len(path["edges"]) >= 1, "Path should have at least 1 edge"

        # Verify edge structure
        for edge in path["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relationship" in edge
            assert edge["relationship"] in ["activates", "inhibits", "increases", "decreases"]
            assert "evidence_count" in edge
            assert edge["evidence_count"] > 0
            assert "belief" in edge
            assert 0 <= edge["belief"] <= 1
            assert "statement_type" in edge

    finally:
        await service.close()


@pytest.mark.asyncio
async def test_indra_response_parsing():
    """Test parsing of INDRA API response structure.

    Uses a known query to verify we correctly parse the OpenAPI schema.
    """
    service = INDRAService()

    # Create a mock response matching OpenAPI schema
    mock_response = {
        "query_hash": "test123",
        "time_limit": 30,
        "timed_out": False,
        "path_results": {
            "source": {"name": "IL6", "namespace": "HGNC", "identifier": "6018", "lookup": ""},
            "target": {"name": "CRP", "namespace": "HGNC", "identifier": "2367", "lookup": ""},
            "paths": {
                "IL6": [
                    {
                        "path": [
                            {"name": "IL6", "namespace": "HGNC", "identifier": "6018", "lookup": ""},
                            {"name": "CRP", "namespace": "HGNC", "identifier": "2367", "lookup": ""}
                        ],
                        "edge_data": [
                            {
                                "edge": [
                                    {"name": "IL6", "namespace": "HGNC", "identifier": "6018"},
                                    {"name": "CRP", "namespace": "HGNC", "identifier": "2367"}
                                ],
                                "statements": {
                                    "IncreaseAmount": {
                                        "stmt_type": "IncreaseAmount",
                                        "source_counts": {"reach": 100, "sparser": 50},
                                        "statements": [
                                            {
                                                "stmt_type": "IncreaseAmount",
                                                "evidence_count": 150,
                                                "stmt_hash": 12345678,
                                                "source_counts": {"reach": 100, "sparser": 50},
                                                "belief": 0.95,
                                                "curated": True,
                                                "english": "IL6 increases CRP",
                                                "db_url_hash": "https://db.indra.bio/statements/from_hash/12345678"
                                            }
                                        ]
                                    }
                                },
                                "belief": 0.95,
                                "weight": 0.05,
                                "db_url_edge": "https://db.indra.bio/..."
                            }
                        ]
                    }
                ]
            }
        }
    }

    # Parse the mock response
    paths = service._parse_path_response(mock_response)

    # Verify parsing
    assert len(paths) == 1
    path = paths[0]

    # Check nodes
    assert len(path["nodes"]) == 2
    assert path["nodes"][0]["name"] == "IL6"
    assert path["nodes"][1]["name"] == "CRP"

    # Check edges
    assert len(path["edges"]) == 1
    edge = path["edges"][0]
    assert edge["source"] == "IL6"
    assert edge["target"] == "CRP"
    assert edge["relationship"] == "increases"
    assert edge["evidence_count"] == 150  # Sum of source_counts
    assert edge["belief"] == 0.95
    assert edge["statement_type"] == "IncreaseAmount"


@pytest.mark.asyncio
async def test_indra_caching():
    """Test that caching works correctly."""
    service = INDRAService()
    try:
        # First call - should hit API or cache
        paths1 = await service.find_causal_paths("IL6", "CRP", max_depth=2, use_cache=True)

        # Second call - should hit runtime cache
        paths2 = await service.find_causal_paths("IL6", "CRP", max_depth=2, use_cache=True)

        # Should be the same
        assert len(paths1) == len(paths2)

    finally:
        await service.close()


@pytest.mark.asyncio
async def test_indra_entity_grounding():
    """Test complete entity grounding workflow."""
    service = INDRAService()
    try:
        # Ground PM2.5
        pm25 = await service.ground_entity("PM2.5")
        assert pm25 is not None
        # Should have name and grounding info
        assert "name" in pm25 or "database" in pm25

        # Ground CRP
        crp = await service.ground_entity("CRP")
        assert crp is not None

    finally:
        await service.close()
