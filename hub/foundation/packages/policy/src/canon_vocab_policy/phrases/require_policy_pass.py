"""Require that a policy evaluation passes.

Complete vertical slice:
- Evaluates policy using existing evaluate_policy phrase
- Raises PolicyDeniedError if policy denies
- Returns satisfied: bool for gate pattern

Regulatory: PRD-001 Section B - All decisions must pass policy
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import PolicyDeniedError
from ..types import PolicyDecision
from .evaluate_policy import EvaluatePolicySpecs, evaluate_policy

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequirePolicyPassSpecs", "require_policy_pass"]


class RequirePolicyPassSpecs(BaseModel):
    """Specs for require policy pass phrase."""

    # inputs
    policy_id: str
    facts: dict[str, Any] | None = None
    derived: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    # outputs
    satisfied: bool = False
    policy_evaluation_id: UUID | None = None
    evaluated_at: datetime | None = None
    verdict: PolicyDecision | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(RequirePolicyPassSpecs),
    inputs={"policy_id", "facts", "derived", "context"},
    outputs={
        "satisfied",
        "policy_id",
        "policy_evaluation_id",
        "evaluated_at",
        "verdict",
    },
)
async def require_policy_pass(
    options: RequirePolicyPassSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a policy evaluation passes.

    Gate pattern wrapper around evaluate_policy. Blocks execution
    if policy denies.

    Args:
        options: Options containing policy_id and facts to evaluate.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if policy allows.

    Raises:
        PolicyDeniedError: If policy evaluation returns DENY.
    """
    # Evaluate policy using existing phrase
    eval_opts = EvaluatePolicySpecs(
        policy_id=options.policy_id,
        facts=options.facts,
        derived=options.derived,
        context=options.context,
        raise_on_deny=False,  # We handle deny ourselves
    )

    result = await evaluate_policy(eval_opts, ctx)

    decision = result.get("decision", PolicyDecision.DENY)
    evaluated_at = result.get("evaluated_at", now_utc())
    deny_reasons = result.get("deny_reasons", ())
    conditions_missing = result.get("conditions_missing", ())

    if decision == PolicyDecision.DENY:
        raise PolicyDeniedError(
            policy_id=options.policy_id,
            deny_reasons=deny_reasons,
            conditions_missing=conditions_missing,
        )

    return {
        "satisfied": True,
        "policy_id": options.policy_id,
        "policy_evaluation_id": None,  # TODO: Track evaluation IDs
        "evaluated_at": evaluated_at,
        "verdict": decision,
    }
