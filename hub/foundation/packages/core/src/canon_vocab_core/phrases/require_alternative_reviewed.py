"""Require alternative reviewed phrase.

Verifies that alternatives have been reviewed before proceeding.
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

from ..types import AlternativeReviewStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireAlternativeReviewedSpecs", "require_alternative_reviewed"]


class RequireAlternativeReviewedSpecs(BaseModel):
    """Specs for require alternative reviewed phrase.

    Regulatory:
        - EEOC UGESP Section 3B (Less discriminatory alternatives)
        - EU AI Act Art. 9 (Risk management alternatives)
        - ADA 42 USC 12112 (Reasonable accommodation)
    """

    # inputs
    resource_id: UUID
    alternative_type: str
    # outputs
    satisfied: bool
    review_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewed_at: datetime | None = None
    conclusion: str | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireAlternativeReviewedSpecs),
    inputs={"resource_id", "alternative_type"},
    outputs={
        "satisfied",
        "resource_id",
        "alternative_type",
        "review_id",
        "reviewer_id",
        "reviewed_at",
        "conclusion",
        "reason",
    },
)
async def require_alternative_reviewed(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Require that alternatives have been reviewed before proceeding.

    Generic alternative review gate for any compliance domain.
    Domain libraries compose this with specific alternative types:
    - EEOC: "less_discriminatory" alternatives
    - EU AI Act: "less_invasive" alternatives
    - ADA: "reasonable_accommodation" alternatives

    Args:
        options: Requirement options (resource_id, alternative_type)
        ctx: Request context

    Returns:
        dict with satisfaction status and review details

    Raises:
        RequirementNotMetError: If no review found or review incomplete.
    """
    resource_id = options.get("resource_id")
    alternative_type = options.get("alternative_type")

    query = """
        SELECT review_id, reviewer_id, reviewed_at, status, conclusion
        FROM alternative_reviews
        WHERE resource_id = $1 AND alternative_type = $2 AND tenant_id = $3
        ORDER BY reviewed_at DESC NULLS LAST
        LIMIT 1
    """
    rows = await fetch(
        query,
        resource_id,
        alternative_type,
        ctx.tenant_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Already filtered in query
    )

    if not rows:
        raise RequirementNotMetError(
            requirement="alternative_reviewed",
            reason=f"Alternative review required ({alternative_type})",
        )

    row = rows[0]
    status = AlternativeReviewStatus(row["status"])

    if status not in (
        AlternativeReviewStatus.REVIEWED,
        AlternativeReviewStatus.NOT_APPLICABLE,
        AlternativeReviewStatus.WAIVED,
    ):
        raise RequirementNotMetError(
            requirement="alternative_reviewed",
            reason=f"Alternative review status: {status.value}",
        )

    return {
        "satisfied": True,
        "resource_id": resource_id,
        "alternative_type": alternative_type,
        "review_id": row["review_id"],
        "reviewer_id": row["reviewer_id"],
        "reviewed_at": row["reviewed_at"],
        "conclusion": row["conclusion"],
        "reason": None,
    }
