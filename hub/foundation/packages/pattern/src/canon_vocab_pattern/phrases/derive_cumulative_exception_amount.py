"""Track expense exception patterns for a manager.

Complete vertical slice:
- Wraps derive_cumulative_amount for exception metric
- Tracks manager-level exception granting
- Detects "5 small = 1 material" exception stacking

this surface: Detect exception stacking where a manager grants many
small exceptions that cumulatively exceed material thresholds.

Compliance Context:
    - SOX Section 302: Management assessment of controls
    - Pay equity: Exception pattern monitoring
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .derive_cumulative_amount import (
    DeriveCumulativeAmountSpecs,
    derive_cumulative_amount,
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveCumulativeExceptionAmountSpecs", "derive_cumulative_exception_amount"]


class DeriveCumulativeExceptionAmountSpecs(BaseModel):
    """Specs for derive cumulative exception amount phrase."""

    # inputs
    manager_id: UUID
    period_days: int
    threshold: Decimal | None = None
    # outputs
    total_amount: Decimal | None = None
    count: int | None = None
    exceeds_threshold: bool | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(DeriveCumulativeExceptionAmountSpecs),
    inputs={"manager_id", "period_days", "threshold"},
    outputs={
        "manager_id",
        "period_days",
        "total_amount",
        "count",
        "exceeds_threshold",
        "threshold",
        "window_start",
        "window_end",
    },
)
async def derive_cumulative_exception_amount(
    options: DeriveCumulativeExceptionAmountSpecs,
    ctx: RequestContext,
) -> dict:
    """Track expense exception patterns for a manager.

    this surface: Detect exception stacking where a manager grants many
    small exceptions that cumulatively exceed material thresholds.

    Args:
        options: Options with manager_id, period_days, threshold
        ctx: Request context

    Returns:
        Dict tracking exception totals

    Example:
        >>> result = await derive_cumulative_exception_amount(
        ...     DeriveCumulativeExceptionAmountSpecs(
        ...         manager_id=manager_id, period_days=365, threshold=Decimal("10000")
        ...     ),
        ...     ctx,
        ... )
        >>> if result["exceeds_threshold"] and result["count"] >= 5:
        ...     # "5 small = 1 material" pattern detected
        ...     raise PatternDetected("exception_stacking", result)
    """
    cumulative_options = DeriveCumulativeAmountSpecs(
        entity_id=options.manager_id,
        metric="exception",
        period_days=options.period_days,
        threshold=options.threshold,
    )
    result = await derive_cumulative_amount(cumulative_options, ctx)

    return {
        "manager_id": options.manager_id,
        "period_days": options.period_days,
        "total_amount": result["total_amount"],
        "count": result["count"],
        "exceeds_threshold": result["exceeds_threshold"],
        "threshold": options.threshold,
        "window_start": result["window_start"],
        "window_end": result["window_end"],
    }
