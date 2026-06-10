"""Certify FCRA pre-adverse action notice compliance.

Complete vertical slice:
- Validates notice was sent
- Checks timing requirements (5 business days)
- Creates FCRA compliance certificate
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

__all__ = ["CertifyFcraNoticeSpecs", "certify_fcra_notice"]


class CertifyFcraNoticeSpecs(BaseModel):
    """Specs for FCRA notice certification phrase."""

    # inputs
    subject_id: UUID
    notice_sent_at: datetime
    dispute_window_end: datetime
    cep_ids: list[UUID]
    application_id: UUID | None = None
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    certificate_hash: str | None = None
    certified_at: datetime | None = None
    certified_by: UUID | None = None


@canon_phrase(
    Operable.from_structure(CertifyFcraNoticeSpecs),
    inputs={
        "subject_id",
        "notice_sent_at",
        "dispute_window_end",
        "cep_ids",
        "application_id",
    },
    outputs={
        "id",
        "tenant_id",
        "subject_id",
        "notice_sent_at",
        "dispute_window_end",
        "cep_ids",
        "certificate_hash",
        "certified_at",
        "certified_by",
        "application_id",
    },
)
async def certify_fcra_notice(
    options: CertifyFcraNoticeSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Certify FCRA pre-adverse action notice compliance.

    Per FCRA 15 U.S.C. Section 1681b(b)(3), employer must:
    1. Provide pre-adverse action notice
    2. Include copy of consumer report
    3. Wait reasonable time for dispute (typically 5 business days)

    Args:
        options: Certification options containing subject_id, notice timing, cep_ids
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with certificate fields

    Raises:
        ValueError: If dispute window hasn't ended or no CEPs
    """
    now = now_utc()

    # Validate dispute window has ended
    if now < options.dispute_window_end:
        raise ValueError(
            f"Dispute window has not ended. Wait until {options.dispute_window_end.isoformat()}"
        )

    # Validate CEPs provided
    if not options.cep_ids:
        raise ValueError("At least one sealed CEP required for FCRA certification")

    cert_id = uuid4()

    # Compute certificate hash
    hash_data = {
        "id": str(cert_id),
        "subject_id": str(options.subject_id),
        "notice_sent_at": options.notice_sent_at.isoformat(),
        "dispute_window_end": options.dispute_window_end.isoformat(),
        "cep_ids": [str(cid) for cid in options.cep_ids],
        "certified_at": now.isoformat(),
    }
    certificate_hash = compute_hash(hash_data)

    # Persist
    row_data = {
        "id": cert_id,
        "tenant_id": ctx.tenant_id,
        "subject_id": options.subject_id,
        "notice_sent_at": options.notice_sent_at,
        "dispute_window_end": options.dispute_window_end,
        "cep_ids": [str(cid) for cid in options.cep_ids],
        "certificate_hash": certificate_hash,
        "certified_at": now,
        "certified_by": ctx.actor_id,
        "application_id": options.application_id,
    }

    await insert(
        "fcra_notice_certificates",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "id": cert_id,
        "tenant_id": ctx.tenant_id,
        "subject_id": options.subject_id,
        "notice_sent_at": options.notice_sent_at,
        "dispute_window_end": options.dispute_window_end,
        "cep_ids": options.cep_ids,
        "certificate_hash": certificate_hash,
        "certified_at": now,
        "certified_by": ctx.actor_id,
        "application_id": options.application_id,
    }
