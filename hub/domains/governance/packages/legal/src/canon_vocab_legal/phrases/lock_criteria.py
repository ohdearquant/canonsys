"""Lock evaluation criteria for workflow immutability.

Creates immutable record proving criteria were defined
BEFORE any selection/evaluation occurred.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..types import CriteriaLock

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["LockCriteriaSpecs", "lock_criteria"]


class LockCriteriaSpecs(BaseModel):
    """Specs for lock criteria phrase."""

    # inputs
    workflow_id: UUID
    workflow_type: str
    criteria: dict[str, Any]
    # outputs
    lock_id: UUID | None = None
    tenant_id: UUID | None = None
    criteria_hash: str | None = None
    locked_at: datetime | None = None
    locked_by: UUID | None = None


lock_criteria_operable = Operable.from_structure(LockCriteriaSpecs)


@canon_phrase(
    lock_criteria_operable,
    inputs={"workflow_id", "workflow_type", "criteria"},
    outputs={
        "lock_id",
        "tenant_id",
        "workflow_id",
        "workflow_type",
        "criteria",
        "criteria_hash",
        "locked_at",
        "locked_by",
    },
)
async def lock_criteria(
    options: LockCriteriaSpecs,
    ctx: RequestContext,
) -> dict:
    """Lock evaluation criteria for a workflow.

    Creates immutable record proving criteria were defined
    BEFORE any selection/evaluation occurred.

    Args:
        options: Lock options (workflow_id, workflow_type, criteria)
        ctx: Request context (tenant, actor)

    Returns:
        dict with lock details

    Raises:
        ValueError: If criteria empty.
    """
    workflow_id: UUID = options.workflow_id
    workflow_type: str = options.workflow_type
    criteria: dict[str, Any] = options.criteria

    if not criteria:
        raise ValueError("Criteria cannot be empty")

    now = now_utc()
    lock_id = uuid4()

    # Compute deterministic hash
    hash_data = {
        "workflow_id": str(workflow_id),
        "workflow_type": workflow_type,
        "criteria": criteria,
        "locked_at": now.isoformat(),
    }
    criteria_hash = compute_hash(hash_data)

    lock = CriteriaLock(
        id=lock_id,
        tenant_id=ctx.tenant_id,
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        criteria=criteria,
        criteria_hash=criteria_hash,
        locked_at=now,
        locked_by=ctx.actor_id,
    )

    # Persist (immutable - insert only, no updates)
    row_data = {
        "id": lock.id,
        "tenant_id": lock.tenant_id,
        "workflow_id": lock.workflow_id,
        "workflow_type": lock.workflow_type,
        "criteria": criteria,
        "criteria_hash": lock.criteria_hash,
        "locked_at": lock.locked_at,
        "locked_by": lock.locked_by,
    }

    await insert(
        "criteria_locks",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "lock_id": lock.id,
        "tenant_id": lock.tenant_id,
        "workflow_id": lock.workflow_id,
        "workflow_type": lock.workflow_type,
        "criteria": criteria,
        "criteria_hash": lock.criteria_hash,
        "locked_at": lock.locked_at,
        "locked_by": lock.locked_by,
    }


# Export auto-generated types from the Phrase object
LockCriteriaOptions = lock_criteria.options_type
LockCriteriaResult = lock_criteria.result_type
