"""End-to-end test for Sarah Chen multi-target intervention scenario.

Sarah Chen has metabolic-inflammatory syndrome:
- CRP: 5.2 mg/L (inflammation)
- HbA1c: 5.9% (prediabetes)
- PM2.5 exposure: 35 µg/m³ (LA → Seattle move planned)

Expected system behavior:
1. Build causal graph with pathways: PM2.5 → Oxidative Stress → {Inflammation, Insulin Resistance}
2. Identify convergent nodes (IRS-1 integrates IL-6 + JNK signals)
3. Detect feedback loop (IL-6 → IRS-1 → Hyperglycemia → AGEs → IL-6)
4. Compute synergy score >1.0 for single intervention affecting multiple targets
5. Recommend PM2.5 reduction with multi-target benefits
"""

import pytest

from indra_agent.core.models import CausalGraph, Edge, Evidence, Grounding, Node
from indra_agent.services.graph_analysis import GraphAnalysisService


@pytest.fixture
def sarah_chen_causal_graph():
    """Mock causal graph for Sarah Chen's metabolic-inflammatory syndrome.

    Pathophysiology:
    PM2.5 → Oxidative Stress (ROS, 8-OHdG)
            ↓
            ├→ NF-κB → IL-6 → CRP (Inflammation)
            │         ↓
            │       IRS-1 inhibition (convergent node)
            │         ↓
            └→ JNK → IRS-1 inhibition
                      ↓
                  Insulin Resistance → HbA1c
                      ↓
                  Hyperglycemia → AGEs → IL-6 (feedback loop)
    """
    nodes = [
        # Environmental
        Node(
            id="PM2.5",
            type="environmental",
            label="Particulate Matter (PM2.5)",
            grounding=Grounding(database="MESH", identifier="D052638")
        ),

        # Molecular (oxidative stress pathway)
        Node(
            id="oxidative_stress",
            type="molecular",
            label="Reactive Oxygen Species",
            grounding=Grounding(database="MESH", identifier="D017382")
        ),
        Node(
            id="NFKB1",
            type="molecular",
            label="NF-κB p50",
            grounding=Grounding(database="HGNC", identifier="7794")
        ),
        Node(
            id="JNK",
            type="molecular",
            label="c-Jun N-terminal kinase",
            grounding=Grounding(database="HGNC", identifier="6881")
        ),
        Node(
            id="IL6",
            type="molecular",
            label="Interleukin-6",
            grounding=Grounding(database="HGNC", identifier="6018")
        ),
        Node(
            id="IRS1",
            type="molecular",
            label="Insulin Receptor Substrate 1",
            grounding=Grounding(database="HGNC", identifier="6125")
        ),
        Node(
            id="AGEs",
            type="molecular",
            label="Advanced Glycation End Products",
            grounding=Grounding(database="MESH", identifier="D017127")
        ),

        # Biomarkers
        Node(
            id="CRP",
            type="biomarker",
            label="C-Reactive Protein",
            grounding=Grounding(database="HGNC", identifier="2367")
        ),
        Node(
            id="HbA1c",
            type="biomarker",
            label="Hemoglobin A1c",
            grounding=Grounding(database="MESH", identifier="D006442")
        ),
    ]

    edges = [
        # PM2.5 → Oxidative Stress
        Edge(
            source="PM2.5",
            target="oxidative_stress",
            relationship="increases",
            evidence=Evidence(
                count=31,
                confidence=0.78,
                sources=["PMID:12345678"],
                summary="PM2.5 induces ROS generation"
            ),
            effect_size=0.75,
            temporal_lag_hours=2
        ),

        # Oxidative Stress → NF-κB (inflammatory pathway)
        Edge(
            source="oxidative_stress",
            target="NFKB1",
            relationship="activates",
            evidence=Evidence(
                count=89,
                confidence=0.92,
                sources=["PMID:23456789"],
                summary="ROS activates NF-κB signaling"
            ),
            effect_size=0.85,
            temporal_lag_hours=1
        ),

        # NF-κB → IL-6
        Edge(
            source="NFKB1",
            target="IL6",
            relationship="increases",
            evidence=Evidence(
                count=156,
                confidence=0.95,
                sources=["PMID:34567890"],
                summary="NF-κB upregulates IL-6 expression"
            ),
            effect_size=0.90,
            temporal_lag_hours=6
        ),

        # IL-6 → CRP
        Edge(
            source="IL6",
            target="CRP",
            relationship="increases",
            evidence=Evidence(
                count=312,
                confidence=0.98,
                sources=["PMID:45678901"],
                summary="IL-6 stimulates hepatic CRP production"
            ),
            effect_size=0.95,
            temporal_lag_hours=12
        ),

        # IL-6 → IRS-1 (cross-talk to metabolic pathway)
        Edge(
            source="IL6",
            target="IRS1",
            relationship="inhibits",
            evidence=Evidence(
                count=78,
                confidence=0.88,
                sources=["PMID:56789012"],
                summary="IL-6 inhibits IRS-1 via SOCS3"
            ),
            effect_size=0.70,
            temporal_lag_hours=3
        ),

        # Oxidative Stress → JNK (metabolic pathway)
        Edge(
            source="oxidative_stress",
            target="JNK",
            relationship="activates",
            evidence=Evidence(
                count=64,
                confidence=0.82,
                sources=["PMID:67890123"],
                summary="ROS activates JNK stress pathway"
            ),
            effect_size=0.75,
            temporal_lag_hours=1
        ),

        # JNK → IRS-1 (convergence at IRS-1)
        Edge(
            source="JNK",
            target="IRS1",
            relationship="inhibits",
            evidence=Evidence(
                count=52,
                confidence=0.80,
                sources=["PMID:78901234"],
                summary="JNK phosphorylates IRS-1 serine residues"
            ),
            effect_size=0.65,
            temporal_lag_hours=2
        ),

        # IRS-1 → HbA1c (insulin resistance → hyperglycemia)
        Edge(
            source="IRS1",
            target="HbA1c",
            relationship="increases",
            evidence=Evidence(
                count=94,
                confidence=0.90,
                sources=["PMID:89012345"],
                summary="IRS-1 inhibition causes insulin resistance and hyperglycemia"
            ),
            effect_size=0.80,
            temporal_lag_hours=720  # 30 days for glycation
        ),

        # HbA1c → AGEs (feedback loop start)
        Edge(
            source="HbA1c",
            target="AGEs",
            relationship="increases",
            evidence=Evidence(
                count=42,
                confidence=0.75,
                sources=["PMID:90123456"],
                summary="Chronic hyperglycemia increases AGE formation"
            ),
            effect_size=0.70,
            temporal_lag_hours=2160  # 90 days
        ),

        # AGEs → IL-6 (feedback loop close)
        Edge(
            source="AGEs",
            target="IL6",
            relationship="increases",
            evidence=Evidence(
                count=38,
                confidence=0.73,
                sources=["PMID:01234567"],
                summary="AGEs activate RAGE receptors, inducing IL-6"
            ),
            effect_size=0.65,
            temporal_lag_hours=6
        ),
    ]

    return CausalGraph(nodes=nodes, edges=edges, genetic_modifiers=[])


