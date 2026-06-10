"""Lock evidence chain to prevent further additions.

Complete vertical slice:
- Validates chain exists and is intact
- Creates a chain_locked event entry
- Prevents further chain_evidence calls for this resource

Regulatory: SOX Section 802, FRCP Rule 37(e) - preservation
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch, insert, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities import ChainEntry, ChainEntryContent
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["LockEvidenceChainSpecs", "lock_evidence_chain"]


class ChainAlreadyLockedError(Exception):
    """Chain is already locked and cannot be modified.

    Regulatory:
        - SOX Section 802: Document integrity
        - ISO 27001 A.12.4.1: Event logging integrity
    """

    def __init__(self, resource_id: UUID, locked_at: datetime):
        self.resource_id = resource_id
        self.locked_at = locked_at
        super().__init__(f"Chain for {resource_id} was locked at {locked_at.isoformat()}")


class LockEvidenceChainSpecs(BaseModel):
    """Specs for lock evidence chain phrase."""

    # inputs
    resource_id: UUID
    resource_type: str = "evidence"
    reason: str | None = None
    # outputs
    locked: bool = False
    lock_entry_id: UUID | None = None
    chain_hash: str | None = None
    sequence: int | None = None
    locked_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(LockEvidenceChainSpecs),
    inputs={"resource_id", "resource_type", "reason"},
    outputs={
        "resource_id",
        "locked",
        "lock_entry_id",
        "chain_hash",
        "sequence",
        "locked_at",
    },
)
async def lock_evidence_chain(
    options: LockEvidenceChainSpecs,
    ctx: RequestContext,
) -> dict:
    """Lock an evidence chain to prevent further additions.

    Creates a special chain_locked event entry that marks the chain
    as finalized. Once locked, no further entries can be added
    (verify_chain will check for lock status).

    Use cases:
    - Case closure: Lock evidence chain when case is finalized
    - Litigation hold: Preserve chain state for legal proceedings
    - Compliance: Demonstrate chain was not modified after decision

    Args:
        options: Options containing resource_id and optional reason.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with lock details.

    Raises:
        ChainAlreadyLockedError: If chain is already locked.
        ValueError: If chain doesn't exist.

    Regulatory basis:
        - SOX Section 802: Document integrity
        - FRCP Rule 37(e): ESI preservation duty
    """
    resource_id = options.resource_id
    resource_type = options.resource_type
    reason = options.reason
    now = now_utc()

    # Check if chain exists
    chain_rows = await fetch(
        """
        SELECT id, sequence, chain_hash, event_type, created_at
        FROM chain_entrys
        WHERE resource_id = $1 AND resource_type = $2
        ORDER BY sequence DESC
        LIMIT 1
        """,
        resource_id,
        resource_type,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not chain_rows:
        raise ValueError(f"No chain found for {resource_type} {resource_id}")

    latest_entry = chain_rows[0]

    # Check if already locked
    if latest_entry["event_type"] == "chain_locked":
        raise ChainAlreadyLockedError(
            resource_id=resource_id,
            locked_at=latest_entry["created_at"],
        )

    # Also check for any lock entry (not just latest)
    lock_row = await select_one(
        "chain_entrys",
        where={
            "resource_id": resource_id,
            "resource_type": resource_type,
            "event_type": "chain_locked",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if lock_row:
        raise ChainAlreadyLockedError(
            resource_id=resource_id,
            locked_at=lock_row["created_at"],
        )

    # Create lock entry
    previous_hash = latest_entry["chain_hash"]
    sequence = latest_entry["sequence"] + 1

    # Payload for lock event
    lock_payload = {
        "reason": reason,
        "locked_by": str(ctx.actor_id),
        "locked_at": now.isoformat(),
        "final_sequence": latest_entry["sequence"],
    }

    payload_hash = compute_hash(lock_payload)

    chain_data = {
        "previous_hash": previous_hash,
        "payload_hash": payload_hash,
        "sequence": sequence,
    }
    chain_hash = compute_hash(chain_data)

    content = ChainEntryContent(
        tenant_id=ctx.tenant_id,
        subject_id=None,  # Lock is resource-level, not subject-level
        actor_id=ctx.actor_id,
        event_type="chain_locked",
        resource_type=resource_type,
        resource_id=resource_id,
        payload_hash=payload_hash,
        previous_hash=previous_hash,
        chain_hash=chain_hash,
        sequence=sequence,
        payload=lock_payload,
    )

    entry = ChainEntry(content=content)

    row_data = {
        "id": entry.id,
        "created_at": entry.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "event_type": content.event_type,
        "resource_type": content.resource_type,
        "resource_id": content.resource_id,
        "payload_hash": content.payload_hash,
        "previous_hash": content.previous_hash,
        "chain_hash": content.chain_hash,
        "sequence": content.sequence,
        "payload": content.payload,
        "updated_at": entry.updated_at,
        "version": entry.version,
    }

    await insert(
        "chain_entrys",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "resource_id": resource_id,
        "locked": True,
        "lock_entry_id": entry.id,
        "chain_hash": chain_hash,
        "sequence": sequence,
        "locked_at": now,
    }


# Export error class
__all__.append("ChainAlreadyLockedError")
