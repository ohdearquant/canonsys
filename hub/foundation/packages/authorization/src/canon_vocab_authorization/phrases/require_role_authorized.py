"""Require that an actor has the required role for an action.

Complete vertical slice:
- Queries actor's roles and permissions
- Checks if role is authorized for the action
- Raises RequirementNotMetError if unauthorized

Regulatory:
    - SOC 2 CC6.1 (Logical access controls)
    - ISO 27001 A.9.2 (User access management)
    - RBAC best practices
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireRoleAuthorizedSpecs", "require_role_authorized"]


class RequireRoleAuthorizedSpecs(BaseModel):
    """Specs for require role authorized phrase."""

    # inputs
    actor_id: UUID
    required_role: str
    action: str
    resource_type: str | None = None
    resource_id: UUID | None = None
    # outputs (defaults required for instantiation with inputs only)
    authorized: bool = False
    actor_roles: tuple[str, ...] | None = None
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireRoleAuthorizedSpecs),
    inputs={"actor_id", "required_role", "action", "resource_type", "resource_id"},
    outputs={
        "authorized",
        "actor_id",
        "required_role",
        "action",
        "actor_roles",
        "checked_at",
        "reason",
    },
)
async def require_role_authorized(
    options: RequireRoleAuthorizedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that an actor has the required role for an action.

    Queries the actor's assigned roles and verifies that at least one
    matches the required role for the specified action.

    Args:
        options: Options containing actor_id, required_role, action, resource_type, resource_id
        ctx: Request context with connection

    Returns:
        Dict with authorization status and metadata.

    Raises:
        RequirementNotMetError: If actor lacks required role
    """
    now = now_utc()
    actor_id: UUID = options.actor_id
    required_role = options.required_role.upper()
    action = options.action

    # Query actor's roles
    query = """
        SELECT role
        FROM actor_roles
        WHERE actor_id = $1
          AND is_active = true
          AND (expires_at IS NULL OR expires_at > $2)
    """
    rows = await ctx.conn.fetch(query, actor_id, now)
    actor_roles = tuple(row["role"].upper() for row in rows)

    # Check if required role is in actor's roles
    if required_role not in actor_roles:
        raise RequirementNotMetError(
            requirement="role_authorized",
            reason=f"Actor {actor_id} lacks required role '{required_role}' for action '{action}'",
        )

    return {
        "authorized": True,
        "actor_id": actor_id,
        "required_role": required_role,
        "action": action,
        "actor_roles": actor_roles,
        "checked_at": now,
        "reason": None,
    }
