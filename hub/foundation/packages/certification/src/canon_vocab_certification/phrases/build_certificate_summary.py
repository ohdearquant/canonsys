"""Build human-readable certificate summary.

Pure function that transforms certificate data into
lawyer-friendly display format.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

__all__ = ["BuildCertificateSummarySpecs", "build_certificate_summary"]

# Threshold for procedural validity
INTEGRITY_THRESHOLD = 70.0


class BuildCertificateSummarySpecs(BaseModel):
    """Specs for certificate summary phrase."""

    # inputs
    case_id: UUID
    decision_type: str
    certified_at: datetime | None = None
    policy_version: str | None = None
    integrity_score: float
    checkpoints_completed: int
    checkpoints_expected: int
    immutability_hash: str | None = None
    # outputs
    status_display: str | None = None
    checkpoints_display: str | None = None


@canon_phrase(
    Operable.from_structure(BuildCertificateSummarySpecs),
    inputs={
        "case_id",
        "decision_type",
        "certified_at",
        "policy_version",
        "integrity_score",
        "checkpoints_completed",
        "checkpoints_expected",
        "immutability_hash",
    },
    outputs={
        "case_id",
        "decision_type",
        "certified_at",
        "policy_version",
        "integrity_score",
        "status_display",
        "checkpoints_display",
        "immutability_hash",
    },
)
def build_certificate_summary(
    options: BuildCertificateSummarySpecs,
) -> dict:
    """Build human-readable certificate summary.

    Pure function - no DB access, just data transformation.

    Args:
        options: Summary options containing case details and integrity metrics

    Returns:
        Dict with formatted summary for UI rendering
    """
    status_display = (
        "PROCEDURALLY VALID" if options.integrity_score >= INTEGRITY_THRESHOLD else "DEFICIENT"
    )
    checkpoints_display = (
        f"{options.checkpoints_completed}/{options.checkpoints_expected} checkpoints"
    )

    return {
        "case_id": str(options.case_id),
        "decision_type": options.decision_type,
        "certified_at": (options.certified_at.isoformat() if options.certified_at else None),
        "policy_version": options.policy_version,
        "integrity_score": options.integrity_score,
        "status_display": status_display,
        "checkpoints_display": checkpoints_display,
        "immutability_hash": options.immutability_hash,
    }
