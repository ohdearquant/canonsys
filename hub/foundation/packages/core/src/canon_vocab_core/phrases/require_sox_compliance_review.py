"""Require SOX compliance review phrase.

Requires SOX compliance review for financial controls.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import SOXReviewStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireSOXComplianceReviewSpecs", "require_sox_compliance_review"]


class RequireSOXComplianceReviewSpecs(BaseModel):
    """Specs for require SOX compliance review phrase.

    Regulatory:
        - SOX Section 302 (Corporate responsibility)
        - SOX Section 404 (Internal control assessment)
        - PCAOB AS 2201 (Auditing internal control)
    """

    # inputs
    control_id: UUID
    # outputs
    satisfied: bool
    status: SOXReviewStatus | None = None
    review_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    findings_count: int = 0
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireSOXComplianceReviewSpecs),
    inputs={"control_id"},
    outputs={
        "satisfied",
        "control_id",
        "status",
        "review_id",
        "reviewer_id",
        "reviewed_at",
        "findings_count",
        "reason",
    },
)
async def require_sox_compliance_review(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Require SOX compliance review for financial controls.

    Args:
        options: Requirement options (control_id)
        ctx: Request context

    Returns:
        dict with satisfaction status and review details

    Raises:
        RequirementNotMetError: If review not found or not compliant.
    """
    control_id = options.get("control_id")

    query = """
        SELECT review_id, status, reviewer_id, reviewed_at, findings_count
        FROM sox_compliance_reviews
        WHERE control_id = $1 AND tenant_id = $2
        ORDER BY reviewed_at DESC
        LIMIT 1
    """
    rows = await fetch(
        query,
        control_id,
        ctx.tenant_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Already filtered in query
    )

    if not rows:
        raise RequirementNotMetError(
            requirement="sox_compliance_review",
            reason=f"SOX compliance review required for control {control_id}",
        )

    row = rows[0]
    status = SOXReviewStatus(row["status"])

    if status != SOXReviewStatus.COMPLIANT:
        raise RequirementNotMetError(
            requirement="sox_compliance_review",
            reason=f"SOX review status: {status.value}",
        )

    return {
        "satisfied": True,
        "control_id": control_id,
        "status": status,
        "review_id": row["review_id"],
        "reviewer_id": row["reviewer_id"],
        "reviewed_at": row["reviewed_at"],
        "findings_count": row["findings_count"],
        "reason": None,
    }
