"""Auth token status enumeration."""

from kron.types import Enum

__all__ = ("TokenStatus",)


class TokenStatus(Enum):
    """Token lifecycle states."""

    ACTIVE = "active"  # Valid and usable
    USED = "used"  # Consumed (one-time tokens)
    REVOKED = "revoked"  # Explicitly invalidated
    EXPIRED = "expired"  # TTL exceeded
