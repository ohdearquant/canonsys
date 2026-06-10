"""Operational errors for enforcement features.

These are distinct from invariant violations (exceptions.py):
- RequirementNotMetError: A precondition check failed (retryable if conditions change)
- InvariantViolation: A regulatory invariant was violated (deterministic failure)

All exceptions inherit from CanonError hierarchy so they can be caught
with `except CanonError`.
"""

from __future__ import annotations

from uuid import UUID

from canon.exceptions import ValidationError

__all__ = ["RequirementNotMetError"]


class RequirementNotMetError(ValidationError):
    """A requirement precondition was not met.

    Used by require_* features when a precondition fails.
    Unlike InvariantViolation, this may be retryable if
    the underlying condition changes.

    This is a compliance gate error indicating a precondition
    was not met. The caller must satisfy the requirement before
    proceeding.

    Inherits from ValidationError so it's caught by `except CanonError`.
    """

    default_message = "Requirement not met"
    default_retryable = True  # May be retryable if conditions change

    def __init__(
        self,
        requirement: str,
        reason: str,
        evidence_id: UUID | None = None,
    ):
        self.requirement = requirement
        self.reason = reason
        self.evidence_id = evidence_id
        super().__init__(
            f"Requirement not met: {requirement} - {reason}",
            details={
                "requirement": requirement,
                "reason": reason,
                **({"evidence_id": str(evidence_id)} if evidence_id else {}),
            },
            retryable=True,
        )
