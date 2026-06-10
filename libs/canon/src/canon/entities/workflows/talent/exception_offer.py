# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Exception Offer workflow entities.

Provides entities for managing compensation exception approvals:
    ExceptionOffer: Main offer record with compensation and workflow state
    OfferApproval: Individual approval decisions in the workflow chain

State Machine:
    DRAFT -> PENDING_HM -> PENDING_SVP (optional) -> PENDING_VP
    -> PENDING_FINANCE -> PENDING_CEO -> APPROVED/REJECTED

Regulatory context:
    - SOX 404: Multi-level approval documentation
    - Employment law: Compensation decision audit trail
    - FLSA: Fair compensation practices documentation
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from kron.types import FK, Enum

from ...entity import Entity, register_entity
from ...shared import Person, TenantAware, User
from .job import Job

__all__ = (
    # Enums
    "OfferStatus",
    "ApproverRole",
    "ApprovalStatus",
    # Content models
    "ExceptionOfferContent",
    "OfferApprovalContent",
    # Entities
    "ExceptionOffer",
    "OfferApproval",
    # Constants
    "STATUS_TO_APPROVER_ROLE",
    "NEXT_STATUS_ON_APPROVAL",
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OfferStatus(Enum):
    """Exception offer workflow states.

    State machine:
    DRAFT -> PENDING_HM -> PENDING_SVP -> PENDING_VP
    -> PENDING_FINANCE -> PENDING_CEO -> APPROVED/REJECTED

    Note: PENDING_SVP is optional and can be skipped based on offer config.
    """

    DRAFT = "draft"
    PENDING_HM = "pending_hm"  # Pending Hiring Manager
    PENDING_SVP = "pending_svp"  # Pending Senior VP (optional)
    PENDING_VP = "pending_vp"  # Pending VP
    PENDING_FINANCE = "pending_finance"
    PENDING_CEO = "pending_ceo"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApproverRole(Enum):
    """Roles in the approval chain."""

    HIRING_MANAGER = "hiring_manager"
    SVP = "svp"  # Senior VP
    VP = "vp"
    FINANCE = "finance"
    CEO = "ceo"


class ApprovalStatus(Enum):
    """Individual approval status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# State Machine Constants
# ---------------------------------------------------------------------------

STATUS_TO_APPROVER_ROLE: dict[OfferStatus, ApproverRole] = {
    OfferStatus.PENDING_HM: ApproverRole.HIRING_MANAGER,
    OfferStatus.PENDING_SVP: ApproverRole.SVP,
    OfferStatus.PENDING_VP: ApproverRole.VP,
    OfferStatus.PENDING_FINANCE: ApproverRole.FINANCE,
    OfferStatus.PENDING_CEO: ApproverRole.CEO,
}

NEXT_STATUS_ON_APPROVAL: dict[OfferStatus, OfferStatus] = {
    OfferStatus.PENDING_HM: OfferStatus.PENDING_SVP,
    OfferStatus.PENDING_SVP: OfferStatus.PENDING_VP,
    OfferStatus.PENDING_VP: OfferStatus.PENDING_FINANCE,
    OfferStatus.PENDING_FINANCE: OfferStatus.PENDING_CEO,
    OfferStatus.PENDING_CEO: OfferStatus.APPROVED,
}


# ---------------------------------------------------------------------------
# ExceptionOffer
# ---------------------------------------------------------------------------


class ExceptionOfferContent(TenantAware):
    """Content for an exception offer record.

    Exception offers track compensation packages that exceed standard bands
    and require multi-level approval. Each approval step is recorded as
    an OfferApproval entity with evidence chain linking.

    Compensation is stored as Decimal for precision:
    - base_salary: Annual base salary in USD
    - bonus: Sign-on or annual bonus in USD
    - equity: Stock/equity value in USD
    - total_comp: Computed total (base + bonus + equity)
    """

    # Subject reference
    candidate_id: FK[Person]
    """The candidate this offer is for."""

    # Job reference
    job_id: FK[Job] | None = None
    """The job posting this offer is associated with."""

    # Creator reference
    created_by_id: FK[User] | None = None
    """User who created the offer."""

    # Position info
    position_title: str | None = None
    """Title of the position this offer is for."""

    # Compensation details (Decimal for financial precision)
    base_salary: Decimal
    """Annual base salary in USD."""

    bonus: Decimal = Decimal("0.00")
    """Sign-on or annual bonus in USD."""

    equity: Decimal = Decimal("0.00")
    """Stock/equity value in USD."""

    total_comp: Decimal
    """Total compensation (base + bonus + equity)."""

    # Workflow status
    status: OfferStatus = OfferStatus.DRAFT
    """Current workflow status."""

    skip_svp: bool = False
    """Whether to skip SVP approval step."""

    justification: str | None = None
    """Business justification for compensation exception."""

    rejection_reason: str | None = None
    """Reason for rejection (populated when status=REJECTED)."""

    rejected_by_id: FK[User] | None = None
    """User who rejected the offer."""

    # Evidence tracking
    evidence_bundle_id: UUID | None = None
    """Evidence bundle ID created on final decision."""

    # Resume access control
    resume_access_granted: bool = False
    """Whether resume access has been granted (on CEO approval)."""

    resume_access_revoked_at: datetime | None = None
    """When resume access was revoked (on final decision)."""

    # Workflow timestamps
    submitted_at: datetime | None = None
    """When offer was submitted for approval."""

    completed_at: datetime | None = None
    """When workflow completed (approved or rejected)."""

    @property
    def is_pending(self) -> bool:
        """Check if offer is in any pending state."""
        return self.status in {
            OfferStatus.PENDING_HM,
            OfferStatus.PENDING_SVP,
            OfferStatus.PENDING_VP,
            OfferStatus.PENDING_FINANCE,
            OfferStatus.PENDING_CEO,
        }

    @property
    def is_terminal(self) -> bool:
        """Check if offer is in a terminal state."""
        return self.status in {OfferStatus.APPROVED, OfferStatus.REJECTED}

    def compute_total_comp(self) -> Decimal:
        """Compute total compensation from components."""
        return self.base_salary + self.bonus + self.equity


@register_entity("exception_offers")
class ExceptionOffer(Entity):
    """Entity representing an exception offer.

    Exception offers go through a multi-level approval workflow.
    Each state transition creates evidence via OfferApproval entities.
    """

    content: ExceptionOfferContent

    # Composite indexes for common query patterns
    _indexes = [
        # Fast lookup by tenant + status (approval queue)
        {"columns": ["tenant_id", "status"]},
        # Fast lookup by candidate (offer history)
        {"columns": ["candidate_id"]},
        # Fast lookup by creator (my offers)
        {"columns": ["created_by_id"]},
    ]


# ---------------------------------------------------------------------------
# OfferApproval
# ---------------------------------------------------------------------------


class OfferApprovalContent(TenantAware):
    """Content for an individual approval decision.

    Each approval represents one step in the multi-level approval chain.
    Immutable after creation for audit trail integrity.
    """

    # Relationships
    offer_id: FK[ExceptionOffer]
    """The exception offer this approval belongs to."""

    # Approver
    approver_id: FK[User] | None = None
    """User who made this approval decision."""

    approver_role: ApproverRole
    """Role of approver (hiring_manager, svp, vp, finance, ceo)."""

    # Decision
    status: ApprovalStatus = ApprovalStatus.PENDING
    """Approval status: pending, approved, rejected."""

    comments: str | None = None
    """Optional comments from approver."""

    # Timing
    approved_at: datetime | None = None
    """When approval/rejection decision was made."""

    # Evidence linking
    evidence_id: UUID | None = None
    """Evidence record ID for this approval step."""

    chain_entry_id: UUID | None = None
    """Chain entry ID linking this approval to the evidence chain."""


@register_entity("offer_approvals", immutable=True)
class OfferApproval(Entity):
    """Immutable approval record. Insert-only for audit trail integrity.

    Each approval creates a link in the evidence chain for the offer.
    Approvals cannot be modified after creation - corrections require
    supersession (new record pointing back to old).
    """

    content: OfferApprovalContent

    # Composite indexes for common query patterns
    _indexes = [
        # Fast lookup by offer + role (check existing approvals)
        {"columns": ["offer_id", "approver_role"]},
        # Fast lookup by approver (my approvals)
        {"columns": ["approver_id"]},
        # Fast lookup by status (pending approvals)
        {"columns": ["status"]},
    ]
