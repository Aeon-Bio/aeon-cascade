"""Pydantic models for intervention discovery API.

These models define the request/response schemas for the intervention discovery
endpoints, ensuring type safety and automatic validation.
"""

from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field


class SharedRegulator(BaseModel):
    """A node that regulates multiple biomarkers."""

    node: str = Field(..., description="Node name (e.g., 'TNF', 'NF-κB')")
    namespace: str = Field("", description="Database namespace (e.g., 'HGNC', 'UP')")
    identifier: str = Field("", description="Database identifier")
    affected_biomarkers: List[str] = Field(..., description="Biomarkers this node regulates")
    coverage: int = Field(..., description="Number of biomarkers affected", ge=1)
    coverage_ratio: float = Field(..., description="Fraction of biomarkers affected", ge=0.0, le=1.0)
    total_evidence: int = Field(..., description="Total papers supporting relationships", ge=0)
    avg_belief: float = Field(..., description="Average INDRA belief score", ge=0.0, le=1.0)
    intervention_score: float = Field(
        ...,
        description="Multi-objective score (coverage + evidence + belief)",
        ge=0.0,
        le=1.0
    )


class InterventionHub(BaseModel):
    """A structural hub with actionability assessment."""

    node: str = Field(..., description="Node name")
    namespace: str = Field("", description="Database namespace")
    identifier: str = Field("", description="Database identifier")
    affected_biomarkers: List[str] = Field(..., description="Biomarkers affected")
    coverage: int = Field(..., description="Number of biomarkers affected", ge=1)
    coverage_ratio: float = Field(..., description="Fraction of biomarkers affected", ge=0.0, le=1.0)
    intervention_type: Literal["signaling", "metabolic", "environmental", "process", "unknown"] = Field(
        ..., description="Type of intervention (based on namespace)"
    )
    actionability: Literal["high", "medium", "low"] = Field(
        ..., description="How actionable this target is"
    )
    druggable: bool = Field(..., description="Whether known drugs/compounds target this node")
    betweenness_count: int = Field(..., description="Number of paths this node appears in", ge=0)
    intervention_score: float = Field(..., description="Combined intervention score", ge=0.0, le=1.0)
    upstream_exposures: List[str] = Field(default_factory=list, description="Upstream environmental/lifestyle factors")
    avg_belief: float = Field(0.7, description="Average belief score", ge=0.0, le=1.0)
    total_evidence: int = Field(0, description="Total evidence count", ge=0)
    reasoning: str = Field(..., description="Human-readable explanation of recommendation")


class MinimalNetworkResult(BaseModel):
    """Result from minimal network (Steiner tree) discovery."""

    total_nodes: int = Field(..., description="Total nodes in minimal subgraph", ge=0)
    total_edges: int = Field(..., description="Total edges in minimal subgraph", ge=0)
    paths_used: int = Field(..., description="Number of paths used to build network", ge=0)
    avg_path_length: float = Field(..., description="Average path length in hops", ge=0.0)
    network_diameter: int = Field(..., description="Longest shortest path in network", ge=0)
    connected_biomarkers: List[str] = Field(..., description="Biomarkers successfully connected")
    disconnected_biomarkers: List[str] = Field(..., description="Biomarkers that couldn't be connected")
    intervention_points: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Nodes with leverage (affect 2+ biomarkers)"
    )
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="All nodes in network")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="All edges in network")


class ConsensusTarget(BaseModel):
    """Target found by multiple discovery methods."""

    node: str = Field(..., description="Node name")
    found_in_methods: List[str] = Field(..., description="Methods that found this target")
    max_coverage: int = Field(..., description="Maximum biomarker coverage across methods", ge=1)
    max_score: float = Field(..., description="Maximum intervention score across methods", ge=0.0, le=1.0)
    recommendation: str = Field(..., description="Combined recommendation text")


class NetworkSummary(BaseModel):
    """Summary of intervention discovery network analysis."""

    total_hubs: int = Field(..., description="Total intervention hubs found", ge=0)
    avg_coverage: float = Field(..., description="Average biomarker coverage per hub", ge=0.0)
    total_paths_analyzed: int = Field(..., description="Total causal paths analyzed", ge=0)
    shared_regulators: int = Field(..., description="Number of shared regulators found", ge=0)
    betweenness_hubs: int = Field(..., description="Number of high-betweenness hubs", ge=0)


