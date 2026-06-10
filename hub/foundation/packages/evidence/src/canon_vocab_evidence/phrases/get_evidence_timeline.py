"""Get evidence timeline for a resource.

Complete vertical slice:
- Queries all chain entries for a resource
- Returns chronological timeline of events
- Includes hash verification status

Regulatory: FRE 901, ISO 27037, FRCP Rule 34
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetEvidenceTimelineSpecs", "TimelineEvent", "get_evidence_timeline"]


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """Single event in evidence timeline."""

    entry_id: UUID
    sequence: int
    event_type: str
    created_at: datetime
    actor_id: UUID | None
    payload_hash: str | None
    chain_hash: str | None
    previous_hash: str | None
    hash_valid: bool  # True if chain_hash matches computed


class GetEvidenceTimelineSpecs(BaseModel):
    """Specs for get evidence timeline phrase."""

    # inputs
    resource_id: UUID
    resource_type: str = "evidence"
    verify_hashes: bool = True  # Verify chain integrity during retrieval
    # outputs
    events: tuple[Any, ...] = ()  # tuple[TimelineEvent, ...]
    total: int = 0
    is_locked: bool = False
    locked_at: datetime | None = None
    chain_valid: bool = False
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetEvidenceTimelineSpecs),
    inputs={"resource_id", "resource_type", "verify_hashes"},
    outputs={
        "resource_id",
        "events",
        "total",
        "is_locked",
        "locked_at",
        "chain_valid",
        "first_event_at",
        "last_event_at",
    },
)
async def get_evidence_timeline(
    options: GetEvidenceTimelineSpecs,
    ctx: RequestContext,
) -> dict:
    """Get chronological timeline of evidence chain events.

    Returns all chain entries for a resource in sequence order,
    optionally verifying hash integrity during retrieval.

    Args:
        options: Options containing resource_id and verification flag.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with events list and timeline metadata.

    Regulatory basis:
        - FRE 901: Authentication of evidence
        - ISO 27037: Digital evidence handling
        - FRCP Rule 34: Production of documents
    """
    resource_id = options.resource_id
    resource_type = options.resource_type
    verify_hashes = options.verify_hashes

    # Query all chain entries for resource
    rows = await fetch(
        """
        SELECT
            id,
            sequence,
            event_type,
            created_at,
            actor_id,
            payload_hash,
            chain_hash,
            previous_hash
        FROM chain_entrys
        WHERE resource_id = $1 AND resource_type = $2
        ORDER BY sequence ASC
        """,
        resource_id,
        resource_type,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        return {
            "resource_id": resource_id,
            "events": (),
            "total": 0,
            "is_locked": False,
            "locked_at": None,
            "chain_valid": True,  # Empty chain is valid
            "first_event_at": None,
            "last_event_at": None,
        }

    events: list[TimelineEvent] = []
    chain_valid = True
    is_locked = False
    locked_at: datetime | None = None
    previous_hash: str | None = None

    for row in rows:
        hash_valid = True

        if verify_hashes:
            # Verify chain hash computation
            expected_chain_hash = compute_hash(
                {
                    "previous_hash": row["previous_hash"],
                    "payload_hash": row["payload_hash"],
                    "sequence": row["sequence"],
                }
            )

            if row["chain_hash"] != expected_chain_hash:
                hash_valid = False
                chain_valid = False

            # Verify linkage to previous
            if row["sequence"] > 0 and row["previous_hash"] != previous_hash:
                hash_valid = False
                chain_valid = False

        # Check for lock event
        if row["event_type"] == "chain_locked":
            is_locked = True
            locked_at = row["created_at"]

        event = TimelineEvent(
            entry_id=row["id"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            created_at=row["created_at"],
            actor_id=row["actor_id"],
            payload_hash=row["payload_hash"],
            chain_hash=row["chain_hash"],
            previous_hash=row["previous_hash"],
            hash_valid=hash_valid,
        )
        events.append(event)

        previous_hash = row["chain_hash"]

    first_event_at = events[0].created_at if events else None
    last_event_at = events[-1].created_at if events else None

    return {
        "resource_id": resource_id,
        "events": tuple(events),
        "total": len(events),
        "is_locked": is_locked,
        "locked_at": locked_at,
        "chain_valid": chain_valid,
        "first_event_at": first_event_at,
        "last_event_at": last_event_at,
    }
