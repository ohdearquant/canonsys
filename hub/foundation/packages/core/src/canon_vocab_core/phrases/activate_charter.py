"""Activate charter phrase.

Activates a ratified charter, superseding any current active charter.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select, select_one, update
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ActivateCharterSpecs", "activate_charter"]


class ActivateCharterSpecs(BaseModel):
    """Specs for activate charter phrase."""

    # inputs
    charter_id: UUID
    effective_from: datetime | None = None
    # outputs
    status: str
    activated_at: datetime
    superseded_charter_id: UUID | None = None


@canon_phrase(
    Operable.from_structure(ActivateCharterSpecs),
    inputs={"charter_id", "effective_from"},
    outputs={
        "charter_id",
        "status",
        "effective_from",
        "activated_at",
        "superseded_charter_id",
    },
)
async def activate_charter(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Activate a ratified charter.

    Validates charter is RATIFIED, supersedes current active charter (if any),
    and activates the new charter.

    Args:
        options: Activation options (charter_id, effective_from)
        ctx: Request context (tenant, actor)

    Returns:
        dict with activation result including superseded charter info

    Raises:
        ValueError: If charter not found, not RATIFIED, or tenant mismatch.
    """
    charter_id = options.get("charter_id")
    effective_from = options.get("effective_from")

    # Fetch charter
    row = await select_one(
        "charters",
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise ValueError(f"Charter {charter_id} not found")

    if row["tenant_id"] != ctx.tenant_id:
        raise ValueError("Charter tenant doesn't match context")

    if row.get("status") != "ratified":
        raise ValueError(f"Only RATIFIED charters can be activated. Current: {row.get('status')}")

    now = now_utc()
    effective = effective_from or now
    superseded_id = None

    # Find and supersede current active charter
    active_charters = await select(
        "charters",
        where={"tenant_id": ctx.tenant_id, "status": "active"},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    for active in active_charters:
        if active["id"] != charter_id:
            superseded_id = active["id"]
            await update(
                "charters",
                {
                    "status": "superseded",
                    "superseded_at": now,
                    "superseded_by_id": charter_id,
                    "updated_at": now,
                    "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
                },
                where={"id": active["id"]},
                conn=ctx.conn,
                tenant_scope=TenantScope.REQUIRED,
            )

    # Activate new charter
    await update(
        "charters",
        {
            "status": "active",
            "effective_from": effective,
            "activated_at": now,
            "updated_at": now,
            "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
        },
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "charter_id": charter_id,
        "status": "active",
        "effective_from": effective,
        "activated_at": now,
        "superseded_charter_id": superseded_id,
    }
