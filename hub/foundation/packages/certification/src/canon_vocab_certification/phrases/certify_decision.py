"""Certify a decision by issuing a certificate.

Complete vertical slice:
- Creates certificate for any workflow type
- Binds facts, evidence, and attestations
- Returns certificate ID and hash

Regulatory: PRD-001 - All decisions must be certified
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..certificate import (
    SCHEMA_VERSION,
    CertificateClass,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
    GateEvaluation,
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CertifyDecisionSpecs", "certify_decision"]


class CertifyDecisionSpecs(BaseModel):
    """Specs for certify decision phrase."""

    # inputs
    workflow_type: str  # e.g., "termination", "pip", "promotion"
    facts: dict[str, Any]  # Structured facts for the decision
    evidence_refs: list[UUID]  # CEP IDs supporting the decision
    gates_passed: list[str] | None = None  # Gate IDs that passed
    attestations: list[dict[str, Any]] | None = None  # Attestation records
    subject_id: UUID | None = None  # Subject of the decision
    case_id: UUID | None = None  # Related case ID
    jurisdiction: str | None = None  # Jurisdiction code
    outcome: str | None = None  # Decision outcome
    outcome_rationale: str | None = None  # Brief rationale
    # outputs
    certificate_id: UUID | None = None
    certificate_hash: str | None = None
    certified_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


def _build_gate_evaluations(gate_ids: list[str] | None, now: datetime) -> list[GateEvaluation]:
    """Build gate evaluation records."""
    if not gate_ids:
        return []

    return [
        GateEvaluation(
            gate_id=gate_id,
            evaluated_at=now,
            passed=True,
        )
        for gate_id in gate_ids
    ]


@canon_phrase(
    Operable.from_structure(CertifyDecisionSpecs),
    inputs={
        "workflow_type",
        "facts",
        "evidence_refs",
        "gates_passed",
        "attestations",
        "subject_id",
        "case_id",
        "jurisdiction",
        "outcome",
        "outcome_rationale",
    },
    outputs={"certificate_id", "certificate_hash", "certified_at", "workflow_type"},
)
async def certify_decision(
    options: CertifyDecisionSpecs,
    ctx: RequestContext,
) -> dict:
    """Certify a decision by issuing a decision certificate.

    Generic certificate issuance for any workflow type. Creates
    a minted certificate binding facts, evidence, and attestations.

    Args:
        options: Options containing workflow_type, facts, evidence_refs.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with certificate_id, certificate_hash, certified_at.

    Raises:
        ValueError: If evidence_refs is empty (decisions require evidence).
    """
    workflow_type = options.workflow_type
    facts = options.facts
    evidence_refs = options.evidence_refs
    now = now_utc()

    if not evidence_refs:
        raise ValueError("Decision certification requires at least one evidence reference")

    # Build gate evaluations
    gates_passed = _build_gate_evaluations(options.gates_passed, now)

    # Build content
    from ..certificate import ActionType, AttestationRecord

    # Map workflow type to action type (best effort)
    try:
        action_type = ActionType(workflow_type)
    except ValueError:
        action_type = ActionType.ADVANCE_CANDIDATE  # Default fallback

    # Build attestation records
    attestations = []
    if options.attestations:
        for a in options.attestations:
            attestations.append(
                AttestationRecord(
                    signer_id=a["signer_id"],
                    signer_role=a["signer_role"],
                    signed_at=a.get("signed_at", now),
                    method=a.get("method", "system"),
                    acknowledgment_text=a.get("acknowledgment_text"),
                )
            )

    content = DecisionCertificateContent(
        tenant_id=ctx.tenant_id,
        subject_id=options.subject_id or ctx.subject_id,
        actor_id=ctx.actor_id,
        schema_version=SCHEMA_VERSION,
        action_type=action_type,
        case_id=options.case_id,
        policy_version=ctx.policy_version,
        jurisdiction=options.jurisdiction or (ctx.jurisdictions[0] if ctx.jurisdictions else None),
        gates_passed=gates_passed,
        evidence_ids=evidence_refs,
        attestations=attestations,
        status=CertificateStatus.MINTED,
        certificate_class=CertificateClass.CERTIFIED,
        defensibility_state=DefensibilityState.FULL,
        minted_at=now,
        validated_at=now,
        outcome=options.outcome,
        outcome_rationale=options.outcome_rationale,
    )

    # Create certificate
    cert = DecisionCertificate(content=content)
    cert.touch(by=ctx.actor_id)

    # Compute certificate hash
    cert_hash = compute_hash(
        {
            "id": str(cert.id),
            "workflow_type": workflow_type,
            "facts": facts,
            "evidence_refs": [str(ref) for ref in evidence_refs],
            "minted_at": now.isoformat(),
        }
    )

    # Build row data
    row_data = {
        "id": cert.id,
        "created_at": cert.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "actor_id": content.actor_id,
        "schema_version": content.schema_version,
        "action_type": (content.action_type.value if content.action_type else workflow_type),
        "case_id": content.case_id,
        "policy_version": content.policy_version,
        "jurisdiction": content.jurisdiction,
        "gates_passed": [g.model_dump() for g in content.gates_passed],
        "evidence_ids": [str(eid) for eid in content.evidence_ids],
        "attestations": [a.model_dump() for a in content.attestations],
        "status": content.status.value,
        "certificate_class": content.certificate_class.value,
        "defensibility_state": content.defensibility_state.value,
        "minted_at": content.minted_at,
        "validated_at": content.validated_at,
        "validation_hash": cert_hash,
        "outcome": content.outcome,
        "outcome_rationale": content.outcome_rationale,
        "content_hash": cert_hash,
        "updated_at": now,
        "updated_by": str(ctx.actor_id) if ctx.actor_id else None,
        "version": 1,
    }

    await insert(
        "decision_certificates",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "certificate_id": cert.id,
        "certificate_hash": cert_hash,
        "certified_at": now,
        "workflow_type": workflow_type,
    }
