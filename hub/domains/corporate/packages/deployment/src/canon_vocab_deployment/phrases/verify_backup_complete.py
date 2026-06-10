"""Verify backup completion for a resource.

Complete vertical slice:
- Queries backup_records table for completed backups
- Returns verification result with backup metadata
- Used as precondition before data operations requiring backup assurance

Regulatory: SOX Section 404, ISO 27001
- SOX 404: Internal controls over financial reporting including data integrity
- ISO 27001 A.12.3: Backup policy and verification requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyBackupCompleteSpecs", "verify_backup_complete"]


class VerifyBackupCompleteSpecs(BaseModel):
    """Specs for verify backup complete phrase."""

    # inputs
    resource_id: UUID
    resource_type: str | None = None
    min_backup_age: datetime | None = None
    # outputs
    verified: bool = False
    checked_at: datetime | None = None
    backup_id: UUID | None = None
    backup_timestamp: datetime | None = None
    backup_type: str | None = None
    storage_location: str | None = None
    content_hash: str | None = None
    reason: str | None = None


verify_backup_complete_operable = Operable.from_structure(VerifyBackupCompleteSpecs)


@canon_phrase(
    verify_backup_complete_operable,
    inputs={"resource_id", "resource_type", "min_backup_age"},
    outputs={
        "verified",
        "resource_id",
        "checked_at",
        "backup_id",
        "backup_timestamp",
        "backup_type",
        "storage_location",
        "content_hash",
        "reason",
    },
)
async def verify_backup_complete(
    options: VerifyBackupCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Check if a completed backup exists for the resource.

    Verifies that the resource has been backed up according to retention
    policy requirements. This is a precondition gate for operations that
    require backup assurance before proceeding.

    Regulatory Citations:
        - SOX Section 404: Requires internal controls ensuring data integrity
          and recoverability for financial reporting systems.
        - ISO 27001 A.12.3.1: Backup copies of information shall be taken
          and tested regularly in accordance with agreed backup policy.

    Args:
        options: Options containing resource_id and optional filters
        ctx: Request context (tenant, actor)

    Returns:
        Dict with:
        - verified=True if completed backup exists meeting criteria
        - verified=False if no qualifying backup found
        - Backup metadata for audit trail when verified
    """
    resource_id = options.resource_id
    resource_type = options.resource_type
    min_backup_age = options.min_backup_age
    now = now_utc()

    # Build query conditions
    conditions: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "resource_id": resource_id,
        "status": "completed",
    }
    if resource_type:
        conditions["resource_type"] = resource_type

    # Query for completed backup
    row = await select_one(
        "backup_records",
        conditions,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "resource_id": resource_id,
            "checked_at": now,
            "reason": "No completed backup found for resource (SOX 404, ISO 27001 A.12.3)",
        }

    # Check min_backup_age if specified
    backup_completed_at = row.get("completed_at")
    if min_backup_age and backup_completed_at and backup_completed_at < min_backup_age:
        return {
            "verified": False,
            "resource_id": resource_id,
            "checked_at": now,
            "backup_id": row["id"],
            "backup_timestamp": backup_completed_at,
            "reason": f"Backup too old: completed at {backup_completed_at}, required after {min_backup_age}",
        }

    # Backup verified
    return {
        "verified": True,
        "resource_id": resource_id,
        "checked_at": now,
        "backup_id": row["id"],
        "backup_timestamp": backup_completed_at,
        "backup_type": row.get("backup_type"),
        "storage_location": row.get("storage_location"),
        "content_hash": row.get("content_hash"),
    }


# Export auto-generated types from the Phrase object
VerifyBackupCompleteOptions = verify_backup_complete.options_type
VerifyBackupCompleteResult = verify_backup_complete.result_type
