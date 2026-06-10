"""Verify that privileged review has been completed for legal matter.

Regulatory:
    - Attorney-Client Privilege (evidence protection)
    - Work Product Doctrine (FRCP 26(b)(3))
    - Common Interest Privilege
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import PrivilegedReviewStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyPrivilegedReviewCompleteSpecs", "verify_privileged_review_complete"]


class VerifyPrivilegedReviewCompleteSpecs(BaseModel):
    """Specs for verify privileged review complete phrase."""

    # inputs
    matter_id: UUID
    # outputs
    verified: bool | None = None
    status: PrivilegedReviewStatus | None = None
    reviewer_id: UUID | None = None
    completed_at: datetime | None = None
    privilege_type: str | None = None
    reason: str | None = None


verify_privileged_review_complete_operable = Operable.from_structure(
    VerifyPrivilegedReviewCompleteSpecs
)


@canon_phrase(
    verify_privileged_review_complete_operable,
    inputs={"matter_id"},
    outputs={
        "verified",
        "matter_id",
        "status",
        "reviewer_id",
        "completed_at",
        "privilege_type",
        "reason",
    },
)
async def verify_privileged_review_complete(
    options: VerifyPrivilegedReviewCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that privileged review has been completed for legal matter.

    Args:
        options: Options containing matter_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with verification status and review details.
    """
    matter_id: UUID = options.matter_id

    # Need ORDER BY for most recent review
    rows = await fetch(
        """
        SELECT status, reviewer_id, completed_at, privilege_type
        FROM privileged_reviews
        WHERE matter_id = $1
        ORDER BY completed_at DESC NULLS LAST
        LIMIT 1
        """,
        matter_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        return {
            "verified": False,
            "matter_id": matter_id,
            "status": PrivilegedReviewStatus.PENDING,
            "reviewer_id": None,
            "completed_at": None,
            "privilege_type": None,
            "reason": "No privileged review found",
        }

    row = rows[0]
    status = PrivilegedReviewStatus(row["status"])

    return {
        "verified": status in (PrivilegedReviewStatus.COMPLETE, PrivilegedReviewStatus.WAIVED),
        "matter_id": matter_id,
        "status": status,
        "reviewer_id": row.get("reviewer_id"),
        "completed_at": row.get("completed_at"),
        "privilege_type": row.get("privilege_type"),
        "reason": (
            None if status == PrivilegedReviewStatus.COMPLETE else f"Status: {status.value}"
        ),
    }


# Export auto-generated types from the Phrase object
VerifyPrivilegedReviewCompleteOptions = verify_privileged_review_complete.options_type
VerifyPrivilegedReviewCompleteResult = verify_privileged_review_complete.result_type
