"""Clinical Report Generator for Intervention Discovery.

This module generates human-readable clinical reports from intervention discovery results,
translating technical graph-theoretic findings into patient-friendly recommendations.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from indra_agent.core.intervention_models import (
    ConsensusTarget,
    InterventionHub,
    SharedRegulator,
    MinimalNetworkResult,
    PathwayMechanism,
    PredictedEffect,
)

logger = logging.getLogger(__name__)


def generate_intervention_clinical_report(
    consensus_targets: List[ConsensusTarget],
    intervention_hubs: List[InterventionHub],
    shared_regulators: Optional[List[SharedRegulator]] = None,
    minimal_network: Optional[MinimalNetworkResult] = None,
    user_context: Optional[Dict[str, Any]] = None,
    format: str = "markdown",
) -> str:
    """Generate human-readable clinical report for intervention recommendations.

    Args:
        consensus_targets: Targets found by multiple discovery methods
        intervention_hubs: Structural hubs with actionability assessment
        shared_regulators: Literature-based shared regulators (optional)
        minimal_network: Minimal network result (optional)
        user_context: Patient context with biomarkers, genetics, current values
        format: Output format - "markdown" or "html" (default: "markdown")

    Returns:
        Formatted clinical report as string
    """
    if user_context is None:
        user_context = {}

    biomarkers = user_context.get("biomarkers", [])
    current_values = user_context.get("current_biomarker_values", {})
    genetics = user_context.get("genetics", {})

    report_lines = []

    # Header
    report_lines.append("# INTERVENTION DISCOVERY REPORT")
    report_lines.append("")
    report_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Patient Context
    report_lines.append("## Patient Context")
    report_lines.append("")

    if biomarkers:
        report_lines.append(f"**Target Biomarkers**: {', '.join(biomarkers)}")
    else:
        report_lines.append("**Target Biomarkers**: Not specified")

    if current_values:
        report_lines.append("")
        report_lines.append("**Current Values**:")
        for biomarker, value in current_values.items():
            report_lines.append(f"- {biomarker}: {value}")
    else:
        report_lines.append("**Current Values**: Not provided")

    if genetics:
        report_lines.append("")
        report_lines.append("**Genetic Context**:")
        for gene, variant in genetics.items():
            report_lines.append(f"- {gene}: {variant}")
    else:
        report_lines.append("**Genetic Context**: Not available")

    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Top Intervention Targets
    report_lines.append("## Top Intervention Targets")
    report_lines.append("")
    report_lines.append("These targets regulate multiple biomarkers simultaneously, enabling synergistic interventions:")
    report_lines.append("")

    # Show top 3 intervention hubs
    top_hubs = intervention_hubs[:3] if intervention_hubs else []

    for i, hub in enumerate(top_hubs, 1):
        total_biomarkers = len(biomarkers) if biomarkers else hub.coverage
        coverage_pct = (hub.coverage_ratio * 100) if total_biomarkers > 0 else 0

        report_lines.append(f"### {i}. {hub.node} ({hub.intervention_type.upper()})")
        report_lines.append("")
        report_lines.append(f"**Coverage**: {hub.coverage}/{total_biomarkers} biomarkers ({coverage_pct:.0f}%)")
        report_lines.append(f"**Actionability**: {hub.actionability.upper()}")

        if hub.druggable:
            report_lines.append(f"**Druggable**: ✓ Yes - existing drugs or compounds available")
        else:
            report_lines.append(f"**Druggable**: ✗ No - requires lifestyle or indirect approaches")

        report_lines.append("")
        report_lines.append(f"**Mechanism**: {hub.reasoning}")
        report_lines.append("")
        report_lines.append(f"**Affected Biomarkers**: {', '.join(hub.affected_biomarkers)}")
        report_lines.append("")

        # Clinical significance
        significance = _generate_clinical_significance(hub, user_context)
        report_lines.append("**Clinical Significance**:")
        report_lines.append(significance)
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    if not top_hubs:
        report_lines.append("*No intervention hubs found. This may indicate the biomarkers are not connected in the INDRA database.*")
        report_lines.append("")

    # Consensus Recommendations
    if consensus_targets:
        report_lines.append("## Consensus Recommendations")
        report_lines.append("")
        report_lines.append("These targets were identified by **multiple independent methods** (high confidence):")
        report_lines.append("")

        for target in consensus_targets:
            methods_str = ", ".join(target.found_in_methods)
            report_lines.append(f"- **{target.node}** (found by: {methods_str})")
            report_lines.append(f"  - {target.recommendation}")
            report_lines.append("")

        report_lines.append("---")
        report_lines.append("")

    # Additional Methods Summary
    if shared_regulators:
        report_lines.append("## Literature-Based Regulators")
        report_lines.append("")
        report_lines.append(f"Found {len(shared_regulators)} shared regulators from scientific literature:")
        report_lines.append("")

        for reg in shared_regulators[:5]:  # Top 5
            report_lines.append(
                f"- **{reg.node}**: Regulates {reg.coverage} biomarkers "
                f"(evidence: {reg.total_evidence} papers, belief: {reg.avg_belief:.2f})"
            )

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    if minimal_network:
        report_lines.append("## Minimal Causal Network")
        report_lines.append("")
        report_lines.append(f"**Network Size**: {minimal_network.total_nodes} nodes, {minimal_network.total_edges} edges")
        report_lines.append(f"**Network Diameter**: {minimal_network.network_diameter} hops (longest path)")
        report_lines.append(f"**Average Path Length**: {minimal_network.avg_path_length:.1f} hops")
        report_lines.append("")

        if minimal_network.connected_biomarkers:
            report_lines.append(f"**Connected Biomarkers**: {', '.join(minimal_network.connected_biomarkers)}")

        if minimal_network.disconnected_biomarkers:
            report_lines.append(f"**Disconnected Biomarkers**: {', '.join(minimal_network.disconnected_biomarkers)}")
            report_lines.append("*(These biomarkers have no known causal paths in the INDRA database)*")

        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    # Next Steps
    report_lines.append("## Next Steps")
    report_lines.append("")
    report_lines.append("1. **Discuss with Healthcare Provider**: Review these findings with your doctor or specialist")
    report_lines.append("2. **Genetic Testing**: Consider genetic testing if not already done (may reveal contraindications)")
    report_lines.append("3. **Baseline Monitoring**: Establish current biomarker levels before any intervention")
    report_lines.append("4. **Track Changes**: Monitor biomarker changes at regular intervals (e.g., 3-6 months)")
    report_lines.append("5. **Re-Evaluate**: Reassess intervention effectiveness and adjust as needed")
    report_lines.append("")

    # Disclaimers
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## Important Disclaimers")
    report_lines.append("")
    report_lines.append("⚠️ **FOR RESEARCH AND INFORMATIONAL PURPOSES ONLY**")
    report_lines.append("")
    report_lines.append("This report is based on computational analysis of scientific literature and biological databases. It is NOT medical advice.")
    report_lines.append("")
    report_lines.append("**Key Points**:")
    report_lines.append("- Always consult with a licensed healthcare provider before making any health decisions")
    report_lines.append("- This system discovers biological mechanisms, not treatment protocols")
    report_lines.append("- Actual drug efficacy, dosing, and safety profiles require clinical evaluation")
    report_lines.append("- Individual responses vary based on genetics, comorbidities, and other factors")
    report_lines.append("- No drug recommendations or prescriptions are provided")
    report_lines.append("")
    report_lines.append("**Data Sources**: INDRA bio-ontology database (https://indra.bio)")
    report_lines.append("")

    # Convert to HTML if requested
    if format == "html":
        return _markdown_to_html("\n".join(report_lines))

    return "\n".join(report_lines)


def generate_validation_report(
    target_node: str,
    pathway_analysis: List[PathwayMechanism],
    predicted_effects: Dict[str, PredictedEffect],
    synergy_score: float,
    clinical_significance: str,
    user_context: Optional[Dict[str, Any]] = None,
    format: str = "markdown",
) -> str:
    """Generate clinical report for intervention validation results.

    Args:
        target_node: The intervention target being validated
        pathway_analysis: Causal pathways from target to biomarkers
        predicted_effects: Predicted biomarker changes
        synergy_score: Multi-target synergy score (>1.0 = super-additive)
        clinical_significance: Clinical interpretation
        user_context: Patient context (optional)
        format: Output format - "markdown" or "html"

    Returns:
        Formatted validation report as string
    """
    if user_context is None:
        user_context = {}

    report_lines = []

    # Header
    report_lines.append("# INTERVENTION VALIDATION REPORT")
    report_lines.append("")
    report_lines.append(f"**Target**: {target_node}")
    report_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Synergy Assessment
    report_lines.append("## Synergy Assessment")
    report_lines.append("")
    report_lines.append(f"**Synergy Score**: {synergy_score:.2f}")

    if synergy_score >= 1.3:
        synergy_level = "STRONG SYNERGY"
        interpretation = "This intervention shows super-additive effects - targeting one node produces benefits greater than the sum of individual effects"
    elif synergy_score >= 1.1:
        synergy_level = "MODERATE SYNERGY"
        interpretation = "This intervention shows synergistic effects across multiple biomarkers"
    else:
        synergy_level = "ADDITIVE EFFECTS"
        interpretation = "This intervention shows additive effects - benefits are roughly proportional to coverage"

    report_lines.append(f"**Level**: {synergy_level}")
    report_lines.append(f"**Interpretation**: {interpretation}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Pathway Mechanisms
    report_lines.append("## Causal Pathways")
    report_lines.append("")
    report_lines.append(f"Found {len(pathway_analysis)} causal pathways from {target_node} to target biomarkers:")
    report_lines.append("")

    for pathway in pathway_analysis:
        report_lines.append(f"### {pathway.source} → {pathway.target}")
        report_lines.append("")
        report_lines.append(f"**Mechanism**: {pathway.mechanism}")
        report_lines.append(f"**Confidence**: {pathway.confidence:.2f}")
        report_lines.append(f"**Expected Time Lag**: {pathway.temporal_lag_hours} hours")

        if pathway.evidence_count > 0:
            report_lines.append(f"**Supporting Evidence**: {pathway.evidence_count} scientific papers")

        report_lines.append("")

    if not pathway_analysis:
        report_lines.append("*No causal pathways found. This target may not directly affect the requested biomarkers.*")
        report_lines.append("")

    report_lines.append("---")
    report_lines.append("")

    # Predicted Effects
    report_lines.append("## Predicted Biomarker Changes")
    report_lines.append("")

    if predicted_effects:
        report_lines.append("| Biomarker | Baseline | Predicted | Change | % Change | Confidence |")
        report_lines.append("|-----------|----------|-----------|--------|----------|------------|")

        for biomarker, effect in predicted_effects.items():
            change_symbol = "↓" if effect.delta < 0 else "↑" if effect.delta > 0 else "→"
            report_lines.append(
                f"| {biomarker} | {effect.baseline:.2f} | {effect.predicted:.2f} | "
                f"{change_symbol} {abs(effect.delta):.2f} | {effect.pct_change:+.1f}% | {effect.confidence} |"
            )

        report_lines.append("")
    else:
        report_lines.append("*No predicted effects available (baseline values not provided)*")
        report_lines.append("")

    # Clinical Significance
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## Clinical Significance")
    report_lines.append("")
    report_lines.append(clinical_significance)
    report_lines.append("")

    # Disclaimers
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("## Important Disclaimers")
    report_lines.append("")
    report_lines.append("⚠️ **FOR RESEARCH AND INFORMATIONAL PURPOSES ONLY**")
    report_lines.append("")
    report_lines.append("These predictions are based on computational modeling of biological pathways. Actual clinical outcomes may vary significantly.")
    report_lines.append("")
    report_lines.append("**Limitations**:")
    report_lines.append("- Predictions assume ideal conditions and do not account for individual variability")
    report_lines.append("- Drug bioavailability, pharmacokinetics, and dosing are not modeled")
    report_lines.append("- Side effects, contraindications, and drug interactions are not assessed")
    report_lines.append("- Always consult with a licensed healthcare provider before making any health decisions")
    report_lines.append("")

    # Convert to HTML if requested
    if format == "html":
        return _markdown_to_html("\n".join(report_lines))

    return "\n".join(report_lines)


def _generate_clinical_significance(
    hub: InterventionHub,
    user_context: Dict[str, Any],
) -> str:
    """Generate clinical significance interpretation for an intervention hub.

    Args:
        hub: Intervention hub with coverage and actionability info
        user_context: Patient context with current biomarker values

    Returns:
        Human-readable clinical significance text
    """
    significance_lines = []

    # Multi-target synergy
    if hub.coverage >= 3:
        significance_lines.append(
            f"✓ **Multi-Target Synergy**: This target regulates {hub.coverage} biomarkers simultaneously, "
            "enabling synergistic effects instead of treating conditions in isolation."
        )
    elif hub.coverage == 2:
        significance_lines.append(
            f"✓ **Dual-Target Benefits**: This target affects {hub.coverage} biomarkers, "
            "providing coordinated regulation."
        )
    else:
        significance_lines.append(
            "⚠️ **Single-Target**: This target affects only one biomarker. "
            "Consider combining with other interventions for synergistic effects."
        )

    # Actionability
    if hub.actionability == "high":
        if hub.druggable:
            significance_lines.append(
                "✓ **High Actionability**: This is a druggable target with existing compounds or drugs. "
                "Clinical evidence may be available."
            )
        else:
            significance_lines.append(
                "✓ **High Actionability**: This target can be modulated through lifestyle interventions "
                "or environmental changes."
            )
    elif hub.actionability == "medium":
        significance_lines.append(
            "⚡ **Moderate Actionability**: This target may require indirect approaches or combination strategies."
        )
    else:
        significance_lines.append(
            "⚠️ **Low Actionability**: This target is difficult to modulate directly. "
            "May serve as a biomarker rather than intervention point."
        )

    # Structural importance
    if hub.betweenness_count > 15:
        significance_lines.append(
            f"✓ **Critical Bottleneck**: This node appears in {hub.betweenness_count} causal pathways, "
            "indicating it is a structural bottleneck in the biological network."
        )
    elif hub.betweenness_count > 5:
        significance_lines.append(
            f"⚡ **Network Hub**: This node appears in {hub.betweenness_count} pathways, "
            "suggesting moderate centrality in the network."
        )

    # Mechanism type
    if hub.intervention_type == "signaling":
        significance_lines.append(
            "🔬 **Signaling Pathway**: Fast-acting mechanism (hours to days). "
            "Reversible effects, good for acute interventions."
        )
    elif hub.intervention_type == "metabolic":
        significance_lines.append(
            "🔬 **Metabolic Target**: Moderate timeframe (days to weeks). "
            "Sustainable long-term intervention potential."
        )
    elif hub.intervention_type == "environmental":
        significance_lines.append(
            "🌍 **Environmental Factor**: Long-term modulation (weeks to months). "
            "Requires sustained lifestyle or environmental changes."
        )

    return "\n".join(significance_lines)


def _markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to basic HTML.

    This is a simple converter for basic markdown features.
    For production, consider using a library like python-markdown.

    Args:
        markdown_text: Markdown-formatted text

    Returns:
        HTML-formatted text
    """
    html_lines = ["<html>", "<head>", "<style>"]
    html_lines.append("body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }")
    html_lines.append("h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }")
    html_lines.append("h2 { color: #34495e; border-bottom: 2px solid #95a5a6; padding-bottom: 8px; margin-top: 30px; }")
    html_lines.append("h3 { color: #7f8c8d; margin-top: 20px; }")
    html_lines.append("table { border-collapse: collapse; width: 100%; margin: 20px 0; }")
    html_lines.append("th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }")
    html_lines.append("th { background-color: #3498db; color: white; }")
    html_lines.append("tr:nth-child(even) { background-color: #f2f2f2; }")
    html_lines.append("strong { color: #2c3e50; }")
    html_lines.append("code { background-color: #ecf0f1; padding: 2px 6px; border-radius: 3px; }")
    html_lines.append("hr { border: none; border-top: 1px solid #bdc3c7; margin: 30px 0; }")
    html_lines.append("ul, ol { line-height: 1.8; }")
    html_lines.extend(["</style>", "</head>", "<body>"])

    # Simple markdown to HTML conversion
    lines = markdown_text.split("\n")
    in_code_block = False
    in_list = False

    for line in lines:
        # Code blocks
        if line.startswith("```"):
            if in_code_block:
                html_lines.append("</pre>")
                in_code_block = False
            else:
                html_lines.append("<pre><code>")
                in_code_block = True
            continue

        if in_code_block:
            html_lines.append(line)
            continue

        # Headers
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        # Horizontal rules
        elif line.strip() == "---":
            html_lines.append("<hr>")
        # Lists
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.startswith("1. ") or (len(line) > 2 and line[0].isdigit() and line[1:3] == ". "):
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            # Find the actual start of the list item text
            item_text = line.split(". ", 1)[1] if ". " in line else line
            html_lines.append(f"<li>{item_text}</li>")
        else:
            if in_list:
                html_lines.append("</ul>" if lines[lines.index(line) - 1].startswith(("-", "*")) else "</ol>")
                in_list = False

            # Paragraphs
            if line.strip():
                # Bold and italic (simple replacement)
                line = line.replace("**", "<strong>").replace("**", "</strong>")
                line = line.replace("*", "<em>").replace("*", "</em>")
                html_lines.append(f"<p>{line}</p>")
            else:
                html_lines.append("<br>")

    if in_list:
        html_lines.append("</ul>")

    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)
