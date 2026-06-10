"""Trigger firing for await directives in Charter Runtime.

Handles external event triggers that unblock `await` directives in phases.
When a trigger fires, phases in WAITING_TRIGGER transition to IN_PROGRESS
so the assignee can proceed with their action.

Trigger Types:
    - Standalone await: `await event_name` in a phase body
      Phase goes to WAITING_TRIGGER, then IN_PROGRESS on trigger fire.
    - Require await: `require await event_name` as a phase precondition
      Phase can't activate until trigger fires (checked via evidence query).

Usage:
    from canon.runtime.trigger import fire_trigger

    result = await fire_trigger(
        run_id=run_id,
        trigger_name="candidate_files_dispute",
        actor_id=user_id,
        tenant_id=tenant_id,
        data={"dispute_id": "..."},
        conn=conn,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon.db import TenantScope, fetch

from .evidence import EvidenceEventType, record_phase_evidence
from .phase_state import InvalidPhaseTransition, PhaseState, is_valid_transition

if TYPE_CHECKING:
    import asyncpg

__all__ = (
    "TriggerNotFoundError",
    "TriggerResult",
    "fire_trigger",
    "has_trigger_fired",
)

logger = logging.getLogger(__name__)


class TriggerNotFoundError(Exception):
    """No phase is waiting for this trigger in the given run."""

    def __init__(self, run_id: UUID, trigger_name: str):
        self.run_id = run_id
        self.trigger_name = trigger_name
        super().__init__(f"No phase waiting for trigger '{trigger_name}' in run {run_id}")


@dataclass(frozen=True, slots=True)
class TriggerResult:
    """Result of firing a trigger."""

    trigger_name: str
    phases_unblocked: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "trigger_name": self.trigger_name,
            "phases_unblocked": list(self.phases_unblocked),
            "evidence_ids": [str(eid) for eid in self.evidence_ids],
        }


async def fire_trigger(
    *,
    run_id: UUID,
    trigger_name: str,
    actor_id: UUID,
    tenant_id: UUID,
    data: dict[str, Any] | None = None,
    conn: asyncpg.Connection,
) -> TriggerResult:
    """Fire an external trigger to unblock awaiting phases.

    Finds phases in WAITING_TRIGGER state for this run, checks if they
    have an await for the given trigger_name, and transitions them to
    IN_PROGRESS.

    Args:
        run_id: CharterRun ID.
        trigger_name: Name of the trigger event (e.g., 'candidate_files_dispute').
        actor_id: User who fired the trigger.
        tenant_id: Tenant ID.
        data: Optional payload data for the trigger event.
        conn: Database connection.

    Returns:
        TriggerResult with unblocked phase names and evidence IDs.

    Raises:
        TriggerNotFoundError: If no phase is waiting for this trigger.
    """
    # 1. Find phases in WAITING_TRIGGER state for this run
    waiting_rows = await fetch(
        """
        SELECT id, phase_name, workflow_name, trigger_names
        FROM phase_executions
        WHERE run_id = $1
          AND status = $2
        """,
        run_id,
        PhaseState.WAITING_TRIGGER.value,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not waiting_rows:
        raise TriggerNotFoundError(run_id, trigger_name)

    # 2. Filter to phases that are waiting on this specific trigger
    matching_phases: list[dict] = []
    for row in waiting_rows:
        trigger_names = row.get("trigger_names") or []
        if trigger_name in trigger_names:
            matching_phases.append(dict(row))

    if not matching_phases:
        raise TriggerNotFoundError(run_id, trigger_name)

    # 3. Transition matching phases from WAITING_TRIGGER to IN_PROGRESS
    unblocked: list[str] = []
    evidence_ids: list[UUID] = []

    for phase in matching_phases:
        phase_name = phase["phase_name"]
        workflow_name = phase["workflow_name"]

        # Validate transition
        if not is_valid_transition(PhaseState.WAITING_TRIGGER, PhaseState.IN_PROGRESS):
            raise InvalidPhaseTransition(
                from_state=PhaseState.WAITING_TRIGGER,
                to_state=PhaseState.IN_PROGRESS,
                phase_name=phase_name,
                run_id=str(run_id),
            )

        # Update phase status with optimistic locking:
        # Include current status in WHERE to prevent duplicate transitions
        # from concurrent trigger fires.
        result = await conn.execute(
            """
            UPDATE phase_executions
            SET status = $1
            WHERE run_id = $2
              AND workflow_name = $3
              AND phase_name = $4
              AND status = $5
            """,
            PhaseState.IN_PROGRESS.value,
            run_id,
            workflow_name,
            phase_name,
            PhaseState.WAITING_TRIGGER.value,
        )

        # If no rows affected, another concurrent call already transitioned
        if result == "UPDATE 0":
            continue

        # Record evidence
        evidence_data: dict[str, Any] = {
            "trigger_name": trigger_name,
            "workflow_name": workflow_name,
        }
        if data:
            evidence_data["trigger_data"] = data

        result = await record_phase_evidence(
            run_id=run_id,
            phase_name=phase_name,
            event_type=EvidenceEventType.TRIGGER_FIRED,
            actor_id=actor_id,
            tenant_id=tenant_id,
            data=evidence_data,
            conn=conn,
        )

        evidence_ids.append(result.evidence_id)
        unblocked.append(phase_name)

        logger.info(
            "Trigger '%s' fired for phase '%s' (run: %s, actor: %s)",
            trigger_name,
            phase_name,
            run_id,
            actor_id,
        )

    return TriggerResult(
        trigger_name=trigger_name,
        phases_unblocked=tuple(unblocked),
        evidence_ids=tuple(evidence_ids),
    )


async def has_trigger_fired(
    *,
    run_id: UUID,
    trigger_name: str,
    conn: asyncpg.Connection,
) -> bool:
    """Check if a trigger has been fired for a run.

    Used by require_eval to check `require await trigger_name` expressions.
    Queries evidence records for trigger.fired events matching the trigger name.

    Args:
        run_id: CharterRun ID.
        trigger_name: Name of the trigger to check.
        conn: Database connection.

    Returns:
        True if the trigger has been fired.
    """
    rows = await fetch(
        """
        SELECT id FROM evidences
        WHERE source_id = $1
          AND evidence_type = $2
          AND data->>'trigger_name' = $3
          AND is_deleted = false
        LIMIT 1
        """,
        str(run_id),
        f"runtime.{EvidenceEventType.TRIGGER_FIRED.value}",
        trigger_name,
        conn=conn,
        tenant_scope=TenantScope.DISABLED,
    )

    return len(rows) > 0
