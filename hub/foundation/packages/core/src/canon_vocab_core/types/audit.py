"""Audit-related type definitions.

Types for audit completion and currency verification.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "AuditStatus",
    "VerifyAuditCompleteResult",
    "VerifyAuditCurrentResult",
]


class AuditStatus(StrEnum):
    """Status of an audit."""

    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class VerifyAuditCompleteResult:
    """Result of audit completion verification.

    Regulatory:
        - SOX Section 404 (Internal control audit)
        - SOC 2 CC4.1 (Monitoring activities)
        - ISO 27001 A.18.2 (Security reviews)
    """

    verified: bool
    audit_id: UUID
    resource_id: UUID
    status: AuditStatus
    completed_at: datetime | None = None
    auditor_id: UUID | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class VerifyAuditCurrentResult:
    """Result of audit currency verification.

    Checks that an audit is within its age threshold.

    Regulatory:
        - NYC LL144 Section 20-870 (Bias audit within 1 year)
        - SOX Section 404 (Annual internal control audit)
        - SOC 2 CC4.1 (Periodic monitoring)
        - ISO 27001 A.18.2 (Security reviews)
    """

    verified: bool
    resource_id: UUID
    audit_type: str
    audit_id: UUID | None = None
    last_audit_at: datetime | None = None
    expires_at: datetime | None = None
    days_since_audit: int | None = None
    reason: str | None = None
