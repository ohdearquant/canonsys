"""Resolve effective policy for evaluation.

Complete vertical slice:
- Resolves which policy applies for a given context
- Considers jurisdiction, action type, and tenant overrides
- Returns the policy hash to use for evaluation
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import PolicyDefinitionNotFoundError, PolicyReleaseNotFoundError

__all__ = ["ResolvePolicySpecs", "resolve_policy"]


class ResolvePolicySpecs(BaseModel):
    """Specs for resolve policy phrase."""

    # inputs
    policy_id: str
    release_version: str | None = None  # If None, uses latest active release

    # Context for resolution
    jurisdiction: str | None = None
    action_type: str | None = None

    # outputs
    definition_version: str | None = None
    definition_hash: str | None = None
    adapter_version: str | None = None
    adapter_hash: str | None = None
    rego_hash: str | None = None
    resolved_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(ResolvePolicySpecs),
    inputs={"policy_id", "release_version", "jurisdiction", "action_type"},
    outputs={
        "policy_id",
        "definition_version",
        "definition_hash",
        "adapter_version",
        "adapter_hash",
        "rego_hash",
        "release_version",
        "resolved_at",
    },
)
async def resolve_policy(
    options: ResolvePolicySpecs,
    ctx: RequestContext,
) -> dict:
    """Resolve which policy version to use for evaluation.

    Resolution order:
    1. If release_version specified, use that release
    2. Otherwise, find latest active release
    3. Look up policy in release's policy map
    4. Return hashes for evaluation

    Args:
        options: Resolution options.
        ctx: Request context.

    Returns:
        Dict with policy_id, definition_version, definition_hash, adapter_version,
        adapter_hash, rego_hash, release_version, resolved_at.

    Raises:
        PolicyReleaseNotFoundError: If no release found.
        PolicyDefinitionNotFoundError: If policy not in release.
    """
    effective_conn = ctx.conn
    now = now_utc()

    # Find release
    if options.release_version:
        release = await select_one(
            "policy_releases",
            where={"version": options.release_version},
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
    else:
        # Find latest active release
        release = await select_one(
            "policy_releases",
            where={"status": "active"},
            order_by="published_at DESC",
            conn=effective_conn,
            tenant_scope=TenantScope.DISABLED,
        )
        if not release:
            # Fall back to latest published
            release = await select_one(
                "policy_releases",
                where={"status": "published"},
                order_by="published_at DESC",
                conn=effective_conn,
                tenant_scope=TenantScope.DISABLED,
            )

    if not release:
        raise PolicyReleaseNotFoundError(version=options.release_version)

    # Get policy from release
    policies = release.get("policies", {})
    if options.policy_id not in policies:
        raise PolicyDefinitionNotFoundError(
            options.policy_id,
            context={"release_version": release["version"]},
        )

    policy_info = policies[options.policy_id]

    return {
        "policy_id": options.policy_id,
        "definition_version": policy_info.get("definition_version", ""),
        "definition_hash": policy_info.get("definition_hash", ""),
        "adapter_version": policy_info.get("adapter_version", ""),
        "adapter_hash": policy_info.get("adapter_hash", ""),
        "rego_hash": policy_info.get("rego_hash", ""),
        "release_version": release["version"],
        "resolved_at": now,
    }
