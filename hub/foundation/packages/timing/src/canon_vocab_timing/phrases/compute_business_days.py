"""Compute business days between dates or from a start date.

Compliance Context:
    - FCRA Section 1681b(b)(3) (5 business days default)
    - FCRA Section 1681i (30 days for dispute investigation)
    - State variations (California 7 days, etc.)
    - Employment law notice periods
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ComputeBusinessDaysSpecs", "compute_business_days"]


def _is_business_day(d: date) -> bool:
    """Check if a date is a business day (Mon-Fri).

    Note: This is a simplified implementation that does not account
    for holidays. Production use should integrate with a holiday calendar.
    """
    return d.weekday() < 5  # Monday = 0, Friday = 4


def _add_business_days(start: date, days: int) -> date:
    """Add business days to a date.

    Args:
        start: Starting date
        days: Number of business days to add (can be negative)

    Returns:
        Date after adding the specified business days
    """
    if days == 0:
        return start

    direction = 1 if days > 0 else -1
    remaining = abs(days)
    current = start

    while remaining > 0:
        current += timedelta(days=direction)
        if _is_business_day(current):
            remaining -= 1

    return current


def _count_business_days(start: date, end: date) -> int:
    """Count business days between two dates (exclusive of end).

    Args:
        start: Start date (inclusive)
        end: End date (exclusive)

    Returns:
        Number of business days
    """
    if start >= end:
        return 0

    count = 0
    current = start
    while current < end:
        if _is_business_day(current):
            count += 1
        current += timedelta(days=1)

    return count


class ComputeBusinessDaysSpecs(BaseModel):
    """Specs for compute business days phrase."""

    # inputs (one of these patterns)
    start_date: datetime | None = None
    end_date: datetime | None = None
    business_days_to_add: int | None = Field(
        default=None, description="Business days to add to start_date"
    )
    jurisdiction: str = Field(default="federal", description="Jurisdiction for holiday calendar")
    # outputs
    computed_date: datetime | None = None
    business_days_count: int | None = None
    calendar_days_count: int | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(ComputeBusinessDaysSpecs),
    inputs={"start_date", "end_date", "business_days_to_add", "jurisdiction"},
    outputs={
        "start_date",
        "end_date",
        "computed_date",
        "business_days_count",
        "calendar_days_count",
        "reason",
    },
)
async def compute_business_days(
    options,
    ctx: RequestContext,
) -> dict:
    """Compute business days for compliance timing.

    Two modes:
    1. Count business days: Provide start_date and end_date
    2. Add business days: Provide start_date and business_days_to_add

    Args:
        options: Computation options - typed frozen dataclass
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with computed_date, business_days_count, calendar_days_count, reason

    Example (count days):
        >>> result = await compute_business_days(
        ...     {"start_date": notice_sent, "end_date": now}, ctx
        ... )
        >>> print(f"Elapsed: {result['business_days_count']} business days")

    Example (add days):
        >>> result = await compute_business_days(
        ...     {"start_date": notice_sent, "business_days_to_add": 5}, ctx
        ... )
        >>> waiting_period_ends = result["computed_date"]
    """
    start_date = options.start_date
    end_date = options.end_date
    business_days_to_add = options.business_days_to_add

    # Mode 1: Count business days between two dates
    if start_date is not None and end_date is not None:
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        end_d = end_date.date() if isinstance(end_date, datetime) else end_date

        business_count = _count_business_days(start_d, end_d)
        calendar_count = (end_d - start_d).days

        return {
            "start_date": start_date,
            "end_date": end_date,
            "computed_date": None,
            "business_days_count": business_count,
            "calendar_days_count": calendar_count,
            "reason": None,
        }

    # Mode 2: Add business days to start date
    if start_date is not None and business_days_to_add is not None:
        start_d = start_date.date() if isinstance(start_date, datetime) else start_date
        computed_d = _add_business_days(start_d, business_days_to_add)

        # Convert back to datetime with same time component
        if isinstance(start_date, datetime):
            computed_dt = datetime.combine(computed_d, start_date.time(), tzinfo=start_date.tzinfo)
        else:
            computed_dt = datetime.combine(computed_d, datetime.min.time())

        calendar_count = abs((computed_d - start_d).days)

        return {
            "start_date": start_date,
            "end_date": None,
            "computed_date": computed_dt,
            "business_days_count": abs(business_days_to_add),
            "calendar_days_count": calendar_count,
            "reason": None,
        }

    # Invalid input combination
    return {
        "start_date": start_date,
        "end_date": end_date,
        "computed_date": None,
        "business_days_count": None,
        "calendar_days_count": None,
        "reason": "Invalid input: provide (start_date + end_date) or (start_date + business_days_to_add)",
    }
