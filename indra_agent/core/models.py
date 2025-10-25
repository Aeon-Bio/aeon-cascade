"""Pydantic models for INDRA causal discovery API.

These models define the request/response contract as specified in
agentic-system-spec.md.
"""

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class LocationHistory(BaseModel):
    """Location history entry."""

    city: str
    start_date: str
    end_date: Optional[str] = None
    avg_pm25: float


class UserContext(BaseModel):
    """User context including genetics, biomarkers, and location history."""

    user_id: str
    genetics: Dict[str, str] = Field(default_factory=dict)
    current_biomarkers: Dict[str, float] = Field(default_factory=dict)
    location_history: List[LocationHistory] = Field(default_factory=list)


class Query(BaseModel):
    """User query specification."""

    text: str
    intent: Optional[Literal["prediction", "explanation", "intervention"]] = None
    focus_biomarkers: Optional[List[str]] = None


class RequestOptions(BaseModel):
    """Optional request configuration."""

    max_graph_depth: int = 4
    min_evidence_count: int = 2
    include_interventions: bool = False


class CausalDiscoveryRequest(BaseModel):
    """Request format for /api/v1/causal_discovery endpoint."""

    request_id: str
    user_context: UserContext
    query: Query
    options: RequestOptions = Field(default_factory=RequestOptions)


class Grounding(BaseModel):
    """Entity grounding to biological databases."""

    database: Literal["MESH", "HGNC", "CHEBI", "GO", "FPLX", "UP", "PUBCHEM", "NCIT"]
    identifier: str


class Node(BaseModel):
    """Causal graph node."""

    id: str
    type: Literal["environmental", "molecular", "biomarker", "genetic"]
    label: str
    grounding: Grounding


class Evidence(BaseModel):
    """Evidence supporting a causal relationship."""

    count: int = Field(ge=0, description="Number of supporting papers")
    confidence: float = Field(ge=0, le=1, description="Confidence score (INDRA belief)")
    sources: List[str] = Field(description="List of PMIDs")
    summary: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Validate INDRA belief score (confidence).

        This is separate from effect_size but should also be [0, 1].
        """
        if not 0 <= v <= 1:
            logger.error(f"Invalid confidence score: {v} (must be ∈ [0,1])")
            raise ValueError(f"confidence must be in [0, 1], got {v}")

        # Warn about suspiciously low confidence
        if v < 0.1:
            logger.warning(
                f"Very low confidence: {v:.3f}. "
                f"Consider filtering low-belief edges (min_belief=0.2)."
            )

        return v

    @field_validator("count")
    @classmethod
    def validate_count(cls, v: int) -> int:
        """Validate evidence count.

        Warn about edges with no supporting papers.
        """
        if v == 0:
            logger.warning(
                "Edge has 0 supporting papers. "
                "Consider setting min_evidence_count > 0 in RequestOptions."
            )

        return v


class Edge(BaseModel):
    """Causal graph edge."""

    source: str
    target: str
    relationship: Literal["activates", "inhibits", "increases", "decreases"]
    evidence: Evidence
    effect_size: float = Field(
        ge=0, le=1, description="Normalized effect strength (0-1)"
    )
    temporal_lag_hours: int = Field(ge=0, description="Hours from cause to effect")

    @field_validator("effect_size")
    @classmethod
    def validate_effect_size(cls, v: float, info) -> float:
        """Ensure effect_size is in valid range [0, 1] with warnings.

        This validator prevents Monte Carlo crashes from malformed INDRA data.
        See ARCHITECTURE_FIX_PLAN.md Issue #8 for details.
        """
        # Hard constraints (raise errors)
        if not 0 <= v <= 1:
            logger.error(
                f"Invalid effect_size: {v} (must be ∈ [0,1]). "
                f"This violates probability constraints for Monte Carlo simulation."
            )
            raise ValueError(f"effect_size must be in [0, 1], got {v}")

        # Soft warnings (log but allow)
        edge_info = f"{info.data.get('source', '?')} → {info.data.get('target', '?')}"

        if v < 0.05:
            logger.warning(
                f"Very weak effect: {edge_info} has effect_size={v:.4f} "
                f"(< 0.05). Consider filtering low-confidence edges."
            )
        elif v > 0.98:
            logger.warning(
                f"Near-deterministic effect: {edge_info} has effect_size={v:.4f} "
                f"(> 0.98). May indicate over-confident INDRA belief or saturated formula."
            )

        return v

    @field_validator("temporal_lag_hours")
    @classmethod
    def validate_temporal_lag(cls, v: int, info) -> int:
        """Ensure temporal_lag_hours is non-negative (causality constraint).

        Negative temporal lag violates causality (effect before cause).
        See ARCHITECTURE_FIX_PLAN.md Issue #8 for details.
        """
        edge_info = f"{info.data.get('source', '?')} → {info.data.get('target', '?')}"

        # Hard constraint: causality violation
        if v < 0:
            logger.error(
                f"Causality violation: {edge_info} has temporal_lag={v}h "
                f"(negative lag means effect before cause!)"
            )
            raise ValueError(
                f"temporal_lag_hours must be >= 0 (causality constraint), got {v}"
            )

        # Soft warnings
        if v == 0:
            logger.warning(
                f"Instantaneous effect: {edge_info} has temporal_lag=0h. "
                f"May want to set minimum lag (e.g., 1h) for biological realism."
            )
        elif v > 168:  # > 1 week
            logger.warning(
                f"Long temporal lag: {edge_info} has temporal_lag={v}h "
                f"({v/24:.1f} days). May lose relevance for short-term predictions."
            )

        return v


class GeneticModifier(BaseModel):
    """Genetic variant that modulates causal paths."""

    variant: str
    affected_nodes: List[str]
    effect_type: Literal["amplifies", "dampens"]
    magnitude: float = Field(gt=0, description="Effect magnitude multiplier")


class CausalGraph(BaseModel):
    """Complete causal graph structure."""

    nodes: List[Node]
    edges: List[Edge]
    genetic_modifiers: List[GeneticModifier] = Field(default_factory=list)


class Metadata(BaseModel):
    """Response metadata."""

    query_time_ms: int
    indra_paths_explored: int
    total_evidence_papers: int


class PredictionTimeline(BaseModel):
    """Temporal prediction for a single biomarker."""

    baseline: float = Field(description="Baseline biomarker value")
    timeline: List[Dict[str, Any]] = Field(
        description="List of prediction points: [{day, mean, confidence_interval, risk_level}]"
    )
    unit: str = Field(description="Measurement unit (e.g., 'mg/L', 'pg/mL')")

    @field_validator("timeline")
    @classmethod
    def validate_timeline_structure(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate timeline structure."""
        required_fields = {"day", "mean", "confidence_interval", "risk_level"}
        for entry in v:
            missing = required_fields - set(entry.keys())
            if missing:
                raise ValueError(f"Timeline entry missing fields: {missing}")

            # Validate confidence_interval is a 2-element list
            ci = entry.get("confidence_interval")
            if not isinstance(ci, list) or len(ci) != 2:
                raise ValueError("confidence_interval must be [lower, upper]")

            # Validate risk_level
            if entry.get("risk_level") not in ["low", "moderate", "high", "unknown"]:
                raise ValueError(f"Invalid risk_level: {entry.get('risk_level')}")

        return v


