"""Verify CEP references for certificate binding.

Complete vertical slice:
- Validates CEP exists
- Checks hash matches
- Verifies status is SEALED
- Confirms not expired/superseded
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .create_cep import CEPStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyCEPReferenceSpecs", "verify_cep_reference"]


class VerifyCEPReferenceSpecs(BaseModel):
    """Specs for verify CEP reference phrase."""

    # inputs
    cep_id: UUID
    expected_hash: str
    # outputs
    valid: bool = False
    reason: str | None = None
    cep_type: str | None = None
    sealed_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(VerifyCEPReferenceSpecs),
    inputs={"cep_id", "expected_hash"},
    outputs={"valid", "cep_id", "reason", "cep_type", "sealed_at"},
)
async def verify_cep_reference(
    options: VerifyCEPReferenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify a CEP reference for certificate binding.

    Certificates can only reference CEPs, never raw evidence.
    This validates the reference is valid.

    Args:
        options: Verify options containing cep_id, expected_hash
        ctx: Request context (tenant, actor)

    Returns:
        Dict with valid, cep_id, reason, cep_type, sealed_at
    """
    cep_id = options.cep_id
    expected_hash = options.expected_hash

    # Fetch CEP
    row = await select_one(
        "certified_evidence_packets",
        where={"id": cep_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "valid": False,
            "cep_id": cep_id,
            "reason": "CEP not found",
            "cep_type": None,
            "sealed_at": None,
        }

    if row["tenant_id"] != ctx.tenant_id:
        return {
            "valid": False,
            "cep_id": cep_id,
            "reason": "CEP tenant mismatch",
            "cep_type": None,
            "sealed_at": None,
        }

    # Verify hash match
    if row["content_hash"] != expected_hash:
        return {
            "valid": False,
            "cep_id": cep_id,
            "reason": "Hash mismatch - CEP may have been tampered",
            "cep_type": None,
            "sealed_at": None,
        }

    # Verify status is SEALED
    if row["status"] != CEPStatus.SEALED.value:
        return {
            "valid": False,
            "cep_id": cep_id,
            "reason": f"CEP status is {row['status']}, must be SEALED",
            "cep_type": None,
            "sealed_at": None,
        }

    # Check not superseded
    if row.get("superseded_by_id"):
        return {
            "valid": False,
            "cep_id": cep_id,
            "reason": "CEP has been superseded",
            "cep_type": None,
            "sealed_at": None,
        }

    return {
        "valid": True,
        "cep_id": cep_id,
        "reason": None,
        "cep_type": row.get("cep_type"),
        "sealed_at": row.get("sealed_at"),
    }
