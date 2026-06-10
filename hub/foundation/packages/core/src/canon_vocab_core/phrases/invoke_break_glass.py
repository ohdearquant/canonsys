"""Invoke break-glass phrase.

Emergency action invocation with degraded defensibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..types import BreakGlassCertificate, BreakGlassReason

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["InvokeBreakGlassSpecs", "invoke_break_glass"]


class InvokeBreakGlassSpecs(BaseModel):
    """Specs for invoke break-glass phrase.

    DEGRADED DEFENSIBILITY: Harder to defend in litigation.
    NON-EXPORTABLE: Cannot leave organization without Legal sign-off.
    """

    # inputs
    action: str
    reason_code: BreakGlassReason
    attestation: str
    subject_id: UUID | None = None
    case_id: UUID | None = None
    # outputs
    certificate_id: UUID
    issued_at: datetime
    defensibility_state: str
    notified_parties: tuple[str, ...]


@canon_phrase(
    Operable.from_structure(InvokeBreakGlassSpecs),
    inputs={"action", "reason_code", "attestation", "subject_id", "case_id"},
    outputs={"certificate_id", "issued_at", "defensibility_state", "notified_parties"},
)
async def invoke_break_glass(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Invoke break-glass for an emergency action.

    Creates a BreakGlassCertificate with DEGRADED defensibility.
    Triggers auto-notification to Legal, ER, and Audit.

    Args:
        options: Break-glass options (action, reason_code, attestation, subject_id, case_id)
        ctx: Request context (tenant, actor)

    Returns:
        dict with certificate details

    Raises:
        ValueError: If attestation is empty or too short, or actor missing.
    """
    action: str = options["action"]
    reason_code: BreakGlassReason = options["reason_code"]
    attestation: str = options.get("attestation", "")
    subject_id: UUID | None = options.get("subject_id")
    case_id: UUID | None = options.get("case_id")

    # Validate attestation - must be substantive, not empty
    if not attestation or len(attestation.strip()) < 50:
        raise ValueError(
            "Break-glass attestation must be substantive (at least 50 characters). "
            "This is a typed justification, not a checkbox."
        )

    # Resolve subject_id - prefer explicit, fallback to context
    resolved_subject_id = subject_id or ctx.subject_id
    if resolved_subject_id is None:
        raise ValueError("Break-glass requires a subject_id")

    # Require actor_id for accountability
    if ctx.actor_id is None:
        raise ValueError("Break-glass requires an identified actor")

    # Require tenant_id
    if ctx.tenant_id is None:
        raise ValueError("Break-glass requires a tenant context")

    # Create certificate
    cert = BreakGlassCertificate(
        certificate_id=uuid4(),
        action=action,
        subject_id=resolved_subject_id,
        actor_id=ctx.actor_id,
        tenant_id=ctx.tenant_id,
        reason_code=reason_code,
        attestation=attestation.strip(),
        case_id=case_id,
    )

    # Persist to database
    row_data = {
        "id": cert.certificate_id,
        "created_at": cert.issued_at,
        "tenant_id": cert.tenant_id,
        "subject_id": cert.subject_id,
        "actor_id": cert.actor_id,
        "certificate_type": cert.certificate_type,
        "action": cert.action,
        "reason_code": cert.reason_code.value,
        "attestation": cert.attestation,
        "case_id": cert.case_id,
        "review_required_by": cert.review_required_by,
        "defensibility_state": cert.defensibility_state,
        "exportable": cert.exportable,
        "notified_parties": list(cert.notified_parties),
        "content_hash": compute_hash(cert.to_dict()),
    }

    await insert(
        "break_glass_certificates",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Queue notifications to Legal, ER, Audit
    await _queue_break_glass_notifications(cert, ctx)

    return {
        "certificate_id": cert.certificate_id,
        "issued_at": cert.issued_at,
        "defensibility_state": cert.defensibility_state,
        "notified_parties": cert.notified_parties,
    }


async def _queue_break_glass_notifications(
    cert: BreakGlassCertificate,
    ctx: RequestContext,
) -> None:
    """Queue notifications for break-glass invocation.

    Auto-notifies Legal, ER, and Audit per TDS-016.
    """
    notification_data = {
        "certificate_id": str(cert.certificate_id),
        "tenant_id": str(cert.tenant_id),
        "action": cert.action,
        "reason_code": cert.reason_code.value,
        "actor_id": str(cert.actor_id),
        "issued_at": cert.issued_at.isoformat(),
    }

    for party in cert.notified_parties:
        await insert(
            "notification_queue",
            {
                "id": uuid4(),
                "created_at": now_utc(),
                "tenant_id": cert.tenant_id,
                "notification_type": "break_glass_invoked",
                "recipient_group": party,
                "payload": notification_data,
                "status": "pending",
            },
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )
