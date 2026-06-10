"""Create a new workflow run.

Tracks workflow execution with evidence chain.

Regulatory context:
    - NYC LL144: AEDT audit requires tracking complete workflow execution
    - EU AI Act: Transparency requires documenting AI system operations
    - SOC 2: Change tracking requires workflow state management
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from canon_vocab_evidence import save_evidence
from pydantic import BaseModel

from canon.db import TenantScope, insert
from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CreateWorkflowRunSpecs", "create_workflow_run"]


class CreateWorkflowRunSpecs(BaseModel):
    """Specs for create workflow run phrase."""

    # inputs
    workflow_type: str
    workflow_version: str = "1.0"
    job_id: UUID | None = None
    person_id: UUID | None = None
    # outputs
    workflow_run_id: UUID | None = None
    status: str | None = None
    evidence_id: UUID | None = None
    started_at: datetime | None = None


create_workflow_run_operable = Operable.from_structure(CreateWorkflowRunSpecs)


@canon_phrase(
    create_workflow_run_operable,
    inputs={"workflow_type", "workflow_version", "job_id", "person_id"},
    outputs={"workflow_run_id", "workflow_type", "status", "evidence_id", "started_at"},
)
async def create_workflow_run(
    options: CreateWorkflowRunSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a new workflow run with evidence.

    Args:
        options: Create options containing workflow_type, workflow_version, job_id, person_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with workflow_run_id, workflow_type, status, evidence_id, started_at
    """
    now = now_utc()
    workflow_run_id = uuid4()

    workflow_type = options.workflow_type
    workflow_version = options.workflow_version
    job_id = options.job_id
    person_id = options.person_id

    # 1. Create WorkflowRun row
    workflow_row = {
        "id": workflow_run_id,
        "tenant_id": ctx.tenant_id,
        "workflow_type": workflow_type,
        "workflow_version": workflow_version,
        "status": "pending",
        "job_id": job_id,
        "person_id": person_id,
        "created_at": now,
        "updated_at": now,
    }

    await insert(
        "workflow_runs",
        workflow_row,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # 2. Create evidence for workflow creation
    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=person_id,
        evidence_type="workflow.created",
        title=f"Workflow created: {workflow_type}",
        data={
            "workflow_run_id": str(workflow_run_id),
            "workflow_type": workflow_type,
            "workflow_version": workflow_version,
            "job_id": str(job_id) if job_id else None,
            "person_id": str(person_id) if person_id else None,
        },
        source="canon",
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)

    # 3. Save evidence (creates genesis chain entry)
    saved_evidence = await save_evidence(evidence, ctx, conn=ctx.conn)

    return {
        "workflow_run_id": workflow_run_id,
        "workflow_type": workflow_type,
        "status": "pending",
        "evidence_id": saved_evidence.id,
        "started_at": now,
    }


# Export auto-generated types from the Phrase object
CreateWorkflowRunOptions = create_workflow_run.options_type
CreateWorkflowRunResult = create_workflow_run.result_type
