"""Verify audit currency phrase.

Checks that an audit is within its age threshold.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyAuditCurrentSpecs", "verify_audit_current"]


class VerifyAuditCurrentSpecs(BaseModel):
    """Specs for verify audit current phrase.

    Regulatory:
        - NYC LL144 Section 20-870 (Bias audit within 1 year)
        - SOX Section 404 (Annual internal control audit)
        - SOC 2 CC4.1 (Periodic monitoring)
        - ISO 27001 A.18.2 (Security reviews)
    """

    # inputs
    resource_id: UUID
    audit_type: str
    max_age_days: int = 365
    # outputs
    verified: bool
    audit_id: UUID | None = None
    last_audit_at: datetime | None = None
    expires_at: datetime | None = None
    days_since_audit: int | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyAuditCurrentSpecs),
    inputs={"resource_id", "audit_type", "max_age_days"},
    outputs={
        "verified",
        "resource_id",
        "audit_type",
        "audit_id",
        "last_audit_at",
        "expires_at",
        "days_since_audit",
        "reason",
    },
)
async def verify_audit_current(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify that an audit is current (within age threshold).

    Generic audit freshness check for any compliance domain.
    Domain libraries compose this with specific audit types.

    Regulatory:
        - NYC LL144 Section 20-870 (Bias audit within 1 year)
        - SOX Section 404 (Annual internal control audit)
        - SOC 2 CC4.1 (Periodic monitoring)
        - ISO 27001 A.18.2 (Security reviews)

    Args:
        options: Verification options (resource_id, audit_type, max_age_days)
        ctx: Request context (tenant, actor)

    Returns:
        dict with currency status and timing details
    """
    resource_id = options.get("resource_id")
    audit_type = options.get("audit_type")
    max_age_days = options.get("max_age_days", 365)

    query = """
        SELECT audit_id, completed_at
        FROM audits
        WHERE resource_id = $1 AND audit_type = $2 AND status = 'complete' AND tenant_id = $3
        ORDER BY completed_at DESC
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
            "resource_id": resource_id,
            "audit_type": audit_type,
            "audit_id": None,
            "last_audit_at": None,
            "expires_at": None,
            "days_since_audit": None,
            "reason": f"No completed {audit_type} audit found",
        }

    row = rows[0]
    last_audit_at = row["completed_at"]
    now = datetime.now(UTC)
    age = now - last_audit_at
    days_since = age.days
    expires_at = last_audit_at + timedelta(days=max_age_days)

    if days_since > max_age_days:
        return {
            "verified": False,
            "resource_id": resource_id,
            "audit_type": audit_type,
            "audit_id": row["audit_id"],
            "last_audit_at": last_audit_at,
            "expires_at": expires_at,
            "days_since_audit": days_since,
            "reason": f"Audit expired ({days_since} days old, max {max_age_days})",
        }

    return {
        "verified": True,
        "resource_id": resource_id,
        "audit_type": audit_type,
        "audit_id": row["audit_id"],
        "last_audit_at": last_audit_at,
        "expires_at": expires_at,
        "days_since_audit": days_since,
        "reason": None,
    }
