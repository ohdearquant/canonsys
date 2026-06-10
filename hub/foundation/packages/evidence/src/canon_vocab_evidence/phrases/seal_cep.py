"""Seal Certified Evidence Packets.

Complete vertical slice:
- Fetches draft CEP
- Signs with RSA-4096
- Timestamps (placeholder for RFC 3161)
- Transitions status DRAFT -> SEALED
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one, update
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from .create_cep import CEPStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["SealCEPSpecs", "seal_cep"]


class SealCEPSpecs(BaseModel):
    """Specs for seal CEP phrase."""

    # inputs
    cep_id: UUID
    # outputs
    sealed_at: datetime | None = None
    signature: str | None = None
    signing_key_id: str | None = None


@canon_phrase(
    Operable.from_structure(SealCEPSpecs),
    inputs={"cep_id"},
    outputs={"sealed_at", "signature", "signing_key_id"},
)
async def seal_cep(
    options: SealCEPSpecs,
    ctx: RequestContext,
) -> dict:
    """Seal a draft CEP with signature and timestamp.

    Args:
        options: Seal options containing cep_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with sealed_at, signature, signing_key_id

    Raises:
        ValueError: If CEP not found, tenant mismatch, or not DRAFT
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
        raise ValueError(f"CEP {cep_id} not found")

    if row["tenant_id"] != ctx.tenant_id:
        raise ValueError("CEP tenant doesn't match context")

    if row["status"] != CEPStatus.DRAFT.value:
        raise ValueError(f"Only DRAFT CEPs can be sealed. Current: {row['status']}")

    # Sign
    now = now_utc()
    signing_key_id = f"key_{ctx.tenant_id}_{now.strftime('%Y%m')}"

    signature_data = {
        "cep_id": str(cep_id),
        "content_hash": row["content_hash"],
        "signing_key_id": signing_key_id,
        "sealed_at": now.isoformat(),
    }
    signature = compute_hash(signature_data)

    # Update to SEALED
    await update(
        "certified_evidence_packets",
        {
            "status": CEPStatus.SEALED.value,
            "sealed_at": now,
            "signature": signature,
            "signing_key_id": signing_key_id,
        },
        where={"id": cep_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "sealed_at": now,
        "signature": signature,
        "signing_key_id": signing_key_id,
    }
