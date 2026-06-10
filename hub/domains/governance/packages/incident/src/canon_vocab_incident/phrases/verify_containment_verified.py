"""Verify that incident containment has been verified.

Checks the containment verification status for an incident without
raising exceptions. Returns verification state for decision making.

Regulatory: GDPR Art. 33, HIPAA 164.308(a)(6), SOC 2 CC7.3
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ContainmentVerificationStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyContainmentVerifiedSpecs", "verify_containment_verified"]


class VerifyContainmentVerifiedSpecs(BaseModel):
    """Specs for verify containment verified phrase."""

    # inputs
    incident_id: UUID
    # outputs
    verified: bool = False
    status: ContainmentVerificationStatus | None = None
    verified_at: datetime | None = None
    verifier_id: UUID | None = None
    reason: str | None = None


verify_containment_verified_operable = Operable.from_structure(VerifyContainmentVerifiedSpecs)


@canon_phrase(
    verify_containment_verified_operable,
    inputs={"incident_id"},
    outputs={
        "verified",
        "incident_id",
        "status",
        "verified_at",
        "verifier_id",
        "reason",
    },
)
async def verify_containment_verified(
    options: VerifyContainmentVerifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that incident containment has been verified.

    Regulatory:
        - GDPR Art. 33 (Breach notification)
        - HIPAA 164.308(a)(6) (Security incident procedures)
        - SOC 2 CC7.3 (Incident response)

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with verification status.
    """
    incident_id = options.incident_id

    # Query for containment verification record
    row = await select_one(
        "incident_containment_verifications",
        {
            "tenant_id": ctx.tenant_id,
            "incident_id": incident_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "incident_id": incident_id,
            "status": ContainmentVerificationStatus.PENDING,
            "reason": "No containment verification found",
        }

    status = ContainmentVerificationStatus(row.get("status", "pending"))

    return {
        "verified": status == ContainmentVerificationStatus.VERIFIED,
        "incident_id": incident_id,
        "status": status,
        "verified_at": row.get("verified_at"),
        "verifier_id": row.get("verifier_id"),
        "reason": (
            None if status == ContainmentVerificationStatus.VERIFIED else f"Status: {status.value}"
        ),
    }


# Export auto-generated types from the Phrase object
VerifyContainmentVerifiedOptions = verify_containment_verified.options_type
VerifyContainmentVerifiedResult = verify_containment_verified.result_type
