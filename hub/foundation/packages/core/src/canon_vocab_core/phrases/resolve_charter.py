"""Resolve charter phrase.

Resolves the active charter for a tenant.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ResolveCharterSpecs", "resolve_charter"]


class ResolveCharterSpecs(BaseModel):
    """Specs for resolve charter phrase."""

    # inputs
    tenant_id: UUID
    as_of: datetime | None = None
    # outputs
    found: bool
    charter_id: UUID | None = None
    status: str | None = None
    effective_from: datetime | None = None


def _is_charter_effective(row: dict, check_time: datetime) -> bool:
    """Check if charter is currently effective."""
    status = row.get("status")
    if status != "active":
        return False

    effective_from = row.get("effective_from")
    if effective_from and check_time < effective_from:
        return False

    superseded_at = row.get("superseded_at")
    return not (superseded_at and check_time >= superseded_at)


@canon_phrase(
    Operable.from_structure(ResolveCharterSpecs),
    inputs={"tenant_id", "as_of"},
    outputs={"found", "tenant_id", "charter_id", "status", "effective_from"},
)
async def resolve_charter(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Resolve the active charter for a tenant.

    Args:
        options: Resolution options (tenant_id, as_of)
        ctx: Request context

    Returns:
        dict with charter resolution result
    """
    tenant_id = options.get("tenant_id")
    as_of = options.get("as_of")
    check_time = as_of or now_utc()

    # Find active charter for tenant
    rows = await select(
        "charters",
        where={"tenant_id": tenant_id, "status": "active"},
        order_by="effective_from DESC",
        limit=10,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    for row in rows:
        if _is_charter_effective(row, check_time):
            return {
                "found": True,
                "tenant_id": tenant_id,
                "charter_id": row["id"],
                "status": row.get("status"),
                "effective_from": row.get("effective_from"),
            }

    return {
        "found": False,
        "tenant_id": tenant_id,
        "charter_id": None,
        "status": None,
        "effective_from": None,
    }
