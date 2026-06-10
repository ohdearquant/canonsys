"""Derive prior action count within lookback window.

Complete vertical slice:
- Queries evidences table for matching actions
- Counts actions matching entity_id or actor_id
- Returns count with window metadata

Critical for:
- Manager bypass pattern detection
- Credential renewal abuse
- Override frequency monitoring

Compliance Context:
    - SOX Section 302: Management assessment of internal controls
    - SOC 2 CC5.2: Control activities - anti-gaming
    - BSA/AML: Suspicious activity pattern detection
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetchval
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DerivePriorActionCountSpecs", "derive_prior_action_count"]


class DerivePriorActionCountSpecs(BaseModel):
    """Specs for derive prior action count phrase."""

    # inputs
    entity_id: UUID
    action_type: str
    lookback_days: int
    # outputs
    count: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(DerivePriorActionCountSpecs),
    inputs={"entity_id", "action_type", "lookback_days"},
    outputs={
        "count",
        "entity_id",
        "action_type",
        "lookback_days",
        "window_start",
        "window_end",
    },
)
async def derive_prior_action_count(
    options: DerivePriorActionCountSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive count of prior actions of a specific type within lookback window.

    Queries the evidences table for actions matching the entity and type
    within the specified lookback period. Matches either:
    - subject_id = entity_id (person the evidence is about)
    - data->>'actor_id' = entity_id (person who performed the action)

    This enables detection of patterns like:
    - Manager repeatedly granting exceptions (actor_id match)
    - Employee repeatedly receiving exceptions (subject_id match)

    Args:
        options: Options with entity_id, action_type, lookback_days
        ctx: Request context for tenant scope

    Returns:
        Dict with count, entity_id, action_type, lookback_days, window_start, window_end

    Regulatory context:
        - SOX Section 302: Management assessment of internal controls
        - SOC 2 CC5.2: Control activities - anti-gaming
        - BSA/AML: Suspicious activity pattern detection
    """
    window_end = now_utc()
    window_start = window_end - timedelta(days=options.lookback_days)

    # Query evidences for matching actions within window
    # Matches both subject_id (who the action is about) and
    # data->>'actor_id' (who performed the action) for flexibility
    sql = """
        SELECT COUNT(*)
        FROM evidences
        WHERE tenant_id = $1
          AND evidence_type = $2
          AND (
              subject_id = $3
              OR data->>'actor_id' = $4
          )
          AND collected_at >= $5
          AND collected_at <= $6
          AND is_deleted = false
    """

    action_count = await fetchval(
        sql,
        ctx.tenant_id,
        options.action_type,
        options.entity_id,
        str(options.entity_id),  # JSONB comparison needs string
        window_start,
        window_end,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "count": action_count or 0,
        "entity_id": options.entity_id,
        "action_type": options.action_type,
        "lookback_days": options.lookback_days,
        "window_start": window_start,
        "window_end": window_end,
    }
