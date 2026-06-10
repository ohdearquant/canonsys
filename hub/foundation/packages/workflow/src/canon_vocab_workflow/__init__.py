"""Workflow feature - vertical slice for workflow provenance tracking.

This module provides the complete workflow domain implementation:
- Types: WorkflowRunStatus, WorkflowType, VendorCallStatus
- Phrases: create_workflow_run, record_workflow_step, record_vendor_call, complete_workflow_run
- Exceptions: WorkflowNotFoundError, WorkflowNotCompleteError, etc.

Regulatory context:
    - NYC LL144 (AEDT audit trail)
    - EU AI Act (Transparency requirements)
    - SOC 2 (Change tracking)

Usage:
    from canon_vocab_workflow import (
        # Types
        WorkflowRunStatus,
        WorkflowType,
        VendorCallStatus,
        # Specs
        CreateWorkflowRunSpecs,
        CompleteWorkflowRunSpecs,
        RecordWorkflowStepSpecs,
        RecordVendorCallSpecs,
        # Phrases
        create_workflow_run,
        record_workflow_step,
        record_vendor_call,
        complete_workflow_run,
        # Exceptions
        WorkflowNotFoundError,
        ToolConfigMismatchError,
        # Package metadata
        WORKFLOW,
    )
"""

# Package metadata
# Exceptions
from .exceptions import (
    StepNotLoggedError,
    ToolConfigMismatchError,
    VendorCallNotLoggedError,
    WorkflowAlreadyCompleteError,
    WorkflowFailedError,
    WorkflowNotCompleteError,
    WorkflowNotFoundError,
)
from .package import WORKFLOW

# Phrases
from .phrases import (
    CompleteWorkflowRunSpecs,
    CreateWorkflowRunSpecs,
    RecordVendorCallSpecs,
    RecordWorkflowStepSpecs,
    complete_workflow_run,
    create_workflow_run,
    record_vendor_call,
    record_workflow_step,
)

# Service
from .service import WorkflowService

# Types
from .types import VendorCallStatus, WorkflowRunStatus, WorkflowType

__all__ = [
    # Service
    "WorkflowService",
    # Package metadata
    "WORKFLOW",
    # Specs classes (Pydantic BaseModels)
    "CompleteWorkflowRunSpecs",
    "CreateWorkflowRunSpecs",
    "RecordVendorCallSpecs",
    "RecordWorkflowStepSpecs",
    # Types - Enums
    "VendorCallStatus",
    "WorkflowRunStatus",
    "WorkflowType",
    # Exceptions
    "StepNotLoggedError",
    "ToolConfigMismatchError",
    "VendorCallNotLoggedError",
    "WorkflowAlreadyCompleteError",
    "WorkflowFailedError",
    "WorkflowNotCompleteError",
    "WorkflowNotFoundError",
    # Phrase functions
    "complete_workflow_run",
    "create_workflow_run",
    "record_vendor_call",
    "record_workflow_step",
]
