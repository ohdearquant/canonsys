"""Require workflow run completed successfully before proceeding.

Complete vertical slice:
- Validates workflow run exists and has completed status
- Raises WorkflowNotFoundError if run does not exist
- Raises WorkflowNotCompleteError if run is not in completed state

Regulatory: NYC LL144 - AEDT results require completed workflow provenance
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import WorkflowNotCompleteError, WorkflowNotFoundError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireWorkflowCompleteSpecs",
    "WorkflowNotCompleteError",
    "WorkflowNotFoundError",
    "require_workflow_complete",
]


class RequireWorkflowCompleteSpecs(BaseModel):
    """Specs for require workflow complete phrase."""

    # inputs
    workflow_run_id: UUID
    # outputs
    satisfied: bool = False
    workflow_type: str | None = None
    status: str | None = None
    completed_at: str | None = None


@canon_phrase(
    Operable.from_structure(RequireWorkflowCompleteSpecs),
    inputs={"workflow_run_id"},
    outputs={
        "satisfied",
        "workflow_run_id",
        "workflow_type",
        "status",
        "completed_at",
    },
)
async def require_workflow_complete(
    options: RequireWorkflowCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a workflow run has completed successfully.

    Gate pattern that enforces workflow completion before downstream
    operations can proceed. Queries workflow_runs table directly.

    Args:
        options: Options containing workflow_run_id.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if workflow is completed.

    Raises:
        WorkflowNotFoundError: If workflow run does not exist.
        WorkflowNotCompleteError: If workflow run is not completed.

    Regulatory citations:
        - NYC LL144: AEDT results require completed workflow provenance
        - EU AI Act Article 14: Human oversight requires completed workflow audit
        - SOC 2 CC4.1: Information quality requires workflow completion
    """
    workflow_run_id = options.workflow_run_id

    row = await select_one(
        "workflow_runs",
        where={"id": workflow_run_id, "tenant_id": ctx.tenant_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise WorkflowNotFoundError(workflow_run_id=workflow_run_id)

    current_status = row.get("status", "unknown")

    if current_status != "completed":
        raise WorkflowNotCompleteError(
            workflow_run_id=workflow_run_id,
            current_status=current_status,
        )

    completed_at = row.get("completed_at")
    completed_at_str = (
        completed_at.isoformat()
        if hasattr(completed_at, "isoformat")
        else str(completed_at)
        if completed_at
        else None
    )

    return {
        "satisfied": True,
        "workflow_run_id": workflow_run_id,
        "workflow_type": row.get("workflow_type"),
        "status": current_status,
        "completed_at": completed_at_str,
    }
