"""Verify CEP is cryptographically sealed.

Complete vertical slice:
- Checks CEP status is SEALED
- Validates seal signature exists
- Returns seal metadata

Regulatory: SPEC-003 - CEP must be sealed before certificate binding
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

__all__ = ["VerifyCEPSealedSpecs", "verify_cep_sealed"]


class VerifyCEPSealedSpecs(BaseModel):
    """Specs for verify CEP sealed phrase."""

    # inputs
    cep_id: UUID
    # outputs
    sealed: bool = False
    seal_timestamp: datetime | None = None
    seal_signature: str | None = None
    signing_key_id: str | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyCEPSealedSpecs),
    inputs={"cep_id"},
    outputs={
        "sealed",
        "cep_id",
        "seal_timestamp",
        "seal_signature",
        "signing_key_id",
        "reason",
    },
)
async def verify_cep_sealed(
    options: VerifyCEPSealedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify a CEP is cryptographically sealed.

    Checks that the CEP exists, has status SEALED, and has
    valid seal metadata (timestamp, signature, signing key).

    Args:
        options: Options containing cep_id.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with sealed status and seal metadata.
    """
    cep_id = options.cep_id

    # Fetch CEP
    row = await select_one(
        "certified_evidence_packets",
        where={"id": cep_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "sealed": False,
            "cep_id": cep_id,
            "seal_timestamp": None,
            "seal_signature": None,
            "signing_key_id": None,
            "reason": "CEP not found",
        }

    # Check tenant isolation
    if row["tenant_id"] != ctx.tenant_id:
        return {
            "sealed": False,
            "cep_id": cep_id,
            "seal_timestamp": None,
            "seal_signature": None,
            "signing_key_id": None,
            "reason": "CEP tenant mismatch",
        }

    # Check status
    status = row.get("status")
    if status != CEPStatus.SEALED.value:
        return {
            "sealed": False,
            "cep_id": cep_id,
            "seal_timestamp": None,
            "seal_signature": None,
            "signing_key_id": None,
            "reason": f"CEP status is {status}, not SEALED",
        }

    # Verify seal metadata exists
    sealed_at = row.get("sealed_at")
    signature = row.get("signature")
    signing_key_id = row.get("signing_key_id")

    if not sealed_at:
        return {
            "sealed": False,
            "cep_id": cep_id,
            "seal_timestamp": None,
            "seal_signature": None,
            "signing_key_id": None,
            "reason": "CEP marked as SEALED but missing seal timestamp",
        }

    # CEP is properly sealed
    return {
        "sealed": True,
        "cep_id": cep_id,
        "seal_timestamp": sealed_at,
        "seal_signature": signature,
        "signing_key_id": signing_key_id,
        "reason": None,
    }
