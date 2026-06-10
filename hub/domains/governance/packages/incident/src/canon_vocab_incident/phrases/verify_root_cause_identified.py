"""Verify that root cause has been identified for an incident.

Checks the root cause analysis status without raising exceptions.
Returns verification state for decision making.

Regulatory: SOC 2 CC7.4, ISO 27001 A.16.1.6, NIST SP 800-61
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import RootCauseStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyRootCauseIdentifiedSpecs", "verify_root_cause_identified"]


class VerifyRootCauseIdentifiedSpecs(BaseModel):
    """Specs for verify root cause identified phrase."""

    # inputs
    incident_id: UUID
    # outputs
    verified: bool = False
    status: RootCauseStatus | None = None
    identified_at: datetime | None = None
    root_cause_id: UUID | None = None
    reason: str | None = None


verify_root_cause_identified_operable = Operable.from_structure(VerifyRootCauseIdentifiedSpecs)


@canon_phrase(
    verify_root_cause_identified_operable,
    inputs={"incident_id"},
    outputs={
        "verified",
        "incident_id",
        "status",
        "identified_at",
        "root_cause_id",
        "reason",
    },
)
async def verify_root_cause_identified(
    options: VerifyRootCauseIdentifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that root cause has been identified for an incident.

    Returns verified=True if root cause analysis is complete.

    Regulatory:
        - SOC 2 CC7.4 (Incident response)
        - ISO 27001 A.16.1.6 (Learning from incidents)
        - NIST SP 800-61 (Incident handling)

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with verification status.
    """
    incident_id = options.incident_id

    # Query for root cause analysis record
    row = await select_one(
        "incident_root_cause_analysis",
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
            "status": RootCauseStatus.UNKNOWN,
            "reason": "No root cause analysis found",
        }

    status = RootCauseStatus(row.get("status", "unknown"))

    if status == RootCauseStatus.IDENTIFIED:
        return {
            "verified": True,
            "incident_id": incident_id,
            "status": status,
            "identified_at": row.get("identified_at"),
            "root_cause_id": row.get("root_cause_id"),
        }

    return {
        "verified": False,
        "incident_id": incident_id,
        "status": status,
        "reason": f"Root cause analysis status: {status.value}",
    }


# Export auto-generated types from the Phrase object
VerifyRootCauseIdentifiedOptions = verify_root_cause_identified.options_type
VerifyRootCauseIdentifiedResult = verify_root_cause_identified.result_type
