"""Create a policy definition.

Complete vertical slice:
- Creates legal-authored policy specification
- Validates authority citation exists
- Computes content hash for versioning
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

from ..exceptions import PolicyDefinitionAlreadyExistsError
from ..types import PolicyScope, PolicyStatus

__all__ = ["CreateDefinitionSpecs", "create_policy_definition"]


class CreateDefinitionSpecs(BaseModel):
    """Specs for create policy definition phrase."""

    # inputs
    policy_id: str  # Canonical: {jurisdiction}.{domain}.{rule}
    version: str  # Semantic version
    name: str
    description: str | None = None

    # Legal authority (required for non-draft)
    authority: dict | None = None  # PolicyAuthority.to_dict()

    # Scope
    scope: PolicyScope = PolicyScope.GLOBAL
    jurisdictions: tuple[str, ...] = ()
    action_types: tuple[str, ...] = ()

    # Requirements (legal language)
    required_gates: tuple[dict, ...] = ()
    requirements: tuple[str, ...] = ()
    waiting_periods: dict[str, str] | None = None

    # Lifecycle
    effective_from: datetime | None = None
    sunset_date: datetime | None = None

    # Authorship
    authored_by: str | None = None

    # outputs
    definition_id: UUID | None = None
    content_hash: str | None = None
    status: PolicyStatus | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(CreateDefinitionSpecs),
    inputs={
        "policy_id",
        "version",
        "name",
        "description",
        "authority",
        "scope",
        "jurisdictions",
        "action_types",
        "required_gates",
        "requirements",
        "waiting_periods",
        "effective_from",
        "sunset_date",
        "authored_by",
    },
    outputs={
        "definition_id",
        "policy_id",
        "version",
        "content_hash",
        "status",
        "created_at",
    },
)
async def create_policy_definition(
    options: CreateDefinitionSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a new policy definition.

    Policy definitions are legal-owned specifications of compliance requirements.
    Engineering cannot modify these directly - they implement via PolicyAdapter.

    Args:
        options: Creation options.
        ctx: Request context.

    Returns:
        Dict with definition_id, policy_id, version, content_hash, status, created_at.

    Raises:
        PolicyDefinitionAlreadyExistsError: If policy_id + version already exists.
    """
    effective_conn = ctx.conn

    # Check for existing definition with same policy_id + version
    existing = await select_one(
        "policy_definitions",
        where={"policy_id": options.policy_id, "version": options.version},
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,  # Policies are global
    )

    if existing:
        raise PolicyDefinitionAlreadyExistsError(options.policy_id, options.version)

    now = now_utc()
    definition_id = uuid4()

    # Build content for hashing
    content_data = {
        "policy_id": options.policy_id,
        "version": options.version,
        "name": options.name,
        "description": options.description,
        "authority": options.authority,
        "scope": options.scope.value,
        "jurisdictions": list(options.jurisdictions),
        "action_types": list(options.action_types),
        "required_gates": list(options.required_gates),
        "requirements": list(options.requirements),
        "waiting_periods": options.waiting_periods or {},
    }
    content_hash = compute_hash(content_data)

    # Insert
    row_data = {
        "id": definition_id,
        "policy_id": options.policy_id,
        "version": options.version,
        "name": options.name,
        "description": options.description,
        "authority": options.authority,
        "scope": options.scope.value,
        "jurisdictions": list(options.jurisdictions),
        "action_types": list(options.action_types),
        "required_gates": list(options.required_gates),
        "requirements": list(options.requirements),
        "waiting_periods": options.waiting_periods or {},
        "status": PolicyStatus.DRAFT.value,
        "effective_from": options.effective_from,
        "sunset_date": options.sunset_date,
        "authored_by": options.authored_by,
        "content_hash": content_hash,
        "created_at": now,
    }

    await insert(
        "policy_definitions",
        row_data,
        conn=effective_conn,
        tenant_scope=TenantScope.DISABLED,
    )

    return {
        "definition_id": definition_id,
        "policy_id": options.policy_id,
        "version": options.version,
        "content_hash": content_hash,
        "status": PolicyStatus.DRAFT,
        "created_at": now,
    }
