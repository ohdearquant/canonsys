"""Record typed attestations for certificates and workflows.

Complete vertical slice:
- Validates attestation text (substantive, not checkbox)
- Creates immutable attestation record
- Links to certificate or workflow
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

__all__ = ["AttestationType", "RecordAttestationSpecs", "record_attestation"]


class AttestationType(StrEnum):
    """Types of attestation (scope limitation)."""

    PROCESS_ADHERENCE = "process_adherence"
    """Attests process was followed."""

    PARITY_CONFIRMATION = "parity_confirmation"
    """Attests similar treatment."""

    ER_CLEARANCE = "er_clearance"
    """Attests ER review complete."""

    EXECUTIVE_OVERRIDE = "executive_override"
    """Attests risk acceptance."""

    WITNESS = "witness"
    """Attests presence at event."""


class RecordAttestationSpecs(BaseModel):
    """Specs for attestation recording phrase."""

    # inputs
    target_type: str  # certificate, workflow, cep
    target_id: UUID
    attestation_type: AttestationType
    attestation_text: str
    attester_role: str
    ip_address: str | None = None
    user_agent: str | None = None
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    attester_id: UUID | None = None
    attestation_hash: str | None = None
    attested_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(RecordAttestationSpecs),
    inputs={
        "target_type",
        "target_id",
        "attestation_type",
        "attestation_text",
        "attester_role",
        "ip_address",
        "user_agent",
    },
    outputs={
        "id",
        "tenant_id",
        "attestation_type",
        "attester_id",
        "attester_role",
        "target_type",
        "target_id",
        "attestation_text",
        "attestation_hash",
        "attested_at",
        "ip_address",
        "user_agent",
    },
)
async def record_attestation(
    options: RecordAttestationSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Record a typed attestation.

    Attestations are PROCESS attestations, not outcome attestations.
    The signer attests to following procedure, NOT to correctness of decision.

    Args:
        options: Attestation options containing target, type, text, role
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with attestation record fields

    Raises:
        ValueError: If attestation text too short or actor missing
    """
    if len(options.attestation_text.strip()) < 20:
        raise ValueError("Attestation must be substantive (min 20 characters)")

    if not ctx.actor_id:
        raise ValueError("Attestation requires identified actor")

    now = now_utc()
    attest_id = uuid4()

    # Compute attestation hash
    hash_data = {
        "target_type": options.target_type,
        "target_id": str(options.target_id),
        "attestation_type": options.attestation_type.value,
        "attestation_text": options.attestation_text,
        "attester_id": str(ctx.actor_id),
        "attested_at": now.isoformat(),
    }
    attestation_hash = compute_hash(hash_data)

    # Persist (immutable)
    row_data = {
        "id": attest_id,
        "tenant_id": ctx.tenant_id,
        "attestation_type": options.attestation_type.value,
        "attester_id": ctx.actor_id,
        "attester_role": options.attester_role,
        "target_type": options.target_type,
        "target_id": options.target_id,
        "attestation_text": options.attestation_text,
        "attestation_hash": attestation_hash,
        "attested_at": now,
        "ip_address": options.ip_address,
        "user_agent": options.user_agent,
    }

    await insert(
        "attestation_records",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "id": attest_id,
        "tenant_id": ctx.tenant_id,
        "attestation_type": options.attestation_type,
        "attester_id": ctx.actor_id,
        "attester_role": options.attester_role,
        "target_type": options.target_type,
        "target_id": options.target_id,
        "attestation_text": options.attestation_text,
        "attestation_hash": attestation_hash,
        "attested_at": now,
        "ip_address": options.ip_address,
        "user_agent": options.user_agent,
    }
