"""Policy lifecycle status enumeration."""

from kron.types import Enum


class PolicyStatus(Enum):
    """Policy lifecycle status.

    Tracks policy from authoring through retirement.
    Only ACTIVE policies are enforced.
    """

    DRAFT = "draft"  # Being authored
    REVIEW = "review"  # Under legal review
    APPROVED = "approved"  # Legal approved, not yet active
    ACTIVE = "active"  # Currently enforced
    DEPRECATED = "deprecated"  # Superseded, in grace period
    RETIRED = "retired"  # No longer applicable
