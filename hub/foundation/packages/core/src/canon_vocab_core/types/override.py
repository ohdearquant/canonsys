"""Override-related type definitions.

Types for break-glass invocations and executive override operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, Any

from kron.utils import now_utc

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "BreakGlassCertificate",
    "BreakGlassReason",
    "ExecutiveOverride",
    "OverrideAuthority",
]


class BreakGlassReason(StrEnum):
    """Enumerated reasons for break-glass invocation.

    These are NOT checkboxes - typed attestation text is still required.
    """

    SAFETY_THREAT = "safety_threat"
    """Immediate safety concern (e.g., active threat, harassment)."""

    SYSTEM_OUTAGE = "system_outage"
    """Governing system unavailable."""

    TIME_CRITICAL = "time_critical"
    """Deadline cannot be met through normal process."""

    LEGAL_MANDATE = "legal_mandate"
    """Legal/regulatory requirement for immediate action."""

    OTHER = "other"
    """Other reason - requires detailed attestation."""


@dataclass(frozen=True, slots=True)
class BreakGlassCertificate:
    """Certificate issued for break-glass actions.

    IMMUTABLE: Once created, cannot be modified.
    DEGRADED DEFENSIBILITY: Harder to defend in litigation.
    NON-EXPORTABLE: Cannot leave organization without Legal sign-off.
    """

    # Required fields
    certificate_id: UUID
    action: str
    subject_id: UUID
    actor_id: UUID
    tenant_id: UUID
    reason_code: BreakGlassReason
    attestation: str  # Typed justification, NOT checkbox

    # Fixed defaults (system-enforced)
    certificate_type: str = "BREAK_GLASS"
    case_id: UUID | None = None
    issued_at: datetime = field(default_factory=now_utc)
    review_required_by: str = "Legal"
    defensibility_state: str = "DEGRADED"
    exportable: bool = False
    notified_parties: tuple[str, ...] = ("Legal", "ER", "Audit")

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "certificate_id": str(self.certificate_id),
            "certificate_type": self.certificate_type,
            "action": self.action,
            "subject_id": str(self.subject_id),
            "actor_id": str(self.actor_id),
            "tenant_id": str(self.tenant_id),
            "reason_code": self.reason_code.value,
            "attestation": self.attestation,
            "case_id": str(self.case_id) if self.case_id else None,
            "issued_at": self.issued_at.isoformat(),
            "review_required_by": self.review_required_by,
            "defensibility_state": self.defensibility_state,
            "exportable": self.exportable,
            "notified_parties": list(self.notified_parties),
        }


class OverrideAuthority(str, Enum):
    """Authorized executive roles for override."""

    CHRO = "chro"  # Chief HR Officer
    GC = "gc"  # General Counsel
    CEO = "ceo"  # Chief Executive Officer
    CFO = "cfo"  # Chief Financial Officer


@dataclass(frozen=True, slots=True)
class ExecutiveOverride:
    """Executive override record.

    Records a policy deviation authorized by an executive role.
    Creates a certificate with DEGRADED defensibility requiring Legal review.
    """

    id: UUID
    tenant_id: UUID
    authority: OverrideAuthority
    authority_user_id: UUID
    override_scope: str
    policy_deviation: str
    risk_acceptance: bool
    override_hash: str
    created_at: datetime
    referenced_certificate_id: UUID | None = None
    attestation_text: str | None = None
