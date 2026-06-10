"""Authorization status enumerations.

Status types for various authorization checks and workflows.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ApprovalChainStatus",
    "ApproverStatus",
    "ClearanceLevel",
    "ERClearanceStatus",
    "SegregationStatus",
]


class ERClearanceStatus(StrEnum):
    """ER (Employee Relations) clearance status values.

    Used to track whether a subject is cleared for termination or
    other HR actions that require ER review.
    """

    CLEARED = "cleared"  # No active ER context
    ACTIVE_CONTEXT = "active_context"  # Active ER matter exists
    UNKNOWN = "unknown"  # Cannot determine (treat as not cleared)


class ClearanceLevel(StrEnum):
    """Security clearance levels.

    Used for information release controls under ITAR, EAR, and NISPOM.
    Levels are ordered from least to most sensitive.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"


class SegregationStatus(StrEnum):
    """Segregation of duties analysis status.

    Tracks the progress of SoD analysis for access control decisions.
    """

    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    FAILED = "failed"


class ApprovalChainStatus(StrEnum):
    """Status of an approval chain.

    Tracks whether all required approvals have been obtained.
    """

    COMPLETE = "complete"
    PENDING = "pending"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApproverStatus(StrEnum):
    """Status of an individual approver in the chain.

    Tracks the approval state of a single approver within
    a multi-approver workflow.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DELEGATED = "delegated"
    SKIPPED = "skipped"
