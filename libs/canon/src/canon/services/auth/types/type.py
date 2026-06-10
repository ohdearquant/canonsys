"""Auth token type enumeration."""

from kron.types import Enum

__all__ = ("TokenType",)


class TokenType(Enum):
    """Types of authentication tokens."""

    API_KEY = "api_key"  # Long-lived programmatic access
    MAGIC_LINK = "magic_link"  # One-time passwordless login
    PASSWORD_RESET = "password_reset"  # One-time password reset
    EMAIL_VERIFY = "email_verify"  # Email verification
    INVITE = "invite"  # User invitation
