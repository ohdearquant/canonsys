"""Require complete chain of custody for evidence.

Gate phrase that enforces chain of custody documentation
requirements before proceeding with high-risk operations.
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

__all__ = ["RequireChainOfCustodyCompleteSpecs", "require_chain_of_custody_complete"]


class RequireChainOfCustodyCompleteSpecs(BaseModel):
    """Specs for require chain of custody complete phrase."""

    # inputs
    evidence_id: UUID
    # outputs
    satisfied: bool = False
    chain_id: UUID | None = None
    entries_count: int = 0
    last_entry_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireChainOfCustodyCompleteSpecs),
    inputs={"evidence_id"},
    outputs={
        "satisfied",
        "evidence_id",
        "chain_id",
        "entries_count",
        "last_entry_at",
        "reason",
    },
)
async def require_chain_of_custody_complete(
    options: RequireChainOfCustodyCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """
    Require complete chain of custody documentation for evidence.

    Raises RequirementNotMetError if chain incomplete or missing.

    Regulatory:
        - FRE 901 (Authentication of evidence)
        - FRCP 26(b)(4) (Discovery requirements)
        - ISO 27037 (Digital evidence handling)
    """
    evidence_id = options.evidence_id

    query = """
        SELECT chain_id, entries_count, last_entry_at, is_complete
        FROM evidence_chain_of_custody
        WHERE evidence_id = $1
    """
    row = await ctx.db.fetchrow(query, evidence_id, conn=ctx.conn)

    if not row:
        raise RequirementNotMetError(
            requirement="chain_of_custody_complete",
            message=f"Chain of custody required for evidence {evidence_id}",
            context={"evidence_id": str(evidence_id)},
        )

    if not row["is_complete"]:
        raise RequirementNotMetError(
            requirement="chain_of_custody_complete",
            message=f"Chain of custody incomplete for evidence {evidence_id}",
            context={"evidence_id": str(evidence_id), "entries": row["entries_count"]},
        )

    return {
        "satisfied": True,
        "evidence_id": evidence_id,
        "chain_id": row["chain_id"],
        "entries_count": row["entries_count"],
        "last_entry_at": row["last_entry_at"],
        "reason": None,
    }
