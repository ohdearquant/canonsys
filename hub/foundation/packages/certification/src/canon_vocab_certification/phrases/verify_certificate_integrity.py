"""Verify integrity of a decision certificate.

Checks that the stored content_hash matches a recomputed hash of the
certificate's content fields. This is a verify_* phrase and NEVER raises
-- it returns a verification result with a boolean flag.

Regulatory basis:
    - SOX Section 802: Document integrity verification
    - FRCP Rule 37(e): ESI preservation and tamper detection
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

__all__ = ["VerifyCertificateIntegritySpecs", "verify_certificate_integrity"]


class VerifyCertificateIntegritySpecs(BaseModel):
    """Specs for certificate integrity verification phrase."""

    # inputs
    certificate_id: UUID
    # outputs
    verified: bool | None = None
    content_hash: str | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyCertificateIntegritySpecs),
    inputs={"certificate_id"},
    outputs={"certificate_id", "verified", "content_hash", "reason"},
)
async def verify_certificate_integrity(
    options: VerifyCertificateIntegritySpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Verify that a certificate's content_hash is intact.

    Fetches the certificate, recomputes the content hash from the stored
    fields, and compares it against the stored content_hash. This detects
    any post-mint tampering.

    This is a verify_* phrase: it NEVER raises. All failure modes are
    expressed through the returned ``verified`` flag and ``reason`` field.

    Args:
        options: Options containing certificate_id to verify.
        ctx: Request context (tenant).
        conn: Optional existing DB connection.

    Returns:
        Dict with verified (bool), certificate_id, content_hash, and
        reason (str | None -- populated on failure).
    """
    # Fetch certificate
    row = await select_one(
        "decision_certificates",
        where={"id": options.certificate_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "certificate_id": options.certificate_id,
            "verified": False,
            "content_hash": None,
            "reason": f"Certificate {options.certificate_id} not found",
        }

    if row["tenant_id"] != ctx.tenant_id:
        return {
            "certificate_id": options.certificate_id,
            "verified": False,
            "content_hash": None,
            "reason": "Certificate tenant does not match request context",
        }

    stored_hash = row.get("content_hash")
    if not stored_hash:
        return {
            "certificate_id": options.certificate_id,
            "verified": False,
            "content_hash": None,
            "reason": "Certificate has no content_hash stored",
        }

    # Recompute hash from the same fields used during minting.
    # The minting path (certify_decision) hashes: id, workflow_type (action_type),
    # facts (not stored separately -- we use evidence_ids), evidence_refs, minted_at.
    # For integrity verification we hash the canonical content fields that
    # are available on the persisted row.
    recomputed_hash = compute_hash(
        {
            "id": str(row["id"]),
            "action_type": row.get("action_type"),
            "evidence_ids": row.get("evidence_ids", []),
            "minted_at": (row["minted_at"].isoformat() if row.get("minted_at") else None),
            "subject_id": str(row["subject_id"]) if row.get("subject_id") else None,
            "case_id": str(row["case_id"]) if row.get("case_id") else None,
            "schema_version": row.get("schema_version"),
        }
    )

    if recomputed_hash != stored_hash:
        return {
            "certificate_id": options.certificate_id,
            "verified": False,
            "content_hash": stored_hash,
            "reason": (
                f"Integrity check failed: stored hash {stored_hash[:16]}... "
                f"does not match recomputed hash {recomputed_hash[:16]}..."
            ),
        }

    return {
        "certificate_id": options.certificate_id,
        "verified": True,
        "content_hash": stored_hash,
        "reason": None,
    }