class InterventionDiscoveryRequest(BaseModel):
    """Request for intervention discovery."""

    request_id: str = Field(..., description="Unique request identifier")
    biomarkers: List[str] = Field(..., description="Target biomarkers to cover", min_length=2)
    exposures: Optional[List[str]] = Field(None, description="Environmental/lifestyle exposures (root causes)")
    genetics: Optional[Dict[str, str]] = Field(None, description="User genetic context")
    current_biomarker_values: Optional[Dict[str, float]] = Field(None, description="Current biomarker measurements")
    options: Optional["InterventionDiscoveryOptions"] = Field(
        default_factory=lambda: InterventionDiscoveryOptions(),
        description="Discovery options"
    )


class InterventionDiscoveryOptions(BaseModel):
    """Options for intervention discovery."""

    methods: List[Literal["shared_regulators", "intervention_hubs", "minimal_network"]] = Field(
        default=["shared_regulators", "intervention_hubs", "minimal_network"],
        description="Which discovery methods to run"
    )
    max_depth: int = Field(3, description="Maximum path depth to search", ge=1, le=5)
    min_coverage: int = Field(2, description="Minimum biomarkers a regulator must affect", ge=1)
    belief_cutoff: float = Field(0.6, description="Minimum INDRA belief score", ge=0.0, le=1.0)
    prioritize_druggable: bool = Field(True, description="Prioritize druggable targets in results")


class InterventionDiscoveryResponse(BaseModel):
    """Response from intervention discovery."""

    status: Literal["success", "error"] = Field(..., description="Request status")
    request_id: str = Field(..., description="Request identifier")
    results: Dict[str, Any] = Field(..., description="Discovery results (shared_regulators, intervention_hubs, minimal_network)")
    consensus_targets: List[ConsensusTarget] = Field(..., description="Targets found by multiple methods")
    network_summary: NetworkSummary = Field(..., description="Network analysis summary")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds", ge=0)
    error_message: Optional[str] = Field(None, description="Error message if status=error")


class PredictedEffect(BaseModel):
    """Predicted effect of intervention on a biomarker."""

    baseline: float = Field(..., description="Baseline biomarker value")
    predicted: float = Field(..., description="Predicted value after intervention")
    delta: float = Field(..., description="Change (predicted - baseline)")
    pct_change: float = Field(..., description="Percent change")
    confidence: Literal["high", "medium", "low"] = Field("medium", description="Confidence in prediction")


class PathwayMechanism(BaseModel):
    """Causal pathway mechanism."""

    source: str = Field(..., description="Source node")
    target: str = Field(..., description="Target biomarker")
    mechanism: str = Field(..., description="Human-readable mechanism (e.g., 'SRC → NF-κB → IL6 → CRP')")
    confidence: float = Field(..., description="Pathway confidence (belief)", ge=0.0, le=1.0)
    temporal_lag_hours: int = Field(..., description="Expected time lag in hours", ge=0)
    evidence_count: int = Field(0, description="Supporting papers", ge=0)


class InterventionValidationRequest(BaseModel):
    """Request to validate an intervention target."""

    target_node: str = Field(..., description="Intervention target to validate")
    biomarkers: List[str] = Field(..., description="Biomarkers to predict effects on", min_length=1)
    genetics: Optional[Dict[str, str]] = Field(None, description="User genetic context")
    current_biomarker_values: Optional[Dict[str, float]] = Field(None, description="Current biomarker values")
    simulate_effect_size: float = Field(
        0.3,
        description="Simulated intervention effect size (0.0-1.0)",
        ge=0.0,
        le=1.0
    )


class InterventionValidationResponse(BaseModel):
    """Response with predicted intervention effects."""

    status: Literal["success", "error"] = Field(..., description="Validation status")
    target_node: str = Field(..., description="Intervention target")
    affects_all_biomarkers: bool = Field(..., description="Whether target affects all requested biomarkers")
    pathway_analysis: List[PathwayMechanism] = Field(..., description="Causal pathways from target to biomarkers")
    predicted_effects: Dict[str, PredictedEffect] = Field(..., description="Predicted effects per biomarker")
    synergy_score: float = Field(..., description="Synergy score (>1.0 = super-additive)", ge=0.0)
    clinical_significance: str = Field(..., description="Clinical interpretation of predicted effects")
    error_message: Optional[str] = Field(None, description="Error message if status=error")


# Update forward references
InterventionDiscoveryRequest.model_rebuild()
