"""Verify chain of custody completeness.

Non-gating verification that checks chain of custody status
without raising errors - returns status for decision making.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "CustodyChainStatus",
    "VerifyChainOfCustodyCompleteSpecs",
    "verify_chain_of_custody_complete",
]


class CustodyChainStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    BROKEN = "broken"
    NOT_STARTED = "not_started"


class VerifyChainOfCustodyCompleteSpecs(BaseModel):
    """Specs for verify chain of custody complete phrase."""

    # inputs
    evidence_id: UUID
    # outputs
    verified: bool = False
    status: CustodyChainStatus = CustodyChainStatus.NOT_STARTED
    chain_id: UUID | None = None
    entries_count: int = 0
    last_transfer_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyChainOfCustodyCompleteSpecs),
    inputs={"evidence_id"},
    outputs={
        "verified",
        "evidence_id",
        "status",
        "chain_id",
        "entries_count",
        "last_transfer_at",
        "reason",
    },
)
async def verify_chain_of_custody_complete(
    options: VerifyChainOfCustodyCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """
    Verify that chain of custody is complete and unbroken.

    Regulatory:
        - FRE 901 (Authentication)
        - ISO 27037 (Digital evidence handling)
        - FRCP 34 (Production of documents)
    """
    evidence_id = options.evidence_id

    query = """
        SELECT chain_id, status, entries_count, last_transfer_at
        FROM evidence_chain_of_custody
        WHERE evidence_id = $1
    """
    row = await ctx.db.fetchrow(query, evidence_id, conn=ctx.conn)

    if not row:
        return {
            "verified": False,
            "evidence_id": evidence_id,
            "status": CustodyChainStatus.NOT_STARTED,
            "chain_id": None,
            "entries_count": 0,
            "last_transfer_at": None,
            "reason": "No chain of custody found",
        }

    status = CustodyChainStatus(row["status"])

    return {
        "verified": status == CustodyChainStatus.COMPLETE,
        "evidence_id": evidence_id,
        "status": status,
        "chain_id": row["chain_id"],
        "entries_count": row["entries_count"],
        "last_transfer_at": row["last_transfer_at"],
        "reason": (
            None if status == CustodyChainStatus.COMPLETE else f"Chain status: {status.value}"
        ),
    }
