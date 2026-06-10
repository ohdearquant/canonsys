"""Check freshness of a Transfer Impact Assessment.

TIAs must be periodically reviewed to ensure they reflect current
legal landscape and organizational practices.

Regulatory Context:
    GDPR Art. 5(1)(d) requires data accuracy. TIAs must reflect
    current legal framework. Post-Schrems II, annual review is
    industry standard for adequacy assessments.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import FreshnessStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckTIAFreshnessSpecs", "check_tia_freshness"]


class CheckTIAFreshnessSpecs(BaseModel):
    """Specs for TIA freshness check phrase."""

    # inputs
    tia_id: UUID
    tia_date: date_cls | None = None
    max_age_days: int = 365
    stale_threshold_days: int = 270
    # outputs
    status: FreshnessStatus | None = None
    age_days: int | None = None


@canon_phrase(
    Operable.from_structure(CheckTIAFreshnessSpecs),
    inputs={"tia_id", "tia_date", "max_age_days", "stale_threshold_days"},
    outputs={"status", "age_days", "max_age_days", "tia_id"},
)
async def check_tia_freshness(
    options,
    ctx: RequestContext,
) -> dict:
    """Check freshness of a Transfer Impact Assessment.

    Args:
        options: Check options (tia_id, tia_date, max_age_days, stale_threshold_days)
        ctx: Request context for audit trail

    Returns:
        dict with status, age_days, max_age_days, tia_id
    """
    tia_id: UUID = options.tia_id
    tia_date: date_cls | None = options.tia_date
    max_age_days: int = options.max_age_days
    stale_threshold_days: int = options.stale_threshold_days

    # If tia_date not provided, would query from database
    # For now, use today as fallback (production would look up TIA)
    tia_date = tia_date or date_cls.today()

    today = date_cls.today()
    age_days = (today - tia_date).days

    if age_days > max_age_days:
        status: FreshnessStatus = "expired"
    elif age_days > stale_threshold_days:
        status = "stale"
    else:
        status = "fresh"

    return {
        "status": status,
        "age_days": age_days,
        "max_age_days": max_age_days,
        "tia_id": tia_id,
    }
