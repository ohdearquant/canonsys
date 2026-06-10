"""Derive proximity to quarter end for compliance timing gates.

This is an anti-gaming primitive. Quarter-end proximity MUST be
derived from the actual date, never accepted as user input.

Regulatory Context:
    SOX Section 302 requires quarterly certifications. Transactions
    near quarter-end require heightened scrutiny to prevent gaming.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveQuarterEndSpecs", "derive_quarter_end"]


def _get_quarter_end(effective_date: date_cls) -> tuple[date_cls, str]:
    """Calculate quarter end date and fiscal quarter identifier."""
    year = effective_date.year
    month = effective_date.month

    if month <= 3:
        quarter_end = date_cls(year, 3, 31)
        fiscal_quarter = "Q1"
    elif month <= 6:
        quarter_end = date_cls(year, 6, 30)
        fiscal_quarter = "Q2"
    elif month <= 9:
        quarter_end = date_cls(year, 9, 30)
        fiscal_quarter = "Q3"
    else:
        quarter_end = date_cls(year, 12, 31)
        fiscal_quarter = "Q4"

    return quarter_end, fiscal_quarter


class DeriveQuarterEndSpecs(BaseModel):
    """Specs for quarter end derivation phrase."""

    # inputs
    effective_date: date_cls
    critical_threshold_days: int = 5
    # outputs
    days_remaining: int | None = None
    quarter_end: date_cls | None = None
    fiscal_quarter: str | None = None
    is_critical: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveQuarterEndSpecs),
    inputs={"effective_date", "critical_threshold_days"},
    outputs={"days_remaining", "quarter_end", "fiscal_quarter", "is_critical"},
)
async def derive_quarter_end(
    options,
    ctx: RequestContext,
) -> dict:
    """Derive proximity to quarter end for compliance timing gates.

    Args:
        options: Derivation options (effective_date, critical_threshold_days)
        ctx: Request context for audit trail

    Returns:
        dict with days_remaining, quarter_end, fiscal_quarter, is_critical
    """
    effective_date: date_cls = options.effective_date
    critical_threshold_days: int = options.critical_threshold_days

    quarter_end, fiscal_quarter = _get_quarter_end(effective_date)
    days_remaining = (quarter_end - effective_date).days

    # If past quarter end, days_remaining will be negative
    if days_remaining < 0:
        days_remaining = 0

    return {
        "days_remaining": days_remaining,
        "quarter_end": quarter_end,
        "fiscal_quarter": fiscal_quarter,
        "is_critical": days_remaining <= critical_threshold_days,
    }
