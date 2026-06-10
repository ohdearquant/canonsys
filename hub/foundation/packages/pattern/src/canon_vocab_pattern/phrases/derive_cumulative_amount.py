"""Derive cumulative amount for metric over period.

Complete vertical slice:
- Queries evidence table for amounts matching metric
- Sums amounts within lookback window
- Returns total with threshold comparison

Critical for:
- Budget reallocation abuse detection
- Expense exception stacking
- Override amount aggregation
- Transfer limit circumvention (AML)

Compliance Context:
    - SOX Section 302: Management assessment of controls
    - BSA/AML: Structuring detection (10K threshold)
    - Employment law: Progressive discipline materiality
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import crud
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveCumulativeAmountSpecs", "derive_cumulative_amount"]


class DeriveCumulativeAmountSpecs(BaseModel):
    """Specs for derive cumulative amount phrase."""

    # inputs
    entity_id: UUID
    metric: str
    period_days: int
    threshold: Decimal | None = None
    # outputs
    total_amount: Decimal | None = None
    count: int | None = None
    exceeds_threshold: bool | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(DeriveCumulativeAmountSpecs),
    inputs={"entity_id", "metric", "period_days", "threshold"},
    outputs={
        "entity_id",
        "metric",
        "period_days",
        "total_amount",
        "count",
        "exceeds_threshold",
        "threshold",
        "window_start",
        "window_end",
    },
)
async def derive_cumulative_amount(
    options: DeriveCumulativeAmountSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive cumulative amount for a metric over period.

    Queries the evidence table for records matching the entity and metric type
    within the lookback window, summing amounts from evidence.data['amount'].

    Args:
        options: Options with entity_id, metric, period_days, threshold
        ctx: Request context with tenant_id for RLS

    Returns:
        Dict with entity_id, metric, period_days, total_amount, count,
        exceeds_threshold, threshold, window_start, window_end

    Regulatory: Anti-gaming - detects "5 small = 1 material" patterns.

    Example:
        >>> result = await derive_cumulative_amount(
        ...     DeriveCumulativeAmountSpecs(
        ...         entity_id=manager_id,
        ...         metric="exception",
        ...         period_days=90,
        ...         threshold=Decimal("10000"),
        ...     ),
        ...     ctx,
        ... )
        >>> if result["exceeds_threshold"]:
        ...     # Escalate for material threshold breach
    """
    window_end = now_utc()
    window_start = window_end - timedelta(days=options.period_days)

    # Query evidence table for amounts matching metric within window.
    # Evidence records store amounts in data->'amount' as JSONB.
    # Filter by evidence_type starting with metric prefix (e.g., "reallocation.%")
    #
    # SQL aggregates amount from data JSONB field where:
    # - tenant_id matches (RLS enforced)
    # - evidence_type LIKE '{metric}.%' (matches metric category)
    # - data->>'entity_id' = entity_id (matches the entity)
    # - collected_at within window
    sql = """
        SELECT
            COALESCE(SUM((data->>'amount')::numeric), 0) as total_amount,
            COUNT(*) as count
        FROM "public"."evidence"
        WHERE evidence_type LIKE $1
          AND data->>'entity_id' = $2
          AND collected_at >= $3
          AND collected_at <= $4
    """

    evidence_type_pattern = f"{options.metric}.%"
    entity_id_str = str(options.entity_id)

    rows = await crud.fetch(
        sql,
        evidence_type_pattern,
        entity_id_str,
        window_start,
        window_end,
        conn=ctx.conn,
    )

    # Extract aggregated values
    row = rows[0] if rows else {"total_amount": Decimal(0), "count": 0}
    total_amount = Decimal(str(row.get("total_amount", 0)))
    count = int(row.get("count", 0))

    # Determine if threshold is exceeded
    exceeds_threshold = False
    if options.threshold is not None:
        exceeds_threshold = total_amount >= options.threshold

    return {
        "entity_id": options.entity_id,
        "metric": options.metric,
        "period_days": options.period_days,
        "total_amount": total_amount,
        "count": count,
        "exceeds_threshold": exceeds_threshold,
        "threshold": options.threshold,
        "window_start": window_start,
        "window_end": window_end,
    }
