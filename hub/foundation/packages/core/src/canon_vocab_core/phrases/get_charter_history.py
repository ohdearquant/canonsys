"""Get charter history phrase.

Retrieves charter history for a tenant.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CharterSummary", "GetCharterHistorySpecs", "get_charter_history"]


class CharterSummary(BaseModel):
    """Summary of a charter for history listing."""

    charter_id: UUID
    status: str
    effective_from: datetime | None = None
    ratified_at: datetime | None = None
    created_at: datetime


class GetCharterHistorySpecs(BaseModel):
    """Specs for get charter history phrase."""

    # inputs
    tenant_id: UUID
    limit: int = 10
    # outputs
    count: int
    charters: list[CharterSummary]

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(GetCharterHistorySpecs),
    inputs={"tenant_id", "limit"},
    outputs={"tenant_id", "count", "charters"},
)
async def get_charter_history(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Get charter history for a tenant.

    Args:
        options: Query options (tenant_id, limit)
        ctx: Request context

    Returns:
        dict with list of charter summaries ordered by effective_from DESC
    """
    tenant_id = options.get("tenant_id")
    limit = options.get("limit", 10)

    rows = await select(
        "charters",
        where={"tenant_id": tenant_id},
        order_by="effective_from DESC",
        limit=limit,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    charters = [
        CharterSummary(
            charter_id=row["id"],
            status=row.get("status", "draft"),
            effective_from=row.get("effective_from"),
            ratified_at=row.get("ratified_at"),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return {
        "tenant_id": tenant_id,
        "count": len(charters),
        "charters": charters,
    }
