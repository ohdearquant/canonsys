"""Require that periodic recertification is current.

Complete vertical slice:
- Validates privilege/access recertification is not overdue
- Wraps check_privilege_review with gate semantics
- Raises ReviewOverdueError if recertification is past due

Regulatory: SOX Section 404 - Periodic access review requirements
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ReviewOverdueError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireRecertificationCurrentSpecs",
    "ReviewOverdueError",
    "require_recertification_current",
]


class RequireRecertificationCurrentSpecs(BaseModel):
    """Specs for require recertification current phrase."""

    # inputs
    subject_id: UUID
    review_type: str = "privilege"
    last_review_date: date_cls | None = None
    review_period_days: int = 90
    # outputs
    satisfied: bool = False
    days_since_review: int | None = None


@canon_phrase(
    Operable.from_structure(RequireRecertificationCurrentSpecs),
    inputs={"subject_id", "review_type", "last_review_date", "review_period_days"},
    outputs={
        "satisfied",
        "subject_id",
        "review_type",
        "days_since_review",
        "review_period_days",
    },
)
async def require_recertification_current(
    options: RequireRecertificationCurrentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that periodic recertification is current for a subject.

    Gate pattern that enforces recertification currency. Wraps
    check_privilege_review with raise-on-failure semantics.

    Args:
        options: Options containing subject_id, review_type, last_review_date,
                 review_period_days.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if recertification is current.

    Raises:
        ReviewOverdueError: If recertification is overdue.

    Regulatory citations:
        - SOX Section 404: Periodic access review requirements
        - SOC 2 CC6.1: Logical access review at defined intervals
        - HIPAA Security Rule: Access authorization review
        - PCI DSS 7.2: Access control systems review
    """
    from .check_privilege_review import (
        CheckPrivilegeReviewSpecs,
        check_privilege_review,
    )

    check_options = CheckPrivilegeReviewSpecs(
        subject_id=options.subject_id,
        last_review_date=options.last_review_date,
        review_period_days=options.review_period_days,
    )
    result = await check_privilege_review(check_options, ctx)

    if result["review_due"]:
        days_overdue = 0
        if result["days_since_review"] is not None:
            days_overdue = result["days_since_review"] - options.review_period_days
        else:
            # Never reviewed - consider maximally overdue
            days_overdue = options.review_period_days

        raise ReviewOverdueError(
            subject_id=options.subject_id,
            review_type=options.review_type,
            days_overdue=max(days_overdue, 1),
            review_period_days=options.review_period_days,
        )

    return {
        "satisfied": True,
        "subject_id": options.subject_id,
        "review_type": options.review_type,
        "days_since_review": result["days_since_review"],
        "review_period_days": options.review_period_days,
    }
