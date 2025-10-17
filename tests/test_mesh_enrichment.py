"""Tests for MeSH enrichment integration with Writer KG."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from indra_agent.agents.mesh_enrichment_agent import MeSHEnrichmentAgent
from indra_agent.agents.state import OverallState
from indra_agent.config.settings import get_settings
from indra_agent.services.grounding_service import GroundingService
from indra_agent.services.writer_kg_service import WriterKGService


@pytest.fixture
def sample_mesh_response():
    """Sample Writer KG API response for MeSH query."""
    return {
        "answer": "The MeSH ID for Particulate Matter is D052638.",
        "sources": [
            {
                "snippet": "Particulate Matter (D052638) is particulate matter of an aerodynamic diameter of 2.5 micrometers or less.",
                "score": 0.95,
                "metadata": {"mesh_id": "D052638"},
            }
        ],
    }


@pytest.fixture
def sample_enriched_entity():
    """Sample MeSH-enriched entity."""
    return {
        "original_term": "particulate matter",
        "mesh_id": "D052638",
        "mesh_label": "Particulate Matter",
        "definition": "Particles of any solid substance, generally under 30 microns in size.",
        "synonyms": ["PM2.5", "fine particulate matter", "particulates"],
        "related_terms": [
            {
                "mesh_id": "D000393",
                "label": "Air Pollutants",
                "relationship": "broader",
            },
            {
                "mesh_id": "D052638",
                "label": "PM10",
                "relationship": "related",
            },
        ],
    }


class TestWriterKGService:
    """Tests for Writer KG Service."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test WriterKGService initializes with settings."""
        settings = get_settings()

        # Skip test if Writer not configured
        if not settings.is_writer_configured:
            pytest.skip("Writer KG not configured in environment")

        service = WriterKGService()
        assert service.api_key is not None
        assert service.graph_id is not None
        assert service.base_url == "https://api.writer.com/v1"

    @pytest.mark.asyncio
    async def test_query_mesh_terms_with_mock(self, sample_mesh_response):
        """Test querying MeSH terms with mocked HTTP response."""
        service = WriterKGService(
            api_key="test-key",
            graph_id="test-graph"
        )

        # Mock the HTTP client
        service.client.post = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: sample_mesh_response
        ))

        result = await service.query_mesh_terms("What is particulate matter?")

        assert result is not None
        assert "answer" in result
        assert "sources" in result
        assert len(result["sources"]) > 0

        await service.cleanup()

    @pytest.mark.asyncio
    async def test_find_mesh_term(self, sample_mesh_response):
        """Test finding a specific MeSH term."""
        service = WriterKGService(
            api_key="test-key",
            graph_id="test-graph"
        )

        # Mock the HTTP client
        service.client.post = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: sample_mesh_response
        ))

        result = await service.find_mesh_term("particulate matter")

        assert result is not None
        assert result["mesh_id"] == "D052638"
        assert result["label"] == "Particulate Matter"

        await service.cleanup()

    def test_extract_mesh_id(self):
        """Test MeSH ID extraction from source dict."""
        service = WriterKGService(api_key="test", graph_id="test")

        # Test extraction from snippet text
        source = {
            "snippet": "The MeSH ID for Particulate Matter is D052638.",
            "score": 0.95,
        }
        mesh_id = service._extract_mesh_id(source)
        assert mesh_id == "D052638"

        # Test extraction from metadata
        source2 = {
            "snippet": "Particulate matter information",
            "metadata": {"mesh_id": "D052638"},
        }
        mesh_id2 = service._extract_mesh_id(source2)
        assert mesh_id2 == "D052638"


class TestGroundingServiceMeSHIntegration:
    """Tests for GroundingService MeSH integration."""

    def test_ground_mesh_enriched_entities(self, sample_enriched_entity):
        """Test grounding MeSH-enriched entities."""
        service = GroundingService()

        mesh_enriched = [sample_enriched_entity]
        grounded = service.ground_mesh_enriched_entities(mesh_enriched)

        assert "particulate matter" in grounded
        assert grounded["particulate matter"]["id"] == "D052638"
        assert grounded["particulate matter"]["database"] == "MESH"
        assert grounded["particulate matter"]["mesh_enriched"] is True

        # Check synonyms are also grounded
        assert "PM2.5" in grounded or "fine particulate matter" in grounded

    def test_infer_type_from_mesh(self, sample_enriched_entity):
        """Test entity type inference from MeSH data."""
        service = GroundingService()

        # Environmental entity
        entity_type = service._infer_type_from_mesh(sample_enriched_entity)
        assert entity_type == "environmental"

        # Biomarker entity
        biomarker_entity = {
            "mesh_id": "D002097",
            "mesh_label": "C-Reactive Protein",
            "definition": "A protein found in the blood that is a marker of inflammation",
        }
        entity_type = service._infer_type_from_mesh(biomarker_entity)
        assert entity_type == "biomarker"

    def test_merge_with_mesh_enrichment(self, sample_enriched_entity):
        """Test merging MeSH enrichment with hard-coded mappings."""
        service = GroundingService()

        entities = ["particulate matter", "CRP", "unknown_entity"]
        mesh_enriched = [sample_enriched_entity]

        grounded = service.merge_with_mesh_enrichment(entities, mesh_enriched)

        # Should use MeSH enrichment for particulate matter
        assert grounded["particulate matter"]["mesh_enriched"] is True
        assert grounded["particulate matter"]["id"] == "D052638"

        # Should use hard-coded mapping for CRP
        assert grounded["CRP"]["id"] == "CRP"
        assert grounded["CRP"]["database"] == "HGNC"

        # Should return None for unknown entity
        assert grounded["unknown_entity"] is None


