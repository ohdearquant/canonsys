"""Workflow domain exceptions.

These exceptions are raised by workflow phrases when invariants are violated.
All inherit from AIGovernanceViolation (the domain's base exception) since
workflow provenance is primarily an AI governance concern.

Regulatory context:
    - NYC LL144: AEDT requires same-tool verification
    - EU AI Act: AI transparency requires workflow documentation
    - SOC 2: Change tracking requires workflow completion
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import AIGovernanceViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "StepNotLoggedError",
    "ToolConfigMismatchError",
    "VendorCallNotLoggedError",
    "WorkflowAlreadyCompleteError",
    "WorkflowFailedError",
    "WorkflowNotCompleteError",
    "WorkflowNotFoundError",
]


class WorkflowNotFoundError(AIGovernanceViolation):
    """Workflow run does not exist.

    Raised when: An operation references a workflow_run_id that does not exist
    in the database.

    Regulatory basis:
    - EU AI Act Article 12: Record-keeping requires valid references
    - SOC 2 CC4.1: Information quality requires referential integrity

    Phrase: workflow_must_exist
    """

    default_regulation = "EU AI Act Article 12"
    default_message = "Workflow run not found"

    __slots__ = ("workflow_run_id",)

    def __init__(
        self,
        workflow_run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize workflow not found error.

        Args:
            workflow_run_id: UUID of the workflow run that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        super().__init__(
            f"Workflow run {workflow_run_id} not found",
            context={
                "workflow_run_id": str(workflow_run_id),
            },
            **kwargs,
        )


class WorkflowNotCompleteError(AIGovernanceViolation):
    """Workflow run is not in completed state.

    Raised when: An operation requires a completed workflow but the workflow
    is still pending, running, or failed.

    Regulatory basis:
    - NYC LL144: AEDT results require completed workflow provenance
    - EU AI Act Article 14: Human oversight requires completed workflow audit

    Phrase: workflow_must_be_complete
    """

    default_regulation = "NYC LL144"
    default_message = "Workflow must be completed before this action"

    __slots__ = ("current_status", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        current_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize workflow not complete error.

        Args:
            workflow_run_id: UUID of the workflow run.
            current_status: Current status of the workflow (pending/running/failed).
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.current_status = current_status
        super().__init__(
            f"Workflow run {workflow_run_id} has status '{current_status}' but must be 'completed'",
            context={
                "workflow_run_id": str(workflow_run_id),
                "current_status": current_status,
                "required_status": "completed",
            },
            **kwargs,
        )


class WorkflowAlreadyCompleteError(AIGovernanceViolation):
    """Workflow run is already completed and cannot be modified.

    Raised when: An operation attempts to modify a workflow that has already
    been completed. Completed workflows are immutable for audit integrity.

    Regulatory basis:
    - SOX Section 802: Document integrity requires immutability
    - EU AI Act Article 12: Record integrity requires no post-completion changes

    Phrase: workflow_must_not_be_complete
    """

    default_regulation = "SOX Section 802"
    default_message = "Workflow is already completed and cannot be modified"

    __slots__ = ("completed_at", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        completed_at: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize workflow already complete error.

        Args:
            workflow_run_id: UUID of the workflow run.
            completed_at: ISO timestamp when workflow was completed.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.completed_at = completed_at
        msg = f"Workflow run {workflow_run_id} is already completed"
        if completed_at:
            msg += f" at {completed_at}"
        super().__init__(
            msg,
            context={
                "workflow_run_id": str(workflow_run_id),
                "completed_at": completed_at,
            },
            **kwargs,
        )


class WorkflowFailedError(AIGovernanceViolation):
    """Workflow run has failed and cannot be completed.

    Raised when: An operation attempts to complete a workflow that has
    already failed.

    Regulatory basis:
    - SOC 2 CC4.1: Information quality requires accurate status tracking
    - EU AI Act Article 9: Risk management requires failure documentation

    Phrase: workflow_must_not_be_failed
    """

    default_regulation = "SOC 2 CC4.1"
    default_message = "Workflow has failed and cannot be completed"

    __slots__ = ("error_message", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize workflow failed error.

        Args:
            workflow_run_id: UUID of the workflow run.
            error_message: Error message from the failure.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.error_message = error_message
        msg = f"Workflow run {workflow_run_id} has failed"
        if error_message:
            msg += f": {error_message}"
        super().__init__(
            msg,
            context={
                "workflow_run_id": str(workflow_run_id),
                "error_message": error_message,
            },
            **kwargs,
        )


class VendorCallNotLoggedError(AIGovernanceViolation):
    """Vendor call was not logged in the workflow.

    Raised when: A workflow completion or audit check finds that an expected
    vendor call was not logged with proper provenance.

    Regulatory basis:
    - NYC LL144: AEDT requires logging all AI vendor calls
    - EU AI Act Article 13: Transparency requires vendor call documentation

    Phrase: vendor_call_must_be_logged
    """

    default_regulation = "NYC LL144"
    default_message = "Vendor call not logged in workflow"

    __slots__ = ("step_name", "vendor_code", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        vendor_code: str,
        step_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize vendor call not logged error.

        Args:
            workflow_run_id: UUID of the workflow run.
            vendor_code: Identifier of the vendor whose call was not logged.
            step_name: Name of the step where the call should have been logged.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.vendor_code = vendor_code
        self.step_name = step_name
        msg = f"Vendor call to '{vendor_code}' not logged in workflow {workflow_run_id}"
        if step_name:
            msg += f" (step: {step_name})"
        super().__init__(
            msg,
            context={
                "workflow_run_id": str(workflow_run_id),
                "vendor_code": vendor_code,
                "step_name": step_name,
            },
            **kwargs,
        )


class ToolConfigMismatchError(AIGovernanceViolation):
    """Tool configuration differs from validated/audited version.

    Raised when: verify_same_tool finds the current configuration hash
    differs from the hash recorded during bias audit validation.

    This is a critical AEDT compliance failure - using a different tool
    configuration than what was audited invalidates the bias audit.

    Regulatory basis:
    - NYC LL144: AEDT must be same tool as audited
    - EU AI Act Article 9: Change management for high-risk AI
    - FDA 21 CFR Part 11: Validated system requirements

    Phrase: same_tool_must_be_verified
    """

    default_regulation = "NYC LL144"
    default_message = "Tool configuration mismatch - differs from audited version"

    __slots__ = ("actual_hash", "config_id", "expected_hash", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        config_id: UUID,
        expected_hash: str,
        actual_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize tool config mismatch error.

        Args:
            workflow_run_id: UUID of the workflow run.
            config_id: UUID of the vendor config being verified.
            expected_hash: Configuration hash from bias audit.
            actual_hash: Current configuration hash.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.config_id = config_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"Tool config {config_id} in workflow {workflow_run_id} changed since validation "
            f"(expected {expected_hash[:8]}..., found {actual_hash[:8]}...)",
            context={
                "workflow_run_id": str(workflow_run_id),
                "config_id": str(config_id),
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
            **kwargs,
        )


class StepNotLoggedError(AIGovernanceViolation):
    """Required workflow step was not logged.

    Raised when: A workflow completion or audit check finds that an expected
    step was not logged with proper provenance.

    Regulatory basis:
    - EU AI Act Article 12: Record-keeping requires step documentation
    - SOC 2 CC4.1: Information quality requires complete workflow trail

    Phrase: step_must_be_logged
    """

    default_regulation = "EU AI Act Article 12"
    default_message = "Required workflow step not logged"

    __slots__ = ("step_name", "workflow_run_id")

    def __init__(
        self,
        workflow_run_id: UUID,
        step_name: str,
        **kwargs: Any,
    ) -> None:
        """Initialize step not logged error.

        Args:
            workflow_run_id: UUID of the workflow run.
            step_name: Name of the step that was not logged.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_run_id = workflow_run_id
        self.step_name = step_name
        super().__init__(
            f"Step '{step_name}' not logged in workflow {workflow_run_id}",
            context={
                "workflow_run_id": str(workflow_run_id),
                "step_name": step_name,
            },
            **kwargs,
        )
