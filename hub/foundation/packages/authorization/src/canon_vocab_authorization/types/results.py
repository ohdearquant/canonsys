"""Authorization result dataclasses.

Frozen result types for all authorization checks and actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from .status import ApprovalChainStatus, ERClearanceStatus, SegregationStatus

__all__ = [
    # Check results
    "ERClearanceResult",
    # Require results
    "RequireDistinctIdentitiesResult",
    "RequireDualApprovalResult",
    "RequireSegregationAnalysisResult",
    "RoleApprovalResult",
    # Verify results
    "VerifyApprovalChainCompleteResult",
]


# =============================================================================
# Check Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class ERClearanceResult:
    """Result of ER clearance check."""

    cleared: bool
    status: ERClearanceStatus
    subject_id: UUID
    checked_at: datetime
    er_case_id: UUID | None = None
    reason: str | None = None


# =============================================================================
# Require Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class RequireDistinctIdentitiesResult:
    """Result of distinct identities requirement check.

    Regulatory: SOX Section 404, COSO Framework, SOC 2 CC5.1, PCI DSS 6.4.2

    Attributes:
        distinct: Whether the identities are different (True = compliant)
        identity_a: First identity ID
        identity_b: Second identity ID
        role_a: Role of first identity (e.g., "preparer")
        role_b: Role of second identity (e.g., "approver")
        reason: Human-readable explanation
    """

    distinct: bool
    identity_a: UUID
    identity_b: UUID
    role_a: str
    role_b: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RequireDualApprovalResult:
    """Result of dual approval requirement check.

    Regulatory:
        - SOX Section 404 (Segregation of duties)
        - PCI DSS v4.0 Req. 8.6 (Multi-factor)
        - SOC 2 CC6.1 (Logical access controls)
    """

    satisfied: bool
    request_id: UUID
    approvals_required: int
    approvals_received: int
    approver_ids: tuple[UUID, ...] = ()
    first_approval_at: datetime | None = None
    second_approval_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RequireSegregationAnalysisResult:
    """Result of segregation analysis requirement check.

    Regulatory:
        - SOX Section 404 (Internal controls)
        - SOC 2 CC5.1 (Control activities)
        - COSO Framework (Segregation of duties)
    """

    satisfied: bool
    resource_id: UUID
    status: SegregationStatus
    analysis_id: UUID | None = None
    completed_at: datetime | None = None
    conflicts_found: int = 0
    reason: str | None = None


# =============================================================================
# Verify Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class VerifyApprovalChainCompleteResult:
    """Result of approval chain verification.

    Regulatory:
        - SOX Section 404 (Segregation of duties)
        - SOC 2 CC6.1 (Logical access controls)
        - ISO 27001 A.9.2 (User access management)
    """

    verified: bool
    request_id: UUID
    status: ApprovalChainStatus
    approvals_required: int
    approvals_received: int
    completed_at: datetime | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class RoleApprovalResult:
    """Result of role-specific approval verification.

    Regulatory:
        - SOX Section 404 (Internal controls require appropriate authority)
        - SOC 2 CC6.1 (Logical access controls)
        - GDPR Art. 37-39 (DPO requirements)
        - ISO 27001 A.6.1.1 (Roles and responsibilities)

    Attributes:
        approved: True if required role has approved
        request_id: The request that was checked
        required_role: The role that was required
        approver_id: ID of the approver (if approved)
        approver_name: Name of the approver (if approved)
        approved_at: Timestamp of approval (if approved)
        delegation_chain: If approval was delegated, the chain of delegation
        reason: Explanation if not approved
    """

    approved: bool
    request_id: UUID
    required_role: str
    approver_id: UUID | None = None
    approver_name: str | None = None
    approved_at: datetime | None = None
    delegation_chain: tuple[str, ...] | None = None
    reason: str | None = None
