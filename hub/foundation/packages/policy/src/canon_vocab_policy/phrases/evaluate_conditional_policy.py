"""Evaluate a policy with conditional predicates.

Complete vertical slice:
- Evaluates policy conditions based on context
- Applies predicates to determine applicability
- Returns evaluation result with matched conditions

Regulatory:
    - SOX Section 404 (Conditional controls)
    - SOC 2 CC1.1-1.4 (Control environment)
    - Risk-based policy application
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import PolicyDecision
from .evaluate_policy import EvaluatePolicySpecs, evaluate_policy

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["EvaluateConditionalPolicySpecs", "evaluate_conditional_policy"]


class EvaluateConditionalPolicySpecs(BaseModel):
    """Specs for evaluate conditional policy phrase."""

    # inputs
    policy_id: str
    facts: dict[str, Any] | None = None
    predicates: dict[str, Any] | None = None  # Conditions to check before evaluation
    context: dict[str, Any] | None = None
    # outputs (defaults required for instantiation with inputs only)
    applicable: bool = False
    decision: PolicyDecision | None = None
    predicates_matched: tuple[str, ...] = ()
    predicates_failed: tuple[str, ...] = ()
    evaluated_at: datetime | None = None
    reason: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(EvaluateConditionalPolicySpecs),
    inputs={"policy_id", "facts", "predicates", "context"},
    outputs={
        "applicable",
        "policy_id",
        "decision",
        "predicates_matched",
        "predicates_failed",
        "evaluated_at",
        "reason",
    },
)
async def evaluate_conditional_policy(
    options: EvaluateConditionalPolicySpecs,
    ctx: RequestContext,
) -> dict:
    """Evaluate a policy with conditional predicates.

    First checks if the policy applies based on predicates (conditions).
    If predicates pass, evaluates the policy. If predicates fail, the
    policy is considered non-applicable (not denied).

    Predicate types supported:
    - jurisdiction: Geographic jurisdiction code
    - action_type: Type of action being performed
    - risk_level: Risk classification (low/medium/high/critical)
    - data_classification: Data sensitivity level
    - actor_type: Type of actor (employee/contractor/vendor)

    Args:
        options: Options containing policy_id, facts, and predicates
        ctx: Request context with connection

    Returns:
        Dict with applicability, decision, and predicate results.
    """
    now = now_utc()
    policy_id = options.policy_id
    predicates = options.predicates or {}

    # Get policy definition to check its conditions
    row = await select_one(
        "policy_definitions",
        where={"policy_id": policy_id, "status": "active"},
        order_by="version DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    if not row:
        return {
            "applicable": False,
            "policy_id": policy_id,
            "decision": None,
            "predicates_matched": (),
            "predicates_failed": (),
            "evaluated_at": now,
            "reason": f"Policy '{policy_id}' not found or not active",
        }

    # Get policy conditions from definition
    policy_conditions = row.get("conditions", {}) or {}

    # Check predicates against policy conditions
    predicates_matched: list[str] = []
    predicates_failed: list[str] = []

    for key, expected in policy_conditions.items():
        actual = predicates.get(key)
        if actual is None:
            # Predicate not provided - policy may still apply with defaults
            continue
        if isinstance(expected, list):
            if actual in expected:
                predicates_matched.append(f"{key}={actual}")
            else:
                predicates_failed.append(f"{key}={actual} (expected one of {expected})")
        elif actual == expected:
            predicates_matched.append(f"{key}={actual}")
        else:
            predicates_failed.append(f"{key}={actual} (expected {expected})")

    # If any predicates failed, policy is not applicable
    if predicates_failed:
        return {
            "applicable": False,
            "policy_id": policy_id,
            "decision": None,
            "predicates_matched": tuple(predicates_matched),
            "predicates_failed": tuple(predicates_failed),
            "evaluated_at": now,
            "reason": f"Policy not applicable: {', '.join(predicates_failed)}",
        }

    # Predicates passed - evaluate the policy
    eval_opts = EvaluatePolicySpecs(
        policy_id=policy_id,
        facts=options.facts,
        context=options.context,
        raise_on_deny=False,
    )

    eval_result = await evaluate_policy(eval_opts, ctx)

    decision = eval_result.get("decision", PolicyDecision.DENY)

    return {
        "applicable": True,
        "policy_id": policy_id,
        "decision": decision,
        "predicates_matched": tuple(predicates_matched),
        "predicates_failed": (),
        "evaluated_at": now,
        "reason": (None if decision == PolicyDecision.ALLOW else "Policy evaluation denied"),
    }
