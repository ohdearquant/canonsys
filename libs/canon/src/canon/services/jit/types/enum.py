from kron.types import Enum

__all__ = ("TokenStatus", "TokenType")


class TokenType(Enum):
    """Types of authentication tokens."""

    API_KEY = "api_key"  # Long-lived programmatic access
    MAGIC_LINK = "magic_link"  # One-time passwordless login
    PASSWORD_RESET = "password_reset"  # One-time password reset
    EMAIL_VERIFY = "email_verify"  # Email verification
    INVITE = "invite"  # User invitation


class TokenStatus(Enum):
    """Token lifecycle states."""

    ACTIVE = "active"  # Valid and usable
    USED = "used"  # Consumed (one-time tokens)
    REVOKED = "revoked"  # Explicitly invalidated
    EXPIRED = "expired"  # TTL exceeded
