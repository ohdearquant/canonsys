"""Identity domain exceptions.

These exceptions are raised by identity phrases when invariants are violated.
All inherit from AuthorizationViolation (the domain's base exception).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import AuthorizationViolation

if TYPE_CHECKING:
    from uuid import UUID

    from .types import AALLevel, AuthPosture

__all__ = [
    "AssuranceLevelInsufficientError",
    "AuthPostureInsufficientError",
    "IdPPostureInsufficientError",
    "RequestNotAuthenticatedError",
]


class AuthPostureInsufficientError(AuthorizationViolation):
    """Authentication posture does not meet required level.

    Raised when: verify_strong_auth_posture finds the subject's
    authentication posture is below what's required.

    Regulatory basis:
    - NIST SP 800-63B Section 4: Authenticator assurance levels
    - SOC 2 CC6.1: Logical and physical access controls
    - GDPR Art. 32: Security of processing

    Phrase: auth_posture_must_be_sufficient
    """

    default_regulation = "NIST SP 800-63B"
    default_message = "Authentication posture insufficient"

    __slots__ = ("actual_posture", "required_posture", "subject_id")

    def __init__(
        self,
        subject_id: UUID,
        required_posture: AuthPosture,
        actual_posture: AuthPosture,
        **kwargs: Any,
    ) -> None:
        """Initialize auth posture insufficient error.

        Args:
            subject_id: UUID of the subject with insufficient posture.
            required_posture: Posture level required for the operation.
            actual_posture: Subject's actual posture level.
            **kwargs: Additional arguments passed to parent.
        """
        self.subject_id = subject_id
        self.required_posture = required_posture
        self.actual_posture = actual_posture
        super().__init__(
            f"Auth posture insufficient: required '{required_posture}', "
            f"subject {subject_id} has '{actual_posture}'",
            context={
                "subject_id": str(subject_id),
                "required_posture": required_posture,
                "actual_posture": actual_posture,
            },
            **kwargs,
        )


class AssuranceLevelInsufficientError(AuthorizationViolation):
    """Authenticator assurance level does not meet required level.

    Raised when: verify_assurance_equivalent finds the source AAL
    is below the target AAL required.

    Regulatory basis:
    - NIST SP 800-63B Section 4: Authenticator assurance levels
    - FedRAMP: AAL2 minimum for Moderate, AAL3 for High
    - eIDAS: Substantial (AAL2) and High (AAL3) LoA

    Phrase: assurance_level_must_be_sufficient
    """

    default_regulation = "NIST SP 800-63B"
    default_message = "Assurance level insufficient"

    __slots__ = ("gap", "source_level", "target_level")

    def __init__(
        self,
        source_level: AALLevel,
        target_level: AALLevel,
        gap: int,
        **kwargs: Any,
    ) -> None:
        """Initialize assurance level insufficient error.

        Args:
            source_level: The AAL level of the authentication being evaluated.
            target_level: The AAL level required for the operation.
            gap: Number of levels between source and target.
            **kwargs: Additional arguments passed to parent.
        """
        self.source_level = source_level
        self.target_level = target_level
        self.gap = gap
        super().__init__(
            f"Assurance level insufficient: required '{target_level}', "
            f"have '{source_level}' (gap: {gap})",
            context={
                "source_level": source_level,
                "target_level": target_level,
                "gap": gap,
            },
            **kwargs,
        )


class IdPPostureInsufficientError(AuthorizationViolation):
    """Identity provider posture attestation does not meet required level.

    Raised when: verify_idp_posture_attestation finds the IdP's
    posture attestation is below what's required.

    Regulatory basis:
    - NIST SP 800-63C Section 5: Federation assurance
    - SOC 2 CC9.2: Third-party risk management
    - FedRAMP: Identity provider authorization requirements

    Phrase: idp_posture_must_be_sufficient
    """

    default_regulation = "NIST SP 800-63C"
    default_message = "IdP posture attestation insufficient"

    __slots__ = ("actual_posture", "idp_id", "required_posture")

    def __init__(
        self,
        idp_id: UUID,
        required_posture: str,
        actual_posture: str,
        **kwargs: Any,
    ) -> None:
        """Initialize IdP posture insufficient error.

        Args:
            idp_id: UUID of the identity provider.
            required_posture: Posture level required.
            actual_posture: IdP's actual attested posture level.
            **kwargs: Additional arguments passed to parent.
        """
        self.idp_id = idp_id
        self.required_posture = required_posture
        self.actual_posture = actual_posture
        super().__init__(
            f"IdP {idp_id} posture insufficient: required '{required_posture}', "
            f"has '{actual_posture}'",
            context={
                "idp_id": str(idp_id),
                "required_posture": required_posture,
                "actual_posture": actual_posture,
            },
            **kwargs,
        )


class RequestNotAuthenticatedError(AuthorizationViolation):
    """Request source is not properly authenticated.

    Raised when: verify_request_source_authenticated finds no valid
    authentication for the request.

    Regulatory basis:
    - NIST SP 800-63 Section 6: Authentication and lifecycle
    - SOC 2 CC6.1: Entity implements logical access security
    - OAuth 2.0 RFC 6749: Authorization framework

    Phrase: request_must_be_authenticated
    """

    default_regulation = "NIST SP 800-63"
    default_message = "Request not authenticated"

    __slots__ = ("reason", "request_id")

    def __init__(
        self,
        request_id: UUID,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """Initialize request not authenticated error.

        Args:
            request_id: UUID of the unauthenticated request.
            reason: Why authentication failed (expired, missing, etc).
            **kwargs: Additional arguments passed to parent.
        """
        self.request_id = request_id
        self.reason = reason
        super().__init__(
            f"Request {request_id} not authenticated: {reason}",
            context={
                "request_id": str(request_id),
                "reason": reason,
            },
            **kwargs,
        )
