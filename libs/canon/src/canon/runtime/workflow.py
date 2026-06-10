"""Workflow lifecycle operations - start and complete charter runs.

This module handles:
1. Starting new workflows (creating CharterRun and PhaseExecutions)
2. Completing charter runs (marking as completed/failed/cancelled)
3. Activating entry phases (phases with no dependencies)

Design decisions:
- All phases are created upfront in PENDING state
- Entry phases (no requires) are immediately activated to WAITING_USER
- Completion cascades are handled separately (in cascade.py)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from canon.dsl.ast import PhaseRefNode, RequireNode
from canon.entities.charter import CharterRunStatus, PhaseStatus

from .registry import get_compiled_charter

if TYPE_CHECKING:
    import asyncpg

    from canon.dsl import CompiledCharter

logger = logging.getLogger(__name__)


class WorkflowNotFoundError(Exception):
    """Raised when a workflow is not found in a charter."""

    def __init__(self, workflow_name: str, charter_name: str) -> None:
        self.workflow_name = workflow_name
        self.charter_name = charter_name
        super().__init__(f"Workflow '{workflow_name}' not found in charter '{charter_name}'")


class WorkflowAlreadyActiveError(Exception):
    """Raised when trying to start a workflow that's already active."""

    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        super().__init__(f"Workflow already active: {run_id}")


def _get_requires_phases(requires: tuple[RequireNode, ...]) -> list[str]:
    """Extract phase names from require clauses.

    Args:
        requires: Tuple of RequireNode from PhaseNode.

    Returns:
        List of phase names that must complete before this phase.
    """
    phase_deps: list[str] = []
    for req in requires:
        if isinstance(req.ref, PhaseRefNode):
            # require other_phase.passed -> depends on other_phase
            phase_deps.append(req.ref.phase)
    return phase_deps


def _get_entry_phases(
    compiled: CompiledCharter,
    workflow_name: str,
) -> list[str]:
    """Get phases that have no dependencies (entry points).

    Entry phases can be activated immediately when workflow starts.

    Args:
        compiled: CompiledCharter with workflow definitions.
        workflow_name: Name of workflow to analyze.

    Returns:
        List of phase names that have no require dependencies.
    """
    entry_phases: list[str] = []

    # Find the workflow
    for workflow in compiled.ast.workflows:
        if workflow.name == workflow_name:
            for phase in workflow.phases:
                deps = _get_requires_phases(phase.requires)
                if not deps:
                    entry_phases.append(phase.name)
            break

    return entry_phases


def _get_phase_role(
    compiled: CompiledCharter,
    workflow_name: str,
    phase_name: str,
) -> str | None:
    """Get the role assigned to a phase from charter roles.

    Looks up the role definition that includes this phase's actions.

    Args:
        compiled: CompiledCharter with role definitions.
        workflow_name: Workflow containing the phase.
        phase_name: Phase name to look up.

    Returns:
        Role name if found, None otherwise.
    """
    # First get the phase's actions
    phase_actions: set[str] = set()
    for workflow in compiled.ast.workflows:
        if workflow.name == workflow_name:
            for phase in workflow.phases:
                if phase.name == phase_name:
                    for action in phase.actions:
                        phase_actions.add(action.call.name)
                    break
            break

    # Now find which role has permission for these actions
    for role in compiled.roles:
        role_actions = set(role.actions)
        if phase_actions & role_actions:  # Any overlap
            return role.name

    # Default: use phase name as role hint (e.g., "hm_approval" -> "hiring_manager")
    # This is a fallback for charters without explicit role definitions
    return None


