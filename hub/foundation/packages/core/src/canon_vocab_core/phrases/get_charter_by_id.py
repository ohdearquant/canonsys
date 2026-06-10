"""Get charter by ID phrase.

Retrieves a specific charter by its ID.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetCharterByIdSpecs", "get_charter_by_id"]


class GetCharterByIdSpecs(BaseModel):
    """Specs for get charter by ID phrase."""

    # inputs
    charter_id: UUID
    # outputs
    found: bool
    status: str | None = None
    effective_from: datetime | None = None
    ratified_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetCharterByIdSpecs),
    inputs={"charter_id"},
    outputs={"found", "charter_id", "status", "effective_from", "ratified_at"},
)
async def get_charter_by_id(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Get a specific charter by ID.

    Args:
        options: Query options (charter_id)
        ctx: Request context

    Returns:
        dict with charter details or not found indicator
    """
    charter_id = options.get("charter_id")

    row = await select_one(
        "charters",
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    if not row:
        return {
            "found": False,
            "charter_id": charter_id,
            "status": None,
            "effective_from": None,
            "ratified_at": None,
        }

    return {
        "found": True,
        "charter_id": row["id"],
        "status": row.get("status"),
        "effective_from": row.get("effective_from"),
        "ratified_at": row.get("ratified_at"),
    }
