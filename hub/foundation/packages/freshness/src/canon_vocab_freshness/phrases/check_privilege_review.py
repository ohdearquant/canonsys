"""Check if privilege recertification is due for a subject.

Access privileges must be periodically reviewed to ensure
least-privilege principles and detect orphaned access.

Regulatory Context:
    SOX requires periodic access reviews for financial systems.
    SOC 2 CC6.1 requires logical access review at defined intervals.
    HIPAA requires workforce access authorization review.
    Industry standard is quarterly (90 days) for privileged access.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckPrivilegeReviewSpecs", "check_privilege_review"]


class CheckPrivilegeReviewSpecs(BaseModel):
    """Specs for privilege review check phrase."""

    # inputs
    subject_id: UUID
    last_review_date: date_cls | None = None
    review_period_days: int = 90
    # outputs
    review_due: bool | None = None
    last_review: date_cls | None = None
    days_since_review: int | None = None


@canon_phrase(
    Operable.from_structure(CheckPrivilegeReviewSpecs),
    inputs={"subject_id", "last_review_date", "review_period_days"},
    outputs={
        "review_due",
        "last_review",
        "days_since_review",
        "review_period_days",
    },
)
async def check_privilege_review(
    options,
    ctx: RequestContext,
) -> dict:
    """Check if privilege recertification is due for a subject.

    Args:
        options: Check options (subject_id, last_review_date, review_period_days)
        ctx: Request context for audit trail

    Returns:
        dict with review_due, last_review, days_since_review, review_period_days
    """
    last_review_date: date_cls | None = options.last_review_date
    review_period_days: int = options.review_period_days

    if last_review_date is None:
        return {
            "review_due": True,
            "last_review": None,
            "days_since_review": None,
            "review_period_days": review_period_days,
        }

    today = date_cls.today()
    days_since_review = (today - last_review_date).days

    return {
        "review_due": days_since_review > review_period_days,
        "last_review": last_review_date,
        "days_since_review": days_since_review,
        "review_period_days": review_period_days,
    }
