"""Derive proximity to filing deadline for regulatory timing gates.

This is a compliance timing primitive. Filing deadline proximity
determines urgency level for review and approval workflows.

Regulatory Context:
    SEC Rule 12b-25 allows limited extensions but imposes additional
    disclosure requirements. Missing deadlines triggers enforcement risk.
"""

from __future__ import annotations

from datetime import date as date_cls, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveFilingDeadlineSpecs", "derive_filing_deadline"]


# Known filing type deadlines (in days from period end)
_FILING_DEADLINES: dict[str, int] = {
    "10-K-LAF": 60,  # Large accelerated filer
    "10-K-AF": 75,  # Accelerated filer
    "10-K-NAF": 90,  # Non-accelerated filer
    "10-Q-LAF": 40,  # Large accelerated filer
    "10-Q-AF": 40,  # Accelerated filer
    "10-Q-NAF": 45,  # Non-accelerated filer
    "8-K": 4,  # Current report (business days)
    "TAX-FEDERAL": 90,  # Corporate tax (90 days after fiscal year)
}


class DeriveFilingDeadlineSpecs(BaseModel):
    """Specs for filing deadline derivation phrase."""

    # inputs
    effective_date: date_cls
    filing_type: str
    critical_threshold_days: int = 3
    deadline_override: date_cls | None = None
    # outputs
    days_remaining: int | None = None
    deadline: date_cls | None = None
    is_critical: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveFilingDeadlineSpecs),
    inputs={
        "effective_date",
        "filing_type",
        "critical_threshold_days",
        "deadline_override",
    },
    outputs={"days_remaining", "deadline", "filing_type", "is_critical"},
)
async def derive_filing_deadline(
    options,
    ctx: RequestContext,
) -> dict:
    """Derive proximity to filing deadline for regulatory timing gates.

    Args:
        options: Derivation options (effective_date, filing_type, critical_threshold_days, deadline_override)
        ctx: Request context for audit trail

    Returns:
        dict with days_remaining, deadline, filing_type, is_critical

    Raises:
        ValueError: If filing_type is unknown and no deadline_override provided
    """
    effective_date: date_cls = options.effective_date
    filing_type: str = options.filing_type
    critical_threshold_days: int = options.critical_threshold_days
    deadline_override: date_cls | None = options.deadline_override

    if deadline_override is not None:
        deadline = deadline_override
    elif filing_type in _FILING_DEADLINES:
        # For standard filings, deadline is calculated from period end
        deadline = effective_date + timedelta(days=_FILING_DEADLINES[filing_type])
    else:
        raise ValueError(
            f"Unknown filing_type '{filing_type}'. "
            f"Known types: {list(_FILING_DEADLINES.keys())}. "
            "Use deadline_override for custom deadlines."
        )

    days_remaining = (deadline - effective_date).days

    return {
        "days_remaining": days_remaining,
        "deadline": deadline,
        "filing_type": filing_type,
        "is_critical": days_remaining <= critical_threshold_days,
    }