async def start_workflow(
    charter_id: UUID,
    subject_id: UUID,
    related_entity_type: str,
    related_entity_id: UUID,
    workflow_name: str,
    initiated_by_id: UUID,
    tenant_id: UUID,
    conn: asyncpg.Connection,
    *,
    run_context: dict | None = None,
) -> UUID:
    """Start a new charter workflow.

    Creates a CharterRun and all PhaseExecutions in PENDING state,
    then activates phases with no requires (entry points).

    Args:
        charter_id: Charter UUID to execute.
        subject_id: Person UUID this workflow is about.
        related_entity_type: Type of related entity (e.g., "exception_offer").
        related_entity_id: UUID of the related entity.
        workflow_name: Name of workflow within the charter.
        initiated_by_id: User UUID who initiated this workflow.
        tenant_id: Tenant UUID for isolation.
        conn: Database connection (should be in transaction).
        run_context: Optional initial context dict.

    Returns:
        UUID of the created CharterRun.

    Raises:
        CharterNotFoundError: If charter doesn't exist.
        WorkflowNotFoundError: If workflow doesn't exist in charter.
    """
    now = datetime.now(UTC)

    # Load and compile charter
    compiled = await get_compiled_charter(charter_id, conn)

    # Verify workflow exists
    if workflow_name not in compiled.phase_order:
        raise WorkflowNotFoundError(workflow_name, compiled.name)

    # Get phase order and workflow definition
    phase_order = compiled.phase_order[workflow_name]

    # Find the workflow AST
    workflow_ast = None
    for wf in compiled.ast.workflows:
        if wf.name == workflow_name:
            workflow_ast = wf
            break

    if not workflow_ast:
        raise WorkflowNotFoundError(workflow_name, compiled.name)

    # Create CharterRun
    run_id = uuid4()
    await conn.execute(
        """
        INSERT INTO charter_runs (
            id, tenant_id, charter_id, charter_snapshot_hash,
            subject_id, related_entity_type, related_entity_id,
            current_workflow, status,
            initiated_by_id, initiated_at, started_at,
            run_context, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            $8, $9,
            $10, $11, $12,
            $13, $14, $15
        )
        """,
        run_id,
        tenant_id,
        charter_id,
        None,  # charter_snapshot_hash - could compute from content_hash
        subject_id,
        related_entity_type,
        related_entity_id,
        workflow_name,
        CharterRunStatus.ACTIVE,
        initiated_by_id,
        now,
        now,
        run_context or {},
        now,
        now,
    )

    logger.info(
        "Created CharterRun %s for charter %s workflow %s",
        run_id,
        charter_id,
        workflow_name,
    )

    # Create PhaseExecutions for all phases (initially PENDING)
    phase_map: dict[str, tuple] = {}  # phase_name -> (phase_ast, sequence)
    for seq, phase_name in enumerate(phase_order):
        for phase in workflow_ast.phases:
            if phase.name == phase_name:
                phase_map[phase_name] = (phase, seq)
                break

    for phase_name, (phase_ast, sequence) in phase_map.items():
        requires_phases = _get_requires_phases(phase_ast.requires)
        assignee_role = _get_phase_role(compiled, workflow_name, phase_name)

        phase_exec_id = uuid4()
        await conn.execute(
            """
            INSERT INTO phase_executions (
                id, tenant_id, run_id,
                workflow_name, phase_name, sequence,
                requires_phases, assignee_role, status,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8, $9,
                $10, $11
            )
            """,
            phase_exec_id,
            tenant_id,
            run_id,
            workflow_name,
            phase_name,
            sequence,
            requires_phases,
            assignee_role,
            PhaseStatus.PENDING,
            now,
            now,
        )

    logger.debug("Created %d PhaseExecutions for run %s", len(phase_map), run_id)

    # Activate entry phases (phases with no requires)
    entry_phases = _get_entry_phases(compiled, workflow_name)
    for phase_name in entry_phases:
        await _activate_phase(run_id, phase_name, now, conn)

    logger.info(
        "Started workflow %s with %d entry phases: %s",
        workflow_name,
        len(entry_phases),
        entry_phases,
    )

    return run_id


async def _activate_phase(
    run_id: UUID,
    phase_name: str,
    now: datetime,
    conn: asyncpg.Connection,
) -> None:
    """Activate a phase - set to WAITING_USER state.

    Internal function called when a phase's dependencies are satisfied.

    Args:
        run_id: CharterRun UUID.
        phase_name: Phase to activate.
        now: Current timestamp.
        conn: Database connection.
    """
    await conn.execute(
        """
        UPDATE phase_executions
        SET status = $1, activated_at = $2, updated_at = $3
        WHERE run_id = $4 AND phase_name = $5
        """,
        PhaseStatus.WAITING_USER,
        now,
        now,
        run_id,
        phase_name,
    )
    logger.debug("Activated phase %s for run %s", phase_name, run_id)


async def complete_charter_run(
    run_id: UUID,
    conn: asyncpg.Connection,
    *,
    outcome: str = "completed",
    failure_reason: str | None = None,
) -> None:
    """Mark a charter run as completed.

    Sets the run status to terminal state and records completion time.

    Args:
        run_id: CharterRun UUID.
        conn: Database connection.
        outcome: Final outcome (completed, cancelled, failed).
        failure_reason: Reason if outcome is failed.
    """
    now = datetime.now(UTC)

    # Map outcome to status
    status_map = {
        "completed": CharterRunStatus.COMPLETED,
        "cancelled": CharterRunStatus.CANCELLED,
        "failed": CharterRunStatus.FAILED,
        "approved": CharterRunStatus.COMPLETED,  # approved is a completed variant
        "rejected": CharterRunStatus.COMPLETED,  # rejected is a completed variant
    }
    status = status_map.get(outcome, CharterRunStatus.COMPLETED)

    await conn.execute(
        """
        UPDATE charter_runs
        SET status = $1, completed_at = $2, final_outcome = $3,
            failure_reason = $4, updated_at = $5
        WHERE id = $6
        """,
        status,
        now,
        outcome,
        failure_reason,
        now,
        run_id,
    )

    logger.info("Completed CharterRun %s with outcome: %s", run_id, outcome)


