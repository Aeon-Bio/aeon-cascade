"""Qualitative insight models for evidence-based hypothesis exploration.

This module defines scientifically honest insight types that replace
quantitative predictions with literature-backed hypotheses.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class KeyPaper(BaseModel):
    """Reference to a key research paper."""

    pmid: str = Field(description="PubMed ID")
    title: str = Field(description="Paper title")
    year: int = Field(description="Publication year")
    authors: Optional[str] = Field(default=None, description="First author et al.")
    journal: Optional[str] = Field(default=None, description="Journal name")


class PathwayInsight(BaseModel):
    """Insight about a causal pathway from literature."""

    type: Literal["pathway"] = "pathway"
    title: str = Field(description="Human-readable pathway title")
    mechanism: str = Field(description="Mechanistic description (e.g., 'PM2.5 → NF-κB → IL-6 → CRP')")
    description: str = Field(description="Detailed explanation of the pathway")
    evidence_strength: Literal["strong", "moderate", "limited"] = Field(
        description="Evidence quality: strong (>100 papers), moderate (20-100), limited (<20)"
    )
    paper_count: int = Field(description="Total number of supporting papers")
    key_papers: list[KeyPaper] = Field(
        default_factory=list, description="Top 3-5 most relevant papers"
    )


class GeneticModifierInsight(BaseModel):
    """Insight about genetic variant effects."""

    type: Literal["genetic_modifier"] = "genetic_modifier"
    gene: str = Field(description="Gene symbol (e.g., 'GSTM1')")
    variant: str = Field(description="Variant description (e.g., 'null deletion')")
    title: str = Field(description="Human-readable title")
    mechanism: str = Field(description="How this variant affects biology")
    description: str = Field(description="Detailed explanation")
    penetrance: Literal["high", "moderate", "variable", "unknown"] = Field(
        description="How consistently this variant affects phenotype"
    )
    tissue_specificity: Optional[str] = Field(
        default=None, description="Which tissues/organs are affected"
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Honest limitations (e.g., 'Effect varies by environmental exposure')"
    )
    key_papers: list[KeyPaper] = Field(default_factory=list)


class InterventionHypothesis(BaseModel):
    """Testable hypothesis about potential interventions."""

    type: Literal["intervention_hypothesis"] = "intervention_hypothesis"
    title: str = Field(description="Human-readable hypothesis")
    intervention: str = Field(description="Proposed intervention (e.g., 'Reduce PM2.5 exposure')")
    rationale: str = Field(description="Why this might work based on mechanisms")
    evidence_basis: str = Field(
        description="What type of evidence supports this (e.g., 'Observational cohorts, limited RCTs')"
    )
    affected_pathways: list[str] = Field(
        description="Which pathways would be affected"
    )
    caveats: list[str] = Field(
        description="Important limitations and uncertainties"
    )
    recommendation: str = Field(
        description="How to test this hypothesis (e.g., 'Monitor CRP if relocating')"
    )
    key_papers: list[KeyPaper] = Field(default_factory=list)


class EnvironmentalContextInsight(BaseModel):
    """Insight about environmental exposures from location history."""

    type: Literal["environmental_context"] = "environmental_context"
    title: str = Field(description="Human-readable title")
    exposure: str = Field(description="Environmental factor (e.g., 'PM2.5')")
    current_level: Optional[float] = Field(
        default=None, description="Current exposure level"
    )
    reference_level: Optional[float] = Field(
        default=None, description="Reference/healthy level"
    )
    health_context: str = Field(
        description="How this exposure relates to user's health"
    )
    potential_mechanisms: list[str] = Field(
        description="Known mechanisms linking exposure to health outcomes"
    )
    caveats: list[str] = Field(default_factory=list)


# Union type for all insight types
Insight = PathwayInsight | GeneticModifierInsight | InterventionHypothesis | EnvironmentalContextInsight


class CausalHypothesisExploration(BaseModel):
    """Complete exploration of causal hypotheses (replaces quantitative predictions)."""

    request_id: str
    insights: list[Insight] = Field(
        description="Evidence-based insights (pathways, genetics, hypotheses)"
    )
    summary: str = Field(
        description="High-level summary of findings"
    )
    total_papers_referenced: int = Field(
        description="Total unique papers across all insights"
    )
    confidence_note: str = Field(
        default="These insights are based on literature synthesis and mechanistic reasoning, "
                "not personalized predictions. Individual responses vary. "
                "Discuss findings with your physician before making health decisions."
    )
