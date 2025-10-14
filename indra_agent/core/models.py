"""Pydantic models for INDRA causal discovery API.

These models define the request/response contract as specified in
agentic-system-spec.md.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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

    database: Literal["MESH", "HGNC", "CHEBI", "GO"]
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
    confidence: float = Field(ge=0, le=1, description="Confidence score")
    sources: List[str] = Field(description="List of PMIDs")
    summary: str


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
    def validate_effect_size(cls, v: float) -> float:
        """Ensure effect_size is in valid range [0, 1]."""
        if not 0 <= v <= 1:
            raise ValueError(f"effect_size must be in [0, 1], got {v}")
        return v

    @field_validator("temporal_lag_hours")
    @classmethod
    def validate_temporal_lag(cls, v: int) -> int:
        """Ensure temporal_lag_hours is non-negative."""
        if v < 0:
            raise ValueError(f"temporal_lag_hours must be >= 0, got {v}")
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


class CausalDiscoveryResponse(BaseModel):
    """Success response for /api/v1/causal_discovery endpoint."""

    request_id: str
    status: Literal["success"] = "success"
    causal_graph: CausalGraph
    metadata: Metadata
    explanations: List[str] = Field(
        min_length=1, max_length=5, description="3-5 human-readable explanations"
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
