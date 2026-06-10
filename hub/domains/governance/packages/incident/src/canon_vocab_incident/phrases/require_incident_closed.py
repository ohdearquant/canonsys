"""Require that an incident has been resolved and closed.

Terminal gate: ensures the full incident lifecycle is complete before
allowing dependent operations such as post-incident reporting,
policy updates, or closure of related compliance workflows.

Regulatory: GDPR Art. 33(5), HIPAA 164.308(a)(6), SOC 2 CC7.4, NIST SP 800-61
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

from ..types import IncidentStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireIncidentClosedSpecs", "require_incident_closed"]


class RequireIncidentClosedSpecs(BaseModel):
    """Specs for require incident closed phrase."""

    # inputs
    incident_id: UUID
    # outputs
    satisfied: bool = False
    status: IncidentStatus | None = None
    closed_at: datetime | None = None
    closed_by: UUID | None = None
    reason: str | None = None


require_incident_closed_operable = Operable.from_structure(RequireIncidentClosedSpecs)


@canon_phrase(
    require_incident_closed_operable,
    inputs={"incident_id"},
    outputs={
        "satisfied",
        "incident_id",
        "status",
        "closed_at",
        "closed_by",
        "reason",
    },
)
async def require_incident_closed(
    options: RequireIncidentClosedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that an incident has been resolved and formally closed.

    Terminal gate for incident response workflows. Ensures the full
    incident lifecycle (declaration, containment, root cause, resolution,
    closure) is complete before allowing dependent operations.

    Regulatory:
        - GDPR Art. 33(5): Documentation of breach facts, effects, and
          remedial action (requires closure for complete record)
        - HIPAA 164.308(a)(6)(ii): Response and reporting procedures
        - SOC 2 CC7.4: Recovery and resumption of normal operations
        - NIST SP 800-61 Section 3.4: Post-incident activity
        - ISO 27001 A.16.1.6: Learning from information security incidents

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with closure verification status.

    Raises:
        RequirementNotMetError: If incident is not closed.
    """
    incident_id = options.incident_id

    # Query for the incident record
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
            requirement="incident_closed",
            reason=f"Incident {incident_id} not found",
        )

    status_value = row.get("status", "draft")

    # Only "closed" status satisfies this terminal gate
    if status_value != IncidentStatus.CLOSED:
        raise RequirementNotMetError(
            requirement="incident_closed",
            reason=(f"Incident {incident_id} is not closed (current status: {status_value})"),
            evidence_id=incident_id,
        )

    return {
        "satisfied": True,
        "incident_id": incident_id,
        "status": IncidentStatus.CLOSED,
        "closed_at": row.get("closed_at"),
        "closed_by": row.get("closed_by"),
        "reason": "Incident formally closed",
    }


# Export auto-generated types from the Phrase object
RequireIncidentClosedOptions = require_incident_closed.options_type
RequireIncidentClosedResult = require_incident_closed.result_type
