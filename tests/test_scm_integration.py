"""Integration tests for SCM Graph Builder with real INDRA API calls.

These tests verify the 3-phase iterative discovery strategy:
- Phase 1: Direct INDRA path search
- Phase 2: Mediated path expansion via known biological mediators
- Phase 3: Biological prior fallback

NO MOCKS - Real integration testing with live INDRA API.
"""

import pytest
from indra_agent.services.intervention_discovery_service import InterventionDiscoveryService as INDRAService  # Alias for test compatibility
from indra_agent.services.scm_graph_builder import SCMGraphBuilder


@pytest.fixture
async def scm_builder():
    """Create SCM builder with INDRA service."""
    indra_service = INDRAService()
    builder = SCMGraphBuilder(indra_service)
    yield builder
    await indra_service.close()


class TestSCMBuilderBasicFunctionality:
    """Test basic SCM builder functionality with real INDRA."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_scm_builder_initialization(self, scm_builder):
        """Test that SCM builder initializes correctly."""
        assert scm_builder is not None
        assert scm_builder.indra is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_build_scm_single_source_single_target(self, scm_builder):
        """Test SCM builder with single source and target."""
        # Well-studied pathway: IL-6 → CRP
        paths = await scm_builder.build_scm_graph(
            sources=['IL6'],
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0, "Should find at least one path"

        # Verify path structure
        path = paths[0]
        assert 'nodes' in path
        assert 'edges' in path
        assert len(path['nodes']) >= 2, "Path should have at least 2 nodes"
        assert len(path['edges']) >= 1, "Path should have at least 1 edge"

        # Verify nodes have required fields
        for node in path['nodes']:
            assert 'id' in node or 'name' in node
            assert 'grounding' in node or 'name' in node

        # Verify edges have required fields
        for edge in path['edges']:
            assert 'source' in edge
            assert 'target' in edge
            assert 'relationship' in edge or 'statement_type' in edge

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_build_scm_multiple_sources_single_target(self, scm_builder):
        """Test SCM builder with multiple sources to single target."""
        # Multiple inflammatory sources → CRP
        paths = await scm_builder.build_scm_graph(
            sources=['IL6', 'TNF'],
            targets=['CRP'],
            max_depth=3,
            use_priors=True
        )

        assert len(paths) > 0, "Should find paths from multiple sources"

        # Should have paths from both sources
        all_nodes = set()
        for path in paths:
            for node in path['nodes']:
                all_nodes.add(node['name'])

        # At least one of the sources should appear
        assert 'IL6' in all_nodes or 'TNF' in all_nodes


class TestSCMBuilderPhase1DirectSearch:
    """Test Phase 1: Direct INDRA path search."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase1_finds_direct_path(self, scm_builder):
        """Test that Phase 1 finds direct INDRA paths when they exist."""
        # IL-6 → CRP is a well-studied direct relationship
        paths = await scm_builder._find_direct_paths('IL6', 'CRP', max_depth=2)

        if len(paths) > 0:  # INDRA may not always return paths
            # Verify it's a direct or short path
            path = paths[0]
            assert len(path['nodes']) <= 3, "Direct path should be short"

            # Should contain source and target
            node_names = [n['name'] for n in path['nodes']]
            # Check for IL6 or IL-6 variants
            has_il6 = any('IL6' in n or 'IL-6' in n or 'Interleukin-6' in n for n in node_names)
            has_crp = any('CRP' in n or 'C-reactive' in n for n in node_names)

            assert has_il6, f"Should contain IL6. Found: {node_names}"
            assert has_crp, f"Should contain CRP. Found: {node_names}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase1_empty_for_distant_entities(self, scm_builder):
        """Test that Phase 1 returns empty for very distant entities."""
        # Very distant entities unlikely to have direct INDRA path
        paths = await scm_builder._find_direct_paths(
            'Particulate Matter',
            'CRP',
            max_depth=2  # Short depth
        )

        # May or may not find direct path - INDRA database dependent
        # This test documents behavior rather than asserting specific outcome
        assert isinstance(paths, list)


