"""Phase lifecycle state machine for charter runtime.

Defines the valid states a phase can be in and the allowed transitions
between them. This enforces proper workflow progression and prevents
invalid state changes.

Regulatory Context:
    Phase state transitions are audit-grade events. Invalid transitions
    indicate either bugs or attempted manipulation. The state machine
    ensures compliance workflows progress only through sanctioned paths.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Set

__all__ = (
    "PHASE_TRANSITIONS",
    "InvalidPhaseTransition",
    "PhaseState",
    "get_terminal_states",
    "is_valid_transition",
)


class PhaseState(Enum):
    """Phase execution lifecycle states.

    These mirror the PhaseStatus class in canon.entities.charter.phase_execution
    but as a proper Enum for type safety and transition validation.

    State Progression (happy path):
        PENDING -> WAITING_USER -> IN_PROGRESS -> COMPLETED

    Alternative Paths:
        PENDING -> WAITING_GATE -> WAITING_USER (if phase has require gates)
        PENDING -> SKIPPED (conditional logic)
        WAITING_USER -> WAITING_TRIGGER (if phase has await directive)
        IN_PROGRESS -> FAILED (gate failure or rejection)
    """

    PENDING = "pending"
    """Phase created, waiting for predecessor phases to complete."""

    WAITING_GATE = "waiting_gate"
    """Predecessor complete, waiting for require gates to pass.

    Example: `require verify_consent("background_check")` must return true.
    """

    WAITING_USER = "waiting_user"
    """All gates passed, phase is in assignee's inbox awaiting action."""

    WAITING_TRIGGER = "waiting_trigger"
    """Phase active but blocked on external trigger event.

    Example: `await candidate_files_dispute` blocks until event fires.
    """

    IN_PROGRESS = "in_progress"
    """User has claimed the phase and is actively working on it."""

    COMPLETED = "completed"
    """Phase completed successfully. Terminal state."""

    SKIPPED = "skipped"
    """Phase skipped (e.g., skip_svp=True in context). Terminal state."""

    FAILED = "failed"
    """Phase failed (gate failure, rejection, or error). Terminal state."""


# Valid state transitions
# Key = current state, Value = set of valid target states
PHASE_TRANSITIONS: dict[PhaseState, Set[PhaseState]] = {
    PhaseState.PENDING: {
        PhaseState.WAITING_GATE,  # Has require gates to evaluate
        PhaseState.WAITING_USER,  # No gates, go directly to user inbox
        PhaseState.WAITING_TRIGGER,  # Has await directives, wait for trigger
        PhaseState.SKIPPED,  # Conditional skip
    },
    PhaseState.WAITING_GATE: {
        PhaseState.WAITING_USER,  # All gates passed
        PhaseState.FAILED,  # Gate failed
        PhaseState.SKIPPED,  # Conditional skip
    },
    PhaseState.WAITING_USER: {
        PhaseState.IN_PROGRESS,  # User claimed phase
        PhaseState.WAITING_TRIGGER,  # Phase has await directive
        PhaseState.SKIPPED,  # Conditional skip (rare, but possible)
    },
    PhaseState.WAITING_TRIGGER: {
        PhaseState.IN_PROGRESS,  # Trigger fired, user can proceed
        PhaseState.FAILED,  # Timeout or cancellation
    },
    PhaseState.IN_PROGRESS: {
        PhaseState.COMPLETED,  # Success
        PhaseState.FAILED,  # Failure or rejection
    },
    # Terminal states - no outgoing transitions
    PhaseState.COMPLETED: frozenset(),
    PhaseState.SKIPPED: frozenset(),
    PhaseState.FAILED: frozenset(),
}


def is_valid_transition(from_state: PhaseState, to_state: PhaseState) -> bool:
    """Check if a state transition is valid.

    Args:
        from_state: Current phase state.
        to_state: Desired target state.

    Returns:
        True if the transition is allowed by the state machine.
    """
    valid_targets = PHASE_TRANSITIONS.get(from_state, frozenset())
    return to_state in valid_targets


def get_terminal_states() -> frozenset[PhaseState]:
    """Get all terminal (final) states.

    Terminal states have no outgoing transitions.

    Returns:
        Set of terminal PhaseState values.
    """
    return frozenset(state for state, targets in PHASE_TRANSITIONS.items() if not targets)


class InvalidPhaseTransition(Exception):
    """Raised when an invalid phase state transition is attempted.

    This is a programming error or attempted manipulation. The error
    includes full context for audit logging.
    """

    def __init__(
        self,
        from_state: PhaseState | str,
        to_state: PhaseState | str,
        *,
        phase_name: str | None = None,
        run_id: str | None = None,
    ):
        # Handle both PhaseState and string values
        from_value = from_state.value if isinstance(from_state, PhaseState) else from_state
        to_value = to_state.value if isinstance(to_state, PhaseState) else to_state

        self.from_state = from_value
        self.to_state = to_value
        self.phase_name = phase_name
        self.run_id = run_id

        parts = [f"Invalid phase transition: {from_value} -> {to_value}"]
        if phase_name:
            parts.append(f"phase={phase_name}")
        if run_id:
            parts.append(f"run_id={run_id}")

        super().__init__(", ".join(parts))

    def to_dict(self) -> dict:
        """Serialize for audit logging."""
        return {
            "error": "InvalidPhaseTransition",
            "from_state": self.from_state,
            "to_state": self.to_state,
            "phase_name": self.phase_name,
            "run_id": self.run_id,
        }
