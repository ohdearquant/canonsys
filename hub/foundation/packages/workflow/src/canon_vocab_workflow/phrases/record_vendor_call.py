"""Record a vendor call within a workflow step.

Tracks individual vendor API calls with provenance hashes
for complete audit trail.

Regulatory context:
    - NYC LL144: Each vendor/AEDT call must be logged with provenance
    - EU AI Act: External AI calls require input/output documentation
    - SOC 2: Vendor calls require audit trail
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

__all__ = ["RecordVendorCallSpecs", "record_vendor_call"]


class RecordVendorCallSpecs(BaseModel):
    """Specs for record vendor call phrase."""

    # inputs
    workflow_run_id: UUID
    step_evidence_id: UUID
    vendor_code: str
    config_hash: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    duration_ms: int
    status: str = "success"
    error_message: str | None = None
    subject_id: UUID | None = None
    # outputs
    evidence_id: UUID | None = None
    input_hash: str | None = None
    output_hash: str | None = None


record_vendor_call_operable = Operable.from_structure(RecordVendorCallSpecs)


@canon_phrase(
    record_vendor_call_operable,
    inputs={
        "workflow_run_id",
        "step_evidence_id",
        "vendor_code",
        "config_hash",
        "input_data",
        "output_data",
        "duration_ms",
        "status",
        "error_message",
        "subject_id",
    },
    outputs={
        "evidence_id",
        "vendor_code",
        "status",
        "input_hash",
        "output_hash",
        "error_message",
    },
)
async def record_vendor_call(
    options: RecordVendorCallSpecs,
    ctx: RequestContext,
) -> dict:
    """Record a vendor call within a workflow step.

    Args:
        options: Vendor call options containing workflow_run_id, step_evidence_id, vendor_code,
                config_hash, input_data, output_data, duration_ms, status, error_message, subject_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with evidence_id, vendor_code, status, input_hash, output_hash, error_message
    """
    workflow_run_id = options.workflow_run_id
    step_evidence_id = options.step_evidence_id
    vendor_code = options.vendor_code
    config_hash = options.config_hash
    input_data = options.input_data
    output_data = options.output_data
    duration_ms = options.duration_ms
    status = options.status
    error_message = options.error_message
    subject_id = options.subject_id

    # 1. Compute input and output hashes
    input_hash = compute_hash(input_data)
    output_hash = compute_hash(output_data)

    # 2. Create evidence for vendor call
    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=subject_id,
        evidence_type=f"vendor.call.{vendor_code}",
        title=f"Vendor call: {vendor_code}",
        data={
            "workflow_run_id": str(workflow_run_id),
            "step_evidence_id": str(step_evidence_id),
            "vendor_code": vendor_code,
            "config_hash": config_hash,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error_message,
        },
        source=vendor_code,
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)

    # 3. Save evidence
    saved_evidence = await save_evidence(evidence, ctx, conn=ctx.conn)

    return {
        "evidence_id": saved_evidence.id,
        "vendor_code": vendor_code,
        "status": status,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "error_message": error_message,
    }


# Export auto-generated types from the Phrase object
RecordVendorCallOptions = record_vendor_call.options_type
RecordVendorCallResult = record_vendor_call.result_type
