"""Certificate-related types.

Re-exports core certificate types and defines feature-specific types.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

# Re-export types from local certificate module
from ..certificate import (
    CertificateClass,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
    InputFingerprint,
    ModelIdentity,
    ReviewBehavior,
)

__all__ = (
    # Re-exports from core
    "CertificateClass",
    "CertificateStatus",
    "DecisionCertificate",
    "DecisionCertificateContent",
    "DefensibilityState",
    "InputFingerprint",
    "IntegrityVerification",
    "ModelIdentity",
    # Feature-specific
    "ProceduralIntegrity",
    "ReviewBehavior",
)


class ProceduralIntegrity(BaseModel):
    """Procedural integrity metrics for a certificate.

    Tracks whether the process was followed correctly,
    independent of the outcome.
    """

    checkpoints_completed: int = 0
    checkpoints_expected: int = 0
    all_checkpoints_completed: bool = False
    goals_unchanged: bool = True
    resources_delivered: list[str] = Field(default_factory=list)
    resources_promised_not_delivered: list[str] = Field(default_factory=list)
    timeline_followed: bool = True
    integrity_score: float = 0.0  # 0-100
    integrity_issues: list[str] = Field(default_factory=list)


class IntegrityVerification(BaseModel):
    """Result of VERIFY_INTEGRITY action.

    Deterministic pass/fail based on evidence chain verification.
    """

    case_id: UUID
    integrity_passed: bool
    integrity_score: float  # 0-100
    evidence_count: int
    verified_count: int
    issues: list[str]