async def cancel_charter_run(
    run_id: UUID,
    cancelled_by_id: UUID,
    conn: asyncpg.Connection,
    *,
    reason: str | None = None,
) -> None:
    """Cancel an active charter run.

    Sets all pending/waiting phases to SKIPPED and marks run as CANCELLED.

    Args:
        run_id: CharterRun UUID.
        cancelled_by_id: User who cancelled.
        conn: Database connection.
        reason: Optional cancellation reason.
    """
    now = datetime.now(UTC)

    # Skip all non-terminal phases
    await conn.execute(
        """
        UPDATE phase_executions
        SET status = $1, action_taken = 'cancelled',
            action_by_id = $2, action_at = $3, updated_at = $4
        WHERE run_id = $5
          AND status NOT IN ($6, $7, $8)
        """,
        PhaseStatus.SKIPPED,
        cancelled_by_id,
        now,
        now,
        run_id,
        PhaseStatus.COMPLETED,
        PhaseStatus.FAILED,
        PhaseStatus.SKIPPED,
    )

    # Mark run as cancelled
    await complete_charter_run(
        run_id,
        conn,
        outcome="cancelled",
        failure_reason=reason,
    )

    logger.info("Cancelled CharterRun %s by user %s", run_id, cancelled_by_id)


async def get_run_status(
    run_id: UUID,
    conn: asyncpg.Connection,
) -> dict:
    """Get the current status of a charter run.

    Returns a summary of the run including phase statuses.

    Args:
        run_id: CharterRun UUID.
        conn: Database connection.

    Returns:
        Dict with run status, phase counts, current phase info.
    """
    # Get run info
    run_row = await conn.fetchrow(
        """
        SELECT id, status, current_workflow, current_phase,
               initiated_at, started_at, completed_at, final_outcome
        FROM charter_runs
        WHERE id = $1
        """,
        run_id,
    )

    if not run_row:
        return {"error": "Run not found"}

    # Get phase status counts
    phase_counts = await conn.fetch(
        """
        SELECT status, COUNT(*) as count
        FROM phase_executions
        WHERE run_id = $1
        GROUP BY status
        """,
        run_id,
    )

    status_counts = {row["status"]: row["count"] for row in phase_counts}

    # Get waiting phases (in inbox)
    waiting_phases = await conn.fetch(
        """
        SELECT phase_name, assignee_role, activated_at
        FROM phase_executions
        WHERE run_id = $1 AND status = $2
        ORDER BY sequence
        """,
        run_id,
        PhaseStatus.WAITING_USER,
    )

    return {
        "run_id": run_row["id"],
        "status": run_row["status"],
        "current_workflow": run_row["current_workflow"],
        "current_phase": run_row["current_phase"],
        "initiated_at": run_row["initiated_at"],
        "started_at": run_row["started_at"],
        "completed_at": run_row["completed_at"],
        "final_outcome": run_row["final_outcome"],
        "phase_counts": status_counts,
        "waiting_phases": [
            {
                "phase_name": p["phase_name"],
                "assignee_role": p["assignee_role"],
                "waiting_since": p["activated_at"],
            }
            for p in waiting_phases
        ],
    }


async def is_workflow_complete(
    run_id: UUID,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> bool:
    """Check if all phases in a workflow are complete.

    A workflow is complete when all terminal phases have completed.
    Terminal phases are those with no downstream dependencies.

    Args:
        run_id: CharterRun UUID.
        compiled: CompiledCharter for phase analysis.
        conn: Database connection.

    Returns:
        True if workflow is complete.
    """
    # Get the run's workflow
    row = await conn.fetchrow(
        "SELECT current_workflow FROM charter_runs WHERE id = $1",
        run_id,
    )
    if not row:
        return False

    workflow_name = row["current_workflow"]
    if not workflow_name:
        return False

    # Check if all phases are in terminal state
    pending_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM phase_executions
        WHERE run_id = $1
          AND status NOT IN ($2, $3, $4)
        """,
        run_id,
        PhaseStatus.COMPLETED,
        PhaseStatus.FAILED,
        PhaseStatus.SKIPPED,
    )

    return pending_count == 0
