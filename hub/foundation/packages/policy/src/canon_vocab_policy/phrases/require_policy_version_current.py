"""Require that a policy version is current (not outdated).

Complete vertical slice:
- Checks if the specified version is the latest active
- Prevents operations against outdated policy versions
- Raises RequirementNotMetError if outdated

Regulatory:
    - SOX Section 404 (Current policy enforcement)
    - SOC 2 CC1.4 (Commitment to competence)
    - ISO 27001 A.5.1 (Policies for information security)
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

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequirePolicyVersionCurrentSpecs", "require_policy_version_current"]


class RequirePolicyVersionCurrentSpecs(BaseModel):
    """Specs for require policy version current phrase."""

    # inputs
    policy_id: str
    version: str
    # outputs (defaults required for instantiation with inputs only)
    current: bool = False
    latest_version: str | None = None
    version_gap: int = 0  # How many versions behind
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequirePolicyVersionCurrentSpecs),
    inputs={"policy_id", "version"},
    outputs={
        "current",
        "policy_id",
        "version",
        "latest_version",
        "version_gap",
        "checked_at",
        "reason",
    },
)
async def require_policy_version_current(
    options: RequirePolicyVersionCurrentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a policy version is current.

    Verifies that the specified policy version is the latest active
    version. Operations against outdated policy versions should be
    rejected to ensure compliance with current requirements.

    Args:
        options: Options containing policy_id and version
        ctx: Request context with connection

    Returns:
        Dict with current=True if version is latest.

    Raises:
        RequirementNotMetError: If version is outdated
    """
    now = now_utc()
    policy_id = options.policy_id
    version = options.version

    # Get the latest active version
    latest_row = await select_one(
        "policy_definitions",
        where={"policy_id": policy_id, "status": "active"},
        order_by="version DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,
    )

    if not latest_row:
        # No active version - check if requested version exists at all
        version_row = await select_one(
            "policy_definitions",
            where={"policy_id": policy_id, "version": version},
            conn=ctx.conn,
            tenant_scope=TenantScope.DISABLED,
        )
        if not version_row:
            raise RequirementNotMetError(
                requirement="policy_version_current",
                reason=f"Policy '{policy_id}' version '{version}' not found",
            )
        raise RequirementNotMetError(
            requirement="policy_version_current",
            reason=f"Policy '{policy_id}' has no active version",
        )

    latest_version = latest_row["version"]

    if version != latest_version:
        # Calculate version gap (simple integer comparison for semantic versions)
        try:
            # Parse versions like "1.0", "2.1" etc
            def parse_version(v: str) -> tuple[int, ...]:
                return tuple(int(p) for p in v.replace("v", "").split("."))

            current_parts = parse_version(version)
            latest_parts = parse_version(latest_version)
            # Simple gap calculation based on major version
            latest_parts[0] - current_parts[0]
        except (ValueError, IndexError):
            pass

        raise RequirementNotMetError(
            requirement="policy_version_current",
            reason=(
                f"Policy '{policy_id}' version '{version}' is outdated. "
                f"Latest version is '{latest_version}'"
            ),
        )

    return {
        "current": True,
        "policy_id": policy_id,
        "version": version,
        "latest_version": latest_version,
        "version_gap": 0,
        "checked_at": now,
        "reason": None,
    }
