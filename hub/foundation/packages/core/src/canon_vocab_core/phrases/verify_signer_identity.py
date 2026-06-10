"""Verify signer identity phrase.

Verifies an evidence artifact was signed by a specific role.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifySignerIdentitySpecs", "verify_signer_identity"]


class VerifySignerIdentitySpecs(BaseModel):
    """Specs for verify signer identity phrase.

    Regulatory citations:
        - SOX Section 302: CEO/CFO must certify financial reports
        - EU AI Act Art. 17: Human oversight requires accountability
        - FCRA Section 1681m: Adverse action requires authorized signoff
    """

    # inputs
    evidence_id: UUID
    expected_role: str
    # outputs
    verified: bool
    signer_id: UUID | None = None
    signer_role: str | None = None
    signed_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifySignerIdentitySpecs),
    inputs={"evidence_id", "expected_role"},
    outputs={
        "verified",
        "evidence_id",
        "signer_id",
        "signer_role",
        "expected_role",
        "signed_at",
        "reason",
    },
)
async def verify_signer_identity(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify an evidence artifact was signed by a specific role.

    Checks attestation records for the evidence to verify the expected
    role has attested to it. Does NOT raise exceptions for mismatches -
    returns verification result for caller to handle.

    Args:
        options: Verification options (evidence_id, expected_role)
        ctx: Request context

    Returns:
        dict with verification status
    """
    evidence_id = options.get("evidence_id")
    expected_role = options.get("expected_role")

    # Query attestation records for this evidence with expected role
    row = await select_one(
        "attestation_records",
        where={
            "target_type": "evidence",
            "target_id": evidence_id,
            "attester_role": expected_role,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if row:
        # Found attestation with expected role
        return {
            "verified": True,
            "evidence_id": evidence_id,
            "signer_id": row["attester_id"],
            "signer_role": row["attester_role"],
            "expected_role": expected_role,
            "signed_at": row.get("attested_at"),
            "reason": f"Evidence signed by {expected_role}",
        }

    # Check if evidence has ANY attestation (for better error message)
    any_attestation = await select_one(
        "attestation_records",
        where={
            "target_type": "evidence",
            "target_id": evidence_id,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if any_attestation:
        # Evidence has attestation but wrong role
        return {
            "verified": False,
            "evidence_id": evidence_id,
            "signer_id": any_attestation["attester_id"],
            "signer_role": any_attestation["attester_role"],
            "expected_role": expected_role,
            "signed_at": any_attestation.get("attested_at"),
            "reason": f"Evidence signed by {any_attestation['attester_role']}, not {expected_role}",
        }

    # No attestation found at all
    return {
        "verified": False,
        "evidence_id": evidence_id,
        "signer_id": None,
        "signer_role": None,
        "expected_role": expected_role,
        "signed_at": None,
        "reason": "No attestation found for evidence",
    }
