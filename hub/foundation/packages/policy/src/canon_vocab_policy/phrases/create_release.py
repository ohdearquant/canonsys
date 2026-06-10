"""Create a policy release.

Complete vertical slice:
- Creates immutable snapshot of policy definitions + adapters
- Validates all referenced policies exist
- Computes bundle hash for integrity
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from canon.db import TenantScope, insert, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..exceptions import PolicyAdapterNotFoundError, PolicyDefinitionNotFoundError

__all__ = ["CreateReleaseSpecs", "create_policy_release"]


class CreateReleaseSpecs(BaseModel):
    """Specs for create policy release phrase."""

    # inputs
    version: str  # "2026.01", "2026.01.1"
    description: str = ""

    # Policy IDs to include (will resolve to latest adapter for each)
    policy_ids: tuple[str, ...] = ()

    # Or explicit policy -> adapter mapping
    # {"policy_id": {"definition_version": "1.0", "adapter_version": "1"}}
    explicit_policies: dict[str, dict] | None = None

    # outputs
    release_id: UUID | None = None
    policies: dict[str, dict] | None = (
        None  # policy_id -> {definition_hash, adapter_hash, rego_hash}
    )
    bundle_hash: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(CreateReleaseSpecs),
    inputs={"version", "description", "policy_ids", "explicit_policies"},
    outputs={"release_id", "version", "policies", "bundle_hash", "created_at"},
)
async def create_policy_release(
    options: CreateReleaseSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a new policy release (draft).

    A release is an immutable snapshot of policies. Once published, it cannot
    be modified. Multiple tenants can activate the same release via Charter.

    Args:
        options: Creation options.
        ctx: Request context.

    Returns:
        Dict with release_id, version, policies, bundle_hash, created_at.

    Raises:
        PolicyDefinitionNotFoundError: If a policy doesn't exist.
        PolicyAdapterNotFoundError: If a policy has no adapter.
    """
    effective_conn = ctx.conn
    now = now_utc()
    release_id = uuid4()

    # Resolve policies
    policies: dict[str, dict] = {}

    if options.explicit_policies:
        # Use explicit mapping
        for policy_id, config in options.explicit_policies.items():
            definition = await select_one(
                "policy_definitions",
                where={
                    "policy_id": policy_id,
                    "version": config.get("definition_version"),
                },
                conn=effective_conn,
                tenant_scope=TenantScope.DISABLED,
            )
            if not definition:
                raise PolicyDefinitionNotFoundError(policy_id, config.get("definition_version"))

            adapter = await select_one(
                "policy_adapters",
                where={
                    "policy_id": policy_id,
                    "version": config.get("adapter_version"),
                },
                conn=effective_conn,
                tenant_scope=TenantScope.DISABLED,
            )
            if not adapter:
                raise PolicyAdapterNotFoundError(policy_id=policy_id)

            policies[policy_id] = {
                "definition_version": definition["version"],
                "definition_hash": definition.get("content_hash"),
                "adapter_version": adapter["version"],
                "adapter_hash": adapter.get("adapter_hash"),
                "rego_hash": adapter.get("rego_hash"),
            }
    else:
        # Resolve latest for each policy_id
        for policy_id in options.policy_ids:
            # Get latest definition
            definition = await select_one(
                "policy_definitions",
                where={"policy_id": policy_id},
                order_by="created_at DESC",
                conn=effective_conn,
                tenant_scope=TenantScope.DISABLED,
            )
            if not definition:
                raise PolicyDefinitionNotFoundError(policy_id)

            # Get latest adapter matching definition version
            adapter = await select_one(
                "policy_adapters",
                where={
                    "policy_id": policy_id,
                    "policy_definition_version": definition["version"],
                },
                order_by="created_at DESC",
                conn=effective_conn,
                tenant_scope=TenantScope.DISABLED,
            )
            if not adapter:
                raise PolicyAdapterNotFoundError(policy_id=policy_id)

            policies[policy_id] = {
                "definition_version": definition["version"],
                "definition_hash": definition.get("content_hash"),
                "adapter_version": adapter["version"],
                "adapter_hash": adapter.get("adapter_hash"),
                "rego_hash": adapter.get("rego_hash"),
            }

    # Compute bundle hash (hash of all policy hashes)
    bundle_data = {
        "version": options.version,
        "policies": policies,
    }
    bundle_hash = compute_hash(bundle_data)

    # Insert
    row_data = {
        "id": release_id,
        "version": options.version,
        "description": options.description,
        "policies": policies,
        "policy_families": {},  # Future: group related policies
        "bundle_hash": bundle_hash,
        "status": "draft",
        "created_at": now,
    }

    await insert(
        "policy_releases",
        row_data,
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,
    )

    return {
        "release_id": release_id,
        "version": options.version,
        "policies": policies,
        "bundle_hash": bundle_hash,
        "created_at": now,
    }
