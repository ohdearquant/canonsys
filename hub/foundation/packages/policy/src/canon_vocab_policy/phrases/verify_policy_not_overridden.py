"""Verify that a policy has not been overridden by an exception.

Complete vertical slice:
- Checks for active policy exceptions
- Verifies no override applies to this context
- Returns verification result (does not raise)

Regulatory:
    - SOX Section 404 (Exception management)
    - SOC 2 CC6.1 (Logical access controls)
    - Policy exception audit trail
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyPolicyNotOverriddenSpecs", "verify_policy_not_overridden"]


class VerifyPolicyNotOverriddenSpecs(BaseModel):
    """Specs for verify policy not overridden phrase."""

    # inputs
    policy_id: str
    subject_id: UUID | None = None
    resource_id: UUID | None = None
    action_type: str | None = None
    # outputs (defaults required for instantiation with inputs only)
    not_overridden: bool = False
    exception_id: UUID | None = None
    exception_reason: str | None = None
    exception_approved_by: UUID | None = None
    exception_expires_at: datetime | None = None
    checked_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(VerifyPolicyNotOverriddenSpecs),
    inputs={"policy_id", "subject_id", "resource_id", "action_type"},
    outputs={
        "not_overridden",
        "policy_id",
        "exception_id",
        "exception_reason",
        "exception_approved_by",
        "exception_expires_at",
        "checked_at",
    },
)
async def verify_policy_not_overridden(
    options: VerifyPolicyNotOverriddenSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a policy has not been overridden by an exception.

    Checks for active policy exceptions that would override the normal
    policy behavior. Exceptions can be:
    - Subject-specific (applies to a particular person)
    - Resource-specific (applies to a particular resource)
    - Action-specific (applies to a particular action type)
    - General (applies to all contexts)

    Args:
        options: Options containing policy_id and optional context
        ctx: Request context with connection

    Returns:
        Dict with not_overridden=True if no exception applies.
    """
    now = now_utc()
    policy_id = options.policy_id

    # Build query for matching exceptions
    base_query = """
        SELECT
            id,
            reason,
            approved_by,
            expires_at,
            subject_id,
            resource_id,
            action_type
        FROM policy_exceptions
        WHERE policy_id = $1
          AND is_active = true
          AND (expires_at IS NULL OR expires_at > $2)
    """

    params: list[Any] = [policy_id, now]
    param_idx = 3

    # Build match conditions
    conditions: list[str] = []

    # Always check for general exceptions (no specific context)
    conditions.append("(subject_id IS NULL AND resource_id IS NULL AND action_type IS NULL)")

    # Check for subject-specific exception
    if options.subject_id:
        conditions.append(f"subject_id = ${param_idx}")
        params.append(options.subject_id)
        param_idx += 1

    # Check for resource-specific exception
    if options.resource_id:
        conditions.append(f"resource_id = ${param_idx}")
        params.append(options.resource_id)
        param_idx += 1

    # Check for action-specific exception
    if options.action_type:
        conditions.append(f"action_type = ${param_idx}")
        params.append(options.action_type)
        param_idx += 1

    if conditions:
        base_query += f" AND ({' OR '.join(conditions)})"

    base_query += " ORDER BY expires_at ASC NULLS LAST LIMIT 1"

    row = await ctx.conn.fetchrow(base_query, *params)

    if row:
        # Exception found - policy IS overridden
        return {
            "not_overridden": False,
            "policy_id": policy_id,
            "exception_id": row["id"],
            "exception_reason": row["reason"],
            "exception_approved_by": row["approved_by"],
            "exception_expires_at": row["expires_at"],
            "checked_at": now,
        }

    # No exception - policy is NOT overridden
    return {
        "not_overridden": True,
        "policy_id": policy_id,
        "exception_id": None,
        "exception_reason": None,
        "exception_approved_by": None,
        "exception_expires_at": None,
        "checked_at": now,
    }
