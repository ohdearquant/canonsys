"""Verify credit report is fresh enough for permissible use.

FCRA requires consumer reports to be reasonably current at the
time of use. Industry standard is 30 days for most decisions.

Regulatory Context:
    FCRA Section 604(b)(3) requires reports used for employment
    to be "no more than 30 days old" per FTC guidance. Some
    states (e.g., California) have additional requirements.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyCreditFreshnessSpecs", "verify_credit_freshness"]


class VerifyCreditFreshnessSpecs(BaseModel):
    """Specs for credit freshness verification phrase."""

    # inputs
    report_date: date_cls
    max_age_days: int = 30
    # outputs
    is_fresh: bool | None = None
    age_days: int | None = None


@canon_phrase(
    Operable.from_structure(VerifyCreditFreshnessSpecs),
    inputs={"report_date", "max_age_days"},
    outputs={"is_fresh", "report_date", "age_days", "max_age_days"},
)
async def verify_credit_freshness(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify credit report is fresh enough for permissible use.

    Args:
        options: Verification options (report_date, max_age_days) - typed frozen dataclass
        ctx: Request context for audit trail

    Returns:
        dict with is_fresh, report_date, age_days, max_age_days
    """
    report_date: date_cls = options.report_date
    max_age_days: int = options.max_age_days

    today = date_cls.today()
    age_days = (today - report_date).days

    return {
        "is_fresh": age_days <= max_age_days,
        "report_date": report_date,
        "age_days": age_days,
        "max_age_days": max_age_days,
    }
