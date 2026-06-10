"""Check if equity analysis is stale for compensation decisions.

Equity data (market comparisons, internal equity analysis) must be
reasonably current when used for compensation decisions.

Regulatory Context:
    SEC requires equity compensation to be based on current fair values.
    Pay equity laws (CA SB 973, EU Pay Transparency) require decisions
    based on current, accurate market and internal equity data.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckEquityStalenessSpecs", "check_equity_staleness"]


class CheckEquityStalenessSpecs(BaseModel):
    """Specs for equity staleness check phrase."""

    # inputs
    analysis_date: date_cls
    max_age_days: int = 90
    # outputs
    is_stale: bool | None = None
    age_days: int | None = None


@canon_phrase(
    Operable.from_structure(CheckEquityStalenessSpecs),
    inputs={"analysis_date", "max_age_days"},
    outputs={"is_stale", "age_days", "max_age_days", "analysis_date"},
)
async def check_equity_staleness(
    options,
    ctx: RequestContext,
) -> dict:
    """Check if equity analysis is stale for compensation decisions.

    Args:
        options: Check options (analysis_date, max_age_days) - typed frozen dataclass
        ctx: Request context for audit trail

    Returns:
        dict with is_stale, age_days, max_age_days, analysis_date
    """
    analysis_date: date_cls = options.analysis_date
    max_age_days: int = options.max_age_days

    today = date_cls.today()
    age_days = (today - analysis_date).days

    return {
        "is_stale": age_days > max_age_days,
        "age_days": age_days,
        "max_age_days": max_age_days,
        "analysis_date": analysis_date,
    }
