"""Require backup verification before proceeding.

Enforces disaster recovery (DR) requirements by ensuring that
backup verification has been completed for a resource before
allowing sensitive operations.

Regulatory: SOX Section 404, NIST SP 800-53 CP-9
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
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireBackupVerifiedSpecs", "require_backup_verified"]


class RequireBackupVerifiedSpecs(BaseModel):
    """Specs for require backup verified phrase."""

    # inputs
    resource_id: UUID
    # outputs
    satisfied: bool = False
    backup_id: UUID | None = None
    verified_at: datetime | None = None
    reason: str | None = None


require_backup_verified_operable = Operable.from_structure(RequireBackupVerifiedSpecs)


@canon_phrase(
    require_backup_verified_operable,
    inputs={"resource_id"},
    outputs={"satisfied", "backup_id", "verified_at", "reason"},
)
async def require_backup_verified(
    options: RequireBackupVerifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that backup has been verified before proceeding.

    Checks that a verified backup exists for the specified resource.
    This is a hard gate - if backup is not verified, the operation
    cannot proceed.

    Regulatory:
        - SOX Section 404: Internal controls over financial reporting
        - NIST SP 800-53 CP-9: System backup requirements
        - ISO 27001 A.12.3: Information backup

    Args:
        options: Options containing resource_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with verification status and backup details.

    Raises:
        RequirementNotMetError: If no verified backup exists for the resource.
    """
    resource_id = options.resource_id
    now = now_utc()

    # Query for verified backup record
    row = await select_one(
        "backup_verifications",
        {
            "tenant_id": ctx.tenant_id,
            "resource_id": resource_id,
            "status": "verified",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="backup_verified",
            reason=f"No verified backup found for resource {resource_id}",
        )

    # Check if backup verification has expired
    verified_at = row.get("verified_at")
    expires_at = row.get("expires_at")

    if expires_at and expires_at < now:
        raise RequirementNotMetError(
            requirement="backup_verified",
            reason=f"Backup verification expired at {expires_at.isoformat()}",
            evidence_id=row["id"],
        )

    return {
        "satisfied": True,
        "backup_id": row["id"],
        "verified_at": verified_at,
        "reason": "Backup verification confirmed",
    }


# Export auto-generated types from the Phrase object
RequireBackupVerifiedOptions = require_backup_verified.options_type
RequireBackupVerifiedResult = require_backup_verified.result_type
