"""Auth feature - vertical slice for authentication token management.

This module provides the complete auth domain implementation:
- Types: AuthToken, AuthTokenContent, TokenType, TokenStatus
- Actions: (to be added) create, verify, revoke, refresh
- Exceptions: AuthTokenNotValidError, AuthTokenExpiredError, etc.

Usage:
    from hub.services.auth import (
        # Types
        AuthToken,
        AuthTokenContent,
        TokenType,
        TokenStatus,
        # Exceptions
        AuthTokenNotValidError,
    )
"""

# Exceptions
from .exceptions import (
    AuthTokenExhaustedError,
    AuthTokenExpiredError,
    AuthTokenNotValidError,
    AuthTokenRevokedError,
)

# Types
from .types import AuthToken, AuthTokenContent, TokenStatus, TokenType

__all__ = [
    # Types
    "AuthToken",
    "AuthTokenContent",
    "TokenType",
    "TokenStatus",
    # Exceptions
    "AuthTokenNotValidError",
    "AuthTokenExpiredError",
    "AuthTokenRevokedError",
    "AuthTokenExhaustedError",
]
