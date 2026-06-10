"""Workflow run types.

Types related to workflow run lifecycle and identification.

Regulatory context:
    - NYC LL144: AEDT audit requires tracking complete workflow execution
    - EU AI Act: Transparency requires documenting AI system operations
    - SOC 2: Change tracking requires workflow state management
"""

from kron.types import Enum

__all__ = (
    "WorkflowRunStatus",
    "WorkflowType",
)


class WorkflowRunStatus(Enum):
    """Workflow run lifecycle states.

    A workflow run progresses through these states:
        PENDING -> RUNNING -> COMPLETED | FAILED

    States:
        PENDING: Created but not yet started
        RUNNING: Actively executing steps
        COMPLETED: Successfully finished with all steps
        FAILED: Terminated due to error
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """Check if this is a terminal state (cannot transition further)."""
        return self in (WorkflowRunStatus.COMPLETED, WorkflowRunStatus.FAILED)

    def can_complete(self) -> bool:
        """Check if workflow can transition to COMPLETED from this state."""
        return self in (WorkflowRunStatus.PENDING, WorkflowRunStatus.RUNNING)


class WorkflowType(Enum):
    """Standard workflow type identifiers.

    These are the canonical workflow types that the system tracks.
    Custom workflow types can be added but should be registered
    for consistent audit trail naming.

    Workflow types map to specific compliance requirements:
        - SCREENING: FCRA, EEOC compliance
        - VERIFICATION: SOC 2 verification controls
        - SCORING: NYC LL144 AEDT requirements
        - HIRING_BRIEF: Internal documentation
        - INTERVIEW_SCORECARD: EEOC documentation
        - MARKET_MAP: Competitive intelligence
    """

    # Candidate workflows
    SCREENING = "screening"
    VERIFICATION = "verification"
    SCORING = "scoring"

    # Internal workflows
    HIRING_BRIEF = "hiring_brief"
    INTERVIEW_SCORECARD = "interview_scorecard"
    MARKET_MAP = "market_map"

    # Generic
    CUSTOM = "custom"
