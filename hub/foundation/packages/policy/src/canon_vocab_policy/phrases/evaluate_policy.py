"""Evaluate a policy.

Complete vertical slice:
- Fetches policy adapter from DB by hash
- Loads Rego into engine (regorus)
- Evaluates input and returns decision
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import (
    PolicyAdapterNotFoundError,
    PolicyDeniedError,
    PolicyEvaluationError,
)
from ..types import PolicyDecision

__all__ = ["EvaluatePolicySpecs", "evaluate_policy"]


class EvaluatePolicySpecs(BaseModel):
    """Specs for evaluate policy phrase."""

    # inputs - identify policy by hash (preferred) or ID
    rego_hash: str | None = None
    policy_id: str | None = None
    adapter_version: str | None = None

    # Input data
    facts: dict[str, Any] | None = None
    derived: dict[str, Any] | None = None
    context: dict[str, Any] | None = None

    # Behavior
    raise_on_deny: bool = False

    # outputs
    decision: PolicyDecision | None = None
    evaluated_at: datetime | None = None
    deny_reasons: tuple[str, ...] = ()
    conditions_met: tuple[str, ...] = ()
    conditions_missing: tuple[str, ...] = ()

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(EvaluatePolicySpecs),
    inputs={
        "rego_hash",
        "policy_id",
        "adapter_version",
        "facts",
        "derived",
        "context",
        "raise_on_deny",
    },
    outputs={
        "decision",
        "policy_id",
        "rego_hash",
        "evaluated_at",
        "deny_reasons",
        "conditions_met",
        "conditions_missing",
    },
)
async def evaluate_policy(
    options: EvaluatePolicySpecs,
    ctx: RequestContext,
) -> dict:
    """Evaluate a policy against input facts.

    Fetches the Rego code from DB and evaluates using regorus engine.
    No filesystem I/O at runtime - all from database.

    Args:
        options: Evaluation options with facts and policy identifier.
        ctx: Request context.

    Returns:
        Dict with decision, policy_id, rego_hash, evaluated_at, deny_reasons,
        conditions_met, conditions_missing.

    Raises:
        PolicyAdapterNotFoundError: If policy/adapter not found.
        PolicyEvaluationError: If Rego evaluation fails.
        PolicyDeniedError: If raise_on_deny=True and policy denies.
    """
    effective_conn = ctx.conn

    # Find adapter
    if options.rego_hash:
        adapter = await select_one(
            "policy_adapters",
            where={"rego_hash": options.rego_hash},
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
    elif options.policy_id:
        where_clause: dict[str, Any] = {"policy_id": options.policy_id}
        if options.adapter_version:
            where_clause["version"] = options.adapter_version
        adapter = await select_one(
            "policy_adapters",
            where=where_clause,
            order_by="created_at DESC",
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
    else:
        raise ValueError("Either rego_hash or policy_id must be provided")

    if not adapter:
        raise PolicyAdapterNotFoundError(
            policy_id=options.policy_id,
            context={"rego_hash": options.rego_hash},
        )

    policy_id = adapter["policy_id"]
    rego_hash = adapter.get("rego_hash", "")
    rego_content = adapter.get("rego_content", "")
    rego_package = adapter.get("rego_package", policy_id.replace(".", "_"))
    entrypoint = adapter.get("rego_entrypoint", "allow")

    # Build input
    input_data = {
        "facts": options.facts or {},
        "derived": options.derived or {},
        "context": options.context or {},
    }

    now = now_utc()

    # Evaluate using regorus
    deny_reasons: list[str] = []
    try:
        import regorus

        engine = regorus.Engine()

        # Add policy from string
        engine.add_policy(f"{rego_package}.rego", rego_content)

        # Set input
        engine.set_input_json(json.dumps(input_data))

        # Evaluate allow
        allow_result = engine.eval_rule(f"data.{rego_package}.{entrypoint}")
        allow = bool(allow_result) if allow_result is not None else False

        # Evaluate deny reasons if available
        try:
            deny_result = engine.eval_rule(f"data.{rego_package}.deny")
            if deny_result:
                if isinstance(deny_result, (list, set)):
                    deny_reasons = list(deny_result)
                elif isinstance(deny_result, dict):
                    deny_reasons = list(deny_result.keys())
        except Exception:
            pass  # deny rule may not exist

        # Determine decision
        if allow and not deny_reasons:
            decision = PolicyDecision.ALLOW
        elif deny_reasons or not allow:
            decision = PolicyDecision.DENY
        else:
            decision = PolicyDecision.ALLOW

    except ImportError as e:
        raise PolicyEvaluationError(
            policy_id=policy_id,
            reason="regorus OPA engine is not installed — policy enforcement unavailable",
            context={"import_error": str(e)},
        ) from e

    except Exception as e:
        raise PolicyEvaluationError(
            policy_id=policy_id,
            reason=str(e),
            context={"rego_hash": rego_hash},
        ) from e

    result = {
        "decision": decision,
        "policy_id": policy_id,
        "rego_hash": rego_hash,
        "evaluated_at": now,
        "deny_reasons": tuple(deny_reasons),
        "conditions_met": (),  # TODO: Extract from Rego
        "conditions_missing": (),  # TODO: Extract from Rego
    }

    if options.raise_on_deny and decision == PolicyDecision.DENY:
        raise PolicyDeniedError(
            policy_id=policy_id,
            deny_reasons=tuple(deny_reasons),
            conditions_missing=(),
        )

    return result
