"""Revoke a decision certificate via supersession.

CanonSys certificates are never mutated -- revocation is implemented as
supersession. This phrase creates a new superseding certificate that
records the revocation reason and the revoking actor, then transitions the
original certificate to SUPERSEDED status.

Immutability via supersession (per CanonSys principles):
    - Original certificate content is never changed.
    - Only the status field transitions to SUPERSEDED.
    - A new record links back via supersedes_id.

Regulatory basis:
    - SOX Section 802: Document integrity and correction procedures
    - Employment law: Auditable decision trail
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, insert, select_one, update
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..certificate import (
    SCHEMA_VERSION,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
)

__all__ = ["RevokeCertificateSpecs", "revoke_certificate"]


class RevokeCertificateSpecs(BaseModel):
    """Specs for certificate revocation phrase."""

    # inputs
    certificate_id: UUID
    revocation_reason: str
    revoked_by: UUID
    # outputs
    revocation_id: UUID | None = None
    supersedes_id: UUID | None = None
    revoked_at: datetime | None = None
    status: CertificateStatus | None = None


@canon_phrase(
    Operable.from_structure(RevokeCertificateSpecs),
    inputs={"certificate_id", "revocation_reason", "revoked_by"},
    outputs={
        "certificate_id",
        "revocation_id",
        "supersedes_id",
        "revoked_at",
        "status",
    },
)
async def revoke_certificate(
    options: RevokeCertificateSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Revoke a certificate by creating a superseding revocation record.

    Follows the Supersession Doctrine: the original certificate is never
    mutated (content-wise). Only its status transitions to SUPERSEDED.
    A new certificate record is created that links back to the original
    via ``supersedes_id`` and carries the revocation metadata.

    Args:
        options: Revocation options containing certificate_id,
            revocation_reason, and revoked_by (actor UUID).
        ctx: Request context (tenant, actor).
        conn: Optional existing DB connection.

    Returns:
        Dict with revocation_id (new certificate), supersedes_id
        (original), revoked_at timestamp, and resulting status.

    Raises:
        ValueError: If original certificate not found, tenant mismatch,
            or certificate is not in MINTED status.
    """
    # Fetch original certificate
    original_row = await select_one(
        "decision_certificates",
        where={"id": options.certificate_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not original_row:
        raise ValueError(f"Certificate {options.certificate_id} not found")

    if original_row["tenant_id"] != ctx.tenant_id:
        raise ValueError("Certificate tenant does not match request context")

    if original_row["status"] != CertificateStatus.MINTED.value:
        raise ValueError(
            f"Only MINTED certificates can be revoked. Current status: {original_row['status']}"
        )

    now = now_utc()

    # Build superseding certificate content with revocation metadata.
    # Inherits scope fields from the original; action_type and evidence
    # are carried forward for audit continuity.
    from ..certificate import ActionType

    action_enum = None
    if original_row.get("action_type"):
        try:
            action_enum = ActionType(original_row["action_type"])
        except ValueError:
            action_enum = ActionType.ADVANCE_CANDIDATE  # safe fallback

    content = DecisionCertificateContent(
        tenant_id=ctx.tenant_id,
        subject_id=original_row.get("subject_id"),
        actor_id=options.revoked_by,
        schema_version=SCHEMA_VERSION,
        action_type=action_enum,
        case_id=original_row.get("case_id"),
        policy_version=ctx.policy_version,
        jurisdiction=original_row.get("jurisdiction"),
        evidence_ids=[UUID(eid) for eid in (original_row.get("evidence_ids") or [])],
        status=CertificateStatus.MINTED,
        certificate_class=original_row["certificate_class"],
        defensibility_state=DefensibilityState.DEGRADED,
        supersedes_id=options.certificate_id,
        minted_at=now,
        validated_at=now,
        outcome="revoked",
        outcome_rationale=options.revocation_reason,
    )

    # Compute validation hash for the revocation record
    validation_hash = compute_hash(
        {
            "supersedes_id": str(options.certificate_id),
            "revocation_reason": options.revocation_reason,
            "revoked_by": str(options.revoked_by),
            "revoked_at": now.isoformat(),
        }
    )
    content.validation_hash = validation_hash

    # Create new superseding certificate
    new_cert = DecisionCertificate(content=content)
    new_cert.updated_at = now
    new_cert.updated_by = str(options.revoked_by)
    new_cert.content_hash = validation_hash

    # Build row data for insertion
    row_data = {
        "id": new_cert.id,
        "created_at": new_cert.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "schema_version": content.schema_version,
        "action_type": (content.action_type.value if content.action_type else None),
        "case_id": content.case_id,
        "policy_version": content.policy_version,
        "jurisdiction": content.jurisdiction,
        "gates_passed": [],
        "evidence_ids": [str(eid) for eid in content.evidence_ids],
        "attestations": [],
        "status": content.status.value,
        "certificate_class": content.certificate_class.value,
        "defensibility_state": content.defensibility_state.value,
        "minted_at": content.minted_at,
        "validated_at": content.validated_at,
        "validation_hash": validation_hash,
        "supersedes_id": content.supersedes_id,
        "outcome": content.outcome,
        "outcome_rationale": content.outcome_rationale,
        "content_hash": validation_hash,
        "updated_at": now,
        "updated_by": str(options.revoked_by),
        "version": 1,
    }

    await insert(
        "decision_certificates",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Transition original certificate status to SUPERSEDED.
    # This is the ONLY allowed mutation per the Supersession Doctrine.
    await update(
        "decision_certificates",
        {
            "status": CertificateStatus.SUPERSEDED.value,
            "updated_at": now,
            "updated_by": str(options.revoked_by),
        },
        where={"id": options.certificate_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "certificate_id": options.certificate_id,
        "revocation_id": new_cert.id,
        "supersedes_id": options.certificate_id,
        "revoked_at": now,
        "status": CertificateStatus.SUPERSEDED,
    }
