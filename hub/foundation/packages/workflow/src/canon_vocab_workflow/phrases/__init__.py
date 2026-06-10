"""Workflow domain phrases.

All workflow operations in one place:
- Workflow lifecycle: create_workflow_run, complete_workflow_run
- Provenance tracking: record_workflow_step, record_vendor_call
- Gate: require_workflow_complete

Regulatory context:
    - NYC LL144 (AEDT audit trail)
    - EU AI Act (Transparency requirements)
    - SOC 2 (Change tracking)
"""

from .complete_workflow_run import CompleteWorkflowRunSpecs, complete_workflow_run
from .create_workflow_run import CreateWorkflowRunSpecs, create_workflow_run
from .record_vendor_call import RecordVendorCallSpecs, record_vendor_call
from .record_workflow_step import RecordWorkflowStepSpecs, record_workflow_step
from .require_workflow_complete import (
    RequireWorkflowCompleteSpecs,
    require_workflow_complete,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "CompleteWorkflowRunSpecs",
    "CreateWorkflowRunSpecs",
    "RecordVendorCallSpecs",
    "RecordWorkflowStepSpecs",
    "RequireWorkflowCompleteSpecs",
    # Phrase functions
    "complete_workflow_run",
    "create_workflow_run",
    "record_vendor_call",
    "record_workflow_step",
    "require_workflow_complete",
]
