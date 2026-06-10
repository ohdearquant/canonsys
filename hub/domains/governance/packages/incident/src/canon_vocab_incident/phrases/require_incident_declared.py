"""Require that an incident has been formally declared.

Enforces incident response requirements by ensuring that an incident
has been formally declared before allowing dependent operations.

Regulatory: GDPR Art. 33, HIPAA 164.308(a)(6)(ii), SOC 2 CC7.2
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

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireIncidentDeclaredSpecs", "require_incident_declared"]


class RequireIncidentDeclaredSpecs(BaseModel):
    """Specs for require incident declared phrase."""

    # inputs
    incident_id: UUID
    # outputs
    satisfied: bool = False
    declared_at: datetime | None = None
    declared_by: UUID | None = None
    reason: str | None = None


require_incident_declared_operable = Operable.from_structure(RequireIncidentDeclaredSpecs)


@canon_phrase(
    require_incident_declared_operable,
    inputs={"incident_id"},
    outputs={"satisfied", "incident_id", "declared_at", "declared_by", "reason"},
)
async def require_incident_declared(
    options: RequireIncidentDeclaredSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that an incident has been formally declared.

    Raises RequirementNotMetError if incident not declared.

    Regulatory:
        - GDPR Art. 33 (Breach notification timing)
        - HIPAA 164.308(a)(6)(ii) (Response and reporting)
        - SOC 2 CC7.2 (Incident identification)

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with declaration status.

    Raises:
        RequirementNotMetError: If incident is not declared.
    """
    incident_id = options.incident_id

    # Query for declared incident (status != 'draft')
    row = await select_one(
        "incidents",
        {
            "tenant_id": ctx.tenant_id,
            "id": incident_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="incident_declared",
            reason=f"Incident {incident_id} not found",
        )

    # Check that incident is not in draft status
    status = row.get("status", "draft")
    if status == "draft":
        raise RequirementNotMetError(
            requirement="incident_declared",
            reason=f"Incident {incident_id} must be formally declared (current status: draft)",
            evidence_id=incident_id,
        )

    return {
        "satisfied": True,
        "incident_id": incident_id,
        "declared_at": row.get("declared_at"),
        "declared_by": row.get("declared_by"),
        "reason": "Incident formally declared",
    }


# Export auto-generated types from the Phrase object
RequireIncidentDeclaredOptions = require_incident_declared.options_type
RequireIncidentDeclaredResult = require_incident_declared.result_type
