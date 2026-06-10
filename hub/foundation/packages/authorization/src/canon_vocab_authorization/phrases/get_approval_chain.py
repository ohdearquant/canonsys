"""Get the approval chain for a request.

Complete vertical slice:
- Queries the required approvers for a request
- Returns ordered list of approvers with status
- Query pattern (no raising)

Regulatory:
    - SOX Section 404 (Approval documentation)
    - SOC 2 CC6.1 (Logical access controls)
    - ISO 27001 A.9.2 (User access management)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ApproverStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ApproverStatus", "GetApprovalChainSpecs", "get_approval_chain"]


class ApproverInfo(BaseModel):
    """Information about an approver in the chain."""

    approver_id: UUID
    approver_name: str | None
    required_role: str
    status: ApproverStatus
    sequence: int
    approved_at: datetime | None = None
    delegated_to: UUID | None = None


class GetApprovalChainSpecs(BaseModel):
    """Specs for get approval chain phrase."""

    # inputs
    request_id: UUID
    include_delegations: bool = True
    # outputs (defaults required for instantiation with inputs only)
    approvers: tuple[dict, ...] | None = None
    total_required: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_pending: int = 0
    chain_complete: bool = False
    queried_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetApprovalChainSpecs),
    inputs={"request_id", "include_delegations"},
    outputs={
        "request_id",
        "approvers",
        "total_required",
        "total_approved",
        "total_rejected",
        "total_pending",
        "chain_complete",
        "queried_at",
    },
)
async def get_approval_chain(
    options: GetApprovalChainSpecs,
    ctx: RequestContext,
) -> dict:
    """Get the approval chain for a request.

    Returns the ordered list of required approvers and their current
    status. This is a query operation that does not enforce any
    requirements.

    Args:
        options: Options containing request_id
        ctx: Request context with connection

    Returns:
        Dict with approvers list and aggregate statistics.
    """
    now = now_utc()
    request_id: UUID = options.request_id
    include_delegations = options.include_delegations

    # Query approval chain with status
    query = """
        SELECT
            ac.approver_id,
            ac.required_role,
            ac.sequence,
            ac.status,
            ac.approved_at,
            ac.delegated_to,
            p.name as approver_name
        FROM approval_chain_members ac
        LEFT JOIN principals p ON ac.approver_id = p.id
        WHERE ac.request_id = $1
        ORDER BY ac.sequence
    """
    rows = await ctx.conn.fetch(query, request_id)

    approvers: list[dict] = []
    total_approved = 0
    total_rejected = 0
    total_pending = 0

    for row in rows:
        status = ApproverStatus(row["status"])

        if status == ApproverStatus.APPROVED:
            total_approved += 1
        elif status == ApproverStatus.REJECTED:
            total_rejected += 1
        elif status == ApproverStatus.PENDING:
            total_pending += 1

        approver_info = {
            "approver_id": row["approver_id"],
            "approver_name": row["approver_name"],
            "required_role": row["required_role"],
            "status": status.value,
            "sequence": row["sequence"],
            "approved_at": row["approved_at"],
        }

        if include_delegations and row["delegated_to"]:
            approver_info["delegated_to"] = row["delegated_to"]

        approvers.append(approver_info)

    total_required = len(approvers)
    chain_complete = total_approved >= total_required and total_rejected == 0

    return {
        "request_id": request_id,
        "approvers": tuple(approvers),
        "total_required": total_required,
        "total_approved": total_approved,
        "total_rejected": total_rejected,
        "total_pending": total_pending,
        "chain_complete": chain_complete,
        "queried_at": now,
    }
