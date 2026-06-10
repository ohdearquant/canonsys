"""Workflow step types.

Types related to workflow steps and vendor calls.

Regulatory context:
    - NYC LL144: Each AEDT call must be logged with provenance
    - EU AI Act: AI system calls require input/output documentation
    - SOC 2: Vendor calls require audit trail
"""

from kron.types import Enum

__all__ = ("VendorCallStatus",)


class VendorCallStatus(Enum):
    """Status of a vendor API call within a workflow step.

    Tracks the outcome of individual vendor calls for audit purposes.

    States:
        SUCCESS: Call completed successfully
        FAILURE: Call failed with error
        TIMEOUT: Call timed out
        RETRY: Call is being retried
        SKIPPED: Call was skipped (conditional logic)
    """

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RETRY = "retry"
    SKIPPED = "skipped"

    def is_error(self) -> bool:
        """Check if this status represents an error condition."""
        return self in (VendorCallStatus.FAILURE, VendorCallStatus.TIMEOUT)

    def is_terminal(self) -> bool:
        """Check if this status is terminal (no further action)."""
        return self in (
            VendorCallStatus.SUCCESS,
            VendorCallStatus.FAILURE,
            VendorCallStatus.SKIPPED,
        )
