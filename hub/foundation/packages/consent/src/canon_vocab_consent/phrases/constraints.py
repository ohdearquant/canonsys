"""Consent-related truth machine phrases.

These phrases encode regulatory invariants for consent validation.
GDPR Article 7, FCRA 15 U.S.C. 1681b(b)(2).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..exceptions import (
    ConsentExpiredError,
    ConsentNotValidError,
    ConsentWithdrawnError,
)
from ..types import ConsentStatus

if TYPE_CHECKING:
    from ..types import ConsentScope, ConsentToken

__all__ = [
    "consent_must_be_valid",
    "consent_must_not_be_expired",
    "consent_must_not_be_withdrawn",
    "consent_scope_must_cover",
]


def consent_must_be_valid(token: ConsentToken) -> None:
    """Assert consent token is in ACTIVE status.

    Regulatory basis: FCRA Section 1681b(b)(2) requires valid consent
    before procuring a consumer report. Valid consent means the token
    exists and has status ACTIVE.

    Args:
        token: The consent token to validate.

    Raises:
        ConsentNotValidError: If token status is not ACTIVE.

    Truth Machine Semantics:
        If this function returns, the consent token is confirmed to be
        in ACTIVE status. No further status checking is needed.

    Example:
        >>> consent_must_be_valid(token)  # Passes silently if valid
        >>> # If we reach here, consent status is ACTIVE
    """
    content = token.content
    if content.status != ConsentStatus.ACTIVE:
        raise ConsentNotValidError(
            subject_id=content.subject_id,
            scope=content.scope.value,
            regulation="FCRA Section 1681b(b)(2)",
            context={
                "token_id": str(token.id),
                "current_status": content.status.value,
                "expected_status": "ACTIVE",
            },
        )


def consent_must_not_be_expired(
    token: ConsentToken,
    now: datetime | None = None,
) -> None:
    """Assert consent token has not expired.

    Regulatory basis: GDPR Article 7(3) requires consent to remain valid.
    Organizational policy may set consent validity windows. Once expired,
    consent cannot be relied upon for processing.

    Args:
        token: The consent token to validate.
        now: Reference time for expiration check. Defaults to current UTC time.

    Raises:
        ConsentExpiredError: If token.expires_at is set and has passed.

    Truth Machine Semantics:
        If this function returns, the consent token has not expired
        as of the reference time. The consent remains temporally valid.

    Note:
        If token.expires_at is None, the consent has no expiration and
        this check passes (consent is perpetual until revoked).

    Example:
        >>> consent_must_not_be_expired(token)  # Passes if not expired
        >>> consent_must_not_be_expired(token, now=some_future_date)  # Check at future time
    """
    content = token.content

    # No expiration set means consent is perpetual
    if content.expires_at is None:
        return

    check_time = now if now is not None else datetime.now(UTC)

    # Ensure check_time is timezone-aware for comparison
    if check_time.tzinfo is None:
        check_time = check_time.replace(tzinfo=UTC)

    # Ensure expires_at is timezone-aware for comparison
    expires_at = content.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if check_time >= expires_at:
        raise ConsentExpiredError(
            subject_id=content.subject_id,
            scope=content.scope.value,
            expired_at=content.expires_at,
            regulation="GDPR Article 7(3)",
            context={
                "token_id": str(token.id),
                "check_time": check_time.isoformat(),
            },
        )


def consent_must_not_be_withdrawn(token: ConsentToken) -> None:
    """Assert consent has not been explicitly withdrawn.

    Regulatory basis: GDPR Article 7(3) - withdrawal must be as easy
    as granting. Once withdrawn (status REVOKED), consent cannot be
    relied upon for any processing activities.

    Args:
        token: The consent token to validate.

    Raises:
        ConsentWithdrawnError: If token status is REVOKED.

    Truth Machine Semantics:
        If this function returns, the data subject has not withdrawn
        their consent. The consent remains legally valid for processing.

    Note:
        This specifically checks for explicit withdrawal (REVOKED status).
        Expired consent is a different invariant (consent_must_not_be_expired).

    Example:
        >>> consent_must_not_be_withdrawn(token)  # Passes if not revoked
        >>> # If we reach here, consent has not been withdrawn
    """
    content = token.content
    if content.status == ConsentStatus.REVOKED:
        # Use revoked_at if available, otherwise use current time
        withdrawn_at = content.revoked_at
        if withdrawn_at is None:
            withdrawn_at = datetime.now(UTC)

        raise ConsentWithdrawnError(
            subject_id=content.subject_id,
            scope=content.scope.value,
            withdrawn_at=withdrawn_at,
            regulation="GDPR Article 7(3)",
            context={
                "token_id": str(token.id),
                "revocation_reason": content.revocation_reason,
            },
        )


def consent_scope_must_cover(
    token: ConsentToken,
    required_scope: ConsentScope,
) -> None:
    """Assert consent token covers the required scope.

    Regulatory basis: FCRA Section 1681b(b)(2) requires consent for
    the specific purpose. Consent for one scope (e.g., employment
    verification) does not authorize a different scope (e.g., credit check).

    Args:
        token: The consent token to validate.
        required_scope: The scope required for the operation.

    Raises:
        ConsentNotValidError: If token.scope does not match required_scope.

    Truth Machine Semantics:
        If this function returns, the consent token's scope covers the
        required scope. The processing activity is authorized by consent.

    Note:
        This performs an exact match. Future implementations may support
        scope hierarchies where broader consent covers narrower scopes.

    Example:
        >>> consent_scope_must_cover(token, ConsentScope.BACKGROUND_CHECK)
        >>> # If we reach here, consent covers background check scope
    """
    content = token.content

    if content.scope != required_scope:
        raise ConsentNotValidError(
            subject_id=content.subject_id,
            scope=required_scope.value,
            regulation="FCRA Section 1681b(b)(2)",
            context={
                "token_id": str(token.id),
                "token_scope": content.scope.value,
                "required_scope": required_scope.value,
                "reason": f"Consent scope '{content.scope.value}' does not cover required scope '{required_scope.value}'",
            },
        )
