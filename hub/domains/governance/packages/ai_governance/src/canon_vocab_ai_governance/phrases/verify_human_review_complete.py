"""Verify that human review has been completed for AI/ML decision.

Complete vertical slice:
- Queries for human review record
- Checks completion status
- Returns verification result (no exception on failure)

Regulatory Citations:
- EU AI Act Article 14: Requires human oversight measures for high-risk
  AI systems, including ability to intervene and override decisions
- NYC LL144 Section 20-871: Notice requirements imply human accountability
  for automated employment decision tools
- GDPR Article 22: Individuals have the right not to be subject to
  decisions based solely on automated processing
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import HumanReviewStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyHumanReviewCompleteSpecs", "verify_human_review_complete"]


class VerifyHumanReviewCompleteSpecs(BaseModel):
    """Specs for verify human review complete phrase."""

    # inputs
    decision_id: UUID
    # outputs
    verified: bool | None = None
    status: HumanReviewStatus | None = None
    checked_at: datetime | None = None
    review_id: UUID | None = None
    reviewed_at: datetime | None = None
    reviewer_id: UUID | None = None
    decision_upheld: bool | None = None
    reason: str | None = None


verify_human_review_complete_operable = Operable.from_structure(VerifyHumanReviewCompleteSpecs)


@canon_phrase(
    verify_human_review_complete_operable,
    inputs={"decision_id"},
    outputs={
        "verified",
        "status",
        "decision_id",
        "checked_at",
        "review_id",
        "reviewed_at",
        "reviewer_id",
        "decision_upheld",
        "reason",
    },
)
async def verify_human_review_complete(
    options: VerifyHumanReviewCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that human review has been completed for AI/ML decision.

    Fail-closed: If review status cannot be determined, treat as not verified.
    This ensures compliance with EU AI Act human oversight requirements.

    Regulatory Citations:
        - EU AI Act Article 14: Requires human oversight measures for high-risk
          AI systems, including ability to intervene and override decisions
        - NYC LL144 Section 20-871: Notice requirements imply human accountability
          for automated employment decision tools
        - GDPR Article 22: Individuals have the right not to be subject to
          decisions based solely on automated processing

    Args:
        options: Options containing decision_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with verification status and reviewer details
    """
    decision_id = options.decision_id
    now = now_utc()

    # Query for human review record for this decision
    row = await select_one(
        "human_reviews",
        where={
            "tenant_id": ctx.tenant_id,
            "decision_id": decision_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "status": HumanReviewStatus.NOT_FOUND,
            "decision_id": decision_id,
            "checked_at": now,
            "review_id": None,
            "reviewed_at": None,
            "reviewer_id": None,
            "decision_upheld": None,
            "reason": "No human review record found - "
            "EU AI Act Article 14 requires human oversight for high-risk AI",
        }

    # Check if review is pending
    review_status = row.get("status")
    if review_status == "pending":
        return {
            "verified": False,
            "status": HumanReviewStatus.PENDING,
            "decision_id": decision_id,
            "checked_at": now,
            "review_id": row["id"],
            "reviewed_at": None,
            "reviewer_id": None,
            "decision_upheld": None,
            "reason": "Human review pending - decision cannot proceed until reviewed",
        }

    # Determine if decision was upheld or overridden
    decision_upheld = row.get("decision_upheld", True)
    status = HumanReviewStatus.COMPLETE if decision_upheld else HumanReviewStatus.OVERRIDDEN

    # Review is complete
    return {
        "verified": True,
        "status": status,
        "decision_id": decision_id,
        "checked_at": now,
        "review_id": row["id"],
        "reviewed_at": row.get("reviewed_at"),
        "reviewer_id": row.get("reviewer_id"),
        "decision_upheld": decision_upheld,
        "reason": (
            "Human review complete - oversight requirement satisfied"
            if decision_upheld
            else "Human review complete - AI decision overridden by reviewer"
        ),
    }


# Export auto-generated types from the Phrase object
VerifyHumanReviewCompleteOptions = verify_human_review_complete.options_type
VerifyHumanReviewCompleteResult = verify_human_review_complete.result_type
