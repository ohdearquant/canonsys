"""Auth domain exceptions.

These exceptions are raised when auth invariants are violated.
All inherit from AuthorizationViolation (the domain's base exception).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from canon.enforcement.exceptions import AuthorizationViolation

__all__ = [
    "AuthTokenExhaustedError",
    "AuthTokenExpiredError",
    "AuthTokenNotValidError",
    "AuthTokenRevokedError",
]


class AuthTokenNotValidError(AuthorizationViolation):
    """Auth token does not exist or is not valid.

    Raised when: verify_auth_token finds no valid token, or the token
    status is not ACTIVE.

    Regulatory basis:
    - SOC 2 CC6.1: Logical access security
    - PCI DSS 8.2: Authentication requirements

    Phrase: auth_token_must_be_valid
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Auth token not valid"

    __slots__ = ("token_id", "token_type")

    def __init__(
        self,
        token_id: UUID,
        token_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize auth token not valid error.

        Args:
            token_id: UUID of the token.
            token_type: Type of token (api_key, magic_link, etc.).
            **kwargs: Additional arguments passed to parent.
        """
        self.token_id = token_id
        self.token_type = token_type
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"token_id": str(token_id), "token_type": token_type}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Auth token {token_id} of type '{token_type}' is not valid",
            context=merged_context,
            **kwargs,
        )


class AuthTokenExpiredError(AuthorizationViolation):
    """Auth token has expired.

    Raised when: verify_auth_token finds a token past its expiration date.

    Regulatory basis:
    - SOC 2 CC6.1: Time-limited access
    - PCI DSS 8.1.4: Session timeout requirements

    Phrase: auth_token_must_not_be_expired
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Auth token has expired"

    __slots__ = ("expired_at", "token_id")

    def __init__(
        self,
        token_id: UUID,
        expired_at: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize auth token expired error.

        Args:
            token_id: UUID of the token.
            expired_at: Timestamp when the token expired.
            **kwargs: Additional arguments passed to parent.
        """
        self.token_id = token_id
        self.expired_at = expired_at
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "token_id": str(token_id),
            "expired_at": expired_at.isoformat(),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Auth token {token_id} expired at {expired_at.isoformat()}",
            context=merged_context,
            **kwargs,
        )


class AuthTokenRevokedError(AuthorizationViolation):
    """Auth token has been revoked.

    Raised when: verify_auth_token finds a token with status REVOKED.

    Regulatory basis:
    - SOC 2 CC6.2: Access removal
    - PCI DSS 8.1.3: Immediate access revocation

    Phrase: auth_token_must_not_be_revoked
    """

    default_regulation = "SOC 2 CC6.2"
    default_message = "Auth token has been revoked"

    __slots__ = ("revoked_at", "revoked_reason", "token_id")

    def __init__(
        self,
        token_id: UUID,
        revoked_at: datetime,
        revoked_reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize auth token revoked error.

        Args:
            token_id: UUID of the token.
            revoked_at: Timestamp when the token was revoked.
            revoked_reason: Reason for revocation, if provided.
            **kwargs: Additional arguments passed to parent.
        """
        self.token_id = token_id
        self.revoked_at = revoked_at
        self.revoked_reason = revoked_reason
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "token_id": str(token_id),
            "revoked_at": revoked_at.isoformat(),
        }
        if revoked_reason:
            base_context["revoked_reason"] = revoked_reason
        merged_context = {**base_context, **extra_context}
        msg = f"Auth token {token_id} was revoked at {revoked_at.isoformat()}"
        if revoked_reason:
            msg += f" (reason: {revoked_reason})"
        super().__init__(msg, context=merged_context, **kwargs)


class AuthTokenExhaustedError(AuthorizationViolation):
    """Auth token has exhausted its allowed uses.

    Raised when: verify_auth_token finds a one-time token that has
    already been used.

    Regulatory basis:
    - SOC 2 CC6.1: One-time use tokens
    - PCI DSS 8.2.5: One-time authentication

    Phrase: auth_token_must_have_remaining_uses
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Auth token has no remaining uses"

    __slots__ = ("max_uses", "token_id", "use_count")

    def __init__(
        self,
        token_id: UUID,
        max_uses: int,
        use_count: int,
        **kwargs: Any,
    ) -> None:
        """Initialize auth token exhausted error.

        Args:
            token_id: UUID of the token.
            max_uses: Maximum allowed uses for this token.
            use_count: Number of times the token has been used.
            **kwargs: Additional arguments passed to parent.
        """
        self.token_id = token_id
        self.max_uses = max_uses
        self.use_count = use_count
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "token_id": str(token_id),
            "max_uses": max_uses,
            "use_count": use_count,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Auth token {token_id} exhausted: used {use_count}/{max_uses} times",
            context=merged_context,
            **kwargs,
        )
