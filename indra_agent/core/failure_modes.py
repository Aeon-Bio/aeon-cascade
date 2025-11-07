"""Transparent failure mode tracking for causal discovery.

This module provides structured failure mode analysis when pathways cannot be found,
helping users understand WHY queries fail and what to do about it.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class FailureReason(str, Enum):
    """Classification of why pathway discovery failed."""

    NO_DIRECT_PATH = "NO_DIRECT_PATH"
    """Direct INDRA query found 0 statements, but mediator expansion may succeed"""

    INDRA_COVERAGE_GAP = "INDRA_COVERAGE_GAP"
    """Entities well-covered individually, but relationship not in INDRA database"""

    ENTITY_GROUNDING_FAILURE = "ENTITY_GROUNDING_FAILURE"
    """Entities not recognized or ambiguous (query error)"""

    TIMEOUT = "TIMEOUT"
    """Query exceeded production SLA (5s), search incomplete"""

    NO_CAUSAL_RELATIONSHIP = "NO_CAUSAL_RELATIONSHIP"
    """Query nonsensical or no plausible biological mechanism"""


@dataclass
class DiscoveryAttempt:
    """Record of a single pathway discovery attempt.

    Tracks what was tried, how long it took, and whether it succeeded.
    """

    phase: str
    """Discovery phase: 'Phase 1: Direct INDRA', 'Phase 2: Mediator expansion', etc."""

    query: str
    """Query executed: 'APOB → BDNF', 'PM2.5 → oxidative stress', etc."""

    result: str
    """Outcome: '0 statements found', '1 path found via oxidative stress', etc."""

    duration_ms: int
    """Time taken in milliseconds"""

    success: bool
    """Whether this attempt found paths"""

    reason: Optional[str] = None
    """Failure reason if success=False: 'INDRA coverage gap', 'timeout', etc."""

    mediators_tried: Optional[List[str]] = None
    """For Phase 2: List of mediators attempted"""

    statements_count: Optional[int] = None
    """Number of INDRA statements retrieved (if applicable)"""


@dataclass
class INDRACoverage:
    """INDRA database coverage for query entities.

    Helps distinguish database gaps from biological reality.
    """

    entity_name: str
    """Entity being analyzed (e.g., 'APOB', 'IL6')"""

    statement_count: int
    """Number of INDRA statements involving this entity"""

    well_covered: bool
    """Whether entity has ≥100 statements (considered well-documented)"""

    @classmethod
    def from_statement_count(cls, entity_name: str, count: int) -> "INDRACoverage":
        """Create coverage record from statement count."""
        return cls(
            entity_name=entity_name,
            statement_count=count,
            well_covered=count >= 100
        )


@dataclass
class FailureMode:
    """Transparent explanation of why pathway discovery failed.

    Provides:
    - Classification of failure type
    - Human-readable explanation
    - Step-by-step discovery attempts
    - Actionable suggestions for user
    - INDRA database coverage analysis
    """

    reason: FailureReason
    """High-level classification of failure"""

    explanation: str
    """Human-readable explanation (2-3 sentences)"""

    discovery_attempts: List[DiscoveryAttempt] = field(default_factory=list)
    """Chronological log of what was tried"""

    suggestions: List[str] = field(default_factory=list)
    """Actionable recommendations (3-5 items)"""

    indra_coverage: Dict[str, INDRACoverage] = field(default_factory=dict)
    """Coverage analysis for source and target entities"""

    total_duration_ms: int = 0
    """Total time spent on discovery"""

    @property
    def phases_attempted(self) -> List[str]:
        """List of discovery phases that were attempted."""
        return [attempt.phase for attempt in self.discovery_attempts]

    @property
    def any_success(self) -> bool:
        """Whether ANY attempt succeeded (partial success)."""
        return any(attempt.success for attempt in self.discovery_attempts)

    def to_user_message(self) -> str:
        """Generate user-friendly failure message.

        Returns:
            Multi-line string explaining failure and suggesting next steps
        """
        lines = []

        # Header
        lines.append(f"REASON: {self.reason.value}")
        lines.append("")

        # Discovery attempts
        lines.append("ATTEMPTED:")
        for attempt in self.discovery_attempts:
            status = "✓" if attempt.success else "✗"
            lines.append(f"  {status} {attempt.phase}")
            lines.append(f"     Query: {attempt.query}")
            lines.append(f"     Result: {attempt.result}")
            if attempt.mediators_tried:
                mediator_list = ", ".join(attempt.mediators_tried[:5])
                if len(attempt.mediators_tried) > 5:
                    mediator_list += f", ... ({len(attempt.mediators_tried)} total)"
                lines.append(f"     Mediators: {mediator_list}")
            lines.append("")

        # INDRA coverage (if available)
        if self.indra_coverage:
            lines.append("INDRA COVERAGE:")
            for entity_name, coverage in self.indra_coverage.items():
                status = "well-covered" if coverage.well_covered else "sparse"
                lines.append(
                    f"  - {entity_name}: {coverage.statement_count} statements ({status})"
                )
            lines.append("")

        # Explanation
        lines.append("EXPLANATION:")
        for line in self.explanation.split("\n"):
            lines.append(f"  {line}")
        lines.append("")

        # Suggestions
        if self.suggestions:
            lines.append("SUGGESTIONS:")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)