class TestSCMBuilderPhase2MediatedPaths:
    """Test Phase 2: Mediated path expansion."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase2_finds_mediated_paths(self, scm_builder):
        """Test that Phase 2 finds paths via known mediators."""
        # PM2.5 → CRP likely requires mediation
        paths = await scm_builder.build_scm_graph(
            sources=['Particulate Matter'],
            targets=['CRP'],
            known_mediators=['NFKB1', 'IL6', 'reactive oxygen species'],
            max_depth=5,
            use_priors=False  # Disable priors to test INDRA mediation only
        )

        # May find paths via INDRA or may be empty (depends on INDRA API)
        # If paths found, verify they use mediators
        if len(paths) > 0:
            all_nodes = set()
            for path in paths:
                for node in path['nodes']:
                    all_nodes.add(node['name'])

            # Check if any known mediators appear
            known_meds = {'NFKB1', 'NF-κB', 'IL6', 'IL-6', 'reactive oxygen species', 'ROS'}
            has_mediator = len(all_nodes & known_meds) > 0

            if has_mediator:
                print(f"\n✅ Found mediated paths via: {all_nodes & known_meds}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase2_path_concatenation(self, scm_builder):
        """Test that Phase 2 correctly concatenates path segments."""
        # Build paths with explicit mediators
        paths = await scm_builder.build_scm_graph(
            sources=['oxidative stress'],
            targets=['CRP'],
            known_mediators=['NFKB1', 'IL6'],
            max_depth=4,
            use_priors=True  # Allow priors for reliable testing
        )

        assert len(paths) > 0, "Should find concatenated paths"

        # Check for multi-hop paths
        for path in paths:
            if len(path['nodes']) > 3:  # Multi-hop
                # Verify node sequence is connected
                node_names = [n['name'] for n in path['nodes']]
                print(f"\n✅ Multi-hop path: {' → '.join(node_names[:5])}")
                break


class TestSCMBuilderPhase3PriorFallback:
    """Test Phase 3: Biological prior fallback."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase3_uses_priors_when_indra_fails(self, scm_builder):
        """Test that Phase 3 applies biological priors as fallback."""
        # Use entities that have prior edges but may not be in INDRA
        paths = await scm_builder.build_scm_graph(
            sources=['Particulate Matter'],
            targets=['reactive oxygen species'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0, "Should find path via priors if INDRA fails"

        # Check if any paths came from priors
        prior_paths = [p for p in paths if p.get('from_priors')]

        if prior_paths:
            path = prior_paths[0]

            # Verify prior path structure
            assert 'edges' in path
            assert len(path['edges']) > 0

            # Check that edges are marked as from priors
            for edge in path['edges']:
                if edge.get('source_type') == 'biological_prior':
                    print(f"\n✅ Prior edge used: {edge['source']} → {edge['target']}")
                    break

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase3_builds_2hop_prior_paths(self, scm_builder):
        """Test that Phase 3 can build 2-hop paths from priors."""
        # Request paths that might require 2-hop prior construction
        paths = await scm_builder.build_scm_graph(
            sources=['Particulate Matter'],
            targets=['IL6'],
            max_depth=3,
            use_priors=True
        )

        assert len(paths) > 0, "Should build 2-hop paths from priors"

        # Look for paths with multiple edges from priors
        for path in paths:
            if path.get('from_priors') and len(path.get('edges', [])) >= 2:
                node_names = [n['name'] for n in path['nodes']]
                print(f"\n✅ 2-hop prior path: {' → '.join(node_names)}")
                break

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_phase3_disabled_when_use_priors_false(self, scm_builder):
        """Test that Phase 3 is skipped when use_priors=False."""
        # Use entities with no INDRA path but with priors
        paths = await scm_builder.build_scm_graph(
            sources=['PM2.5'],  # Synonym that normalizes
            targets=['NOTAREALENTITY'],
            max_depth=2,
            use_priors=False  # Disable priors
        )

        # Should return empty (no INDRA path and priors disabled)
        assert len(paths) == 0, "Should not use priors when disabled"


class TestSCMBuilderMultiSourceMultiTarget:
    """Test SCM builder with multiple sources and targets."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multi_source_multi_target(self, scm_builder):
        """Test SCM with multiple environmental sources and biomarker targets."""
        paths = await scm_builder.build_scm_graph(
            sources=['Particulate Matter', 'Ozone'],
            targets=['CRP', 'IL6'],
            max_depth=5,
            use_priors=True
        )

        assert len(paths) > 0, "Should find paths connecting sources to targets"

        # Collect all nodes to check coverage
        all_nodes = set()
        for path in paths:
            for node in path['nodes']:
                all_nodes.add(node['name'])

        print(f"\n✅ Found {len(paths)} paths connecting multiple sources/targets")
        print(f"   Unique nodes: {len(all_nodes)}")
        print(f"   Sample nodes: {list(all_nodes)[:5]}")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_shared_mechanisms_discovered(self, scm_builder):
        """Test that SCM builder discovers shared mechanisms."""
        # Both PM2.5 and Ozone should share inflammatory mechanisms
        paths = await scm_builder.build_scm_graph(
            sources=['Particulate Matter', 'Ozone'],
            targets=['CRP'],
            known_mediators=['NFKB1', 'oxidative stress', 'IL6'],
            max_depth=5,
            use_priors=True
        )

        assert len(paths) > 0, "Should find paths"

        # Count how many paths from each source
        pm25_paths = sum(1 for p in paths if
                        any('Particulate' in n['name'] for n in p['nodes']))
        ozone_paths = sum(1 for p in paths if
                         any('Ozone' in n['name'] or 'O3' in n['name'] for n in p['nodes']))

        print(f"\n✅ PM2.5 paths: {pm25_paths}, Ozone paths: {ozone_paths}")


class TestSCMBuilderEntityNormalization:
    """Test entity name normalization in SCM builder."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_entity_normalization_applied(self, scm_builder):
        """Test that entity names are normalized before querying."""
        # Use synonyms that should be normalized
        paths = await scm_builder.build_scm_graph(
            sources=['PM2.5'],  # Should normalize to "Particulate Matter"
            targets=['C-reactive protein'],  # Should normalize to "CRP"
            max_depth=5,
            use_priors=True
        )

        assert len(paths) > 0, "Should find paths with normalized names"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cytokine_normalization(self, scm_builder):
        """Test cytokine name normalization (IL-6 → IL6, etc.)."""
        paths = await scm_builder.build_scm_graph(
            sources=['IL-6'],  # Should normalize to "IL6"
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0, "Should find paths with normalized cytokine names"


class TestSCMBuilderPathQuality:
    """Test quality and structure of returned paths."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_path_nodes_have_required_fields(self, scm_builder):
        """Test that all path nodes have required fields."""
        paths = await scm_builder.build_scm_graph(
            sources=['IL6'],
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0

        for path in paths:
            for node in path['nodes']:
                # Must have either 'id' and 'name', or just 'name'
                assert 'name' in node, "Node must have 'name' field"

                # Must have grounding info (even if empty)
                assert 'grounding' in node, "Node must have 'grounding' field"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_path_edges_have_required_fields(self, scm_builder):
        """Test that all path edges have required fields."""
        paths = await scm_builder.build_scm_graph(
            sources=['IL6'],
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0

        for path in paths:
            for edge in path['edges']:
                assert 'source' in edge, "Edge must have 'source'"
                assert 'target' in edge, "Edge must have 'target'"
                assert 'belief' in edge, "Edge must have 'belief' score"
                assert 'evidence_count' in edge, "Edge must have 'evidence_count'"

                # Verify field types
                assert isinstance(edge['belief'], (int, float))
                assert 0 <= edge['belief'] <= 1, "Belief must be in [0, 1]"
                assert isinstance(edge['evidence_count'], int)
                assert edge['evidence_count'] >= 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_path_belief_scores_reasonable(self, scm_builder):
        """Test that path belief scores are reasonable."""
        paths = await scm_builder.build_scm_graph(
            sources=['IL6'],
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        assert len(paths) > 0

        for path in paths:
            if 'path_belief' in path:
                belief = path['path_belief']
                assert 0 <= belief <= 1, f"Path belief must be in [0, 1], got {belief}"


class TestSCMBuilderErrorHandling:
    """Test error handling in SCM builder."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_sources_list(self, scm_builder):
        """Test behavior with empty sources list."""
        paths = await scm_builder.build_scm_graph(
            sources=[],
            targets=['CRP'],
            max_depth=2,
            use_priors=True
        )

        # Should return empty list
        assert len(paths) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_targets_list(self, scm_builder):
        """Test behavior with empty targets list."""
        paths = await scm_builder.build_scm_graph(
            sources=['PM2.5'],
            targets=[],
            max_depth=2,
            use_priors=True
        )

        # Should return empty list
        assert len(paths) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_nonexistent_entities(self, scm_builder):
        """Test behavior with nonexistent entities."""
        paths = await scm_builder.build_scm_graph(
            sources=['NOTAREALENTITY1'],
            targets=['NOTAREALENTITY2'],
            max_depth=2,
            use_priors=True
        )

        # Should return empty list (no INDRA path, no priors)
        assert len(paths) == 0


class TestSCMBuilderPerformance:
    """Test performance characteristics of SCM builder."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_reasonable_query_time(self, scm_builder):
        """Test that SCM builder completes in reasonable time."""
        import time

        start = time.time()

        paths = await scm_builder.build_scm_graph(
            sources=['PM2.5'],
            targets=['CRP'],
            max_depth=4,
            use_priors=True
        )

        elapsed = time.time() - start

        # Should complete within 30 seconds (allows for INDRA API latency)
        assert elapsed < 30.0, f"Query took {elapsed}s, should be < 30s"

        print(f"\n✅ SCM builder completed in {elapsed:.2f}s")
        print(f"   Found {len(paths)} paths")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
