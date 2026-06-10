"""Require modification clearance (resource not under legal hold).

Raises LegalHoldViolationError if resource is under active legal hold.

Regulatory:
    - FRCP 37(e) (Spoliation sanctions)
    - SOX Section 802 (Document destruction)
    - 18 U.S.C. Section 1519 (Obstruction)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import LegalHoldViolationError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireModificationClearanceSpecs", "require_modification_clearance"]


class RequireModificationClearanceSpecs(BaseModel):
    """Specs for require modification clearance phrase."""

    # inputs
    resource_id: UUID
    # outputs (no additional outputs beyond resource_id)


require_modification_clearance_operable = Operable.from_structure(RequireModificationClearanceSpecs)


@canon_phrase(
    require_modification_clearance_operable,
    inputs={"resource_id"},
    outputs={"resource_id"},
)
async def require_modification_clearance(
    options: RequireModificationClearanceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require modification clearance (resource not under legal hold).

    Raises LegalHoldViolationError if resource is under active legal hold.

    Args:
        options: Options containing resource_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with resource_id if modification is permitted.

    Raises:
        LegalHoldViolationError: If resource is under legal hold.
    """
    resource_id: UUID = options.resource_id

    # Need ORDER BY for most recent hold
    rows = await fetch(
        """
        SELECT hold_id, hold_type, hold_start
        FROM legal_holds
        WHERE resource_id = $1 AND status = 'active'
        ORDER BY hold_start DESC
        LIMIT 1
        """,
        resource_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if rows:
        row = rows[0]
        raise LegalHoldViolationError(
            resource_id=resource_id,
            action_type="modification",
            hold_id=row["hold_id"],
            hold_type=row["hold_type"],
            reason=f"Resource under {row['hold_type']} hold",
        )

    return {"resource_id": resource_id}


# Export auto-generated types from the Phrase object
RequireModificationClearanceOptions = require_modification_clearance.options_type
RequireModificationClearanceResult = require_modification_clearance.result_type
