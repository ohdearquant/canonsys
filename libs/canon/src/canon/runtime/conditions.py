"""Condition evaluation for when_blocks and situations in charter runtime.

Evaluates predicate-based conditions from compiled charters:
- PredicateNode: field operator value comparisons (==, !=, >, <, >=, <=)
- WhenBlockNode: inline conditional blocks within phases
- SituationNode: jurisdictional/contextual constraints at charter level

The context is a simple dict mapping field names to runtime values,
typically sourced from CharterRun.run_context or environment.

Design decisions:
- Predicate evaluation is pure/sync (no DB, no I/O)
- When blocks add conditional behaviors to phases; they don't change structure
- Situations apply at workflow level (additional requires, waiting periods)
- Missing context fields result in unmatched predicates (fail-open for safety)

Regulatory Context:
    When blocks enable jurisdiction-specific compliance steps.
    For example, NYC LL144 requires AEDT disclosure that other
    jurisdictions do not. Situations provide the mechanism to
    declare these conditional requirements in the charter DSL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from canon.dsl.ast import PredicateNode, SituationNode, WaitingPeriodNode, WhenBlockNode

__all__ = (
    "ConditionResult",
    "SituationOverrides",
    "WhenBlockResult",
    "evaluate_predicate",
    "evaluate_situations",
    "evaluate_when_block",
    "evaluate_when_blocks",
)


# -- Operator dispatch table --------------------------------------------------

_OPERATORS: dict[str, Any] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


# -- Result types -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConditionResult:
    """Result of evaluating a single predicate.

    Attributes:
        matched: Whether the predicate evaluated to True.
        predicate_field: The field name from the predicate.
        predicate_operator: The comparison operator.
        predicate_value: The expected value from the predicate.
        actual_value: The actual value from the runtime context, or None if missing.
        reason: Human-readable explanation when not matched.
    """

    matched: bool
    predicate_field: str
    predicate_operator: str
    predicate_value: str | int | float | bool
    actual_value: Any | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class WhenBlockResult:
    """Result of evaluating a when_block.

    If matched, the additional requires/actions/awaits should be applied
    to the phase at activation time.

    Attributes:
        condition: The underlying predicate evaluation result.
        matched: True if the when_block predicate matched.
        block: The original WhenBlockNode (for access to requires/actions/awaits).
    """

    condition: ConditionResult
    matched: bool
    block: WhenBlockNode


@dataclass(frozen=True, slots=True)
class SituationOverrides:
    """Aggregated result of evaluating all situation nodes.

    Collects all additional requires and waiting period overrides
    from situations whose predicates matched the runtime context.

    Attributes:
        matched_situations: Situation nodes that matched.
        additional_requires: RequireNodes from all matched situations.
        waiting_period_override: The most restrictive waiting period, or None.
        condition_results: Per-situation evaluation details.
    """

    matched_situations: tuple[SituationNode, ...] = ()
    additional_requires: tuple = ()  # tuple[RequireNode, ...]
    waiting_period_override: WaitingPeriodNode | None = None
    condition_results: tuple[ConditionResult, ...] = ()


# -- Core evaluation functions ------------------------------------------------


def _coerce_for_comparison(
    actual: Any,
    expected: str | int | float | bool,
) -> tuple[Any, Any]:
    """Coerce actual value to match expected type for comparison.

    The DSL parser produces typed values (str, int, float, bool).
    Runtime context values may be strings. We coerce the actual value
    to the expected type when possible.

    Args:
        actual: The runtime value from context.
        expected: The value from the predicate (already typed by parser).

    Returns:
        Tuple of (coerced_actual, expected) ready for comparison.
    """
    if actual is None:
        return actual, expected

    # If types already match, no coercion needed
    if type(actual) is type(expected):
        return actual, expected

    # Try coercing actual to expected's type
    try:
        if isinstance(expected, bool):
            # Handle string -> bool
            if isinstance(actual, str):
                return actual.lower() in ("true", "1", "yes"), expected
            return bool(actual), expected
        elif isinstance(expected, int):
            return int(actual), expected
        elif isinstance(expected, float):
            return float(actual), expected
        elif isinstance(expected, str):
            return str(actual), expected
    except (ValueError, TypeError):
        pass

    # Cannot coerce - return as-is (comparison will likely fail)
    return actual, expected


def evaluate_predicate(
    predicate: PredicateNode,
    context: dict[str, Any],
) -> ConditionResult:
    """Evaluate a predicate against a runtime context dict.

    Context is a dict like {"jurisdiction": "NYC", "dispute_status": "FILED"}.

    Supported operators: ==, !=, >, <, >=, <=

    If the predicate field is not present in context, the result is unmatched.
    If the operator is unknown, the result is unmatched with a reason.

    Args:
        predicate: The PredicateNode from the AST.
        context: Runtime context dict mapping field names to values.

    Returns:
        ConditionResult with matched=True/False and evaluation details.
    """
    field_name = predicate.field
    operator = predicate.operator
    expected = predicate.value

    # Check for unknown operator
    op_fn = _OPERATORS.get(operator)
    if op_fn is None:
        return ConditionResult(
            matched=False,
            predicate_field=field_name,
            predicate_operator=operator,
            predicate_value=expected,
            actual_value=None,
            reason=f"Unknown operator: {operator}",
        )

    # Check if field exists in context
    if field_name not in context:
        return ConditionResult(
            matched=False,
            predicate_field=field_name,
            predicate_operator=operator,
            predicate_value=expected,
            actual_value=None,
            reason=f"Field '{field_name}' not found in context",
        )

    actual = context[field_name]

    # Coerce types for comparison
    coerced_actual, coerced_expected = _coerce_for_comparison(actual, expected)

    # Evaluate
    try:
        matched = op_fn(coerced_actual, coerced_expected)
    except TypeError:
        # Incompatible types for comparison (e.g., str > int without coercion)
        return ConditionResult(
            matched=False,
            predicate_field=field_name,
            predicate_operator=operator,
            predicate_value=expected,
            actual_value=actual,
            reason=(
                f"Type mismatch: cannot compare "
                f"{type(actual).__name__} with {type(expected).__name__}"
            ),
        )

    reason = None
    if not matched:
        reason = (
            f"Predicate not satisfied: {field_name} {operator} {expected!r} (actual: {actual!r})"
        )

    return ConditionResult(
        matched=matched,
        predicate_field=field_name,
        predicate_operator=operator,
        predicate_value=expected,
        actual_value=actual,
        reason=reason,
    )


def evaluate_when_block(
    block: WhenBlockNode,
    context: dict[str, Any],
) -> WhenBlockResult:
    """Evaluate a when_block's predicate against runtime context.

    If the predicate matches, the block's additional requires, actions,
    and awaits should be applied to the phase.

    This is a synchronous, pure function - no DB access needed.
    The caller (cascade engine) is responsible for applying the
    additional behaviors.

    Args:
        block: The WhenBlockNode from the phase AST.
        context: Runtime context dict.

    Returns:
        WhenBlockResult with match status and the original block
        for access to conditional behaviors.
    """
    condition = evaluate_predicate(block.predicate, context)

    return WhenBlockResult(
        condition=condition,
        matched=condition.matched,
        block=block,
    )


def evaluate_when_blocks(
    blocks: tuple[WhenBlockNode, ...],
    context: dict[str, Any],
) -> list[WhenBlockResult]:
    """Evaluate all when_blocks for a phase.

    Convenience function that evaluates each block and returns all results.
    Multiple blocks can match simultaneously.

    Args:
        blocks: Tuple of WhenBlockNode from PhaseNode.when_blocks.
        context: Runtime context dict.

    Returns:
        List of WhenBlockResult for each block (matched or not).
    """
    return [evaluate_when_block(block, context) for block in blocks]


def evaluate_situations(
    situations: tuple[SituationNode, ...],
    context: dict[str, Any],
) -> SituationOverrides:
    """Evaluate all situation nodes against runtime context.

    Collects additional requires and waiting period overrides from
    all situations whose predicates match. If multiple situations
    match and have waiting periods, the most restrictive (longest
    minimum waiting period) is used.

    Args:
        situations: Tuple of SituationNode from CompiledCharter.situations.
        context: Runtime context dict (e.g., {"jurisdiction": "NYC"}).

    Returns:
        SituationOverrides with aggregated additional requirements
        and waiting period override.
    """
    matched: list[SituationNode] = []
    all_requires: list = []
    condition_results: list[ConditionResult] = []
    best_waiting_period: WaitingPeriodNode | None = None

    for situation in situations:
        result = evaluate_predicate(situation.predicate, context)
        condition_results.append(result)

        if result.matched:
            matched.append(situation)

            # Collect additional requires
            all_requires.extend(situation.requires)

            # Track waiting period - keep the most restrictive
            if situation.waiting_period is not None:
                if best_waiting_period is None:
                    best_waiting_period = situation.waiting_period
                else:
                    # Most restrictive = longest minimum waiting period
                    if situation.waiting_period.min_value > best_waiting_period.min_value:
                        best_waiting_period = situation.waiting_period

    return SituationOverrides(
        matched_situations=tuple(matched),
        additional_requires=tuple(all_requires),
        waiting_period_override=best_waiting_period,
        condition_results=tuple(condition_results),
    )
