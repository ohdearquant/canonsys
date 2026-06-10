"""Session entity - authenticated user sessions."""

from __future__ import annotations

from ..entity import Entity, register_entity
from .tenant import TenantAware
from .user import UserAware

__all__ = (
    "Session",
    "SessionContent",
)


class SessionContent(TenantAware, UserAware):
    """An authenticated user session.

    Tracks authentication state including token validation,
    session metadata, MFA status, and revocation.
    """

    # Token management
    token_hash: str
    """Hash of refresh token for validation."""

    expires_at: str
    """ISO8601 expiration timestamp."""

    # Session metadata
    ip_address: str | None = None
    user_agent: str | None = None
    device_type: str | None = None  # mobile, tablet, desktop
    auth_method: str = "password"  # password, magic_link, sso, oauth

    # MFA
    mfa_verified: bool = False

    # Activity
    last_activity_at: str | None = None

    # Revocation
    is_revoked: bool = False
    revoked_at: str | None = None
    revoked_reason: str | None = None  # logout, logout_all, timeout, admin


@register_entity("sessions")
class Session(Entity):
    """Entity representing a user session."""

    content: SessionContent
