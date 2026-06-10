"""Phase execution entity - per-phase state within a CharterRun.

PhaseExecution tracks the state of a single phase within a CharterRun.
It captures:
- Assignment by role (from charter) or specific user
- Gate evaluation results
- Actions taken and evidence created
- Document access grants issued
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from kron.types import FK

from ..entity import Entity, register_entity
from ..shared import TenantAware, User
from .run import CharterRun

__all__ = (
    "PhaseExecution",
    "PhaseExecutionContent",
    "PhaseStatus",
)


class PhaseStatus:
    """Phase execution lifecycle states."""

    PENDING = "pending"
    """Phase not yet activated (predecessor not complete)."""

    WAITING_GATE = "waiting_gate"
    """Phase activated, waiting for require gates to pass."""

    WAITING_USER = "waiting_user"
    """Gates passed, waiting for user action."""

    WAITING_TRIGGER = "waiting_trigger"
    """Waiting for external trigger event (await directive)."""

    IN_PROGRESS = "in_progress"
    """User is actively working on this phase."""

    COMPLETED = "completed"
    """Phase completed successfully."""

    SKIPPED = "skipped"
    """Phase skipped (conditional logic or situation predicate)."""

    FAILED = "failed"
    """Phase failed (gate failure or rejection)."""


class PhaseExecutionContent(TenantAware):
    """Content for a phase execution record.

    PhaseExecution tracks the state of a single phase within a CharterRun.
    It captures:
    - Assignment by role (from charter) or specific user
    - Gate evaluation results
    - Actions taken and evidence created
    - Document access grants issued

    Assignment Logic:
        - assignee_role comes from PhaseNode's role binding in charter
        - assignee_id is set when a specific user claims the phase
        - Only users with matching role can claim/act on the phase
    """

    # Run reference
    run_id: FK[CharterRun]
    """The charter run this phase belongs to."""

    # Phase identification
    workflow_name: str
    """Name of the workflow this phase belongs to."""

    phase_name: str
    """Name of this phase (from PhaseNode.name)."""

    sequence: int
    """Order in the workflow (from CompiledCharter.phase_order)."""

    requires_phases: list[str] = Field(default_factory=list)
    """Phase names that must complete before this phase can activate.

    Derived from charter 'require' clauses:
        require previous_phase.passed  ->  requires_phases = ["previous_phase"]

    Used for require-based cascade logic instead of sequence-based.
    """

    # Assignment
    assignee_role: str | None = None
    """Role that can act on this phase (from charter roles)."""

    assignee_id: FK[User] | None = None
    """Specific user assigned/claimed this phase."""

    # Status
    status: str = PhaseStatus.PENDING
    """Current phase status."""

    # Timing
    activated_at: datetime | None = None
    """When phase became active (predecessor complete)."""

    claimed_at: datetime | None = None
    """When a user claimed this phase."""

    # Gate evaluation
    gate_results: dict = Field(default_factory=dict)
    """Results of require gate evaluations.

    Structure:
        {
            "feature_name": {"passed": bool, "result": any, "evaluated_at": iso_str},
            "phase_ref.passed": {"passed": bool, "evaluated_at": iso_str},
        }
    """

    gates_passed_at: datetime | None = None
    """When all gates passed (status moved to WAITING_USER)."""

    # Action taken
    action_taken: str | None = None
    """Action taken: 'approve', 'reject', 'skip', 'escalate'."""

    action_at: datetime | None = None
    """When action was taken."""

    action_by_id: FK[User] | None = None
    """User who took the action."""

    action_notes: str | None = None
    """Notes provided with the action."""

    # Outputs
    output_data: dict | None = None
    """Output data produced by this phase (from OutputNode type)."""

    # Evidence
    evidence_ids: list[UUID] = Field(default_factory=list)
    """Evidence records created during this phase."""

    chain_entry_id: UUID | None = None
    """Chain entry linking this phase to evidence chain."""

    # Document access grants
    grant_token_ids: list[UUID] = Field(default_factory=list)
    """DocumentAccessToken IDs issued for this phase."""

    # Certify tracking (for phases with certify directive)
    is_certified: bool = False
    """Whether this phase produced a certified output."""

    certificate_id: UUID | None = None
    """Certificate ID if certified."""

    # Trigger tracking (for phases with await directives)
    trigger_names: list[str] = Field(default_factory=list)
    """Trigger names this phase is waiting for (from await directives)."""

    # Failure handling
    failure_reason: str | None = None
    """Reason for failure (if status is FAILED)."""

    failed_gate: str | None = None
    """Name of gate that failed (if gate failure)."""


@register_entity("phase_executions")
class PhaseExecution(Entity):
    """Entity representing a phase execution within a CharterRun.

    Each phase in a charter workflow creates a PhaseExecution record
    when activated. The record captures decisions and serves as
    part of the compliance audit trail.
    """

    content: PhaseExecutionContent

    _indexes = [
        # Fast lookup by run (all phases for a run)
        {"columns": ["run_id"]},
        # Fast lookup by run + status (pending phases)
        {"columns": ["run_id", "status"]},
        # CRITICAL: Inbox query - phases waiting for user by role
        {"columns": ["tenant_id", "status", "assignee_role"]},
        # Inbox query - phases waiting for specific user
        {"columns": ["tenant_id", "status", "assignee_id"]},
        # Audit query - phases by actor
        {"columns": ["action_by_id"]},
        # Phase timeline
        {"columns": ["run_id", "workflow_name", "sequence"]},
    ]
