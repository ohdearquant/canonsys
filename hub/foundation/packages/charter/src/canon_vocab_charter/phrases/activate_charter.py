"""Activate a charter (DRAFT -> ACTIVE).

Complete vertical slice:
- Validates charter is in DRAFT status
- Retires any currently active charter for the tenant
- Transitions to ACTIVE with effective date
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select, select_one, update
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import CharterNotFoundError, CharterStatusError
from ..types import CharterStatus

__all__ = ["ActivateCharterSpecs", "activate_charter"]


class ActivateCharterSpecs(BaseModel):
    """Specs for activate charter phrase."""

    # inputs
    charter_id: UUID
    effective_date: datetime | None = None

    # outputs
    status: CharterStatus | None = None
    effective_from: datetime | None = None
    activated_at: datetime | None = None
    superseded_charter_id: UUID | None = None


@canon_phrase(
    Operable.from_structure(ActivateCharterSpecs),
    inputs={"charter_id", "effective_date"},
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
    """Activate a charter (DRAFT -> ACTIVE).

    Activating a charter:
    1. Validates the charter exists and is DRAFT
    2. Retires any currently active charter for the tenant
    3. Transitions the charter to ACTIVE status

    Only one charter can be ACTIVE per tenant at a time. When a new charter
    is activated, the previously active charter is automatically RETIRED.

    Args:
        options: Activation options (charter_id, effective_date)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with activation details

    Raises:
        CharterNotFoundError: If charter doesn't exist
        CharterStatusError: If charter tenant doesn't match context or invalid status
    """
    charter_id = options.get("charter_id")
    effective_date = options.get("effective_date")

    if not charter_id:
        raise ValueError("charter_id is required")

    # Fetch charter
    row = await select_one(
        "charters",
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise CharterNotFoundError(str(charter_id))

    if row["tenant_id"] != ctx.tenant_id:
        raise CharterStatusError(
            str(charter_id),
            current_status="tenant_mismatch",
            required_status="matching_tenant",
        )

    current_status = row.get("status", "unknown")

    # Validate transition using CharterStatus.can_transition_to
    try:
        current = CharterStatus(current_status)
    except ValueError:
        raise CharterStatusError(
            str(charter_id),
            current_status=current_status,
            required_status=CharterStatus.DRAFT.value,
        )

    if not current.can_transition_to(CharterStatus.ACTIVE):
        raise CharterStatusError(
            str(charter_id),
            current_status=current_status,
            required_status=CharterStatus.DRAFT.value,
        )

    now = now_utc()
    effective = effective_date or now
    retired_id = None

    # Find and retire current active charter
    active_charters = await select(
        "charters",
        where={"tenant_id": ctx.tenant_id, "status": CharterStatus.ACTIVE.value},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    for active in active_charters:
        if active["id"] != charter_id:
            retired_id = active["id"]
            await update(
                "charters",
                {
                    "status": CharterStatus.RETIRED.value,
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
            "status": CharterStatus.ACTIVE.value,
            "effective_date": effective,
            "updated_at": now,
            "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
        },
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "charter_id": charter_id,
        "status": CharterStatus.ACTIVE,
        "effective_from": effective,
        "activated_at": now,
        "superseded_charter_id": retired_id,
    }
