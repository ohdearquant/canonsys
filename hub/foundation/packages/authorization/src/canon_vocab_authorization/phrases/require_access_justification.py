"""Require documented justification for accessing sensitive resources.

Complete vertical slice:
- Queries for approved access justification
- Raises JustificationRequiredError if not found/approved
- Gate that blocks operation without justification

Regulatory:
    - HIPAA 164.312(a) (Access controls)
    - GDPR Art. 5(1)(c) (Data minimization)
    - SOC 2 CC6.1 (Logical access)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import JustificationRequiredError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireAccessJustificationSpecs", "require_access_justification"]


class RequireAccessJustificationSpecs(BaseModel):
    """Specs for require access justification phrase."""

    # inputs
    resource_id: UUID
    requester_id: UUID
    # outputs
    justification_id: UUID | None = None


@canon_phrase(
    Operable.from_structure(RequireAccessJustificationSpecs),
    inputs={"resource_id", "requester_id"},
    outputs={"resource_id", "requester_id", "justification_id"},
)
async def require_access_justification(
    options: RequireAccessJustificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require documented justification for accessing sensitive resources.

    Raises JustificationRequiredError if no approved justification exists.

    Args:
        options: Options containing resource_id and requester_id
        ctx: Request context with connection

    Returns:
        Dict with resource_id, requester_id, justification_id if justification exists.

    Raises:
        JustificationRequiredError: If no approved justification exists.
    """
    resource_id: UUID = options.resource_id
    requester_id: UUID = options.requester_id

    query = """
        SELECT justification_id, approved, approved_at
        FROM access_justifications
        WHERE resource_id = $1 AND requester_id = $2
        AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY approved_at DESC NULLS LAST
        LIMIT 1
    """
    row = await ctx.conn.fetchrow(query, resource_id, requester_id)

    if not row:
        raise JustificationRequiredError(
            resource_id=resource_id,
            requester_id=requester_id,
            context={"reason": "No access justification provided"},
        )

    if not row["approved"]:
        raise JustificationRequiredError(
            resource_id=resource_id,
            requester_id=requester_id,
            context={"reason": "Access justification not approved"},
        )

    return {
        "resource_id": resource_id,
        "requester_id": requester_id,
        "justification_id": row["justification_id"],
    }