class CausalDiscoveryResponse(BaseModel):
    """Success response for /api/v1/causal_discovery endpoint."""

    request_id: str
    status: Literal["success"] = "success"
    causal_graph: CausalGraph
    metadata: Metadata
    explanations: List[str] = Field(
        min_length=1, max_length=5, description="3-5 human-readable explanations"
    )
    insights: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Qualitative insights from evidence-based causal hypothesis exploration (Path A)"
    )


class ErrorDetails(BaseModel):
    """Error details."""

    attempted_sources: Optional[List[str]] = None
    attempted_targets: Optional[List[str]] = None
    paths_found: int = 0
    max_depth_reached: bool = False


class ErrorInfo(BaseModel):
    """Error information."""

    code: Literal["NO_CAUSAL_PATH", "TIMEOUT", "INVALID_REQUEST"]
    message: str
    details: Optional[ErrorDetails] = None


class ErrorResponse(BaseModel):
    """Error response for /api/v1/causal_discovery endpoint."""

    request_id: str
    status: Literal["error"] = "error"
    error: ErrorInfo
    partial_result: Optional[Any] = None


# Intervention API Models

class Intervention(BaseModel):
    """Single intervention specification."""

    node_id: str = Field(..., description="Node to intervene on")
    value: float = Field(..., description="Intervention value")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class InterventionRequest(BaseModel):
    """Request for /api/v1/intervene endpoint."""

    request_id: str
    graph_id: str = Field(..., description="Graph ID from /causal_discovery")
    intervention: Intervention
    target_biomarkers: List[str] = Field(..., description="Biomarkers to predict")
    horizon_days: int = Field(90, ge=1, le=365)
    confidence_level: float = Field(0.95, ge=0.5, le=0.99)
    options: Dict[str, Any] = Field(default_factory=dict)


class BiomarkerPrediction(BaseModel):
    """Prediction for a single biomarker."""

    baseline: Dict[str, float] = Field(
        description="Baseline statistics: {mean, ci_lower, ci_upper}"
    )
    post_intervention: Dict[str, float] = Field(
        description="Post-intervention statistics: {mean, ci_lower, ci_upper}"
    )
    delta: Dict[str, float] = Field(
        description="Change: {absolute, percent}"
    )
    timeline: List[Dict[str, Any]] = Field(
        description="Timeline points with day, mean, ci_lower, ci_upper, risk_level"
    )


class AffectedPathway(BaseModel):
    """Causal pathway affected by intervention."""

    pathway: List[str] = Field(description="Sequence of node IDs")
    relationship_chain: List[str] = Field(description="Sequence of relationships")
    total_effect_size: float = Field(ge=-1, le=1)
    explanation: str = Field(max_length=200)


class InterventionMetadata(BaseModel):
    """Metadata for intervention response."""

    computation_time_ms: int
    graph_nodes: int
    confidence_level: float


class InterventionResponse(BaseModel):
    """Success response for /api/v1/intervene endpoint."""

    request_id: str
    status: Literal["success"] = "success"
    intervention_summary: Intervention
    predictions: Dict[str, BiomarkerPrediction]
    affected_pathways: List[AffectedPathway] = Field(default_factory=list)
    metadata: InterventionMetadata
