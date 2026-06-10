"""Supersede decision certificates for corrections.

Complete vertical slice:
- Creates new certificate that supersedes existing MINTED certificate
- Links supersession (new.supersedes_id -> original.id)
- Original certificate transitions to SUPERSEDED status
- Maintains immutability: original never mutated, only status field updated
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
    AttestationRecord,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
)

__all__ = ["SupersedeCertificateSpecs", "supersede_certificate"]


class SupersedeCertificateSpecs(BaseModel):
    """Specs for certificate supersession phrase."""

    # inputs
    original_id: UUID
    action_type: str | None = None
    evidence_ids: list[UUID] | None = None
    attestations: list[dict[str, Any]] | None = None
    reason: str | None = None
    outcome: str | None = None
    outcome_rationale: str | None = None
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    supersedes_id: UUID | None = None
    status: CertificateStatus | None = None
    minted_at: datetime | None = None
    validation_hash: str | None = None


def _certificate_to_row(cert: DecisionCertificate) -> dict[str, Any]:
    """Convert DecisionCertificate to database row dict."""
    content = cert.content

    return {
        "id": cert.id,
        "created_at": cert.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "schema_version": content.schema_version,
        "action_type": content.action_type.value if content.action_type else None,
        "case_id": content.case_id,
        "model_identity": (content.model_identity.model_dump() if content.model_identity else None),
        "input_fingerprints": [f.model_dump() for f in content.input_fingerprints],
        "policy_version": content.policy_version,
        "policy_adapter_hash": content.policy_adapter_hash,
        "tenant_policy_activation_hash": content.tenant_policy_activation_hash,
        "jurisdiction": content.jurisdiction,
        "jurisdiction_context": (
            content.jurisdiction_context.model_dump() if content.jurisdiction_context else None
        ),
        "gates_passed": [g.model_dump() for g in content.gates_passed],
        "review_behavior": (
            content.review_behavior.model_dump() if content.review_behavior else None
        ),
        "evidence_ids": [str(eid) for eid in content.evidence_ids],
        "attestations": [a.model_dump() for a in content.attestations],
        "status": content.status.value,
        "certificate_class": content.certificate_class.value,
        "defensibility_state": content.defensibility_state.value,
        "minted_at": content.minted_at,
        "validated_at": content.validated_at,
        "validation_hash": content.validation_hash,
        "supersedes_id": content.supersedes_id,
        "outcome": content.outcome,
        "outcome_rationale": content.outcome_rationale,
        "retention_policy_ref": content.retention_policy_ref,
        "updated_at": cert.updated_at,
        "updated_by": cert.updated_by,
        "version": cert.version,
        "content_hash": cert.content_hash,
        "integrity_hash": cert.integrity_hash,
    }


@canon_phrase(
    Operable.from_structure(SupersedeCertificateSpecs),
    inputs={
        "original_id",
        "action_type",
        "evidence_ids",
        "attestations",
        "reason",
        "outcome",
        "outcome_rationale",
    },
    outputs={
        "id",
        "tenant_id",
        "original_id",
        "supersedes_id",
        "status",
        "minted_at",
        "validation_hash",
    },
)
async def supersede_certificate(
    options: SupersedeCertificateSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Create new certificate that supersedes an existing MINTED certificate.

    Immutability pattern: Original certificate is never mutated (content-wise).
    Only status field transitions to SUPERSEDED.
    New certificate has supersedes_id pointing back to original.

    Args:
        options: Supersession options containing original_id, new evidence, attestations
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with new superseding certificate fields

    Raises:
        ValueError: If original not found, not MINTED, or tenant mismatch
    """
    # Fetch original certificate
    original_row = await select_one(
        "decision_certificates",
        where={"id": options.original_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not original_row:
        raise ValueError(f"Certificate {options.original_id} not found")

    if original_row["tenant_id"] != ctx.tenant_id:
        raise ValueError("Certificate tenant doesn't match context")

    if original_row["status"] != CertificateStatus.MINTED.value:
        raise ValueError(
            f"Only MINTED certificates can be superseded. Current status: {original_row['status']}"
        )

    # Build new certificate content, inheriting from original where not overridden
    from ..certificate import ActionType

    # Parse action type
    if options.action_type:
        try:
            action_enum = ActionType(options.action_type)
        except ValueError:
            action_enum = ActionType(original_row["action_type"])
    else:
        action_enum = (
            ActionType(original_row["action_type"]) if original_row.get("action_type") else None
        )

    # Build attestation records
    attest_records = []
    if options.attestations:
        for a in options.attestations:
            attest_records.append(
                AttestationRecord(
                    signer_id=a["signer_id"],
                    signer_role=a["signer_role"],
                    signed_at=a.get("signed_at", now_utc()),
                    method=a.get("method", "system"),
                    acknowledgment_text=a.get("acknowledgment_text"),
                    ip_address=a.get("ip_address"),
                    user_agent=a.get("user_agent"),
                )
            )

    # Create new certificate content
    content = DecisionCertificateContent(
        tenant_id=ctx.tenant_id,
        subject_id=original_row.get("subject_id"),
        actor_id=ctx.actor_id,
        schema_version=SCHEMA_VERSION,
        action_type=action_enum,
        case_id=original_row.get("case_id"),
        policy_version=ctx.policy_version,
        jurisdiction=original_row.get("jurisdiction"),
        evidence_ids=(
            options.evidence_ids
            if options.evidence_ids is not None
            else [UUID(eid) for eid in (original_row.get("evidence_ids") or [])]
        ),
        attestations=attest_records,
        status=CertificateStatus.MINTED,  # New cert starts MINTED
        certificate_class=original_row["certificate_class"],
        defensibility_state=DefensibilityState.FULL,
        supersedes_id=options.original_id,  # Link back to original
        outcome=options.outcome,
        outcome_rationale=options.outcome_rationale or options.reason,
    )

    # Compute validation hash
    now = now_utc()

    validation_data = {
        "supersedes_id": str(options.original_id),
        "evidence_ids": [str(eid) for eid in content.evidence_ids],
        "attestations": [a.model_dump() for a in attest_records],
        "reason": options.reason,
    }
    validation_hash = compute_hash(validation_data)

    content.minted_at = now
    content.validated_at = now
    content.validation_hash = validation_hash

    # Create new certificate
    new_cert = DecisionCertificate(content=content)
    new_cert.updated_at = now
    new_cert.updated_by = str(ctx.actor_id) if ctx.actor_id else None

    # Insert new certificate
    new_row_data = _certificate_to_row(new_cert)
    result = await insert(
        "decision_certificates",
        new_row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not result:
        raise RuntimeError("Certificate insert returned no result")

    # Update original certificate status to SUPERSEDED
    # Note: This is the ONLY allowed mutation - status transition
    await update(
        "decision_certificates",
        {
            "status": CertificateStatus.SUPERSEDED.value,
            "updated_at": now,
            "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
        },
        where={"id": options.original_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "id": new_cert.id,
        "tenant_id": ctx.tenant_id,
        "original_id": options.original_id,
        "supersedes_id": options.original_id,
        "status": CertificateStatus.MINTED,
        "minted_at": now,
        "validation_hash": validation_hash,
    }
