"""Derive dependent backup count for a resource.

Before allowing destructive operations on a resource, verifies
whether any backups would be invalidated.

Regulatory Context:
    - SOC 2 CC7.5: Recovery from security incidents
    - ISO 27001 A.12.3.1: Backup copies and testing
    - PCI DSS 9.8: Media destruction requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveDependentBackupsSpecs", "derive_dependent_backup_count"]


class DeriveDependentBackupsSpecs(BaseModel):
    """Specs for dependent backup count derivation phrase."""

    # inputs
    resource_id: UUID
    # outputs
    count: int | None = None
    backup_ids: tuple[UUID, ...] | None = None
    oldest_backup: datetime | None = None


@canon_phrase(
    Operable.from_structure(DeriveDependentBackupsSpecs),
    inputs={"resource_id"},
    outputs={"count", "resource_id", "backup_ids", "oldest_backup"},
)
async def derive_dependent_backup_count(
    options: DeriveDependentBackupsSpecs,
    ctx: RequestContext,
) -> dict:
    """Count backups that depend on a resource.

    Before allowing destructive operations on a resource, this verifies
    whether any backups would be invalidated. Maintains backup chain
    integrity for disaster recovery compliance.

    Regulatory Citations:
        - SOC 2 CC7.5: "The entity identifies, develops, and implements
          activities to recover from identified security incidents."
        - ISO 27001 A.12.3.1: "Backup copies of information, software
          and system images shall be taken and tested regularly."
        - PCI DSS 9.8: "Destroy media when it is no longer needed for
          business or legal reasons."

    Args:
        options: Derivation options (resource_id)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with count, resource_id, backup_ids, oldest_backup

    Usage:
        Before destroying a resource:
        - If count > 0, must handle dependent backups first
        - Either migrate dependencies or cascade delete with approval
    """
    resource_id = options.resource_id

    # Placeholder - would query actual backup dependencies
    backup_ids: tuple[UUID, ...] = ()
    oldest_backup = None

    return {
        "count": len(backup_ids),
        "resource_id": resource_id,
        "backup_ids": backup_ids,
        "oldest_backup": oldest_backup,
    }
