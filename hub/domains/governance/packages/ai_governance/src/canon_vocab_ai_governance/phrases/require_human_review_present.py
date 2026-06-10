"""Require human review be present for AI/ML automated decisions.

Complete vertical slice:
- Queries for human review record with completed status
- Optionally scopes to specific decision_id
- Raises RequirementNotMetError if no review found

Regulatory:
- EU AI Act Art. 14: Human oversight
- GDPR Art. 22: Automated decision-making
- NYC LL144 Section 20-871: Bias audits
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireHumanReviewPresentSpecs", "require_human_review_present"]


class RequireHumanReviewPresentSpecs(BaseModel):
    """Specs for require human review present phrase."""

    # inputs
    model_id: UUID
    decision_id: UUID | None = None
    # outputs
    satisfied: bool | None = None
    reviewer_id: UUID | None = None
    review_timestamp: datetime | None = None
    reason: str | None = None


require_human_review_present_operable = Operable.from_structure(RequireHumanReviewPresentSpecs)


@canon_phrase(
    require_human_review_present_operable,
    inputs={"model_id", "decision_id"},
    outputs={
        "satisfied",
        "model_id",
        "decision_id",
        "reviewer_id",
        "review_timestamp",
        "reason",
    },
)
async def require_human_review_present(
    options: RequireHumanReviewPresentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require human review be present for AI/ML automated decisions.

    Raises RequirementNotMetError if no human review record exists.

    Regulatory:
        - EU AI Act Art. 14 (Human oversight)
        - GDPR Art. 22 (Automated decision-making)
        - NYC LL144 Section 20-871 (Bias audits)

    Args:
        options: Options containing model_id and optional decision_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with satisfied=True and review details if satisfied

    Raises:
        RequirementNotMetError: If no human review record exists
    """
    model_id = options.model_id
    decision_id = options.decision_id

    # Build where clause
    where: dict[str, Any] = {
        "model_id": model_id,
        "tenant_id": ctx.tenant_id,
        "status": "completed",
    }
    if decision_id is not None:
        where["decision_id"] = decision_id

    row = await select_one(
        "ai_human_reviews",
        where=where,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="human_review_present",
            reason=f"No human review found for model {model_id}",
        )

    return {
        "satisfied": True,
        "model_id": model_id,
        "decision_id": decision_id,
        "reviewer_id": row.get("reviewer_id"),
        "review_timestamp": row.get("review_timestamp"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireHumanReviewPresentOptions = require_human_review_present.options_type
RequireHumanReviewPresentResult = require_human_review_present.result_type
