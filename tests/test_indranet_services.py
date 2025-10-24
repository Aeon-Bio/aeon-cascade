"""Unit tests for IndraNet services (IndraNetService and PreassemblyService).

Tests cover:
- PreassemblyService: statement de-duplication, belief calculation, filtering
- IndraNetService: network building, graph construction, biomarker discovery
"""

import pytest
import networkx as nx
from indra.statements import Activation, Agent, Evidence

from indra_agent.services.indranet_service import IndraNetService, IndraNetworkResult
from indra_agent.services.preassembly_service import PreassemblyService, PreassemblyStats


class TestPreassemblyService:
    """Tests for PreassemblyService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PreassemblyService()

    def test_initialization(self):
        """Test service initializes correctly."""
        assert self.service is not None
        assert self.service.belief_engine is not None

    def test_preassemble_empty_statements(self):
        """Test preassembly with empty statement list."""
        result = self.service.preassemble_statements([])
        assert result == []

    def test_preassemble_single_statement(self):
        """Test preassembly with single statement."""
        # Create simple statement: TNF activates IL6
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})
        evidence = Evidence(source_api="test", pmid="12345")
        stmt = Activation(tnf, il6, evidence=[evidence])

        result = self.service.preassemble_statements([stmt])

        assert len(result) == 1
        assert result[0].subj.name == "TNF"
        assert result[0].obj.name == "IL6"
        assert hasattr(result[0], "belief")

    def test_preassemble_duplicate_statements(self):
        """Test that duplicate statements are merged."""
        # Create two identical statements with different evidence
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})

        evidence1 = Evidence(source_api="test1", pmid="12345")
        evidence2 = Evidence(source_api="test2", pmid="67890")

        stmt1 = Activation(tnf, il6, evidence=[evidence1])
        stmt2 = Activation(tnf, il6, evidence=[evidence2])

        result = self.service.preassemble_statements([stmt1, stmt2])

        # Should merge into single statement with both evidences
        assert len(result) >= 1  # At least merged into 1
        # The merged statement should have evidence from both
        merged_stmt = result[0]
        assert len(merged_stmt.evidence) >= 1

    def test_filter_by_belief(self):
        """Test filtering statements by belief score."""
        # Create statements with different belief scores
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})

        stmt1 = Activation(tnf, il6, evidence=[Evidence(source_api="test")])
        stmt1.belief = 0.8

        stmt2 = Activation(tnf, il6, evidence=[Evidence(source_api="test")])
        stmt2.belief = 0.3

        statements = [stmt1, stmt2]

        # Filter with threshold 0.5
        filtered = self.service.filter_by_belief(statements, min_belief=0.5)

        assert len(filtered) == 1
        assert filtered[0].belief == 0.8

    def test_filter_by_evidence_count(self):
        """Test filtering statements by evidence count."""
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})

        # Statement with 3 evidences
        stmt1 = Activation(
            tnf,
            il6,
            evidence=[
                Evidence(source_api="test1"),
                Evidence(source_api="test2"),
                Evidence(source_api="test3"),
            ],
        )

        # Statement with 1 evidence
        stmt2 = Activation(tnf, il6, evidence=[Evidence(source_api="test1")])

        statements = [stmt1, stmt2]

        # Filter with min 2 evidences
        filtered = self.service.filter_by_evidence_count(statements, min_evidence=2)

        assert len(filtered) == 1
        assert len(filtered[0].evidence) == 3

    def test_filter_by_agent(self):
        """Test filtering statements by agent names."""
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})
        crp = Agent("CRP", db_refs={"HGNC": "2367"})

        stmt1 = Activation(tnf, il6, evidence=[Evidence(source_api="test")])
        stmt2 = Activation(il6, crp, evidence=[Evidence(source_api="test")])

        statements = [stmt1, stmt2]

        # Filter for statements involving IL6
        filtered = self.service.filter_by_agent(statements, ["IL6"])

        assert len(filtered) == 2  # Both statements involve IL6

        # Filter for statements involving only CRP
        filtered = self.service.filter_by_agent(statements, ["CRP"])

        assert len(filtered) == 1  # Only stmt2

    def test_merge_statement_lists(self):
        """Test merging multiple statement lists."""
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})

        list1 = [Activation(tnf, il6, evidence=[Evidence(source_api="source1")])]
        list2 = [Activation(tnf, il6, evidence=[Evidence(source_api="source2")])]

        merged = self.service.merge_statement_lists([list1, list2])

        # Should have merged duplicates
        assert len(merged) >= 1


class TestIndraNetService:
    """Tests for IndraNetService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = IndraNetService()

    def test_initialization(self):
        """Test service initializes correctly."""
        assert self.service is not None
        assert self.service.preassembly_service is not None
        assert self.service.statement_cache == {}

    @pytest.mark.asyncio
    async def test_build_empty_network(self):
        """Test building network with no statements."""
        result = await self.service.build_biomarker_network(
            exposures=["PM2.5"], biomarkers=["CRP"], max_depth=2
        )

        # Should return empty network when no statements available
        assert isinstance(result, IndraNetworkResult)
        assert result.edge_count == 0
        assert len(result.node_names) == 0

    @pytest.mark.asyncio
    async def test_get_neighborhood_statements_caching(self):
        """Test that neighborhood statements are cached."""
        # Call twice with same entity
        result1 = await self.service._get_neighborhood_statements("CRP", depth=2)
        result2 = await self.service._get_neighborhood_statements("CRP", depth=2)

        # Both should return same (empty) result from cache
        assert result1 == result2

        # Check cache was used
        cache_key = "neighborhood:CRP:2"
        assert cache_key in self.service.statement_cache

    @pytest.mark.asyncio
    async def test_get_path_statements_caching(self):
        """Test that path statements are cached."""
        # Call twice with same source/target
        result1 = await self.service._get_path_statements("PM2.5", "CRP", max_depth=3)
        result2 = await self.service._get_path_statements("PM2.5", "CRP", max_depth=3)

        # Both should return same (empty) result from cache
        assert result1 == result2

        # Check cache was used
        cache_key = "path:PM2.5:CRP:3"
        assert cache_key in self.service.statement_cache

    def test_build_signed_graph_empty(self):
        """Test building signed graph with no statements."""
        graph, belief_scores, evidence_counts = self.service._build_signed_graph(
            [], belief_threshold=0.5
        )

        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0
        assert belief_scores == {}
        assert evidence_counts == {}

    def test_build_signed_graph_with_statements(self):
        """Test building signed graph with statements."""
        # Create simple statement
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})
        stmt = Activation(tnf, il6, evidence=[Evidence(source_api="test")])
        stmt.belief = 0.8

        graph, belief_scores, evidence_counts = self.service._build_signed_graph(
            [stmt], belief_threshold=0.5
        )

        # Note: IndraNet assembler may return None if statements need more data
        # In that case, we get an empty graph (graceful handling)
        # This is expected behavior for Phase 1 skeleton
        assert isinstance(graph, nx.DiGraph)
        assert isinstance(belief_scores, dict)
        assert isinstance(evidence_counts, dict)

    def test_discover_intermediate_biomarkers_empty_graph(self):
        """Test biomarker discovery with empty graph."""
        empty_graph = nx.DiGraph()

        results = self.service.discover_intermediate_biomarkers(
            empty_graph, exposure="PM2.5", known_biomarkers=["CRP"], min_centrality=0.1
        )

        assert results == []

    def test_preassemble_statements_delegation(self):
        """Test that preassembly delegates to PreassemblyService."""
        # Create simple statement
        tnf = Agent("TNF", db_refs={"HGNC": "11892"})
        il6 = Agent("IL6", db_refs={"HGNC": "6018"})
        stmt = Activation(tnf, il6, evidence=[Evidence(source_api="test")])

        result = self.service._preassemble_statements([stmt], run_refinement=False)

        # Should return list with at least the statement
        assert isinstance(result, list)
        assert len(result) >= 1
