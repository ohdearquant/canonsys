"""Charter runtime instance entity.

CharterRun tracks the execution of a compiled Charter for a specific
subject. Unlike generic WorkflowInstance, CharterRun:
- Links to Charter (compiled DSL source)
- Tracks current workflow AND phase (multi-workflow support)
- Stores context dict for cross-phase data sharing
- References related entity via polymorphic (type, id) pair

Phase execution creates PhaseExecution records for each phase,
preserving the audit trail of decisions made.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from kron.types import FK
from kron.utils import now_utc

from ..entity import Entity, register_entity
from ..shared import Person, TenantAware, User
from .charter import Charter

__all__ = (
    "CharterRun",
    "CharterRunContent",
    "CharterRunStatus",
)


class CharterRunStatus:
    """CharterRun lifecycle states."""

    DRAFT = "draft"
    """Run created but not yet started."""

    ACTIVE = "active"
    """Run is in progress, phases executing."""

    SUSPENDED = "suspended"
    """Run paused (e.g., awaiting external event)."""

    COMPLETED = "completed"
    """All phases completed successfully."""

    CANCELLED = "cancelled"
    """Run terminated before completion."""

    FAILED = "failed"
    """Run terminated due to gate failure or rejection."""


class CharterRunContent(TenantAware):
    """Content for a charter runtime instance.

    CharterRun tracks the execution of a compiled Charter for a specific
    subject. Unlike generic WorkflowInstance, CharterRun:
    - Links to Charter (compiled DSL source)
    - Tracks current workflow AND phase (multi-workflow support)
    - Stores context dict for cross-phase data sharing
    - References related entity via polymorphic (type, id) pair

    Phase execution creates PhaseExecution records for each phase,
    preserving the audit trail of decisions made.
    """

    # Charter reference
    charter_id: FK[Charter]
    """The charter being executed."""

    charter_snapshot_hash: str | None = None
    """Content hash of charter at run start (for version pinning)."""

    # Subject (person this run is about)
    subject_id: FK[Person]
    """The person this charter run is about (candidate, employee)."""

    # Related entity (polymorphic reference)
    related_entity_type: str
    """Type of related entity (e.g., 'offer', 'pip_plan', 'termination')."""

    related_entity_id: UUID
    """ID of the related entity."""

    # Workflow tracking (charters can have multiple workflows)
    current_workflow: str | None = None
    """Name of the currently executing workflow (from CompiledCharter.workflow_names)."""

    current_phase: str | None = None
    """Name of the current phase within the workflow."""

    # Status
    status: str = CharterRunStatus.DRAFT
    """Current lifecycle status."""

    # Initiator
    initiated_by_id: FK[User]
    """User who initiated this run."""

    initiated_at: datetime = Field(default_factory=now_utc)
    """When the run was initiated."""

    started_at: datetime | None = None
    """When the run was started (moved to ACTIVE)."""

    # Completion
    completed_at: datetime | None = None
    """When the run reached terminal state."""

    final_outcome: str | None = None
    """Final outcome: 'approved', 'rejected', 'cancelled', 'failed'."""

    failure_reason: str | None = None
    """Reason for failure (if status is FAILED)."""

    # Context (cross-phase data sharing)
    run_context: dict = Field(default_factory=dict)
    """Context dict for cross-phase data.

    Populated during execution:
        - phase_outputs: {phase_name: output_data}
        - situation_context: {field: value} for situation predicates
        - evidence_ids: [uuid, ...] collected evidence
        - grant_tokens: {phase_name: [token_ids]} active grants
    """

    # Evidence tracking
    evidence_bundle_id: UUID | None = None
    """Evidence bundle ID (created on completion)."""

    certificate_id: UUID | None = None
    """Decision certificate ID (for certify phases)."""

    # Suspension
    suspended_at: datetime | None = None
    """When the run was suspended."""

    suspension_reason: str | None = None
    """Reason for suspension."""

    awaiting_trigger: str | None = None
    """Trigger name if suspended awaiting external event."""


@register_entity("charter_runs")
class CharterRun(Entity):
    """Entity representing a charter runtime instance.

    Tracks execution of a compiled Charter from initiation through
    completion. Each phase creates PhaseExecution records for audit.
    """

    content: CharterRunContent

    _indexes = [
        # Fast lookup by tenant + status (active runs)
        {"columns": ["tenant_id", "status"]},
        # Fast lookup by subject (person's charter runs)
        {"columns": ["subject_id"]},
        # Fast lookup by charter (runs of a charter)
        {"columns": ["charter_id"]},
        # Fast lookup by related entity
        {"columns": ["related_entity_type", "related_entity_id"]},
        # Fast lookup by initiator
        {"columns": ["initiated_by_id"]},
        # Fast lookup by current phase (for debugging)
        {"columns": ["status", "current_workflow", "current_phase"]},
    ]