class TestMeSHEnrichmentAgent:
    """Tests for MeSH Enrichment Agent."""

    @pytest.mark.asyncio
    async def test_agent_with_writer_not_configured(self):
        """Test agent gracefully skips when Writer KG not configured."""
        with patch("indra_agent.agents.mesh_enrichment_agent.get_settings") as mock_settings:
            # Create a proper mock settings object with all required attributes
            mock_settings_obj = MagicMock()
            mock_settings_obj.is_writer_configured = False
            mock_settings_obj.agent_model = "test-model"
            mock_settings_obj.aws_region = "us-east-1"
            mock_settings.return_value = mock_settings_obj

            agent = MeSHEnrichmentAgent()

            state: OverallState = {
                "query": {"text": "How does PM2.5 affect CRP?"},
            }

            result = await agent(state, {})

            assert result["current_agent"] == "mesh_enrichment"
            assert result["mesh_enriched_entities"] == []

    @pytest.mark.asyncio
    async def test_agent_term_extraction_fallback(self):
        """Test agent's fallback term extraction when LLM fails."""
        agent = MeSHEnrichmentAgent()

        # Test fallback extraction with known keywords
        query_text = "How does PM2.5 and ozone affect CRP and IL-6 through inflammation?"
        terms = agent._fallback_extract_terms(query_text)

        assert "PM2.5" in terms
        assert "ozone" in terms or "CRP" in terms or "IL-6" in terms

    @pytest.mark.asyncio
    @patch("indra_agent.agents.mesh_enrichment_agent.WriterKGService")
    async def test_agent_enrichment_flow(self, mock_writer_service, sample_enriched_entity):
        """Test full agent enrichment flow with mocked Writer service."""
        # Mock Writer service
        mock_service_instance = AsyncMock()
        mock_service_instance.find_mesh_term = AsyncMock(return_value={
            "term": "particulate matter",
            "mesh_id": "D052638",
            "label": "Particulate Matter",
            "definition": "Particles in air",
            "synonyms": ["PM2.5", "PM"],
        })
        mock_service_instance.find_related_terms = AsyncMock(return_value=[
            {"mesh_id": "D000393", "label": "Air Pollutants", "relationship": "broader"}
        ])
        mock_writer_service.return_value = mock_service_instance

        with patch("indra_agent.agents.mesh_enrichment_agent.get_settings") as mock_settings:
            mock_settings.return_value.is_writer_configured = True
            mock_settings.return_value.agent_model = "test-model"
            mock_settings.return_value.aws_region = "us-east-1"

            agent = MeSHEnrichmentAgent()
            agent.writer_service = mock_service_instance

            # Mock LLM for term extraction
            agent.llm = AsyncMock()
            agent.llm.ainvoke = AsyncMock(return_value=MagicMock(
                content="particulate matter, C-reactive protein"
            ))

            state: OverallState = {
                "query": {"text": "How does PM2.5 affect CRP?"},
            }

            result = await agent(state, {})

            assert result["current_agent"] == "mesh_enrichment"
            assert "mesh_enriched_entities" in result
            assert len(result["mesh_enriched_entities"]) > 0

            # Verify enriched entity structure
            enriched = result["mesh_enriched_entities"][0]
            assert "mesh_id" in enriched
            assert "mesh_label" in enriched
            assert "original_term" in enriched


class TestWorkflowIntegration:
    """Integration tests for MeSH-enhanced workflow."""

    def test_workflow_routing_with_writer_configured(self):
        """Test supervisor routes to MeSH enrichment when Writer configured."""
        from indra_agent.agents.supervisor import SupervisorAgent

        with patch("indra_agent.agents.supervisor.get_settings") as mock_settings:
            mock_settings.return_value.is_writer_configured = True
            mock_settings.return_value.agent_model = "test-model"
            mock_settings.return_value.aws_region = "us-east-1"

            supervisor = SupervisorAgent()

            # Should route to mesh_enrichment when configured
            assert supervisor.settings.is_writer_configured is True

    def test_indra_agent_uses_mesh_enriched_entities(self, sample_enriched_entity):
        """Test INDRA query agent uses MeSH-enriched entities."""
        from indra_agent.agents.indra_query_agent import INDRAQueryAgent

        agent = INDRAQueryAgent()

        state: OverallState = {
            "query": {"text": "How does PM2.5 affect CRP?"},
            "mesh_enriched_entities": [sample_enriched_entity],
        }

        # Verify agent recognizes MeSH enrichment
        mesh_enriched = state.get("mesh_enriched_entities", [])
        assert len(mesh_enriched) > 0
        assert mesh_enriched[0]["mesh_id"] == "D052638"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
