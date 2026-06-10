"""Verify that all required approvals in a chain are complete.

Complete vertical slice:
- Queries approval chain status
- Returns verification result (does not raise)
- Caller decides how to handle failures

Regulatory:
    - SOX Section 404 (Segregation of duties)
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

from ..types import ApprovalChainStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyApprovalChainCompleteSpecs", "verify_approval_chain_complete"]


class VerifyApprovalChainCompleteSpecs(BaseModel):
    """Specs for verify approval chain complete phrase."""

    # inputs
    request_id: UUID
    # outputs (defaults required for instantiation with inputs only)
    verified: bool = False
    status: ApprovalChainStatus | None = None
    approvals_required: int = 0
    approvals_received: int = 0
    completed_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyApprovalChainCompleteSpecs),
    inputs={"request_id"},
    outputs={
        "verified",
        "request_id",
        "status",
        "approvals_required",
        "approvals_received",
        "completed_at",
        "reason",
    },
)
async def verify_approval_chain_complete(
    options: VerifyApprovalChainCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that all required approvals in a chain are complete.

    Checks the approval chain for a request and returns whether all
    required approvals have been obtained.

    Args:
        options: Options containing request_id
        ctx: Request context with connection

    Returns:
        Dict with verification status and chain metadata.
    """
    request_id: UUID = options.request_id

    query = """
        SELECT status, approvals_required, approvals_received, completed_at
        FROM approval_chains
        WHERE request_id = $1
    """
    row = await ctx.conn.fetchrow(query, request_id)

    if not row:
        return {
            "verified": False,
            "request_id": request_id,
            "status": ApprovalChainStatus.PENDING,
            "approvals_required": 0,
            "approvals_received": 0,
            "completed_at": None,
            "reason": "No approval chain found",
        }

    status = ApprovalChainStatus(row["status"])

    return {
        "verified": status == ApprovalChainStatus.COMPLETE,
        "request_id": request_id,
        "status": status,
        "approvals_required": row["approvals_required"],
        "approvals_received": row["approvals_received"],
        "completed_at": row["completed_at"],
        "reason": (
            None if status == ApprovalChainStatus.COMPLETE else f"Chain status: {status.value}"
        ),
    }
