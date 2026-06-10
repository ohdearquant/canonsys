"""Require legal review completion before proceeding.

Raises LegalReviewRequiredError if no completed legal review exists.

Regulatory:
    - Attorney-Client Privilege (evidence preservation)
    - FRCP 26(b)(3) (Work product doctrine)
    - SOX Section 802 (Document retention)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import LegalReviewRequiredError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireLegalReviewCompleteSpecs", "require_legal_review_complete"]


class RequireLegalReviewCompleteSpecs(BaseModel):
    """Specs for require legal review complete phrase."""

    # inputs
    matter_id: UUID
    # outputs
    satisfied: bool | None = None
    review_id: UUID | None = None
    reviewer_id: UUID | None = None
    completed_at: datetime | None = None
    reason: str | None = None


require_legal_review_complete_operable = Operable.from_structure(RequireLegalReviewCompleteSpecs)


@canon_phrase(
    require_legal_review_complete_operable,
    inputs={"matter_id"},
    outputs={
        "satisfied",
        "matter_id",
        "review_id",
        "reviewer_id",
        "completed_at",
        "reason",
    },
)
async def require_legal_review_complete(
    options: RequireLegalReviewCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Require legal review completion before proceeding.

    Args:
        options: Options containing matter_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfaction status if legal review is complete.

    Raises:
        LegalReviewRequiredError: If no completed legal review exists.
    """
    matter_id: UUID = options.matter_id

    # Need ORDER BY for most recent completed review
    rows = await fetch(
        """
        SELECT review_id, reviewer_id, completed_at
        FROM legal_reviews
        WHERE matter_id = $1 AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        """,
        matter_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        raise LegalReviewRequiredError(
            matter_id=matter_id,
            reason=f"Legal review required for matter {matter_id}",
        )

    row = rows[0]
    return {
        "satisfied": True,
        "matter_id": matter_id,
        "review_id": row.get("review_id"),
        "reviewer_id": row.get("reviewer_id"),
        "completed_at": row.get("completed_at"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireLegalReviewCompleteOptions = require_legal_review_complete.options_type
RequireLegalReviewCompleteResult = require_legal_review_complete.result_type
