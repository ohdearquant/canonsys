"""Create Certified Evidence Packets (CEP).

Complete vertical slice:
- Creates draft CEP with facts and metadata
- Computes content hash over facts
- Persists with status=DRAFT
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

if TYPE_CHECKING:
    from datetime import datetime

    from canon.enforcement import RequestContext

__all__ = ["CEP", "CEPStatus", "CEPType", "CreateCEPSpecs", "create_cep"]


class CEPType(str, Enum):
    """Allowed CEP types - strict taxonomy."""

    PERF_METRIC = "perf_metric"  # Quantitative scores, quota, error rates
    POLICY_LOG = "policy_log"  # Access logs, timecards, security alerts
    CONDUCT_RECORD = "conduct_record"  # Redacted chat/email excerpts
    INVESTIGATION_RULING = "investigation_ruling"  # Final finding only
    PIP_FAIL = "pip_fail"  # Signed PIP doc + binary status


class CEPStatus(str, Enum):
    """CEP lifecycle states."""

    DRAFT = "draft"  # Created, not sealed
    SEALED = "sealed"  # Signed + timestamped, immutable
    SUPERSEDED = "superseded"  # Replaced by new version


@dataclass(frozen=True, slots=True)
class CEP:
    """Certified Evidence Packet."""

    id: UUID
    tenant_id: UUID
    cep_type: CEPType
    status: CEPStatus
    facts: dict[str, Any]
    content_hash: str
    custodian_id: UUID | None
    certifying_actor_id: UUID | None
    created_at: datetime
    sealed_at: datetime | None = None
    signature: str | None = None
    signing_key_id: str | None = None
    superseded_by_id: UUID | None = None


class CreateCEPSpecs(BaseModel):
    """Specs for create CEP phrase."""

    # inputs
    facts: dict[str, Any]
    cep_type: CEPType
    custodian_id: UUID | None = None
    # outputs
    cep_id: UUID | None = None
    content_hash: str | None = None
    status: CEPStatus | None = None


@canon_phrase(
    Operable.from_structure(CreateCEPSpecs),
    inputs={"facts", "cep_type", "custodian_id"},
    outputs={"cep_id", "content_hash", "status"},
)
async def create_cep(
    options: CreateCEPSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a draft Certified Evidence Packet.

    Args:
        options: Create options containing facts, cep_type, custodian_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with cep_id, content_hash, status

    Raises:
        ValueError: If facts empty or invalid type
    """
    facts = options.facts
    cep_type = options.cep_type
    custodian_id = options.custodian_id

    if not facts:
        raise ValueError("CEP must contain facts")

    # Compute content hash
    now = now_utc()
    cep_id = uuid4()

    hash_data = {
        "id": str(cep_id),
        "cep_type": cep_type.value,
        "facts": facts,
        "created_at": now.isoformat(),
    }
    content_hash = compute_hash(hash_data)

    # Build CEP
    cep = CEP(
        id=cep_id,
        tenant_id=ctx.tenant_id,
        cep_type=cep_type,
        status=CEPStatus.DRAFT,
        facts=facts,
        content_hash=content_hash,
        custodian_id=custodian_id,
        certifying_actor_id=ctx.actor_id,
        created_at=now,
    )

    # Persist
    row_data = {
        "id": cep.id,
        "tenant_id": cep.tenant_id,
        "cep_type": cep.cep_type.value,
        "status": cep.status.value,
        "facts": facts,
        "content_hash": cep.content_hash,
        "custodian_id": cep.custodian_id,
        "certifying_actor_id": cep.certifying_actor_id,
        "created_at": cep.created_at,
    }

    await insert(
        "certified_evidence_packets",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "cep_id": cep.id,
        "content_hash": cep.content_hash,
        "status": cep.status,
    }
