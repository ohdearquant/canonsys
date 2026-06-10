"""Workflow service - thin wrapper over workflow phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory context:
    - NYC LL144: AEDT audit trail requirements
    - EU AI Act: AI transparency and record-keeping
    - SOC 2: Change tracking and vendor call logging
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    complete_workflow_run,
    create_workflow_run,
    record_vendor_call,
    record_workflow_step,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["WorkflowService"]


# =============================================================================
# Request Options (for service API documentation)
# =============================================================================


class CreateRunOptions(BaseModel):
    """Options for creating a workflow run."""

    workflow_type: str = Field(
        ..., description="Type of workflow (e.g., 'screening', 'verification')"
    )
    workflow_version: str = Field(default="1.0", description="Version string for the workflow")
    job_id: UUID | None = Field(default=None, description="Optional job association")
    person_id: UUID | None = Field(default=None, description="Optional person/subject association")


class RecordStepOptions(BaseModel):
    """Options for recording a workflow step."""

    workflow_run_id: UUID = Field(..., description="Parent workflow run ID")
    step_name: str = Field(..., description="Name of the step")
    input_data: dict = Field(..., description="Input data (will be hashed for provenance)")
    output_data: dict = Field(..., description="Output data (will be hashed for provenance)")
    duration_ms: int | None = Field(default=None, description="Execution duration in milliseconds")
    subject_id: UUID | None = Field(default=None, description="Optional subject for evidence")


class RecordVendorCallOptions(BaseModel):
    """Options for recording a vendor call."""

    workflow_run_id: UUID = Field(..., description="Parent workflow run ID")
    step_evidence_id: UUID = Field(..., description="Parent step evidence ID")
    vendor_code: str = Field(..., description="Vendor identifier")
    config_hash: str = Field(..., description="Hash of vendor config used")
    input_data: dict = Field(..., description="Input data (will be hashed)")
    output_data: dict = Field(..., description="Output data (will be hashed)")
    duration_ms: int = Field(..., description="Call duration in milliseconds")
    status: str = Field(default="success", description="Call status (success/failure)")
    error_message: str | None = Field(default=None, description="Error message if failed")
    subject_id: UUID | None = Field(default=None, description="Optional subject for evidence")


class CompleteRunOptions(BaseModel):
    """Options for completing a workflow run."""

    workflow_run_id: UUID = Field(..., description="Workflow run to complete")
    quality_score: float | None = Field(default=None, description="Quality score (0-100)")
    quality_passed: bool | None = Field(default=None, description="Quality gate result")
    final_evidence_id: UUID | None = Field(default=None, description="Reference to final evidence")


# =============================================================================
# Service
# =============================================================================


class WorkflowService(CanonService):
    """Workflow service - manages workflow provenance tracking.

    Thin wrapper that delegates to phrase functions.

    All operations emit evidence for full audit trail.
    This is the compliance backbone - all workflow executions
    are traceable and tamper-evident.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="workflow")

    @action(evidence_type="workflow.created")
    async def create_run(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a new workflow run.

        Emits evidence for workflow creation.
        """
        return await create_workflow_run(payload, ctx)

    @action(evidence_type="workflow.step")
    async def record_step(self, payload: dict, ctx: RequestContext) -> dict:
        """Record a workflow step with provenance.

        Each step gets input/output hashes for full data provenance.
        """
        return await record_workflow_step(payload, ctx)

    @action(evidence_type="workflow.vendor_call")
    async def record_vendor_call(self, payload: dict, ctx: RequestContext) -> dict:
        """Record a vendor API call within a workflow step.

        Tracks individual vendor calls with provenance hashes
        for complete audit trail.
        """
        return await record_vendor_call(payload, ctx)

    @action(evidence_type="workflow.completed")
    async def complete_run(self, payload: dict, ctx: RequestContext) -> dict:
        """Complete a workflow run.

        Finalizes workflow with quality metrics and emits completion evidence.

        Raises:
            WorkflowNotFoundError: If workflow run not found
            WorkflowAlreadyCompleteError: If workflow already completed
            WorkflowFailedError: If workflow has failed
        """
        return await complete_workflow_run(payload, ctx)
