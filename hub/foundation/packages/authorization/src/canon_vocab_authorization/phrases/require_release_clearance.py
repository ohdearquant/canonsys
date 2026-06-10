"""Require proper clearance for information release.

Complete vertical slice:
- Gets resource classification level
- Gets requester clearance level
- Compares clearance hierarchy
- Raises ClearanceInsufficientError if insufficient

Regulatory:
    - ITAR 22 CFR 120-130 (Export controls)
    - EAR 15 CFR 730-774 (Export administration)
    - NISPOM 32 CFR 117 (Classified information)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ClearanceInsufficientError
from ..types import ClearanceLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireReleaseClearanceSpecs", "require_release_clearance"]


class RequireReleaseClearanceSpecs(BaseModel):
    """Specs for require release clearance phrase."""

    # inputs
    resource_id: UUID
    requester_id: UUID
    # outputs
    required_clearance: ClearanceLevel | None = None
    requester_clearance: ClearanceLevel | None = None


@canon_phrase(
    Operable.from_structure(RequireReleaseClearanceSpecs),
    inputs={"resource_id", "requester_id"},
    outputs={
        "resource_id",
        "requester_id",
        "required_clearance",
        "requester_clearance",
    },
)
async def require_release_clearance(
    options: RequireReleaseClearanceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require proper clearance for information release.

    Raises ClearanceInsufficientError if requester lacks required clearance.

    Args:
        options: Options containing resource_id and requester_id
        ctx: Request context with connection

    Returns:
        Dict with resource_id, requester_id, required_clearance, requester_clearance.

    Raises:
        ClearanceInsufficientError: If requester lacks required clearance.
    """
    resource_id: UUID = options.resource_id
    requester_id: UUID = options.requester_id

    # Get resource classification
    res_query = """
        SELECT classification_level
        FROM resource_classifications
        WHERE resource_id = $1
    """
    res_row = await ctx.conn.fetchrow(res_query, resource_id)

    if not res_row:
        raise ClearanceInsufficientError(
            resource_id=resource_id,
            required_level="CONFIDENTIAL",
            actual_level=None,
            context={"reason": "Resource classification unknown"},
        )

    required = ClearanceLevel(res_row["classification_level"])

    # Get requester clearance
    user_query = """
        SELECT clearance_level
        FROM user_clearances
        WHERE user_id = $1 AND status = 'active'
    """
    user_row = await ctx.conn.fetchrow(user_query, requester_id)

    if not user_row:
        raise ClearanceInsufficientError(
            resource_id=resource_id,
            required_level=required.value,
            actual_level=None,
            context={"reason": "No active clearance found for requester"},
        )

    requester_level = ClearanceLevel(user_row["clearance_level"])
    clearance_order = list(ClearanceLevel)

    if clearance_order.index(requester_level) < clearance_order.index(required):
        raise ClearanceInsufficientError(
            resource_id=resource_id,
            required_level=required.value,
            actual_level=requester_level.value,
        )

    return {
        "resource_id": resource_id,
        "requester_id": requester_id,
        "required_clearance": required,
        "requester_clearance": requester_level,
    }
