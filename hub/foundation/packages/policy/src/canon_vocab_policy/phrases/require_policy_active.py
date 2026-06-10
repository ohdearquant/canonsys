"""Require that a policy is currently active.

Complete vertical slice:
- Queries policy status
- Verifies policy is in ACTIVE state
- Raises RequirementNotMetError if inactive

Regulatory:
    - SOX Section 404 (Policy enforcement)
    - SOC 2 CC1.1-1.4 (Control environment)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import PolicyStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequirePolicyActiveSpecs", "require_policy_active"]


class RequirePolicyActiveSpecs(BaseModel):
    """Specs for require policy active phrase."""

    # inputs
    policy_id: str
    # outputs (defaults required for instantiation with inputs only)
    satisfied: bool = False
    status: PolicyStatus | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequirePolicyActiveSpecs),
    inputs={"policy_id"},
    outputs={
        "satisfied",
        "policy_id",
        "status",
        "effective_from",
        "effective_until",
        "checked_at",
        "reason",
    },
)
async def require_policy_active(
    options: RequirePolicyActiveSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a policy is currently active.

    Queries the policy status and verifies it is in ACTIVE state.
    A policy is considered active if:
    - Status is ACTIVE
    - Current time is after effective_from (if set)
    - Current time is before effective_until (if set)

    Args:
        options: Options containing policy_id
        ctx: Request context with connection

    Returns:
        Dict with satisfied=True if policy is active.

    Raises:
        RequirementNotMetError: If policy is not active
    """
    now = now_utc()
    policy_id = options.policy_id

    # Query policy definition
    row = await select_one(
        "policy_definitions",
        where={"policy_id": policy_id},
        order_by="created_at DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="policy_active",
            reason=f"Policy '{policy_id}' not found",
        )

    status = PolicyStatus(row.get("status", "draft"))
    effective_from: datetime | None = row.get("effective_from")
    effective_until: datetime | None = row.get("effective_until")

    # Check status
    if status != PolicyStatus.ACTIVE:
        raise RequirementNotMetError(
            requirement="policy_active",
            reason=f"Policy '{policy_id}' is not active (status: {status.value})",
        )

    # Check effective dates
    if effective_from and now < effective_from:
        raise RequirementNotMetError(
            requirement="policy_active",
            reason=f"Policy '{policy_id}' not yet effective (starts: {effective_from})",
        )

    if effective_until and now > effective_until:
        raise RequirementNotMetError(
            requirement="policy_active",
            reason=f"Policy '{policy_id}' has expired (ended: {effective_until})",
        )

    return {
        "satisfied": True,
        "policy_id": policy_id,
        "status": status,
        "effective_from": effective_from,
        "effective_until": effective_until,
        "checked_at": now,
        "reason": None,
    }
