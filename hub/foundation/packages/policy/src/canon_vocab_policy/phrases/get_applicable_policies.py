"""Get policies applicable to a given context.

Complete vertical slice:
- Queries policies matching the context
- Filters by jurisdiction, action type, scope
- Returns ordered list of applicable policies

Regulatory:
    - SOX Section 404 (Policy identification)
    - SOC 2 CC1.1-1.4 (Control environment)
    - Multi-jurisdictional compliance
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import PolicyScope

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetApplicablePoliciesSpecs", "get_applicable_policies"]


class PolicyMatch(BaseModel):
    """Information about a matched policy."""

    policy_id: str
    version: str
    scope: PolicyScope
    priority: int
    conditions: dict[str, Any] | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class GetApplicablePoliciesSpecs(BaseModel):
    """Specs for get applicable policies phrase."""

    # inputs - context for matching
    action_type: str | None = None
    jurisdiction: str | None = None
    resource_type: str | None = None
    data_classification: str | None = None
    actor_type: str | None = None
    # outputs (defaults required for instantiation with inputs only)
    policies: tuple[dict, ...] | None = None
    total_matched: int = 0
    queried_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetApplicablePoliciesSpecs),
    inputs={
        "action_type",
        "jurisdiction",
        "resource_type",
        "data_classification",
        "actor_type",
    },
    outputs={
        "policies",
        "total_matched",
        "action_type",
        "jurisdiction",
        "queried_at",
    },
)
async def get_applicable_policies(
    options: GetApplicablePoliciesSpecs,
    ctx: RequestContext,
) -> dict:
    """Get policies applicable to a given context.

    Queries all active policies and filters them based on the provided
    context (jurisdiction, action type, etc.). Returns policies in
    priority order.

    Policy matching considers:
    - Jurisdiction (exact match or wildcard)
    - Action type (exact match or category)
    - Resource type (exact match or category)
    - Data classification (equal or higher)
    - Actor type (exact match)

    Args:
        options: Options containing context for matching
        ctx: Request context with connection

    Returns:
        Dict with matched policies and count.
    """
    now = now_utc()

    # Build query with optional filters
    base_query = """
        SELECT
            policy_id,
            version,
            scope,
            priority,
            conditions,
            jurisdiction,
            action_types,
            resource_types
        FROM policy_definitions
        WHERE status = 'active'
          AND (effective_from IS NULL OR effective_from <= $1)
          AND (effective_until IS NULL OR effective_until > $1)
    """

    params: list[Any] = [now]
    param_idx = 2

    # Add jurisdiction filter
    if options.jurisdiction:
        base_query += f"""
            AND (jurisdiction IS NULL
                 OR jurisdiction = ${param_idx}
                 OR jurisdiction = '*')
        """
        params.append(options.jurisdiction)
        param_idx += 1

    # Add action type filter
    if options.action_type:
        base_query += f"""
            AND (action_types IS NULL
                 OR ${param_idx} = ANY(action_types)
                 OR '*' = ANY(action_types))
        """
        params.append(options.action_type)
        param_idx += 1

    # Add resource type filter
    if options.resource_type:
        base_query += f"""
            AND (resource_types IS NULL
                 OR ${param_idx} = ANY(resource_types)
                 OR '*' = ANY(resource_types))
        """
        params.append(options.resource_type)
        param_idx += 1

    base_query += " ORDER BY priority DESC, policy_id"

    rows = await ctx.conn.fetch(base_query, *params)

    # Build policy list with additional filtering
    policies: list[dict] = []

    for row in rows:
        conditions = row.get("conditions") or {}

        # Additional predicate checks
        if options.data_classification:
            policy_classification = conditions.get("data_classification")
            if policy_classification:
                # Only match if policy classification <= requested classification
                classification_order = [
                    "public",
                    "internal",
                    "confidential",
                    "restricted",
                ]
                try:
                    policy_level = classification_order.index(policy_classification)
                    request_level = classification_order.index(options.data_classification)
                    if policy_level > request_level:
                        continue  # Policy requires higher classification
                except ValueError:
                    pass  # Unknown classification, include policy

        if options.actor_type:
            policy_actor_types = conditions.get("actor_types")
            if policy_actor_types and options.actor_type not in policy_actor_types:
                continue  # Policy doesn't apply to this actor type

        policies.append(
            {
                "policy_id": row["policy_id"],
                "version": row["version"],
                "scope": row["scope"],
                "priority": row["priority"],
                "conditions": conditions,
            }
        )

    return {
        "policies": tuple(policies),
        "total_matched": len(policies),
        "action_type": options.action_type,
        "jurisdiction": options.jurisdiction,
        "queried_at": now,
    }
