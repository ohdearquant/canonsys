"""Emit decision certificates.

Complete vertical slice:
- Creates provisional certificate from decision context
- Binds evidence, gates, attestations
- Mints (finalizes) certificate when ready
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
    CertificateClass,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
    GateEvaluation,
    InputFingerprint,
    JurisdictionContext,
    ModelIdentity,
    ReviewBehavior,
)

__all__ = [
    "EmitCertificateSpecs",
    "MintCertificateSpecs",
    "emit_certificate",
    "mint_certificate",
]


class EmitCertificateSpecs(BaseModel):
    """Specs for certificate emission phrase."""

    # inputs
    action_type: str
    subject_id: UUID | None = None
    case_id: UUID | None = None
    jurisdiction: str | None = None
    evidence_ids: list[UUID] | None = None
    gates_passed: list[dict[str, Any]] | None = None
    model_identity: dict[str, Any] | None = None
    input_fingerprints: list[dict[str, Any]] | None = None
    review_behavior: dict[str, Any] | None = None
    certificate_class: CertificateClass = CertificateClass.CERTIFIED
    # outputs
    id: UUID | None = None
    tenant_id: UUID | None = None
    status: CertificateStatus | None = None
    created_at: datetime | None = None
    content_hash: str | None = None


class MintCertificateSpecs(BaseModel):
    """Specs for certificate minting phrase."""

    # inputs
    certificate_id: UUID
    attestations: list[dict[str, Any]] | None = None
    outcome: str | None = None
    outcome_rationale: str | None = None
    # outputs
    id: UUID | None = None
    status: CertificateStatus | None = None
    minted_at: datetime | None = None
    validation_hash: str | None = None


def _certificate_to_row(cert: DecisionCertificate) -> dict[str, Any]:
    """Convert DecisionCertificate to database row dict."""
    content = cert.content

    return {
        "id": cert.id,
        "created_at": cert.created_at,
        # Scope
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        # Schema
        "schema_version": content.schema_version,
        # Decision context
        "action_type": content.action_type.value if content.action_type else None,
        "case_id": content.case_id,
        # Computational state (JSONB)
        "model_identity": (content.model_identity.model_dump() if content.model_identity else None),
        "input_fingerprints": [f.model_dump() for f in content.input_fingerprints],
        "policy_version": content.policy_version,
        "policy_adapter_hash": content.policy_adapter_hash,
        "tenant_policy_activation_hash": content.tenant_policy_activation_hash,
        # Jurisdiction
        "jurisdiction": content.jurisdiction,
        "jurisdiction_context": (
            content.jurisdiction_context.model_dump() if content.jurisdiction_context else None
        ),
        # Gates (JSONB array)
        "gates_passed": [g.model_dump() for g in content.gates_passed],
        # Review
        "review_behavior": (
            content.review_behavior.model_dump() if content.review_behavior else None
        ),
        # Evidence binding
        "evidence_ids": [str(eid) for eid in content.evidence_ids],
        # Attestations (JSONB array)
        "attestations": [a.model_dump() for a in content.attestations],
        # Certification
        "status": content.status.value,
        "certificate_class": content.certificate_class.value,
        "defensibility_state": content.defensibility_state.value,
        "minted_at": content.minted_at,
        # Validation
        "validated_at": content.validated_at,
        "validation_hash": content.validation_hash,
        # Supersession
        "supersedes_id": content.supersedes_id,
        # Outcome
        "outcome": content.outcome,
        "outcome_rationale": content.outcome_rationale,
        "retention_policy_ref": content.retention_policy_ref,
        # Audit fields (on Entity, not content)
        "updated_at": cert.updated_at,
        "updated_by": cert.updated_by,
        "version": cert.version,
        "content_hash": cert.content_hash,
        "integrity_hash": cert.integrity_hash,
    }


def _row_to_certificate(row: dict[str, Any]) -> DecisionCertificate:
    """Convert database row to DecisionCertificate."""
    from ..certificate import ActionType

    # Parse enums
    action_type = ActionType(row["action_type"]) if row.get("action_type") else None
    status = CertificateStatus(row["status"])
    cert_class = CertificateClass(row["certificate_class"])
    defensibility = DefensibilityState(row["defensibility_state"])

    # Parse embedded models
    model_id = ModelIdentity(**row["model_identity"]) if row.get("model_identity") else None
    fingerprints = [InputFingerprint(**f) for f in (row.get("input_fingerprints") or [])]
    gates = [GateEvaluation(**g) for g in (row.get("gates_passed") or [])]
    attests = [AttestationRecord(**a) for a in (row.get("attestations") or [])]
    review = ReviewBehavior(**row["review_behavior"]) if row.get("review_behavior") else None
    jurisdiction_ctx = (
        JurisdictionContext(**row["jurisdiction_context"])
        if row.get("jurisdiction_context")
        else None
    )

    content = DecisionCertificateContent(
        tenant_id=row["tenant_id"],
        subject_id=row.get("subject_id"),
        actor_id=row.get("actor_id"),
        schema_version=row.get("schema_version", SCHEMA_VERSION),
        action_type=action_type,
        case_id=row.get("case_id"),
        model_identity=model_id,
        input_fingerprints=fingerprints,
        policy_version=row.get("policy_version"),
        policy_adapter_hash=row.get("policy_adapter_hash"),
        tenant_policy_activation_hash=row.get("tenant_policy_activation_hash"),
        jurisdiction=row.get("jurisdiction"),
        jurisdiction_context=jurisdiction_ctx,
        gates_passed=gates,
        review_behavior=review,
        evidence_ids=[UUID(eid) for eid in (row.get("evidence_ids") or [])],
        attestations=attests,
        status=status,
        certificate_class=cert_class,
        defensibility_state=defensibility,
        minted_at=row.get("minted_at"),
        validated_at=row.get("validated_at"),
        validation_hash=row.get("validation_hash"),
        supersedes_id=row.get("supersedes_id"),
        outcome=row.get("outcome"),
        outcome_rationale=row.get("outcome_rationale"),
        retention_policy_ref=row.get("retention_policy_ref"),
    )

    return DecisionCertificate(
        id=row["id"],
        created_at=row["created_at"],
        content=content,
        # Audit fields live on Entity, not content
        updated_at=row.get("updated_at"),
        updated_by=row.get("updated_by"),
        version=row.get("version", 1),
        content_hash=row.get("content_hash"),
        integrity_hash=row.get("integrity_hash"),
    )


@canon_phrase(
    Operable.from_structure(EmitCertificateSpecs),
    inputs={
        "action_type",
        "subject_id",
        "case_id",
        "jurisdiction",
        "evidence_ids",
        "gates_passed",
        "model_identity",
        "input_fingerprints",
        "review_behavior",
        "certificate_class",
    },
    outputs={
        "id",
        "tenant_id",
        "action_type",
        "subject_id",
        "case_id",
        "status",
        "created_at",
        "content_hash",
    },
)
async def emit_certificate(
    options: EmitCertificateSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Emit a provisional decision certificate.

    Creates certificate in PROVISIONAL status. Call mint_certificate()
    to finalize after all gates pass.

    Args:
        options: Emit options containing action_type, subject, case, evidence, etc.
        ctx: Request context (tenant, actor)
        conn: Optional existing connection

    Returns:
        Dict with created certificate fields
    """
    from ..certificate import ActionType

    # Parse action type
    try:
        action_enum = ActionType(options.action_type)
    except ValueError:
        action_enum = ActionType.ADVANCE_CANDIDATE  # Default fallback

    # Build gate evaluations
    gate_evals = []
    if options.gates_passed:
        for g in options.gates_passed:
            gate_evals.append(
                GateEvaluation(
                    gate_id=g["gate_id"],
                    evaluated_at=g.get("evaluated_at", now_utc()),
                    passed=g.get("passed", True),
                    context_hash=g.get("context_hash"),
                )
            )

    # Build input fingerprints
    fingerprints = []
    if options.input_fingerprints:
        for f in options.input_fingerprints:
            fingerprints.append(
                InputFingerprint(
                    input_id=f["input_id"],
                    content_hash=f["content_hash"],
                    schema_version=f.get("schema_version", "1.0"),
                )
            )

    # Build model identity
    model_id = None
    if options.model_identity:
        model_id = ModelIdentity(**options.model_identity)

    # Build review behavior
    review = None
    if options.review_behavior:
        review = ReviewBehavior(**options.review_behavior)

    # Build jurisdiction context if jurisdiction provided
    jurisdiction_ctx = None
    if options.jurisdiction:
        jurisdiction_ctx = JurisdictionContext(
            primary_jurisdiction=options.jurisdiction,
            secondary_jurisdictions=(list(ctx.jurisdictions) if ctx.jurisdictions else []),
        )

    content = DecisionCertificateContent(
        tenant_id=ctx.tenant_id,
        subject_id=options.subject_id or ctx.subject_id,
        actor_id=ctx.actor_id,
        schema_version=SCHEMA_VERSION,
        action_type=action_enum,
        case_id=options.case_id,
        model_identity=model_id,
        input_fingerprints=fingerprints,
        policy_version=ctx.policy_version,
        jurisdiction=options.jurisdiction or (ctx.jurisdictions[0] if ctx.jurisdictions else None),
        jurisdiction_context=jurisdiction_ctx,
        gates_passed=gate_evals,
        review_behavior=review,
        evidence_ids=options.evidence_ids or [],
        status=CertificateStatus.PROVISIONAL,
        certificate_class=options.certificate_class,
        defensibility_state=DefensibilityState.PROVISIONAL,
    )

    cert = DecisionCertificate(content=content)
    # Compute content hash via Entity lifecycle
    cert.touch(by=ctx.actor_id)
    row_data = _certificate_to_row(cert)

    result = await insert(
        "decision_certificates",
        row_data,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not result:
        raise RuntimeError("Certificate insert returned no result")

    # Return the created certificate
    cert.content_hash = result.get("content_hash")

    return {
        "id": cert.id,
        "tenant_id": ctx.tenant_id,
        "action_type": options.action_type,
        "subject_id": options.subject_id or ctx.subject_id,
        "case_id": options.case_id,
        "status": CertificateStatus.PROVISIONAL,
        "created_at": cert.created_at,
        "content_hash": cert.content_hash,
    }


@canon_phrase(
    Operable.from_structure(MintCertificateSpecs),
    inputs={"certificate_id", "attestations", "outcome", "outcome_rationale"},
    outputs={"id", "status", "minted_at", "validation_hash"},
)
async def mint_certificate(
    options: MintCertificateSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Mint (finalize) a provisional certificate.

    Transitions certificate from PROVISIONAL -> GATED -> MINTED.
    After minting, certificate is immutable (temporal cliff).

    Args:
        options: Mint options containing certificate_id, attestations, outcome
        ctx: Request context
        conn: Optional existing connection

    Returns:
        Dict with minted certificate fields

    Raises:
        ValueError: If certificate not in mintable state
    """
    # Fetch certificate
    row = await select_one(
        "decision_certificates",
        where={"id": options.certificate_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise ValueError(f"Certificate {options.certificate_id} not found")

    if row["status"] not in ("provisional", "gated"):
        raise ValueError(f"Certificate in status '{row['status']}' cannot be minted")

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

    # Compute validation hash
    validation_data = {
        "certificate_id": str(options.certificate_id),
        "gates_passed": row["gates_passed"],
        "evidence_ids": row["evidence_ids"],
        "attestations": [a.model_dump() for a in attest_records],
    }
    validation_hash = compute_hash(validation_data)

    # Update to minted
    now = now_utc()
    update_data = {
        "status": CertificateStatus.MINTED.value,
        "defensibility_state": DefensibilityState.FULL.value,
        "minted_at": now,
        "validated_at": now,
        "validation_hash": validation_hash,
        "attestations": [a.model_dump() for a in attest_records],
        "outcome": options.outcome,
        "outcome_rationale": options.outcome_rationale,
        "updated_at": now,
        "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
    }

    result = await update(
        "decision_certificates",
        update_data,
        where={"id": options.certificate_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not result:
        raise RuntimeError("Certificate update returned no result")

    return {
        "id": options.certificate_id,
        "status": CertificateStatus.MINTED,
        "minted_at": now,
        "validation_hash": validation_hash,
    }
