"""Complete a workflow run.

Finalizes workflow with quality metrics and emits completion evidence.

Regulatory context:
    - NYC LL144: AEDT audit requires documenting workflow completion
    - EU AI Act: Transparency requires recording AI system outcomes
    - SOC 2: Change tracking requires workflow finalization
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon_vocab_evidence import save_evidence
from pydantic import BaseModel

from canon.db import TenantScope, select_one, update
from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CompleteWorkflowRunSpecs", "complete_workflow_run"]


class CompleteWorkflowRunSpecs(BaseModel):
    """Specs for complete workflow run phrase."""

    # inputs
    workflow_run_id: UUID
    quality_score: float | None = None
    quality_passed: bool | None = None
    final_evidence_id: UUID | None = None
    # outputs
    workflow_type: str | None = None
    status: str | None = None
    evidence_id: UUID | None = None
    completed_at: datetime | None = None


complete_workflow_run_operable = Operable.from_structure(CompleteWorkflowRunSpecs)


@canon_phrase(
    complete_workflow_run_operable,
    inputs={"workflow_run_id", "quality_score", "quality_passed", "final_evidence_id"},
    outputs={
        "workflow_run_id",
        "workflow_type",
        "status",
        "quality_score",
        "quality_passed",
        "evidence_id",
        "completed_at",
    },
)
async def complete_workflow_run(
    options: CompleteWorkflowRunSpecs,
    ctx: RequestContext,
) -> dict:
    """Complete a workflow run.

    Args:
        options: Complete options containing workflow_run_id, quality_score, quality_passed, final_evidence_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with workflow_run_id, workflow_type, status, quality_score, quality_passed, evidence_id, completed_at

    Raises:
        ValueError: If workflow run not found or already completed
    """
    workflow_run_id = options.workflow_run_id
    quality_score = options.quality_score
    quality_passed = options.quality_passed
    final_evidence_id = options.final_evidence_id

    # 1. Fetch workflow run
    workflow_row = await select_one(
        "workflow_runs",
        where={"id": workflow_run_id, "tenant_id": ctx.tenant_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not workflow_row:
        raise ValueError(f"Workflow run {workflow_run_id} not found")

    if workflow_row["status"] == "completed":
        raise ValueError(f"Workflow run {workflow_run_id} is already completed")

    if workflow_row["status"] == "failed":
        raise ValueError(f"Workflow run {workflow_run_id} has failed, cannot complete")

    workflow_type = workflow_row["workflow_type"]
    now = now_utc()

    # 2. Update status to "completed" with quality metrics
    update_data: dict[str, Any] = {
        "status": "completed",
        "completed_at": now,
        "updated_at": now,
    }

    if quality_score is not None:
        update_data["quality_score"] = quality_score

    if quality_passed is not None:
        update_data["quality_passed"] = quality_passed

    if final_evidence_id is not None:
        update_data["evidence_id"] = final_evidence_id

    await update(
        "workflow_runs",
        update_data,
        where={"id": workflow_run_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # 3. Emit completion evidence
    evidence_data: dict[str, Any] = {
        "workflow_run_id": str(workflow_run_id),
        "workflow_type": workflow_type,
        "workflow_version": workflow_row.get("workflow_version", "1.0"),
        "completed_at": now.isoformat(),
    }

    if quality_score is not None:
        evidence_data["quality_score"] = quality_score

    if quality_passed is not None:
        evidence_data["quality_passed"] = quality_passed

    if final_evidence_id is not None:
        evidence_data["final_evidence_id"] = str(final_evidence_id)

    # Include business context if present
    job_id = workflow_row.get("job_id")
    person_id = workflow_row.get("person_id")
    if job_id:
        evidence_data["job_id"] = str(job_id)
    if person_id:
        evidence_data["person_id"] = str(person_id)

    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=person_id,
        evidence_type="workflow.completed",
        title=f"Workflow completed: {workflow_type}",
        data=evidence_data,
        source="canon",
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)
    saved_evidence = await save_evidence(evidence, ctx, conn=ctx.conn)

    return {
        "workflow_run_id": workflow_run_id,
        "workflow_type": workflow_type,
        "status": "completed",
        "quality_score": quality_score,
        "quality_passed": quality_passed,
        "evidence_id": saved_evidence.id,
        "completed_at": now,
    }


# Export auto-generated types from the Phrase object
CompleteWorkflowRunOptions = complete_workflow_run.options_type
CompleteWorkflowRunResult = complete_workflow_run.result_type
