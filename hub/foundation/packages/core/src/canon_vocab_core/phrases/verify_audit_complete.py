"""Verify audit completion phrase.

Checks that an audit has been completed for a resource.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import AuditStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyAuditCompleteSpecs", "verify_audit_complete"]


class VerifyAuditCompleteSpecs(BaseModel):
    """Specs for verify audit complete phrase.

    Regulatory:
        - SOX Section 404 (Internal control audit)
        - SOC 2 CC4.1 (Monitoring activities)
        - ISO 27001 A.18.2 (Security reviews)
    """

    # inputs
    resource_id: UUID
    audit_type: str
    # outputs
    verified: bool
    audit_id: UUID
    status: AuditStatus
    completed_at: datetime | None = None
    auditor_id: UUID | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyAuditCompleteSpecs),
    inputs={"resource_id", "audit_type"},
    outputs={
        "verified",
        "audit_id",
        "resource_id",
        "status",
        "completed_at",
        "auditor_id",
        "reason",
    },
)
async def verify_audit_complete(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify that an audit has been completed for a resource.

    Regulatory:
        - SOX Section 404 (Internal control audit)
        - SOC 2 CC4.1 (Monitoring activities)
        - ISO 27001 A.18.2 (Security reviews)

    Args:
        options: Verification options (resource_id, audit_type)
        ctx: Request context (tenant, actor)

    Returns:
        dict with verification status and audit details
    """
    resource_id = options.get("resource_id")
    audit_type = options.get("audit_type")

    query = """
        SELECT audit_id, status, completed_at, auditor_id
        FROM audits
        WHERE resource_id = $1 AND audit_type = $2 AND tenant_id = $3
        ORDER BY completed_at DESC NULLS LAST
        LIMIT 1
    """
    rows = await fetch(
        query,
        resource_id,
        audit_type,
        ctx.tenant_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Already filtered in query
    )

    if not rows:
        return {
            "verified": False,
            "audit_id": UUID("00000000-0000-0000-0000-000000000000"),
            "resource_id": resource_id,
            "status": AuditStatus.NOT_STARTED,
            "completed_at": None,
            "auditor_id": None,
            "reason": f"No {audit_type} audit found",
        }

    row = rows[0]
    status = AuditStatus(row["status"])

    return {
        "verified": status == AuditStatus.COMPLETE,
        "audit_id": row["audit_id"],
        "resource_id": resource_id,
        "status": status,
        "completed_at": row["completed_at"],
        "auditor_id": row["auditor_id"],
        "reason": (None if status == AuditStatus.COMPLETE else f"Audit status: {status.value}"),
    }
