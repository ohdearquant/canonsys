"""Require containment verification before proceeding.

Enforces incident response requirements by ensuring that a security
incident or data breach has been contained before allowing certain
recovery or communication operations.

Regulatory: GDPR Article 33, HIPAA 164.308(a)(6), SOC 2 CC7.3
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ContainmentStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireContainmentVerifiedSpecs", "require_containment_verified"]


class RequireContainmentVerifiedSpecs(BaseModel):
    """Specs for require containment verified phrase."""

    # inputs
    incident_id: UUID
    # outputs
    satisfied: bool = False
    status: ContainmentStatus | None = None
    contained_at: datetime | None = None
    verified_by: UUID | None = None
    reason: str | None = None


require_containment_verified_operable = Operable.from_structure(RequireContainmentVerifiedSpecs)


@canon_phrase(
    require_containment_verified_operable,
    inputs={"incident_id"},
    outputs={
        "satisfied",
        "incident_id",
        "status",
        "contained_at",
        "verified_by",
        "reason",
    },
)
async def require_containment_verified(
    options: RequireContainmentVerifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that incident containment has been verified before proceeding.

    Checks that a security incident has been contained and verified.
    This is a hard gate for incident response workflows - recovery
    and notification operations cannot proceed until containment is
    confirmed.

    Regulatory:
        - GDPR Article 33: Notification of personal data breach
          (72-hour notification window starts after containment)
        - HIPAA 164.308(a)(6): Security incident procedures
        - SOC 2 CC7.3: Incident containment and recovery
        - NIST SP 800-61: Computer Security Incident Handling

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with verification status.

    Raises:
        RequirementNotMetError: If containment is not verified.
    """
    incident_id = options.incident_id

    # Query for incident containment record
    row = await select_one(
        "incident_containments",
        {
            "tenant_id": ctx.tenant_id,
            "incident_id": incident_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # No containment record - requirement not met
        raise RequirementNotMetError(
            requirement="containment_verified",
            reason=f"No containment record found for incident {incident_id}",
        )

    status = ContainmentStatus(row.get("status", "unknown"))
    contained_at = row.get("contained_at")
    verified_by = row.get("verified_by")
    record_id = row.get("id")

    # Check containment status
    if status == ContainmentStatus.NOT_CONTAINED:
        raise RequirementNotMetError(
            requirement="containment_verified",
            reason="Incident has not been contained",
            evidence_id=record_id,
        )

    if status == ContainmentStatus.UNKNOWN:
        # Fail-closed: unknown status treated as not contained
        raise RequirementNotMetError(
            requirement="containment_verified",
            reason="Containment status unknown - cannot proceed until verified",
            evidence_id=record_id,
        )

    if status == ContainmentStatus.PARTIAL:
        # Partial containment - may be acceptable for some operations
        # but for strict compliance, require full containment
        raise RequirementNotMetError(
            requirement="containment_verified",
            reason="Incident only partially contained - full containment required",
            evidence_id=record_id,
        )

    # Full containment verified
    return {
        "satisfied": True,
        "incident_id": incident_id,
        "status": status,
        "contained_at": contained_at,
        "verified_by": verified_by,
        "reason": "Containment verified",
    }


# Export auto-generated types from the Phrase object
RequireContainmentVerifiedOptions = require_containment_verified.options_type
RequireContainmentVerifiedResult = require_containment_verified.result_type