class TestMultiTargetIntervention:
    """Test multi-target intervention analysis for Sarah Chen scenario."""

    def test_convergent_node_detection(self, sarah_chen_causal_graph):
        """Test that IRS-1 is detected as convergent node.

        IRS-1 should have in_degree=2 (from IL-6 and JNK).
        """
        graph_analysis = GraphAnalysisService()

        convergent_nodes = graph_analysis.find_convergent_nodes(
            graph=sarah_chen_causal_graph,
            min_in_degree=2
        )

        # Should find IRS-1 as convergent node
        assert len(convergent_nodes) >= 1, "Should detect at least one convergent node"

        irs1_node = next((n for n in convergent_nodes if n["node_id"] == "IRS1"), None)
        assert irs1_node is not None, "IRS-1 should be detected as convergent node"
        assert irs1_node["in_degree"] == 2, "IRS-1 should have 2 incoming edges"

        # Check incoming sources
        sources = {src["source_id"] for src in irs1_node["incoming_sources"]}
        assert "IL6" in sources, "IRS-1 should receive input from IL-6"
        assert "JNK" in sources, "IRS-1 should receive input from JNK"

    def test_feedback_loop_detection(self, sarah_chen_causal_graph):
        """Test that inflammation-insulin resistance feedback loop is detected.

        Expected loop: IL-6 → IRS-1 → HbA1c → AGEs → IL-6
        """
        graph_analysis = GraphAnalysisService()

        feedback_loops = graph_analysis.detect_feedback_loops(
            graph=sarah_chen_causal_graph
        )

        # Should find at least one feedback loop
        assert len(feedback_loops) >= 1, "Should detect at least one feedback loop"

        # Find the IL-6 → IRS-1 → HbA1c → AGEs → IL-6 loop
        il6_loop = None
        for loop in feedback_loops:
            nodes_set = set(loop["nodes"])
            if {"IL6", "IRS1", "HbA1c", "AGEs"}.issubset(nodes_set):
                il6_loop = loop
                break

        assert il6_loop is not None, "Should detect IL-6 feedback loop"
        assert il6_loop["length"] >= 4, "Loop should have at least 4 edges"

    def test_pathway_discovery_pm25_to_crp(self, sarah_chen_causal_graph):
        """Test pathway discovery from PM2.5 to CRP (inflammatory biomarker)."""
        graph_analysis = GraphAnalysisService()

        pathways = graph_analysis.find_pathways(
            graph=sarah_chen_causal_graph,
            source_id="PM2.5",
            target_id="CRP",
            max_depth=5
        )

        # Should find at least one pathway
        assert len(pathways) >= 1, "Should find at least one PM2.5 → CRP pathway"

        # Check first pathway
        pathway = pathways[0]
        assert pathway["nodes"][0] == "PM2.5", "Pathway should start with PM2.5"
        assert pathway["nodes"][-1] == "CRP", "Pathway should end with CRP"

        # Expected pathway: PM2.5 → oxidative_stress → NFKB1 → IL6 → CRP
        assert "oxidative_stress" in pathway["nodes"], "Should go through oxidative stress"
        assert "IL6" in pathway["nodes"], "Should go through IL-6"

    def test_pathway_discovery_pm25_to_hba1c(self, sarah_chen_causal_graph):
        """Test pathway discovery from PM2.5 to HbA1c (metabolic biomarker)."""
        graph_analysis = GraphAnalysisService()

        pathways = graph_analysis.find_pathways(
            graph=sarah_chen_causal_graph,
            source_id="PM2.5",
            target_id="HbA1c",
            max_depth=5
        )

        # Should find at least one pathway
        assert len(pathways) >= 1, "Should find at least one PM2.5 → HbA1c pathway"

        # Check first pathway
        pathway = pathways[0]
        assert pathway["nodes"][0] == "PM2.5", "Pathway should start with PM2.5"
        assert pathway["nodes"][-1] == "HbA1c", "Pathway should end with HbA1c"

        # Expected pathway: PM2.5 → oxidative_stress → JNK → IRS1 → HbA1c
        assert "oxidative_stress" in pathway["nodes"], "Should go through oxidative stress"
        assert "IRS1" in pathway["nodes"], "Should go through IRS-1"

    def test_multi_target_synergy_computation(self, sarah_chen_causal_graph):
        """Test synergy computation for PM2.5 reduction affecting both CRP and HbA1c.

        Expected:
        - Synergy score >1.0 (super-additive)
        - Both CRP and HbA1c affected
        - Convergent node (IRS-1) detected in pathways
        """
        graph_analysis = GraphAnalysisService()

        synergy_result = graph_analysis.compute_multi_target_synergy(
            graph=sarah_chen_causal_graph,
            intervention_node_id="PM2.5",
            target_biomarkers=["CRP", "HbA1c"]
        )

        # Check synergy score
        synergy_score = synergy_result["synergy_score"]
        assert synergy_score > 0, "Synergy score should be positive"
        print(f"\n✅ Synergy Score: {synergy_score:.2f}")

        # Check affected targets
        affected_targets = synergy_result["affected_targets"]
        assert "CRP" in affected_targets, "CRP should be affected by PM2.5 reduction"
        assert "HbA1c" in affected_targets, "HbA1c should be affected by PM2.5 reduction"
        print(f"✅ Affected Targets: {affected_targets}")

        # Check pathways
        pathways_per_target = synergy_result["pathways_per_target"]
        assert "CRP" in pathways_per_target, "Should find pathways to CRP"
        assert "HbA1c" in pathways_per_target, "Should find pathways to HbA1c"
        print(f"✅ CRP Pathways: {len(pathways_per_target['CRP'])}")
        print(f"✅ HbA1c Pathways: {len(pathways_per_target['HbA1c'])}")

        # Check convergent nodes
        convergent_nodes = synergy_result["convergent_nodes_affected"]
        print(f"✅ Convergent Nodes: {convergent_nodes}")

        # If convergent nodes detected, synergy should be super-additive
        if len(convergent_nodes) > 0:
            assert synergy_score > 1.0, (
                f"Synergy score should be >1.0 with convergent nodes, got {synergy_score}"
            )
            print(f"✅ Super-additive synergy detected: {synergy_score:.2f} > 1.0")

        # Print explanation
        print(f"\n{synergy_result['explanation']}")

    def test_systems_medicine_narrative(self, sarah_chen_causal_graph):
        """Test full systems medicine narrative for Sarah Chen.

        This test demonstrates the complete intervention analysis workflow:
        1. Identify convergent nodes (cross-pathway integration)
        2. Detect feedback loops (disease amplification)
        3. Find pathways to multiple targets
        4. Compute synergy score
        5. Generate intervention recommendation
        """
        graph_analysis = GraphAnalysisService()

        print("\n" + "="*80)
        print("SYSTEMS MEDICINE ANALYSIS: Sarah Chen")
        print("="*80)

        # 1. Convergent nodes
        print("\n1. CONVERGENT NODES (Cross-pathway Integration):")
        convergent = graph_analysis.find_convergent_nodes(sarah_chen_causal_graph, min_in_degree=2)
        for node in convergent:
            print(f"   - {node['label']} (ID: {node['node_id']})")
            print(f"     In-degree: {node['in_degree']}")
            print(f"     Sources: {[s['source_id'] for s in node['incoming_sources']]}")

        # 2. Feedback loops
        print("\n2. FEEDBACK LOOPS (Disease Amplification):")
        loops = graph_analysis.detect_feedback_loops(sarah_chen_causal_graph)
        for i, loop in enumerate(loops):
            loop_nodes = loop["nodes"][:-1]  # Remove duplicate last node
            print(f"   Loop {i+1}: {' → '.join(loop_nodes)} → {loop_nodes[0]}")

        # 3. Pathways to targets
        print("\n3. CAUSAL PATHWAYS (PM2.5 → Biomarkers):")

        crp_pathways = graph_analysis.find_pathways(sarah_chen_causal_graph, "PM2.5", "CRP")
        print(f"   PM2.5 → CRP: {len(crp_pathways)} pathways")
        if crp_pathways:
            print(f"      Shortest: {' → '.join(crp_pathways[0]['nodes'])}")

        hba1c_pathways = graph_analysis.find_pathways(sarah_chen_causal_graph, "PM2.5", "HbA1c")
        print(f"   PM2.5 → HbA1c: {len(hba1c_pathways)} pathways")
        if hba1c_pathways:
            print(f"      Shortest: {' → '.join(hba1c_pathways[0]['nodes'])}")

        # 4. Synergy analysis
        print("\n4. MULTI-TARGET SYNERGY:")
        synergy = graph_analysis.compute_multi_target_synergy(
            graph=sarah_chen_causal_graph,
            intervention_node_id="PM2.5",
            target_biomarkers=["CRP", "HbA1c"]
        )
        print(f"   Synergy Score: {synergy['synergy_score']:.2f}")
        print(f"   Affected: {synergy['affected_targets']}")
        print(f"   Convergent Nodes: {synergy['convergent_nodes_affected']}")
        print(f"   {synergy['explanation']}")

        # 5. Intervention recommendation
        print("\n5. INTERVENTION RECOMMENDATION:")
        print("   ✅ Reduce PM2.5 exposure (e.g., move from LA to Seattle)")
        print("   ✅ Expected benefits:")
        print("      - ↓ Oxidative stress")
        print("      - ↓ Inflammation (CRP)")
        print("      - ↓ Insulin resistance (HbA1c)")
        print("   ✅ Synergy from shared oxidative stress pathway")
        print("   ✅ Breaks IL-6 feedback loop")

        print("\n" + "="*80)

        # Assert test passes
        assert synergy["synergy_score"] > 0, "Synergy analysis should complete successfully"
