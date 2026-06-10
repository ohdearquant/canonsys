"""Consent domain exceptions.

These exceptions are raised by consent phrases when invariants are violated.
All inherit from ConsentViolation (the domain's base exception).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import ConsentViolation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "ConsentExpiredError",
    "ConsentNotValidError",
    "ConsentWithdrawnError",
]


class ConsentNotValidError(ConsentViolation):
    """Consent does not exist or is not valid for the requested scope.

    Raised when: verify_consent finds no valid consent token, or the token
    status is not ACTIVE.

    Regulatory basis:
    - FCRA Section 1681b(b)(2): "obtain consent before procuring consumer report"
    - GDPR Article 7(1): "controller shall be able to demonstrate consent"

    Phrase: consent_must_be_valid
    """

    default_regulation = "FCRA Section 1681b(b)(2)"
    default_message = "Valid consent not found for requested scope"

    __slots__ = ("scope", "subject_id")

    def __init__(
        self,
        subject_id: UUID,
        scope: str,
        **kwargs: Any,
    ) -> None:
        """Initialize consent not valid error.

        Args:
            subject_id: UUID of the data subject (candidate, employee).
            scope: Consent scope that was requested (e.g., "background_check").
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.subject_id = subject_id
        self.scope = scope
        # Extract and merge any passed context with base context
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"subject_id": str(subject_id), "scope": scope}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"No valid consent for subject {subject_id} with scope '{scope}'",
            context=merged_context,
            **kwargs,
        )


class ConsentExpiredError(ConsentViolation):
    """Consent existed but has expired.

    Raised when: verify_consent finds a token that is past its expiration date.

    Regulatory basis:
    - GDPR Article 7(3): "Data subject shall have the right to withdraw consent"
    - Consent validity windows per organizational policy

    Phrase: consent_must_not_be_expired
    """

    default_regulation = "GDPR Article 7(3)"
    default_message = "Consent has expired"

    __slots__ = ("expired_at", "scope", "subject_id")

    def __init__(
        self,
        subject_id: UUID,
        scope: str,
        expired_at: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize consent expired error.

        Args:
            subject_id: UUID of the data subject.
            scope: Consent scope that was requested.
            expired_at: Timestamp when the consent expired.
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.subject_id = subject_id
        self.scope = scope
        self.expired_at = expired_at
        # Extract and merge any passed context with base context
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "subject_id": str(subject_id),
            "scope": scope,
            "expired_at": expired_at.isoformat(),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Consent for subject {subject_id} expired at {expired_at.isoformat()}",
            context=merged_context,
            **kwargs,
        )


class ConsentWithdrawnError(ConsentViolation):
    """Consent was explicitly withdrawn by the data subject.

    Raised when: verify_consent finds a token with status REVOKED.

    Regulatory basis:
    - GDPR Article 7(3): "It shall be as easy to withdraw as to give consent"
    - CCPA Section 1798.120: Right to opt-out

    Phrase: consent_must_not_be_withdrawn
    """

    default_regulation = "GDPR Article 7(3)"
    default_message = "Consent has been withdrawn"

    __slots__ = ("scope", "subject_id", "withdrawn_at")

    def __init__(
        self,
        subject_id: UUID,
        scope: str,
        withdrawn_at: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize consent withdrawn error.

        Args:
            subject_id: UUID of the data subject.
            scope: Consent scope that was requested.
            withdrawn_at: Timestamp when consent was withdrawn.
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.subject_id = subject_id
        self.scope = scope
        self.withdrawn_at = withdrawn_at
        # Extract and merge any passed context with base context
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "subject_id": str(subject_id),
            "scope": scope,
            "withdrawn_at": withdrawn_at.isoformat(),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Consent for subject {subject_id} withdrawn at {withdrawn_at.isoformat()}",
            context=merged_context,
            **kwargs,
        )
