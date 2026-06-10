"""Request timestamp attestation via RFC 3161 TSA.

Complete vertical slice:
- Creates timestamp request for content hash
- Calls TSA service (placeholder for actual TSA)
- Persists attestation record
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

__all__ = ["RequestTimestampAttestationSpecs", "request_timestamp_attestation"]


class RequestTimestampAttestationSpecs(BaseModel):
    """Specs for timestamp attestation request phrase."""

    # inputs
    content_hash: str
    target_type: str | None = None  # evidence, cep, certificate
    target_id: UUID | None = None
    tsa_name: str = "internal"
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    token_hash: str | None = None
    gen_time: datetime | None = None
    requested_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(RequestTimestampAttestationSpecs),
    inputs={"content_hash", "target_type", "target_id", "tsa_name"},
    outputs={
        "id",
        "tenant_id",
        "content_hash",
        "tsa_name",
        "token_hash",
        "gen_time",
        "requested_at",
        "target_type",
        "target_id",
    },
)
async def request_timestamp_attestation(
    options: RequestTimestampAttestationSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Request timestamp attestation for content hash.

    Args:
        options: Timestamp options containing content_hash, optional target info
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with timestamp attestation record
    """
    now = now_utc()
    attest_id = uuid4()

    # Simulate TSA response (in production: call actual RFC 3161 TSA)
    token_data = {
        "content_hash": options.content_hash,
        "gen_time": now.isoformat(),
        "tsa_name": options.tsa_name,
        "nonce": str(attest_id),
    }
    token_hash = compute_hash(token_data)

    # Persist
    row_data = {
        "id": attest_id,
        "tenant_id": ctx.tenant_id,
        "content_hash": options.content_hash,
        "tsa_name": options.tsa_name,
        "token_hash": token_hash,
        "gen_time": now,
        "requested_at": now,
        "target_type": options.target_type,
        "target_id": options.target_id,
    }

    await insert(
        "timestamp_attestations",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "id": attest_id,
        "tenant_id": ctx.tenant_id,
        "content_hash": options.content_hash,
        "tsa_name": options.tsa_name,
        "token_hash": token_hash,
        "gen_time": now,
        "requested_at": now,
        "target_type": options.target_type,
        "target_id": options.target_id,
    }
