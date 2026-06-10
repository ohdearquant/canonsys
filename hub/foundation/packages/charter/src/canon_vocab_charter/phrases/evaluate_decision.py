"""Evaluate a decision against charter policy.

Complete vertical slice:
- Resolves surface binding for charter
- Evaluates facts against active policies
- Returns decision result with conditions and evidence requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from canon.db import TenantScope, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import CharterNotFoundError, CharterStatusError, SurfaceNotBoundError
from ..types import CharterStatus

__all__ = ["EvaluateDecisionSpecs", "evaluate_decision"]


class EvaluateDecisionSpecs(BaseModel):
    """Specs for evaluate decision phrase."""

    # inputs
    charter_id: UUID
    surface_id: str
    facts: dict[str, Any] = Field(default_factory=dict)

    # outputs
    allowed: bool | None = None
    policy_version: str | None = None
    evaluated_at: datetime | None = None
    conditions_met: tuple[str, ...] = ()
    conditions_missing: tuple[str, ...] = ()
    evidence_required: tuple[str, ...] = ()
    blocking_policies: tuple[str, ...] = ()
    advisory_warnings: tuple[str, ...] = ()
    evaluation_context: dict[str, Any] = Field(default_factory=dict)


@canon_phrase(
    Operable.from_structure(EvaluateDecisionSpecs),
    inputs={"charter_id", "surface_id", "facts"},
    outputs={
        "allowed",
        "charter_id",
        "surface_id",
        "policy_version",
        "evaluated_at",
        "conditions_met",
        "conditions_missing",
        "evidence_required",
        "blocking_policies",
        "advisory_warnings",
        "evaluation_context",
    },
)
async def evaluate_decision(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Evaluate a decision against charter policy.

    Evaluates whether an action is permitted under the charter's active
    policies for a specific decision surface. This is the core decision
    gate that ensures compliance before high-risk actions proceed.

    Args:
        options: Evaluation options (charter_id, surface_id, facts)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with evaluation outcome

    Raises:
        CharterNotFoundError: If charter doesn't exist
        CharterStatusError: If charter is not ACTIVE
        SurfaceNotBoundError: If surface is not bound to charter
    """
    charter_id = options.get("charter_id")
    surface_id = options.get("surface_id")
    facts = options.get("facts", {})

    if not charter_id:
        raise ValueError("charter_id is required")
    if not surface_id:
        raise ValueError("surface_id is required")

    # Fetch charter
    charter_row = await select_one(
        "charters",
        where={"id": charter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not charter_row:
        raise CharterNotFoundError(str(charter_id))

    if charter_row["tenant_id"] != ctx.tenant_id:
        raise CharterStatusError(
            str(charter_id),
            current_status="tenant_mismatch",
            required_status="matching_tenant",
        )

    # Only ACTIVE charters can evaluate decisions
    current_status = charter_row.get("status", "unknown")
    if current_status != CharterStatus.ACTIVE.value:
        raise CharterStatusError(
            str(charter_id),
            current_status=current_status,
            required_status=CharterStatus.ACTIVE.value,
        )

    # Fetch surface binding
    binding_row = await select_one(
        "charter_surface_bindings",
        where={"charter_id": charter_id, "surface_id": surface_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not binding_row:
        raise SurfaceNotBoundError(str(charter_id), surface_id)

    policy_version = binding_row.get("policy_version", "unknown")
    evidence_requirements = tuple(binding_row.get("evidence_requirements") or [])

    now = now_utc()

    # Evaluate constraints from canon_vocab_charter
    constraints = charter_row.get("constraints") or []
    conditions_met: list[str] = []
    conditions_missing: list[str] = []
    blocking_policies: list[str] = []
    advisory_warnings: list[str] = []

    for constraint in constraints:
        constraint_id = constraint.get("constraint_id", "unknown")
        gate_id = constraint.get("gate_id")
        service_check = constraint.get("service_check")

        # Check if this constraint has a matching fact
        # The fact key should match the gate_id or service_check
        fact_key = gate_id or service_check
        if fact_key and fact_key in facts:
            fact_value = facts[fact_key]
            if fact_value:
                conditions_met.append(constraint_id)
            else:
                conditions_missing.append(constraint_id)
                # Constraints are blocking by default
                blocking_policies.append(constraint_id)
        else:
            # No fact provided for this constraint - treat as missing
            conditions_missing.append(constraint_id)
            blocking_policies.append(constraint_id)

    # Check evidence requirements against facts
    evidence_required: list[str] = []
    for req in evidence_requirements:
        evidence_fact_key = f"evidence.{req}"
        if evidence_fact_key not in facts or not facts[evidence_fact_key]:
            evidence_required.append(req)

    # Decision is allowed if no blocking policies and no missing evidence
    allowed = len(blocking_policies) == 0 and len(evidence_required) == 0

    return {
        "allowed": allowed,
        "charter_id": charter_id,
        "surface_id": surface_id,
        "policy_version": policy_version,
        "evaluated_at": now,
        "conditions_met": tuple(conditions_met),
        "conditions_missing": tuple(conditions_missing),
        "evidence_required": tuple(evidence_required),
        "blocking_policies": tuple(blocking_policies),
        "advisory_warnings": tuple(advisory_warnings),
        "evaluation_context": {
            "facts_provided": list(facts.keys()),
            "constraint_count": len(constraints),
            "evidence_requirement_count": len(evidence_requirements),
        },
    }
