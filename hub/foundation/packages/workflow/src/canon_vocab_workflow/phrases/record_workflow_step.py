"""Record a workflow step with provenance hashes.

Each step in a workflow gets recorded with input/output hashes
for full data provenance tracking.

Regulatory context:
    - NYC LL144: Each AEDT step must be logged with provenance
    - EU AI Act: AI system steps require input/output documentation
    - SOC 2: Process steps require audit trail
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon_vocab_evidence import save_evidence
from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RecordWorkflowStepSpecs", "record_workflow_step"]


class RecordWorkflowStepSpecs(BaseModel):
    """Specs for record workflow step phrase."""

    # inputs
    workflow_run_id: UUID
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    duration_ms: int | None = None
    subject_id: UUID | None = None
    # outputs
    evidence_id: UUID | None = None
    input_hash: str | None = None
    output_hash: str | None = None


record_workflow_step_operable = Operable.from_structure(RecordWorkflowStepSpecs)


@canon_phrase(
    record_workflow_step_operable,
    inputs={
        "workflow_run_id",
        "step_name",
        "input_data",
        "output_data",
        "duration_ms",
        "subject_id",
    },
    outputs={"evidence_id", "step_name", "input_hash", "output_hash", "duration_ms"},
)
async def record_workflow_step(
    options: RecordWorkflowStepSpecs,
    ctx: RequestContext,
) -> dict:
    """Record a workflow step with provenance.

    Args:
        options: Step options containing workflow_run_id, step_name, input_data, output_data, duration_ms, subject_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with evidence_id, step_name, input_hash, output_hash, duration_ms
    """
    workflow_run_id = options.workflow_run_id
    step_name = options.step_name
    input_data = options.input_data
    output_data = options.output_data
    duration_ms = options.duration_ms
    subject_id = options.subject_id

    # 1. Compute input and output hashes
    input_hash = compute_hash(input_data)
    output_hash = compute_hash(output_data)

    # 2. Create evidence for workflow step
    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=subject_id,
        evidence_type=f"workflow.step.{step_name}",
        title=f"Workflow step: {step_name}",
        data={
            "workflow_run_id": str(workflow_run_id),
            "step_name": step_name,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "duration_ms": duration_ms,
        },
        source="canon",
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)

    # 3. Save evidence
    saved_evidence = await save_evidence(evidence, ctx, conn=ctx.conn)

    return {
        "evidence_id": saved_evidence.id,
        "step_name": step_name,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "duration_ms": duration_ms,
    }


# Export auto-generated types from the Phrase object
RecordWorkflowStepOptions = record_workflow_step.options_type
RecordWorkflowStepResult = record_workflow_step.result_type
