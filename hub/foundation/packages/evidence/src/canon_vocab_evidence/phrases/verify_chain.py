"""Verify chain integrity.

Complete vertical slice:
- Fetches chain entries for a resource
- Verifies hash linkage is unbroken
- Returns verification result with any tampering details
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyChainSpecs", "verify_chain"]


class VerifyChainSpecs(BaseModel):
    """Specs for verify chain phrase."""

    # inputs
    resource_id: UUID
    resource_type: str = "evidence"
    # outputs
    valid: bool = False
    chain_length: int = 0
    broken_at: int | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    message: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyChainSpecs),
    inputs={"resource_id", "resource_type"},
    outputs={
        "valid",
        "chain_length",
        "broken_at",
        "expected_hash",
        "actual_hash",
        "message",
    },
)
async def verify_chain(
    options: VerifyChainSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify the integrity of a resource's chain.

    Checks that each entry's chain_hash correctly links to previous.
    Uses the same hash computation as chain creation.

    Args:
        options: Verify options containing resource_id, resource_type
        ctx: Request context

    Returns:
        Dict with valid, chain_length, broken_at, expected_hash, actual_hash, message
    """
    resource_id = options.resource_id
    resource_type = options.resource_type

    # Fetch all chain entries for this resource, ordered by sequence
    rows = await select(
        "chain_entrys",
        where={"resource_id": resource_id, "resource_type": resource_type},
        order_by="sequence ASC",
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Chain verification may be cross-tenant admin op
    )

    if not rows:
        return {
            "valid": True,
            "chain_length": 0,
            "broken_at": None,
            "expected_hash": None,
            "actual_hash": None,
            "message": "No chain entries found for resource",
        }

    # Verify genesis entry (sequence 0)
    genesis = rows[0]
    if genesis["sequence"] != 0:
        return {
            "valid": False,
            "chain_length": len(rows),
            "broken_at": 0,
            "expected_hash": None,
            "actual_hash": None,
            "message": f"Chain missing genesis entry (starts at sequence {genesis['sequence']})",
        }

    # Verify genesis has no previous_hash
    if genesis["previous_hash"] is not None:
        return {
            "valid": False,
            "chain_length": len(rows),
            "broken_at": 0,
            "expected_hash": None,
            "actual_hash": None,
            "message": "Genesis entry should not have previous_hash",
        }

    # Verify genesis chain_hash
    expected_genesis_hash = compute_hash(
        {
            "previous_hash": None,
            "payload_hash": genesis["payload_hash"],
            "sequence": 0,
        }
    )

    if genesis["chain_hash"] != expected_genesis_hash:
        return {
            "valid": False,
            "chain_length": len(rows),
            "broken_at": 0,
            "expected_hash": expected_genesis_hash,
            "actual_hash": genesis["chain_hash"],
            "message": "Genesis entry chain_hash mismatch",
        }

    # Walk the chain verifying each link
    previous_hash = genesis["chain_hash"]

    for i, entry in enumerate(rows[1:], start=1):
        expected_sequence = i

        # Verify sequence continuity
        if entry["sequence"] != expected_sequence:
            return {
                "valid": False,
                "chain_length": len(rows),
                "broken_at": expected_sequence,
                "expected_hash": None,
                "actual_hash": None,
                "message": f"Sequence gap: expected {expected_sequence}, got {entry['sequence']}",
            }

        # Verify previous_hash links correctly
        if entry["previous_hash"] != previous_hash:
            return {
                "valid": False,
                "chain_length": len(rows),
                "broken_at": entry["sequence"],
                "expected_hash": previous_hash,
                "actual_hash": entry["previous_hash"],
                "message": f"Previous hash mismatch at sequence {entry['sequence']}",
            }

        # Verify chain_hash is correctly computed
        expected_chain_hash = compute_hash(
            {
                "previous_hash": entry["previous_hash"],
                "payload_hash": entry["payload_hash"],
                "sequence": entry["sequence"],
            }
        )

        if entry["chain_hash"] != expected_chain_hash:
            return {
                "valid": False,
                "chain_length": len(rows),
                "broken_at": entry["sequence"],
                "expected_hash": expected_chain_hash,
                "actual_hash": entry["chain_hash"],
                "message": f"Chain hash mismatch at sequence {entry['sequence']}",
            }

        # Move to next link
        previous_hash = entry["chain_hash"]

    return {
        "valid": True,
        "chain_length": len(rows),
        "broken_at": None,
        "expected_hash": None,
        "actual_hash": None,
        "message": f"Chain verified: {len(rows)} entries, integrity intact",
    }
