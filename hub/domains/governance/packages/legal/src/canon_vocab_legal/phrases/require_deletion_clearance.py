"""Require deletion clearance (resource not under legal hold).

Implements fail-closed semantics: if hold status cannot be determined,
deletion is denied. This ensures SOX 802 compliance by preventing
destruction of potentially relevant evidence.

Regulatory Citations:
    - SOX Section 802: Prohibits destruction of evidence in federal
      investigations. Criminal penalties up to 20 years imprisonment.
    - FRCP 37(e): Failure to preserve ESI when litigation is reasonably
      anticipated may result in adverse inference or sanctions.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import LegalHoldViolationError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireDeletionClearanceSpecs", "require_deletion_clearance"]


class RequireDeletionClearanceSpecs(BaseModel):
    """Specs for require deletion clearance phrase."""

    # inputs
    resource_id: UUID
    resource_type: str | None = None
    # outputs
    checked_at: datetime | None = None


require_deletion_clearance_operable = Operable.from_structure(RequireDeletionClearanceSpecs)


@canon_phrase(
    require_deletion_clearance_operable,
    inputs={"resource_id", "resource_type"},
    outputs={"resource_id", "checked_at"},
)
async def require_deletion_clearance(
    options: RequireDeletionClearanceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require deletion clearance (resource not under legal hold).

    Raises LegalHoldViolationError if resource is under legal hold.

    Args:
        options: Options containing resource_id, optional resource_type
        ctx: Request context (tenant, actor)

    Returns:
        dict with resource_id and checked_at if deletion is permitted.

    Raises:
        LegalHoldViolationError: If resource is under legal hold.
    """
    resource_id: UUID = options.resource_id
    resource_type: str | None = options.resource_type

    now = now_utc()

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

    if row:
        # Active legal hold exists - deny deletion
        raise LegalHoldViolationError(
            resource_id=resource_id,
            action_type="deletion",
            hold_id=row["id"],
            hold_type=row.get("hold_type"),
            reason="Resource under active legal hold - deletion prohibited (SOX 802, FRCP 37(e))",
        )

    # No active hold - deletion permitted
    return {
        "resource_id": resource_id,
        "checked_at": now,
    }


# Export auto-generated types from the Phrase object
RequireDeletionClearanceOptions = require_deletion_clearance.options_type
RequireDeletionClearanceResult = require_deletion_clearance.result_type
