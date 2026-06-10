"""Phase completion cascade engine for charter runtime.

Handles the core orchestration logic: when a phase completes, cascade
to evaluate and potentially activate downstream phases.

The cascade engine:
1. Marks the current phase as completed
2. Records evidence of the completion
3. Finds downstream phases (phases that require this one)
4. Evaluates requires for each downstream phase
5. Activates phases whose requires are now satisfied
6. Checks if the entire workflow is complete

Regulatory Context:
    Phase cascading is the mechanism that enforces workflow order.
    Downstream phases cannot activate until their dependencies complete.
    This ensures proper sequencing (e.g., consent -> background check,
    notice -> waiting period -> adverse action).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from canon.db import TenantScope, fetch, select_one, update
from kron.utils import now_utc

from .phase_state import InvalidPhaseTransition, PhaseState, is_valid_transition
from .require_eval import evaluate_requires

if TYPE_CHECKING:
    import asyncpg

    from canon.dsl.compiler import CompiledCharter

__all__ = (
    "CascadeResult",
    "activate_phase",
    "find_downstream_phases",
    "is_workflow_complete",
    "on_phase_completed",
    "on_phase_failed",
)


class CascadeResult:
    """Result of a cascade operation.

    Attributes:
        activated_phases: Phase names that were activated.
        workflow_complete: True if all terminal phases are done.
        errors: Any errors encountered during cascade.
    """

    def __init__(
        self,
        activated_phases: list[str] | None = None,
        workflow_complete: bool = False,
        errors: list[str] | None = None,
    ):
        self.activated_phases = activated_phases or []
        self.workflow_complete = workflow_complete
        self.errors = errors or []

    def to_dict(self) -> dict:
        """Serialize for API response."""
        return {
            "activated_phases": self.activated_phases,
            "workflow_complete": self.workflow_complete,
            "errors": self.errors or None,
        }


async def on_phase_completed(
    run_id: UUID,
    workflow_name: str,
    phase_name: str,
    action_by_id: UUID,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
    *,
    action_notes: str | None = None,
    action_taken: str = "approve",
) -> CascadeResult:
    """Handle phase completion and cascade to downstream phases.

    This is the primary entry point for the cascade engine. Call this
    when a user completes an action on a phase.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        phase_name: Name of the phase that was completed.
        action_by_id: ID of the user who completed the action.
        compiled: The compiled charter for this run.
        conn: Database connection (must have tenant context).
        action_notes: Optional notes from the user.
        action_taken: The action taken (approve, reject, skip, etc.)

    Returns:
        CascadeResult with list of activated phases and workflow status.

    Raises:
        InvalidPhaseTransition: If phase is not in a valid state for completion.
    """
    result = CascadeResult()
    now = now_utc()

    # 1. Get current phase and validate state
    phase_row = await select_one(
        "phase_executions",
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if phase_row is None:
        result.errors.append(f"Phase '{phase_name}' not found in run {run_id}")
        return result

    current_status = phase_row.get("status")

    # Validate transition
    try:
        current_state = PhaseState(current_status)
    except ValueError:
        result.errors.append(f"Unknown phase status: {current_status}")
        return result

    if not is_valid_transition(current_state, PhaseState.COMPLETED):
        raise InvalidPhaseTransition(
            from_state=current_state,
            to_state=PhaseState.COMPLETED,
            phase_name=phase_name,
            run_id=str(run_id),
        )

    # 2. Mark phase as completed
    await update(
        "phase_executions",
        data={
            "status": PhaseState.COMPLETED.value,
            "action_at": now,
            "action_by_id": action_by_id,
            "action_notes": action_notes,
            "action_taken": action_taken,
        },
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # 3. Update CharterRun current_phase
    await update(
        "charter_runs",
        data={
            "current_phase": phase_name,
        },
        where={"id": run_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # 4. Find and evaluate downstream phases
    downstream = await find_downstream_phases(
        run_id=run_id,
        workflow_name=workflow_name,
        completed_phase=phase_name,
        compiled=compiled,
        conn=conn,
    )

    # 5. Activate phases whose requires are now satisfied
    for downstream_phase in downstream:
        try:
            activated = await _try_activate_phase(
                run_id=run_id,
                workflow_name=workflow_name,
                phase_name=downstream_phase,
                compiled=compiled,
                conn=conn,
            )
            if activated:
                result.activated_phases.append(downstream_phase)
        except Exception as e:
            result.errors.append(f"Failed to activate {downstream_phase}: {e}")

    # 6. Check if workflow is complete
    result.workflow_complete = await is_workflow_complete(
        run_id=run_id,
        workflow_name=workflow_name,
        compiled=compiled,
        conn=conn,
    )

    if result.workflow_complete:
        await _complete_charter_run(run_id, conn)

    return result


async def on_phase_failed(
    run_id: UUID,
    workflow_name: str,
    phase_name: str,
    action_by_id: UUID,
    conn: asyncpg.Connection,
    *,
    failure_reason: str | None = None,
    failed_gate: str | None = None,
) -> CascadeResult:
    """Handle phase failure.

    Unlike completion, failure does not cascade. It marks the phase
    as failed and may trigger workflow failure depending on charter config.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        phase_name: Name of the phase that failed.
        action_by_id: ID of the user/system that caused failure.
        conn: Database connection.
        failure_reason: Human-readable failure reason.
        failed_gate: Name of the gate that failed (if gate failure).

    Returns:
        CascadeResult (no activated phases on failure).
    """
    result = CascadeResult()
    now = now_utc()

    # Get current phase
    phase_row = await select_one(
        "phase_executions",
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if phase_row is None:
        result.errors.append(f"Phase '{phase_name}' not found")
        return result

    current_status = phase_row.get("status")

    try:
        current_state = PhaseState(current_status)
    except ValueError:
        result.errors.append(f"Unknown phase status: {current_status}")
        return result

    if not is_valid_transition(current_state, PhaseState.FAILED):
        raise InvalidPhaseTransition(
            from_state=current_state,
            to_state=PhaseState.FAILED,
            phase_name=phase_name,
            run_id=str(run_id),
        )

    # Mark phase as failed
    await update(
        "phase_executions",
        data={
            "status": PhaseState.FAILED.value,
            "action_at": now,
            "action_by_id": action_by_id,
            "action_taken": "reject",
            "failure_reason": failure_reason,
            "failed_gate": failed_gate,
        },
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Mark CharterRun as failed
    await update(
        "charter_runs",
        data={
            "status": "failed",
            "current_phase": phase_name,
            "failure_reason": failure_reason,
            "completed_at": now,
            "final_outcome": "failed",
        },
        where={"id": run_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return result


async def activate_phase(
    run_id: UUID,
    workflow_name: str,
    phase_name: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> bool:
    """Activate a phase - set to waiting_user and create grants.

    This transitions a phase from PENDING to WAITING_USER, making it
    appear in the assignee's inbox.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        phase_name: Name of the phase to activate.
        compiled: The compiled charter.
        conn: Database connection.

    Returns:
        True if phase was activated, False if already active or terminal.

    Raises:
        InvalidPhaseTransition: If current state doesn't allow activation.
    """
    now = now_utc()

    # Get current phase state
    phase_row = await select_one(
        "phase_executions",
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if phase_row is None:
        raise ValueError(f"Phase '{phase_name}' not found in run {run_id}")

    current_status = phase_row.get("status")
    current_state = PhaseState(current_status)

    # Skip if already active or terminal
    if current_state in (
        PhaseState.WAITING_USER,
        PhaseState.WAITING_TRIGGER,
        PhaseState.IN_PROGRESS,
        PhaseState.COMPLETED,
        PhaseState.SKIPPED,
        PhaseState.FAILED,
    ):
        return False

    # Get phase node for assignee info
    phase_node = _get_phase_node(compiled, workflow_name, phase_name)

    # Check for awaits - if phase has await directives, go to WAITING_TRIGGER
    has_awaits = phase_node is not None and len(phase_node.awaits) > 0
    target_state = PhaseState.WAITING_TRIGGER if has_awaits else PhaseState.WAITING_USER

    if not is_valid_transition(current_state, target_state):
        raise InvalidPhaseTransition(
            from_state=current_state,
            to_state=target_state,
            phase_name=phase_name,
            run_id=str(run_id),
        )

    # Build update data
    update_data: dict = {
        "status": target_state.value,
        "activated_at": now,
    }

    # Store trigger names if phase has awaits (for fire_trigger matching)
    if has_awaits:
        update_data["trigger_names"] = [a.trigger for a in phase_node.awaits]

    # Update phase status
    await update(
        "phase_executions",
        data=update_data,
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": phase_name,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return True


async def find_downstream_phases(
    run_id: UUID,
    workflow_name: str,
    completed_phase: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> list[str]:
    """Find phases that depend on the completed phase.

    A phase is downstream if it has `require completed_phase.passed`
    in its require list.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        completed_phase: Name of the phase that just completed.
        compiled: The compiled charter.
        conn: Database connection (unused but kept for consistency).

    Returns:
        List of downstream phase names.
    """
    downstream: list[str] = []

    # Find the workflow
    workflow = None
    for wf in compiled.ast.workflows:
        if wf.name == workflow_name:
            workflow = wf
            break

    if workflow is None:
        return downstream

    # Check each phase's requires
    for phase in workflow.phases:
        for require in phase.requires:
            # Check if this require references the completed phase
            from canon.dsl.ast import PhaseRefNode

            if isinstance(require.ref, PhaseRefNode):
                if require.ref.phase == completed_phase:
                    downstream.append(phase.name)
                    break  # Found a dependency, don't need to check more requires

    return downstream


async def is_workflow_complete(
    run_id: UUID,
    workflow_name: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> bool:
    """Check if the workflow has completed.

    A workflow is complete when all phases are in terminal states
    (completed, skipped, or failed) or when a terminal phase is completed.

    For simplicity in Phase 1, we check if all phases are terminal.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        compiled: The compiled charter.
        conn: Database connection.

    Returns:
        True if workflow is complete.
    """
    # Get all phase executions for this run/workflow
    rows = await fetch(
        """
        SELECT phase_name, status
        FROM phase_executions
        WHERE run_id = $1 AND workflow_name = $2
        """,
        run_id,
        workflow_name,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        return False

    terminal_statuses = {
        PhaseState.COMPLETED.value,
        PhaseState.SKIPPED.value,
        PhaseState.FAILED.value,
    }

    for row in rows:
        if row["status"] not in terminal_statuses:
            return False

    return True


async def _try_activate_phase(
    run_id: UUID,
    workflow_name: str,
    phase_name: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> bool:
    """Try to activate a phase if its requires are satisfied.

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        phase_name: Name of the phase to potentially activate.
        compiled: The compiled charter.
        conn: Database connection.

    Returns:
        True if phase was activated, False if requires not satisfied.
    """
    # Evaluate requires
    result = await evaluate_requires(
        run_id=run_id,
        workflow_name=workflow_name,
        phase_name=phase_name,
        compiled=compiled,
        conn=conn,
    )

    if not result.satisfied:
        return False

    # All requires satisfied - activate the phase
    return await activate_phase(
        run_id=run_id,
        workflow_name=workflow_name,
        phase_name=phase_name,
        compiled=compiled,
        conn=conn,
    )


async def _complete_charter_run(
    run_id: UUID,
    conn: asyncpg.Connection,
) -> None:
    """Mark a CharterRun as completed.

    Called when all phases in the workflow have reached terminal states.

    Args:
        run_id: The CharterRun ID.
        conn: Database connection.
    """
    now = now_utc()

    await update(
        "charter_runs",
        data={
            "status": "completed",
            "completed_at": now,
            "final_outcome": "approved",
        },
        where={"id": run_id},
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )


def _get_phase_node(
    compiled: CompiledCharter,
    workflow_name: str,
    phase_name: str,
):
    """Get PhaseNode from compiled charter.

    Args:
        compiled: The compiled charter.
        workflow_name: Name of the workflow.
        phase_name: Name of the phase.

    Returns:
        PhaseNode if found, None otherwise.
    """
    for workflow in compiled.ast.workflows:
        if workflow.name == workflow_name:
            for phase in workflow.phases:
                if phase.name == phase_name:
                    return phase
    return None
