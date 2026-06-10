"""Ratify charter phrase.

Ratifies a draft charter with signatories.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, select_one, update
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..types import Signatory

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RatifyCharterSpecs", "ratify_charter"]


class RatifyCharterSpecs(BaseModel):
    """Specs for ratify charter phrase."""

    # inputs
    charter_id: UUID
    signatories: list[Signatory]
    # outputs
    status: str
    ratified_at: datetime | None = None
    ratification_hash: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(RatifyCharterSpecs),
    inputs={"charter_id", "signatories"},
    outputs={"charter_id", "status", "ratified_at", "ratification_hash", "signatories"},
)
async def ratify_charter(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Ratify a draft charter with signatories.

    Validates charter is DRAFT, records signatories, computes ratification_hash,
    and transitions to RATIFIED status.

    Args:
        options: Ratification options (charter_id, signatories)
        ctx: Request context (tenant, actor)

    Returns:
        dict with updated charter data including ratification_hash

    Raises:
        ValueError: If charter not found, not DRAFT, or no signatories.
    """
    charter_id = options.get("charter_id")
    signatories = options.get("signatories", [])

    if not signatories:
        raise ValueError("At least one signatory required for ratification")

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

    if row.get("status") != "draft":
        raise ValueError(f"Only DRAFT charters can be ratified. Current: {row.get('status')}")

    # Compute ratification hash
    now = now_utc()

    signatory_data = [
        {
            "user_id": str(s.user_id),
            "role": s.role,
            "signed_at": s.signed_at.isoformat(),
        }
        for s in signatories
    ]

    ratification_data = {
        "charter_id": str(charter_id),
        "content_hash": row.get("content_hash"),
        "signatories": signatory_data,
        "ratified_at": now.isoformat(),
    }
    ratification_hash = compute_hash(ratification_data)

    # Update charter
    await update(
        "charters",
        {
            "status": "ratified",
            "ratified_at": now,
            "ratification_hash": ratification_hash,
            "signatories": signatory_data,
            "updated_at": now,
            "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
        },
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "charter_id": charter_id,
        "status": "ratified",
        "ratified_at": now,
        "ratification_hash": ratification_hash,
        "signatories": signatories,
    }
