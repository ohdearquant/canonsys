"""Require backup verification before destructive operations.

Complete vertical slice:
- Validates most recent backup for a resource is verified
- Checks backup exists and has verified status
- Raises RequirementNotMetError if no verified backup found

Regulatory: SOC 2 CC7.1 - Detection of system changes
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireBackupVerifiedSpecs",
    "RequirementNotMetError",
    "require_backup_verified",
]


class RequireBackupVerifiedSpecs(BaseModel):
    """Specs for require backup verified phrase."""

    # inputs
    resource_id: UUID
    max_age_hours: int = 24
    # outputs
    satisfied: bool = False
    backup_id: UUID | None = None
    backup_age_hours: int | None = None
    verified_at: str | None = None


@canon_phrase(
    Operable.from_structure(RequireBackupVerifiedSpecs),
    inputs={"resource_id", "max_age_hours"},
    outputs={
        "satisfied",
        "resource_id",
        "backup_id",
        "backup_age_hours",
        "max_age_hours",
        "verified_at",
    },
)
async def require_backup_verified(
    options: RequireBackupVerifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a verified backup exists before destructive operations.

    Gate pattern that enforces backup verification. Queries the backups
    table for a recent verified backup of the specified resource.

    Args:
        options: Options containing resource_id and max_age_hours.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if a verified backup exists.

    Raises:
        RequirementNotMetError: If no verified backup found or backup too old.

    Regulatory citations:
        - SOC 2 CC7.1: Infrastructure change detection and recovery
        - ISO 27001 A.12.3.1: Information backup procedures
        - NIST SP 800-34: Contingency planning - backup verification
        - SOC 2 CC9.1: Risk mitigation through backup verification
    """
    resource_id = options.resource_id
    max_age_hours = options.max_age_hours

    # Query most recent verified backup for this resource
    row = await select_one(
        "backups",
        where={
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

    # Check backup age
    from kron.utils import now_utc

    verified_at = row.get("verified_at")
    if verified_at is None:
        raise RequirementNotMetError(
            requirement="backup_verified",
            reason=f"Backup for resource {resource_id} has no verification timestamp",
        )

    now = now_utc()
    age_seconds = (now - verified_at).total_seconds()
    age_hours = int(age_seconds / 3600)

    if age_hours > max_age_hours:
        raise RequirementNotMetError(
            requirement="backup_verified",
            reason=(
                f"Backup for resource {resource_id} is {age_hours}h old "
                f"(max allowed: {max_age_hours}h)"
            ),
        )

    verified_at_str = (
        verified_at.isoformat() if hasattr(verified_at, "isoformat") else str(verified_at)
    )

    return {
        "satisfied": True,
        "resource_id": resource_id,
        "backup_id": row.get("id"),
        "backup_age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "verified_at": verified_at_str,
    }
