"""Legal domain types.

Enums for hold types, appeal status, proceedings, NDAs, clean teams.
CriteriaLock dataclass for workflow immutability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

__all__ = [
    "AppealChannelType",
    "AppealStatus",
    "CleanTeamStatus",
    "CriteriaLock",
    "HoldType",
    "NDAStatus",
    "PrivilegedReviewStatus",
    "ProceedingsStatus",
]


# =============================================================================
# Enums
# =============================================================================


class HoldType(StrEnum):
    """Types of legal holds on resources."""

    LITIGATION = "litigation"
    REGULATORY = "regulatory"
    INVESTIGATION = "investigation"
    PRESERVATION = "preservation"


class AppealStatus(StrEnum):
    """Status of appeal exhaustion."""

    EXHAUSTED = "exhausted"
    PENDING = "pending"
    AVAILABLE = "available"
    WAIVED = "waived"
    TIME_BARRED = "time_barred"


class ProceedingsStatus(StrEnum):
    """Status of legal proceedings."""

    OPEN = "open"
    CLOSED = "closed"
    STAYED = "stayed"
    DISMISSED = "dismissed"
    SETTLED = "settled"


class AppealChannelType(StrEnum):
    """Types of appeal channels for automated decisions."""

    HUMAN_REVIEW = "human_review"
    OPT_OUT = "opt_out"
    CORRECTION = "correction"
    EXPLANATION = "explanation"


class CleanTeamStatus(StrEnum):
    """Status of clean team membership for M&A deals."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    NOT_MEMBER = "not_member"


class NDAStatus(StrEnum):
    """Status of NDA agreements."""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    PENDING = "pending"
    NOT_FOUND = "not_found"


class PrivilegedReviewStatus(StrEnum):
    """Status of privileged legal review."""

    COMPLETE = "complete"
    PENDING = "pending"
    WAIVED = "waived"
    EXPIRED = "expired"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class CriteriaLock:
    """Immutable criteria lock record.

    Used to prove evaluation criteria were defined
    BEFORE any selection/evaluation occurred.

    Attributes:
        id: Unique lock identifier.
        tenant_id: Tenant that owns this lock.
        workflow_id: ID of workflow this binds to.
        workflow_type: Type of workflow (termination, rif, promotion).
        criteria: Evaluation criteria that were frozen.
        criteria_hash: Deterministic hash for verification.
        locked_at: Timestamp when criteria were locked.
        locked_by: Actor who locked the criteria.
    """

    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    workflow_type: str
    criteria: dict[str, Any]
    criteria_hash: str
    locked_at: datetime
    locked_by: UUID | None
