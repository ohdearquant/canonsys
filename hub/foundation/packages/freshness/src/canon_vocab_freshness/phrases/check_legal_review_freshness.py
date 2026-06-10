"""Check if legal review is fresh enough for current decision.

Legal opinions and reviews have limited shelf life due to
changing laws, regulations, and business circumstances.

Regulatory Context:
    SOX requires disclosure controls to be current. Legal opinions
    for M&A transactions typically valid for 30-90 days. Policy
    reviews typically valid for 6 months to 1 year.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckLegalReviewSpecs", "check_legal_review_freshness"]


class CheckLegalReviewSpecs(BaseModel):
    """Specs for legal review freshness check phrase."""

    # inputs
    review_date: date_cls
    max_age_days: int = 180
    # outputs
    is_fresh: bool | None = None
    age_days: int | None = None


@canon_phrase(
    Operable.from_structure(CheckLegalReviewSpecs),
    inputs={"review_date", "max_age_days"},
    outputs={"is_fresh", "review_date", "age_days", "max_age_days"},
)
async def check_legal_review_freshness(
    options,
    ctx: RequestContext,
) -> dict:
    """Check if legal review is fresh enough for current decision.

    Args:
        options: Check options (review_date, max_age_days) - typed frozen dataclass
        ctx: Request context for audit trail

    Returns:
        dict with is_fresh, review_date, age_days, max_age_days
    """
    review_date: date_cls = options.review_date
    max_age_days: int = options.max_age_days

    today = date_cls.today()
    age_days = (today - review_date).days

    return {
        "is_fresh": age_days <= max_age_days,
        "review_date": review_date,
        "age_days": age_days,
        "max_age_days": max_age_days,
    }
