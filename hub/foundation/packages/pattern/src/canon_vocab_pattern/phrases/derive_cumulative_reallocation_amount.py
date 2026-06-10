"""Track budget reallocation patterns for a department.

Complete vertical slice:
- Wraps derive_cumulative_amount for reallocation metric
- Tracks department-level budget shuffling
- Detects circumvention of material change thresholds

CS-056: Detect budget shuffling where many small reallocations
circumvent material change thresholds.

Compliance Context:
    - SOX Section 302: Management assessment of controls
    - Internal controls: Material threshold enforcement
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

__all__ = [
    "DeriveCumulativeReallocationAmountSpecs",
    "derive_cumulative_reallocation_amount",
]


class DeriveCumulativeReallocationAmountSpecs(BaseModel):
    """Specs for derive cumulative reallocation amount phrase."""

    # inputs
    department_id: UUID
    period_days: int
    threshold: Decimal | None = None
    # outputs
    total_amount: Decimal | None = None
    count: int | None = None
    exceeds_threshold: bool | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(DeriveCumulativeReallocationAmountSpecs),
    inputs={"department_id", "period_days", "threshold"},
    outputs={
        "department_id",
        "period_days",
        "total_amount",
        "count",
        "exceeds_threshold",
        "threshold",
        "window_start",
        "window_end",
    },
)
async def derive_cumulative_reallocation_amount(
    options: DeriveCumulativeReallocationAmountSpecs,
    ctx: RequestContext,
) -> dict:
    """Track budget reallocation patterns for a department.

    CS-056: Detect budget shuffling where many small reallocations
    circumvent material change thresholds.

    Args:
        options: Options with department_id, period_days, threshold
        ctx: Request context

    Returns:
        Dict tracking reallocation totals

    Example:
        >>> result = await derive_cumulative_reallocation_amount(
        ...     DeriveCumulativeReallocationAmountSpecs(
        ...         department_id=dept_id, period_days=90, threshold=Decimal("50000")
        ...     ),
        ...     ctx,
        ... )
        >>> if result["exceeds_threshold"]:
        ...     raise MaterialThresholdExceeded("budget_reallocation", result)
    """
    cumulative_options = DeriveCumulativeAmountSpecs(
        entity_id=options.department_id,
        metric="reallocation",
        period_days=options.period_days,
        threshold=options.threshold,
    )
    result = await derive_cumulative_amount(cumulative_options, ctx)

    return {
        "department_id": options.department_id,
        "period_days": options.period_days,
        "total_amount": result["total_amount"],
        "count": result["count"],
        "exceeds_threshold": result["exceeds_threshold"],
        "threshold": options.threshold,
        "window_start": result["window_start"],
        "window_end": result["window_end"],
    }
