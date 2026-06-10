"""Require that data or artifacts have not expired.

Complete vertical slice:
- Validates data age against maximum allowed freshness window
- Raises DataStaleError if data exceeds allowed age
- General-purpose freshness gate for any dated artifact

Regulatory: FCRA Section 604(b)(3) - Report freshness requirements
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import DataStaleError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "DataStaleError",
    "RequireNotExpiredSpecs",
    "require_not_expired",
]


class RequireNotExpiredSpecs(BaseModel):
    """Specs for require not expired phrase."""

    # inputs
    data_type: str
    as_of_date: date_cls
    max_age_days: int = 30
    # outputs
    satisfied: bool = False
    age_days: int | None = None


@canon_phrase(
    Operable.from_structure(RequireNotExpiredSpecs),
    inputs={"data_type", "as_of_date", "max_age_days"},
    outputs={"satisfied", "data_type", "as_of_date", "age_days", "max_age_days"},
)
async def require_not_expired(
    options: RequireNotExpiredSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that data has not expired beyond its freshness window.

    Gate pattern that enforces data freshness. Computes age from
    as_of_date to today and raises if it exceeds max_age_days.

    Args:
        options: Options containing data_type, as_of_date, max_age_days.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if data is within freshness window.

    Raises:
        DataStaleError: If data age exceeds max_age_days.

    Regulatory citations:
        - FCRA Section 604(b)(3): Consumer reports must be reasonably current
        - SOX Section 404: Internal controls require current data
        - GDPR Art. 5(1)(d): Data accuracy and currency
        - SOC 2 CC4.1: Information quality and currency
    """
    today = date_cls.today()
    age_days = (today - options.as_of_date).days

    if age_days > options.max_age_days:
        raise DataStaleError(
            data_type=options.data_type,
            age_days=age_days,
            max_age_days=options.max_age_days,
        )

    return {
        "satisfied": True,
        "data_type": options.data_type,
        "as_of_date": options.as_of_date,
        "age_days": age_days,
        "max_age_days": options.max_age_days,
    }
