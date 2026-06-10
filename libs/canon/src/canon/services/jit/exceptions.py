"""JIT permit domain exceptions.

These exceptions are raised by JIT permit operations when invariants are violated.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from canon.enforcement.exceptions import AuthorizationViolation

__all__ = [
    "PermitActionMismatchError",
    "PermitAlreadyUsedError",
    "PermitExpiredError",
    "PermitNotFoundError",
    "PermitRevokedError",
    "PermitSubjectMismatchError",
]


class PermitNotFoundError(AuthorizationViolation):
    """Permit token does not exist.

    Raised when: redeem_permit or verify_permit cannot find the permit token.

    Phrase: permit_must_exist
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit token not found"

    __slots__ = ("permit_id",)

    def __init__(
        self,
        permit_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize permit not found error.

        Args:
            permit_id: UUID of the permit that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        super().__init__(
            f"Permit token {permit_id} not found",
            context={"permit_id": str(permit_id)},
            **kwargs,
        )


class PermitExpiredError(AuthorizationViolation):
    """Permit token has expired.

    Raised when: redeem_permit finds a token past its expiration.

    Phrase: permit_must_not_be_expired
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit token has expired"

    __slots__ = ("expired_at", "permit_id")

    def __init__(
        self,
        permit_id: UUID,
        expired_at: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize permit expired error.

        Args:
            permit_id: UUID of the expired permit.
            expired_at: When the permit expired.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        self.expired_at = expired_at
        super().__init__(
            f"Permit token {permit_id} expired at {expired_at.isoformat()}",
            context={
                "permit_id": str(permit_id),
                "expired_at": expired_at.isoformat(),
            },
            **kwargs,
        )


class PermitAlreadyUsedError(AuthorizationViolation):
    """Permit token has already been redeemed.

    Raised when: redeem_permit finds a token with status USED.

    Phrase: permit_must_not_be_used
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit token already used"

    __slots__ = ("permit_id", "redeemed_at", "redeemed_by_bp")

    def __init__(
        self,
        permit_id: UUID,
        redeemed_at: datetime,
        redeemed_by_bp: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize permit already used error.

        Args:
            permit_id: UUID of the already-used permit.
            redeemed_at: When the permit was redeemed.
            redeemed_by_bp: Business process that consumed the permit.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        self.redeemed_at = redeemed_at
        self.redeemed_by_bp = redeemed_by_bp
        super().__init__(
            f"Permit token {permit_id} already redeemed at {redeemed_at.isoformat()}"
            + (f" by {redeemed_by_bp}" if redeemed_by_bp else ""),
            context={
                "permit_id": str(permit_id),
                "redeemed_at": redeemed_at.isoformat(),
                "redeemed_by_bp": redeemed_by_bp,
            },
            **kwargs,
        )


class PermitRevokedError(AuthorizationViolation):
    """Permit token has been revoked.

    Raised when: redeem_permit finds a token with status REVOKED.

    Phrase: permit_must_not_be_revoked
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit token has been revoked"

    __slots__ = ("permit_id",)

    def __init__(
        self,
        permit_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize permit revoked error.

        Args:
            permit_id: UUID of the revoked permit.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        super().__init__(
            f"Permit token {permit_id} has been revoked",
            context={"permit_id": str(permit_id)},
            **kwargs,
        )


class PermitSubjectMismatchError(AuthorizationViolation):
    """Permit token subject does not match requested subject.

    Raised when: redeem_permit is called with a different subject_id
    than the permit was issued for.

    Phrase: permit_subject_must_match
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit subject mismatch"

    __slots__ = ("actual_subject_id", "expected_subject_id", "permit_id")

    def __init__(
        self,
        permit_id: UUID,
        expected_subject_id: UUID,
        actual_subject_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize permit subject mismatch error.

        Args:
            permit_id: UUID of the permit.
            expected_subject_id: Subject the permit was issued for.
            actual_subject_id: Subject that was provided.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        self.expected_subject_id = expected_subject_id
        self.actual_subject_id = actual_subject_id
        super().__init__(
            f"Permit {permit_id} was issued for subject {expected_subject_id}, "
            f"but {actual_subject_id} was provided",
            context={
                "permit_id": str(permit_id),
                "expected_subject_id": str(expected_subject_id),
                "actual_subject_id": str(actual_subject_id),
            },
            **kwargs,
        )


class PermitActionMismatchError(AuthorizationViolation):
    """Permit token action does not match requested action.

    Raised when: redeem_permit is called with a different action
    than the permit was issued for.

    Phrase: permit_action_must_match
    """

    default_regulation = "SOX Section 404"
    default_message = "Permit action mismatch"

    __slots__ = ("actual_action", "expected_action", "permit_id")

    def __init__(
        self,
        permit_id: UUID,
        expected_action: str,
        actual_action: str,
        **kwargs: Any,
    ) -> None:
        """Initialize permit action mismatch error.

        Args:
            permit_id: UUID of the permit.
            expected_action: Action the permit was issued for.
            actual_action: Action that was requested.
            **kwargs: Additional arguments passed to parent.
        """
        self.permit_id = permit_id
        self.expected_action = expected_action
        self.actual_action = actual_action
        super().__init__(
            f"Permit {permit_id} was issued for action '{expected_action}', "
            f"but '{actual_action}' was requested",
            context={
                "permit_id": str(permit_id),
                "expected_action": expected_action,
                "actual_action": actual_action,
            },
            **kwargs,
        )
