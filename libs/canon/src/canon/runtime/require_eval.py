"""Require expression evaluator for charter runtime.

Evaluates `require` expressions from compiled charters to determine
if a phase's preconditions are satisfied. Supports:

- Phase completion references: `require other_phase.passed`
- Feature gate calls: `require verify_consent("scope")`  (future)
- Builtin predicates: `require all_phases_passed`  (future)
- Await references: `require await event_name`  (future)

Regulatory Context:
    Require expressions enforce sequential compliance workflows.
    A phase cannot activate until all its requires are satisfied.
    This ensures proper order of operations (e.g., consent before
    background check, notice before adverse action).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from canon.db import TenantScope, select_one
from canon.dsl.ast import (
    AwaitRefNode,
    BuiltinRefNode,
    FeatureCallNode,
    PhaseRefNode,
    RequireNode,
)

if TYPE_CHECKING:
    import asyncpg

    from canon.dsl.compiler import CompiledCharter

__all__ = (
    "RequireResult",
    "evaluate_requires",
    "evaluate_single_require",
)


@dataclass(frozen=True, slots=True)
class RequireResult:
    """Result of evaluating require expressions.

    Attributes:
        satisfied: True if all requires passed.
        unsatisfied: List of require expressions that are not yet satisfied.
        details: Per-require evaluation details for debugging/audit.
    """

    satisfied: bool
    unsatisfied: tuple[str, ...]
    details: dict[str, dict] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Default to empty dict if not provided (frozen dataclass workaround)
        if self.details is None:
            object.__setattr__(self, "details", {})


async def evaluate_requires(
    run_id: UUID,
    workflow_name: str,
    phase_name: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> RequireResult:
    """Evaluate all require conditions for a phase.

    Iterates through the phase's require nodes and evaluates each.
    Returns early on first unsatisfied require (fail-fast).

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow containing the phase.
        phase_name: Name of the phase to evaluate requires for.
        compiled: The compiled charter with AST.
        conn: Database connection (must have tenant context).

    Returns:
        RequireResult indicating if all requires are satisfied.

    Raises:
        ValueError: If phase not found in compiled charter.
    """
    # Find the phase node in the compiled charter
    phase_node = _get_phase_node(compiled, workflow_name, phase_name)
    if phase_node is None:
        raise ValueError(f"Phase '{phase_name}' not found in workflow '{workflow_name}'")

    unsatisfied: list[str] = []
    details: dict[str, dict] = {}

    for require_node in phase_node.requires:
        result = await evaluate_single_require(
            run_id=run_id,
            workflow_name=workflow_name,
            require_node=require_node,
            compiled=compiled,
            conn=conn,
        )
        details[result["expr"]] = result

        if not result["satisfied"]:
            unsatisfied.append(result["expr"])

    return RequireResult(
        satisfied=len(unsatisfied) == 0,
        unsatisfied=tuple(unsatisfied),
        details=details,
    )


async def evaluate_single_require(
    run_id: UUID,
    workflow_name: str,
    require_node: RequireNode,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> dict:
    """Evaluate a single require expression.

    Dispatches to the appropriate evaluator based on the require type:
    - PhaseRefNode: Check if referenced phase is completed
    - FeatureCallNode: Evaluate feature gate (future)
    - BuiltinRefNode: Evaluate builtin predicate (future)
    - AwaitRefNode: Check if trigger has fired (future)

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        require_node: The RequireNode from the AST.
        compiled: The compiled charter.
        conn: Database connection.

    Returns:
        Dict with keys: expr (str), satisfied (bool), reason (str|None).
    """
    ref = require_node.ref

    if isinstance(ref, PhaseRefNode):
        return await _evaluate_phase_ref(run_id, workflow_name, ref, conn)

    elif isinstance(ref, FeatureCallNode):
        return await _evaluate_feature_call(ref)

    elif isinstance(ref, BuiltinRefNode):
        return await _evaluate_builtin_ref(run_id, workflow_name, ref, compiled, conn)

    elif isinstance(ref, AwaitRefNode):
        return await _evaluate_await_ref(run_id, ref, conn)

    else:
        # Unknown require type - fail safe
        return {
            "expr": str(ref),
            "satisfied": False,
            "reason": f"Unknown require type: {type(ref).__name__}",
        }


async def _evaluate_phase_ref(
    run_id: UUID,
    workflow_name: str,
    ref: PhaseRefNode,
    conn: asyncpg.Connection,
) -> dict:
    """Evaluate a phase completion reference.

    Checks if the referenced phase has reached the required state.

    Supported conditions:
    - `phase_name.passed` - Phase status is 'completed'
    - `phase_name.complete` - Phase status is 'completed' (alias)

    Args:
        run_id: The CharterRun ID.
        workflow_name: Name of the workflow.
        ref: The PhaseRefNode with phase name and condition.
        conn: Database connection.

    Returns:
        Evaluation result dict.
    """
    expr = f"{ref.phase}.{ref.condition}"

    # Determine required status based on condition
    if ref.condition in ("passed", "complete"):
        required_status = "completed"
    else:
        # Unknown condition - fail safe
        return {
            "expr": expr,
            "satisfied": False,
            "reason": f"Unknown phase condition: {ref.condition}",
        }

    # Query for the referenced phase execution
    row = await select_one(
        "phase_executions",
        where={
            "run_id": run_id,
            "workflow_name": workflow_name,
            "phase_name": ref.phase,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if row is None:
        return {
            "expr": expr,
            "satisfied": False,
            "reason": f"Phase '{ref.phase}' execution record not found",
        }

    actual_status = row.get("status")
    satisfied = actual_status == required_status

    return {
        "expr": expr,
        "satisfied": satisfied,
        "reason": (
            None
            if satisfied
            else f"Phase status is '{actual_status}', expected '{required_status}'"
        ),
        "actual_status": actual_status,
    }


async def _evaluate_feature_call(ref: FeatureCallNode) -> dict:
    """Evaluate a feature gate call.

    Feature gates are vocabulary features that return a boolean result.
    Examples: verify_consent("scope"), require_er_clearance()

    Note: Full implementation requires binding to the phrase executor.
    For Phase 1, we return unsatisfied with a note.

    Args:
        ref: The FeatureCallNode with feature name and arguments.

    Returns:
        Evaluation result dict.
    """
    # Build expression string for display
    args_str = ", ".join(
        f"{arg.name}={arg.value!r}" if arg.name else repr(arg.value) for arg in ref.args
    )
    expr = f"{ref.name}({args_str})"

    # Phase 1: Feature gate evaluation not yet implemented
    # Return unsatisfied to block progression until implementation
    return {
        "expr": expr,
        "satisfied": False,
        "reason": "Feature gate evaluation not yet implemented",
        "feature_name": ref.name,
    }


async def _evaluate_builtin_ref(
    run_id: UUID,
    workflow_name: str,
    ref: BuiltinRefNode,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> dict:
    """Evaluate a builtin predicate.

    Builtins are system-defined predicates:
    - all_phases_passed: All preceding phases in workflow are completed
    - any_phase_failed: At least one phase has failed (for error handling)

    Args:
        ref: The BuiltinRefNode with predicate name.
        Other args: Context for evaluation.

    Returns:
        Evaluation result dict.
    """
    expr = ref.name

    if ref.name == "all_phases_passed":
        # Check if all phases before this one are completed
        # This requires knowing the phase order from compiled charter
        # For Phase 1, return unsatisfied
        return {
            "expr": expr,
            "satisfied": False,
            "reason": "Builtin predicate 'all_phases_passed' not yet implemented",
        }

    elif ref.name == "any_phase_failed":
        return {
            "expr": expr,
            "satisfied": False,
            "reason": "Builtin predicate 'any_phase_failed' not yet implemented",
        }

    else:
        return {
            "expr": expr,
            "satisfied": False,
            "reason": f"Unknown builtin predicate: {ref.name}",
        }


async def _evaluate_await_ref(
    run_id: UUID,
    ref: AwaitRefNode,
    conn: asyncpg.Connection,
) -> dict:
    """Evaluate an await trigger reference.

    Await triggers are external events that must fire before the phase
    can proceed. Examples: candidate_files_dispute, board_notification_acknowledged

    This checks if the trigger event has been recorded for this run
    by querying evidence records for trigger.fired events.

    Args:
        run_id: The CharterRun ID.
        ref: The AwaitRefNode with trigger name.
        conn: Database connection.

    Returns:
        Evaluation result dict.
    """
    from .trigger import has_trigger_fired

    expr = f"await {ref.trigger}"

    fired = await has_trigger_fired(
        run_id=run_id,
        trigger_name=ref.trigger,
        conn=conn,
    )

    return {
        "expr": expr,
        "satisfied": fired,
        "reason": None if fired else f"Trigger '{ref.trigger}' has not been fired",
        "trigger_name": ref.trigger,
    }


def _get_phase_node(
    compiled: CompiledCharter,
    workflow_name: str,
    phase_name: str,
):
    """Get PhaseNode from compiled charter by workflow and phase name.

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
