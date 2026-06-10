# Copyright (c) 2024-2025, CanonSys
# SPDX-License-Identifier: Apache-2.0
"""Workflow state enums.

Provides state machines for generic workflow execution:
    WorkflowStatus: Overall workflow lifecycle states
    StepStatus: Individual step execution states
    ActionType: Actions that can be taken on workflow steps
    DocumentAccessPurpose: Purposes for JIT document access grants
    DocumentAccessStatus: Status of document access tokens

Regulatory context:
    - SOX 404: Multi-level approval documentation
    - Employment law: Decision audit trail
    - FCRA: Consent-based document access
"""

from __future__ import annotations

from enum import StrEnum

__all__ = (
    "ActionType",
    "DocumentAccessPurpose",
    "DocumentAccessStatus",
    "StepStatus",
    "WorkflowStatus",
)


class WorkflowStatus(StrEnum):
    """Workflow instance lifecycle states.

    State machine:
        DRAFT -> ACTIVE -> COMPLETED
                   |
                   +-> SUSPENDED -> ACTIVE
                   |
                   +-> CANCELLED
    """

    DRAFT = "draft"
    """Workflow created but not yet started."""

    ACTIVE = "active"
    """Workflow is in progress."""

    SUSPENDED = "suspended"
    """Workflow paused (can be resumed)."""

    COMPLETED = "completed"
    """Workflow finished successfully."""

    CANCELLED = "cancelled"
    """Workflow terminated before completion."""


class StepStatus(StrEnum):
    """Individual workflow step states.

    State machine:
        PENDING -> IN_PROGRESS -> APPROVED/REJECTED
                       |
                       +-> DELEGATED (new step for delegate)
                       |
                       +-> SKIPPED
                       |
                       +-> EXPIRED
    """

    PENDING = "pending"
    """Step waiting to be activated."""

    IN_PROGRESS = "in_progress"
    """Step is active and awaiting action."""

    APPROVED = "approved"
    """Step approved, workflow proceeds."""

    REJECTED = "rejected"
    """Step rejected, workflow may terminate."""

    DELEGATED = "delegated"
    """Step delegated to another user."""

    SKIPPED = "skipped"
    """Step skipped (conditional logic)."""

    EXPIRED = "expired"
    """Step exceeded SLA deadline."""


class ActionType(StrEnum):
    """Actions that can be taken on workflow steps."""

    APPROVE = "approve"
    """Approve and advance the workflow."""

    REJECT = "reject"
    """Reject and potentially terminate the workflow."""

    REQUEST_INFO = "request_info"
    """Request additional information before deciding."""

    DELEGATE = "delegate"
    """Delegate decision to another user."""

    ESCALATE = "escalate"
    """Escalate to higher authority."""


class DocumentAccessPurpose(StrEnum):
    """Purposes for granting JIT document access.

    Each purpose maps to specific document types and retention policies.
    FCRA requires consent before accessing consumer reports.
    """

    RESUME_REVIEW = "resume_review"
    """Access to review candidate resume."""

    BACKGROUND_CHECK = "background_check"
    """Access for background check processing."""

    INTERVIEW_PREP = "interview_prep"
    """Access to prepare for candidate interview."""

    OFFER_REVIEW = "offer_review"
    """Access to review offer materials."""

    PIP_REVIEW = "pip_review"
    """Access to review PIP documentation."""

    TERMINATION_REVIEW = "termination_review"
    """Access to review termination materials."""


class DocumentAccessStatus(StrEnum):
    """Status of document access tokens.

    State machine:
        ACTIVE -> USED (on first access)
               -> REVOKED (manual revocation)
               -> EXPIRED (TTL exceeded)
    """

    ACTIVE = "active"
    """Token is valid and can be used."""

    USED = "used"
    """Token has been used (may still allow access within TTL)."""

    REVOKED = "revoked"
    """Token manually revoked."""

    EXPIRED = "expired"
    """Token TTL has expired."""
