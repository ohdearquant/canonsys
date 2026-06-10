"""Require an active legal hold before evidence preservation operations.

Ensures that a formal legal hold exists and is active for a resource
before allowing evidence preservation operations. This is the inverse
of deletion/modification clearance gates -- here we require the hold
to BE active, not absent.

Regulatory: SOX Section 802, FRCP 37(e), 18 U.S.C. 1519
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireLegalHoldActiveSpecs", "require_legal_hold_active"]


class RequireLegalHoldActiveSpecs(BaseModel):
    """Specs for require legal hold active phrase."""

    # inputs
    resource_id: UUID
    resource_type: str | None = None
    # outputs
    hold_id: UUID | None = None
    hold_type: str | None = None
    held_since: datetime | None = None


require_legal_hold_active_operable = Operable.from_structure(RequireLegalHoldActiveSpecs)


@canon_phrase(
    require_legal_hold_active_operable,
    inputs={"resource_id", "resource_type"},
    outputs={"resource_id", "hold_id", "hold_type", "held_since"},
)
async def require_legal_hold_active(
    options: RequireLegalHoldActiveSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that an active legal hold exists for a resource.

    Gate for evidence preservation workflows. Before preservation
    operations proceed, a formal legal hold must be in effect. This
    ensures preservation actions are properly authorized and traceable.

    This is the inverse of require_deletion_clearance: that gate blocks
    when a hold IS active; this gate blocks when a hold IS NOT active.

    Regulatory:
        - SOX Section 802: Requires preservation of documents relevant
          to federal investigations. Criminal penalties up to 20 years.
        - FRCP 37(e): Duty to preserve ESI when litigation is reasonably
          anticipated. Hold must be in effect before preservation begins.
        - 18 U.S.C. Section 1519: Obstruction of justice through
          document destruction. Hold formalizes the preservation duty.
        - FRCP 26(a): Initial disclosure obligations require hold-based
          identification of relevant materials.

    Args:
        options: Options containing resource_id, optional resource_type.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with hold details if an active hold exists.

    Raises:
        RequirementNotMetError: If no active legal hold exists.
    """
    resource_id: UUID = options.resource_id
    resource_type: str | None = options.resource_type

    # Build query conditions
    conditions: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "resource_id": resource_id,
        "status": "active",
    }
    if resource_type:
        conditions["resource_type"] = resource_type

    # Query for active legal hold on this resource
    row = await select_one(
        "legal_holds",
        where=conditions,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="legal_hold_active",
            reason=(
                f"No active legal hold found for resource {resource_id}. "
                "A formal legal hold must be in effect before evidence "
                "preservation operations can proceed (SOX 802, FRCP 37(e))."
            ),
        )

    return {
        "resource_id": resource_id,
        "hold_id": row["id"],
        "hold_type": row.get("hold_type"),
        "held_since": row.get("created_at"),
    }


# Export auto-generated types from the Phrase object
RequireLegalHoldActiveOptions = require_legal_hold_active.options_type
RequireLegalHoldActiveResult = require_legal_hold_active.result_type
