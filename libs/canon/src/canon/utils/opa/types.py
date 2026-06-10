"""Core types for policy enforcement.

Provides:
- PolicyResult: Result of single policy evaluation
- AggregatedResult: Combined result of multiple policies

These types are defined in utils/opa to avoid layering violations.
Higher layers (enforcement, services) should import from here or
via the re-exports in canon.enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from canon.enforcement.policy import EnforcementLevel
from kron.utils import now_utc

__all__ = (
    "AggregatedResult",
    "PolicyResult",
)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    """Result of a single policy evaluation.

    Produced by PolicyEngine.evaluate_single().
    """

    policy_id: str
    """Policy identifier."""

    allowed: bool
    """Whether action is allowed by this policy."""

    enforcement: EnforcementLevel = EnforcementLevel.HARD_MANDATORY
    """Enforcement level of this policy."""

    legal_citation: str | None = None
    """Legal citation for this policy."""

    regulation_url: str | None = None
    """URL to regulation."""

    violation_code: str | None = None
    """Violation code if not allowed."""

    violation_message: str | None = None
    """Human-readable violation message."""

    remediation_steps: tuple[str, ...] = ()
    """Steps to remediate violation."""

    conditions_met: tuple[str, ...] = ()
    """Conditions that were satisfied."""

    conditions_missing: tuple[str, ...] = ()
    """Conditions that were not satisfied."""

    evaluated_at: datetime = field(default_factory=now_utc)
    """When evaluation occurred."""

    evaluation_ms: float = 0.0
    """Evaluation duration in milliseconds."""

    raw_output: dict[str, Any] = field(default_factory=dict)
    """Raw OPA output for debugging."""

    @property
    def is_blocking(self) -> bool:
        """Whether this result blocks action."""
        if self.allowed:
            return False
        return self.enforcement in (
            EnforcementLevel.HARD_MANDATORY,
            EnforcementLevel.SOFT_MANDATORY,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize for evidence storage."""
        return {
            "policy_id": self.policy_id,
            "allowed": self.allowed,
            "enforcement": self.enforcement.value,
            "legal_citation": self.legal_citation,
            "violation_code": self.violation_code,
            "violation_message": self.violation_message,
            "remediation_steps": list(self.remediation_steps),
            "conditions_met": list(self.conditions_met),
            "conditions_missing": list(self.conditions_missing),
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_ms": self.evaluation_ms,
        }


@dataclass(frozen=True, slots=True)
class AggregatedResult:
    """Aggregated result from multiple policy evaluations.

    Combines individual PolicyResults into overall decision.
    """

    allowed: bool
    """Overall decision: True only if no blocking policies failed."""

    results: tuple[PolicyResult, ...] = ()
    """Individual policy results in evaluation order."""

    blocking_count: int = 0
    """Number of blocking failures."""

    advisory_count: int = 0
    """Number of advisory failures (allowed but warned)."""

    evaluated_at: datetime = field(default_factory=now_utc)
    """When aggregation occurred."""

    context: dict[str, Any] = field(default_factory=dict)
    """Additional context (e.g., input_hash)."""

    @classmethod
    def from_results(
        cls,
        results: list[PolicyResult],
        context: dict[str, Any] | None = None,
    ) -> AggregatedResult:
        """Aggregate list of PolicyResults.

        Args:
            results: Individual policy results
            context: Optional additional context

        Returns:
            AggregatedResult with overall decision
        """
        blocking_count = sum(1 for r in results if r.is_blocking)
        advisory_count = sum(
            1 for r in results if not r.allowed and r.enforcement == EnforcementLevel.ADVISORY
        )

        # Allowed only if no blocking failures
        allowed = blocking_count == 0

        return cls(
            allowed=allowed,
            results=tuple(results),
            blocking_count=blocking_count,
            advisory_count=advisory_count,
            context=context or {},
        )

    def get_blocking_results(self) -> list[PolicyResult]:
        """Get results that are blocking action."""
        return [r for r in self.results if r.is_blocking]

    def get_advisory_results(self) -> list[PolicyResult]:
        """Get results that are advisory warnings."""
        return [
            r for r in self.results if not r.allowed and r.enforcement == EnforcementLevel.ADVISORY
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for evidence storage."""
        return {
            "allowed": self.allowed,
            "blocking_count": self.blocking_count,
            "advisory_count": self.advisory_count,
            "results": [r.to_dict() for r in self.results],
            "evaluated_at": self.evaluated_at.isoformat(),
            "context": self.context,
        }
