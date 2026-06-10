"""Verify evidence content integrity via hash.

Complete vertical slice:
- Fetches evidence record
- Recomputes hash from content
- Compares with stored content_hash
- Returns verification result

Regulatory: FRE 901, ISO 27037, SOX Section 802
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyEvidenceIntegritySpecs", "verify_evidence_integrity"]


class VerifyEvidenceIntegritySpecs(BaseModel):
    """Specs for verify evidence integrity phrase."""

    # inputs
    evidence_id: UUID
    # outputs
    valid: bool = False
    stored_hash: str | None = None
    computed_hash: str | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyEvidenceIntegritySpecs),
    inputs={"evidence_id"},
    outputs={"evidence_id", "valid", "stored_hash", "computed_hash", "reason"},
)
async def verify_evidence_integrity(
    options: VerifyEvidenceIntegritySpecs,
    ctx: RequestContext,
) -> dict:
    """Verify evidence content integrity via hash comparison.

    Fetches the evidence record, recomputes the content hash from
    the data field, and compares with the stored content_hash.
    Any mismatch indicates potential tampering or corruption.

    Args:
        options: Options containing evidence_id to verify.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with valid=True if hashes match, details otherwise.

    Regulatory basis:
        - FRE 901: Authentication of evidence
        - ISO 27037: Digital evidence handling
        - SOX Section 802: Document integrity
    """
    evidence_id = options.evidence_id

    # Fetch evidence record
    row = await select_one(
        "evidences",
        where={"id": evidence_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "evidence_id": evidence_id,
            "valid": False,
            "stored_hash": None,
            "computed_hash": None,
            "reason": "Evidence not found",
        }

    # Check tenant access
    if row.get("tenant_id") != ctx.tenant_id:
        return {
            "evidence_id": evidence_id,
            "valid": False,
            "stored_hash": None,
            "computed_hash": None,
            "reason": "Evidence belongs to different tenant",
        }

    stored_hash = row.get("content_hash")
    data = row.get("data")

    # If no data, consider it valid (nothing to hash)
    if data is None:
        return {
            "evidence_id": evidence_id,
            "valid": True,
            "stored_hash": stored_hash,
            "computed_hash": None,
            "reason": "No data content to verify",
        }

    # If no stored hash, cannot verify
    if stored_hash is None:
        return {
            "evidence_id": evidence_id,
            "valid": False,
            "stored_hash": None,
            "computed_hash": None,
            "reason": "Missing content_hash - cannot verify integrity",
        }

    # Compute hash from data
    try:
        computed_hash = compute_hash(data)
    except Exception as e:
        return {
            "evidence_id": evidence_id,
            "valid": False,
            "stored_hash": stored_hash,
            "computed_hash": None,
            "reason": f"Failed to compute hash: {e!s}",
        }

    # Compare hashes
    if stored_hash != computed_hash:
        return {
            "evidence_id": evidence_id,
            "valid": False,
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
            "reason": "Content hash mismatch - possible tampering or corruption",
        }

    return {
        "evidence_id": evidence_id,
        "valid": True,
        "stored_hash": stored_hash,
        "computed_hash": computed_hash,
        "reason": None,
    }
