"""Auth token content and entity types."""

from datetime import datetime

from pydantic import Field

from canon.entities.entity import ContentModel, Entity, register_entity
from canon.entities.shared import Tenant, User
from kron.types import FK
from kron.utils import now_utc

from .status import TokenStatus
from .type import TokenType

__all__ = (
    "AuthToken",
    "AuthTokenContent",
)


class AuthTokenContent(ContentModel):
    """Content for authentication tokens.

    Covers: API keys, magic links, password resets, email verification, invites.

    Security:
        - token_hash stores SHA-256, never plaintext
        - For API keys: prefix + last_four for identification without exposure
        - scopes restrict what the token can access

    Usage:
        # Create token (service layer generates plaintext, stores hash)
        token = AuthToken(content=AuthTokenContent(
            tenant_id=tenant.id,
            user_id=user.id,
            token_type=TokenType.API_KEY,
            token_hash=compute_hash(plaintext_token),
            prefix="sk_live_",
            last_four=plaintext_token[-4:],
            name="Production API Key",
            scopes=["read", "write"],
        ))

        # Verify token
        if stored.token_hash == compute_hash(provided_token):
            # Valid
    """

    # Scope
    tenant_id: FK[Tenant]
    user_id: FK[User] | None = None  # None for invite tokens

    # Token identity
    token_type: TokenType
    token_hash: str  # SHA-256 of token value

    # For API keys (identification without exposure)
    prefix: str | None = None  # e.g., "sk_live_", "sk_test_"
    last_four: str | None = None  # Last 4 chars for display
    name: str | None = None  # User-assigned name

    # Access control (for API keys)
    scopes: list[str] = Field(default_factory=list)  # read, write, admin

    # Lifecycle
    status: TokenStatus = TokenStatus.ACTIVE
    expires_at: datetime | None = None

    # Usage tracking
    used_at: datetime | None = None
    use_count: int = 0
    max_uses: int | None = None  # None = unlimited (API keys), 1 = one-time

    # Revocation
    revoked_at: datetime | None = None
    revoked_by_id: FK[User] | None = None
    revoked_reason: str | None = None

    # Context
    ip_address: str | None = None
    user_agent: str | None = None

    # For invite tokens
    invited_email: str | None = None
    invited_role: str | None = None

    def is_valid(self, as_of: datetime | None = None) -> bool:
        """Check if token is currently valid."""
        if self.status != TokenStatus.ACTIVE:
            return False

        check_time = as_of or now_utc()
        if self.expires_at and check_time >= self.expires_at:
            return False

        if self.max_uses and self.use_count >= self.max_uses:
            return False

        return True

    def record_use(self, ip: str | None = None, ua: str | None = None) -> None:
        """Record token usage (call touch() after for rehash)."""
        self.used_at = now_utc()
        self.use_count += 1
        if ip:
            self.ip_address = ip
        if ua:
            self.user_agent = ua

        # Auto-transition one-time tokens
        if self.max_uses and self.use_count >= self.max_uses:
            self.status = TokenStatus.USED


@register_entity("auth_tokens")
class AuthToken(Entity):
    """Entity representing an authentication token."""

    content: AuthTokenContent
