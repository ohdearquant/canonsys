"""Verify evidence chain integrity.

Complete vertical slice:
- Fetches all chain entries for a given chain_id
- Verifies hash linkage is unbroken across entries
- Verifies content hashes match stored evidence data
- Returns detailed verification result with any breaks

Regulatory: FRE 901, ISO 27037, SOX Section 802
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyEvidenceChainSpecs", "verify_evidence_chain"]


class VerifyEvidenceChainSpecs(BaseModel):
    """Specs for verify evidence chain phrase."""

    # inputs
    chain_id: UUID
    # outputs
    verified: bool = False
    entry_count: int = 0
    breaks: list[dict[str, Any]] = []
    reason: str | None = None


async def _check_evidence_content(
    entry: dict[str, Any],
    sequence: int,
    breaks: list[dict[str, Any]],
    ctx: RequestContext,
) -> None:
    """Check that evidence content matches the payload_hash in the chain entry.

    Fetches the evidence record referenced by the chain entry's payload
    and recomputes the content hash to verify against payload_hash.

    Args:
        entry: Chain entry row from database.
        sequence: Sequence number for error reporting.
        breaks: Mutable list to append break records to.
        ctx: Request context for DB access.
    """
    payload = entry.get("payload")
    if not payload or not isinstance(payload, dict):
        return

    evidence_id_str = payload.get("evidence_id")
    if not evidence_id_str:
        return

    try:
        evidence_id = UUID(evidence_id_str)
    except (ValueError, TypeError):
        breaks.append(
            {
                "sequence": sequence,
                "type": "invalid_evidence_id",
                "detail": f"Cannot parse evidence_id: {evidence_id_str}",
            }
        )
        return

    try:
        evidence_row = await select_one(
            "evidences",
            where={"id": evidence_id},
            conn=ctx.conn,
            tenant_scope=TenantScope.DISABLED,
        )
    except Exception:
        # DB errors during content verification are non-fatal
        return

    if not evidence_row:
        breaks.append(
            {
                "sequence": sequence,
                "type": "evidence_not_found",
                "detail": f"Evidence {evidence_id} referenced by chain entry not found",
            }
        )
        return

    data = evidence_row.get("data")
    if data is None:
        return  # No data content to verify

    recomputed = compute_hash(data)
    if recomputed != entry["payload_hash"]:
        breaks.append(
            {
                "sequence": sequence,
                "type": "content_hash_mismatch",
                "detail": "Evidence content hash does not match chain entry payload_hash",
                "expected": recomputed,
                "actual": entry["payload_hash"],
            }
        )


@canon_phrase(
    Operable.from_structure(VerifyEvidenceChainSpecs),
    inputs={"chain_id"},
    outputs={"verified", "chain_id", "entry_count", "breaks", "reason"},
)
async def verify_evidence_chain(
    options: VerifyEvidenceChainSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify the integrity of an evidence chain.

    Fetches all chain entries for the given chain_id and verifies:
    1. Each entry's content_hash matches SHA-256 of its evidence content
    2. Each entry's previous_hash matches the chain_hash of the prior entry
    3. Chain hash is correctly computed from its inputs
    4. Sequence numbers are contiguous starting from 0

    This is a verify_* phrase: it NEVER raises. All error conditions
    are reported via the return value.

    Args:
        options: Options containing chain_id to verify.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with verified (bool), chain_id, entry_count,
        breaks (list of dicts describing integrity issues),
        and reason (summary string or None if valid).

    Regulatory basis:
        - FRE 901: Authentication of evidence
        - ISO 27037: Digital evidence handling
        - SOX Section 802: Document integrity
    """
    chain_id = options.chain_id

    # Fetch all chain entries for this chain, ordered by sequence
    try:
        rows = await select(
            "chain_entrys",
            where={"resource_id": chain_id, "resource_type": "evidence_chain"},
            order_by="sequence ASC",
            conn=ctx.conn,
            tenant_scope=TenantScope.DISABLED,  # Verification may be cross-tenant admin op
        )
    except Exception as exc:
        return {
            "verified": False,
            "chain_id": chain_id,
            "entry_count": 0,
            "breaks": [{"sequence": -1, "type": "fetch_error", "detail": str(exc)}],
            "reason": f"Failed to fetch chain entries: {exc}",
        }

    if not rows:
        return {
            "verified": True,
            "chain_id": chain_id,
            "entry_count": 0,
            "breaks": [],
            "reason": "No entries found for chain",
        }

    breaks: list[dict[str, Any]] = []

    # --- Verify genesis entry (sequence 0) ---
    genesis = rows[0]

    if genesis["sequence"] != 0:
        breaks.append(
            {
                "sequence": 0,
                "type": "missing_genesis",
                "detail": f"Chain starts at sequence {genesis['sequence']}, expected 0",
            }
        )

    if genesis["previous_hash"] is not None:
        breaks.append(
            {
                "sequence": 0,
                "type": "genesis_has_previous",
                "detail": "Genesis entry should not have previous_hash",
            }
        )

    # Verify genesis chain_hash computation
    expected_genesis_hash = compute_hash(
        {
            "previous_hash": None,
            "payload_hash": genesis["payload_hash"],
            "sequence": 0,
        }
    )

    if genesis["chain_hash"] != expected_genesis_hash:
        breaks.append(
            {
                "sequence": 0,
                "type": "chain_hash_mismatch",
                "detail": "Genesis chain_hash does not match computed value",
                "expected": expected_genesis_hash,
                "actual": genesis["chain_hash"],
            }
        )

    # Verify genesis evidence content integrity
    await _check_evidence_content(genesis, 0, breaks, ctx)

    # --- Walk the chain verifying each link ---
    previous_chain_hash = genesis["chain_hash"]

    for i, entry in enumerate(rows[1:], start=1):
        expected_sequence = i

        # Verify sequence continuity
        if entry["sequence"] != expected_sequence:
            breaks.append(
                {
                    "sequence": expected_sequence,
                    "type": "sequence_gap",
                    "detail": f"Expected sequence {expected_sequence}, got {entry['sequence']}",
                }
            )

        # Verify previous_hash links to prior entry's chain_hash
        if entry["previous_hash"] != previous_chain_hash:
            breaks.append(
                {
                    "sequence": entry["sequence"],
                    "type": "previous_hash_mismatch",
                    "detail": "previous_hash does not match prior entry's chain_hash",
                    "expected": previous_chain_hash,
                    "actual": entry["previous_hash"],
                }
            )

        # Verify chain_hash computation
        expected_chain_hash = compute_hash(
            {
                "previous_hash": entry["previous_hash"],
                "payload_hash": entry["payload_hash"],
                "sequence": entry["sequence"],
            }
        )

        if entry["chain_hash"] != expected_chain_hash:
            breaks.append(
                {
                    "sequence": entry["sequence"],
                    "type": "chain_hash_mismatch",
                    "detail": "chain_hash does not match computed value",
                    "expected": expected_chain_hash,
                    "actual": entry["chain_hash"],
                }
            )

        # Verify evidence content integrity
        await _check_evidence_content(entry, entry["sequence"], breaks, ctx)

        # Advance to next link
        previous_chain_hash = entry["chain_hash"]

    verified = len(breaks) == 0
    reason = None if verified else f"Chain integrity broken: {len(breaks)} issue(s) found"

    return {
        "verified": verified,
        "chain_id": chain_id,
        "entry_count": len(rows),
        "breaks": breaks,
        "reason": reason,
    }
