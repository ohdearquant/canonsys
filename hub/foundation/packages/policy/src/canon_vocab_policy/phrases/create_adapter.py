"""Create a policy adapter.

Complete vertical slice:
- Creates engineering implementation of a policy
- Validates policy definition exists and version matches
- Stores Rego package reference and gate implementations
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

from ..exceptions import (
    PolicyAdapterVersionMismatchError,
    PolicyDefinitionNotFoundError,
)
from ..types import PolicyStatus

__all__ = ["CreateAdapterSpecs", "create_policy_adapter"]


class CreateAdapterSpecs(BaseModel):
    """Specs for create policy adapter phrase."""

    # inputs
    policy_id: str  # Links to PolicyDefinition.policy_id
    policy_definition_version: str  # MUST match PolicyDefinition.version
    adapter_version: str  # Adapter's own version

    # OPA/Rego integration
    rego_content: str  # The actual Rego code
    rego_package: str | None = None  # Package name (derived from content if not provided)
    rego_entrypoint: str = "allow"

    # Gate implementations
    gate_implementations: tuple[dict, ...] = ()
    config: dict | None = None

    # Provenance
    build_commit: str | None = None
    implemented_by: str | None = None

    # outputs
    adapter_id: UUID | None = None
    adapter_hash: str | None = None
    rego_hash: str | None = None
    status: PolicyStatus | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(CreateAdapterSpecs),
    inputs={
        "policy_id",
        "policy_definition_version",
        "adapter_version",
        "rego_content",
        "rego_package",
        "rego_entrypoint",
        "gate_implementations",
        "config",
        "build_commit",
        "implemented_by",
    },
    outputs={
        "adapter_id",
        "policy_id",
        "adapter_version",
        "adapter_hash",
        "rego_hash",
        "status",
        "created_at",
    },
)
async def create_policy_adapter(
    options: CreateAdapterSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a new policy adapter.

    Policy adapters are engineering-owned implementations of policy definitions.
    They contain the actual Rego code and gate implementations.

    Args:
        options: Creation options.
        ctx: Request context.

    Returns:
        Dict with adapter_id, policy_id, adapter_version, adapter_hash, rego_hash, status, created_at.

    Raises:
        PolicyDefinitionNotFoundError: If referenced policy doesn't exist.
        PolicyAdapterVersionMismatchError: If version doesn't match definition.
    """
    effective_conn = ctx.conn

    # Verify policy definition exists
    definition = await select_one(
        "policy_definitions",
        where={"policy_id": options.policy_id},
        order_by="created_at DESC",
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,
    )

    if not definition:
        raise PolicyDefinitionNotFoundError(options.policy_id)

    # Verify version lock
    if definition["version"] != options.policy_definition_version:
        raise PolicyAdapterVersionMismatchError(
            adapter_id=f"{options.policy_id}.v{options.adapter_version}",
            adapter_version=options.policy_definition_version,
            definition_version=definition["version"],
        )

    now = now_utc()
    adapter_id = uuid4()

    # Compute hashes
    rego_hash = compute_hash(options.rego_content)
    adapter_data = {
        "policy_id": options.policy_id,
        "policy_definition_version": options.policy_definition_version,
        "adapter_version": options.adapter_version,
        "rego_hash": rego_hash,
        "gate_implementations": list(options.gate_implementations),
        "config": options.config or {},
    }
    adapter_hash = compute_hash(adapter_data)

    # Derive rego_package from content if not provided
    rego_package = options.rego_package
    if not rego_package:
        # Extract from "package X" line
        for line in options.rego_content.split("\n"):
            line = line.strip()
            if line.startswith("package "):
                rego_package = line[8:].strip()
                break

    # Insert
    row_data = {
        "id": adapter_id,
        "adapter_id": f"{options.policy_id}.v{options.adapter_version}",
        "policy_id": options.policy_id,
        "policy_definition_version": options.policy_definition_version,
        "version": options.adapter_version,
        "rego_content": options.rego_content,
        "rego_package": rego_package,
        "rego_entrypoint": options.rego_entrypoint,
        "rego_hash": rego_hash,
        "gate_implementations": list(options.gate_implementations),
        "config": options.config or {},
        "adapter_hash": adapter_hash,
        "build_commit": options.build_commit,
        "implemented_by": options.implemented_by,
        "status": PolicyStatus.DRAFT.value,
        "created_at": now,
    }

    await insert(
        "policy_adapters",
        row_data,
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,
    )

    return {
        "adapter_id": adapter_id,
        "policy_id": options.policy_id,
        "adapter_version": options.adapter_version,
        "adapter_hash": adapter_hash,
        "rego_hash": rego_hash,
        "status": PolicyStatus.DRAFT,
        "created_at": now,
    }
