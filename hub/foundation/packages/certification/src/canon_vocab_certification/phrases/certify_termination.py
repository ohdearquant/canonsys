"""Certify termination decisions.

Complete vertical slice:
- Validates ER clearance
- Checks CEP references
- Requires parity attestation
- Creates TDC with full audit trail
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

__all__ = ["CertifyTerminationSpecs", "TerminationType", "certify_termination"]


class TerminationType(StrEnum):
    """Types of termination."""

    VOLUNTARY = "voluntary"
    INVOLUNTARY_PERFORMANCE = "involuntary_performance"
    INVOLUNTARY_CONDUCT = "involuntary_conduct"
    INVOLUNTARY_RIF = "involuntary_rif"
    CONTRACT_END = "contract_end"


class CertifyTerminationSpecs(BaseModel):
    """Specs for termination certification phrase."""

    # inputs
    subject_id: UUID
    termination_type: TerminationType
    policy_basis: str
    cep_ids: list[UUID]
    er_clearance_verified: bool
    parity_attested: bool
    effective_date: datetime | None = None
    attestation_id: UUID | None = None
    override_id: UUID | None = None
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    certificate_hash: str | None = None
    certified_at: datetime | None = None
    certified_by: UUID | None = None


@canon_phrase(
    Operable.from_structure(CertifyTerminationSpecs),
    inputs={
        "subject_id",
        "termination_type",
        "policy_basis",
        "cep_ids",
        "er_clearance_verified",
        "parity_attested",
        "effective_date",
        "attestation_id",
        "override_id",
    },
    outputs={
        "id",
        "tenant_id",
        "subject_id",
        "termination_type",
        "policy_basis",
        "cep_ids",
        "er_clearance_verified",
        "parity_attested",
        "certificate_hash",
        "certified_at",
        "certified_by",
        "effective_date",
        "attestation_id",
        "override_id",
    },
)
async def certify_termination(
    options: CertifyTerminationSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Create Termination Decision Certificate.

    Args:
        options: Termination options containing subject_id, type, policy_basis, cep_ids, etc.
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with certificate fields

    Raises:
        ValueError: If required checks not complete
    """
    # Validate required checks for involuntary termination
    if options.termination_type.value.startswith("involuntary"):
        if not options.er_clearance_verified:
            raise ValueError("ER clearance required for involuntary termination")
        if not options.parity_attested:
            raise ValueError("Parity attestation required for involuntary termination")
        if not options.cep_ids:
            raise ValueError("CEP evidence required for involuntary termination")

    now = now_utc()
    cert_id = uuid4()

    # Compute certificate hash
    hash_data = {
        "id": str(cert_id),
        "subject_id": str(options.subject_id),
        "termination_type": options.termination_type.value,
        "policy_basis": options.policy_basis,
        "cep_ids": [str(cid) for cid in options.cep_ids],
        "er_clearance_verified": options.er_clearance_verified,
        "parity_attested": options.parity_attested,
        "certified_at": now.isoformat(),
    }
    certificate_hash = compute_hash(hash_data)

    effective_date = options.effective_date or now

    # Persist
    row_data = {
        "id": cert_id,
        "tenant_id": ctx.tenant_id,
        "subject_id": options.subject_id,
        "termination_type": options.termination_type.value,
        "policy_basis": options.policy_basis,
        "cep_ids": [str(cid) for cid in options.cep_ids],
        "er_clearance_verified": options.er_clearance_verified,
        "parity_attested": options.parity_attested,
        "certificate_hash": certificate_hash,
        "certified_at": now,
        "certified_by": ctx.actor_id,
        "effective_date": effective_date,
        "attestation_id": options.attestation_id,
        "override_id": options.override_id,
    }

    await insert(
        "termination_certificates",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "id": cert_id,
        "tenant_id": ctx.tenant_id,
        "subject_id": options.subject_id,
        "termination_type": options.termination_type,
        "policy_basis": options.policy_basis,
        "cep_ids": options.cep_ids,
        "er_clearance_verified": options.er_clearance_verified,
        "parity_attested": options.parity_attested,
        "certificate_hash": certificate_hash,
        "certified_at": now,
        "certified_by": ctx.actor_id,
        "effective_date": effective_date,
        "attestation_id": options.attestation_id,
        "override_id": options.override_id,
    }
