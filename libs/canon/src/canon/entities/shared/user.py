"""User entity and actor awareness mixins."""

from __future__ import annotations

from typing import ClassVar

from kron.types import FK

from ..entity import ContentModel, Entity, register_entity
from .tenant import TenantAware

__all__ = (
    "ActorAware",
    "OptActorAware",
    "User",
    "UserAware",
    "UserContent",
)


class UserContent(TenantAware):
    """An authenticated user with system access.

    Users belong to a tenant and may be linked to a Person record.
    Role determines permissions within the tenant.

    Security notes:
        - password_hash: bcrypt hash, never plaintext
        - mfa_secret: encrypted TOTP secret
    """

    _sensitive_fields: ClassVar[set[str]] = {"password_hash", "mfa_secret"}
    _unique_within_tenant: ClassVar[set[str]] = {"email"}

    email: str

    # Authentication
    password_hash: str | None = None

    # Access control
    role: str = "member"  # admin, manager, member, viewer
    status: str = "active"  # pending, active, suspended

    # MFA
    mfa_enabled: bool = False
    mfa_secret: str | None = None

    # Profile
    display_name: str | None = None

    # Activity
    last_login_at: str | None = None
    login_count: int = 0


@register_entity("users")
class User(Entity):
    """Entity representing an authenticated user."""

    content: UserContent


class UserAware(ContentModel):
    """Mixin for content owned by a user."""

    user_id: FK[User]


class ActorAware(ContentModel):
    """Mixin for content where a user performed an action."""

    actor_id: FK[User]


class OptActorAware(ContentModel):
    """Mixin for content with optional actor (e.g., system-generated)."""

    actor_id: FK[User] | None = None
