"""AI Governance domain exceptions.

These exceptions are raised by AI governance phrases when invariants are violated.
All inherit from AIGovernanceViolation (the domain's base exception).

Re-exports from canon.enforcement.exceptions for domain-specific access.
"""

from canon.enforcement.exceptions import (
    AIGovernanceViolation,
    BiasAssessmentMissingError,
    DisclosureMissingError,
    HumanReviewMissingError,
    ToolConfigMismatchError,
)

__all__ = [
    "AIGovernanceViolation",
    "BiasAssessmentMissingError",
    "DisclosureMissingError",
    "HumanReviewMissingError",
    "ToolConfigMismatchError",
]
