"""Require dual (or multi) approval for high-risk operations.

Complete vertical slice:
- Queries approval table for request
- Counts approved approvals
- Raises RequirementNotMetError if insufficient

Regulatory:
    - SOX Section 404 (Segregation of duties)
    - PCI DSS v4.0 Req. 8.6 (Multi-factor)
    - SOC 2 CC6.1 (Logical access controls)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireDualApprovalSpecs", "require_dual_approval"]


class RequireDualApprovalSpecs(BaseModel):
    """Specs for require dual approval phrase."""

    # inputs
    request_id: UUID
    min_approvers: int = 2
    # outputs (defaults required for instantiation with inputs only)
    satisfied: bool = False
    approvals_required: int | None = None
    approvals_received: int | None = None
    approver_ids: tuple[UUID, ...] | None = None
    first_approval_at: datetime | None = None
    second_approval_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireDualApprovalSpecs),
    inputs={"request_id", "min_approvers"},
    outputs={
        "satisfied",
        "request_id",
        "approvals_required",
        "approvals_received",
        "approver_ids",
        "first_approval_at",
        "second_approval_at",
        "reason",
    },
)
async def require_dual_approval(
    options: RequireDualApprovalSpecs,
    ctx: RequestContext,
) -> dict:
    """Require dual (or multi) approval for high-risk operations.

    Queries the approval table and verifies that at least min_approvers
    have approved the request.

    Args:
        options: Options containing request_id and min_approvers
        ctx: Request context with connection

    Returns:
        Dict with approval status and metadata.

    Raises:
        RequirementNotMetError: If insufficient approvals
    """
    request_id: UUID = options.request_id
    min_approvers = options.min_approvers

    query = """
        SELECT approver_id, approved_at
        FROM request_approvals
        WHERE request_id = $1 AND status = 'approved'
        ORDER BY approved_at
    """
    rows = await ctx.conn.fetch(query, request_id)

    approver_ids = tuple(row["approver_id"] for row in rows)
    approvals_received = len(approver_ids)

    if approvals_received < min_approvers:
        raise RequirementNotMetError(
            requirement="dual_approval",
            reason=f"Requires {min_approvers} approvals, got {approvals_received}",
        )

    return {
        "satisfied": True,
        "request_id": request_id,
        "approvals_required": min_approvers,
        "approvals_received": approvals_received,
        "approver_ids": approver_ids,
        "first_approval_at": rows[0]["approved_at"] if rows else None,
        "second_approval_at": rows[1]["approved_at"] if len(rows) > 1 else None,
        "reason": None,
    }
