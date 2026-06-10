"""Certification domain exceptions.

These exceptions are raised by certification actions when invariants are violated.
All inherit from the appropriate base exception in canon.enforcement.exceptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import (
    AuthorizationViolation,
    EvidenceViolation,
    TimingViolation,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "AttestationInvalidError",
    # Attestation errors
    "AttestationRequiredError",
    "CertificateAlreadyExistsError",
    "CertificateImmutableError",
    "CertificateNotFoundError",
    # Certificate errors
    "CertificateNotMintedError",
    # Timing errors
    "DisputeWindowNotClosedError",
    # Authorization errors
    "ERClearanceRequiredError",
    "ParityAttestationRequiredError",
]


# =============================================================================
# Certificate Errors
# =============================================================================


class CertificateNotMintedError(EvidenceViolation):
    """Certificate exists but is not in MINTED status.

    Raised when: An operation requires a minted certificate but the certificate
    is still in PROVISIONAL or GATED status.

    Regulatory basis:
    - SOX Section 802: Document finalization requirements
    - Employment law: Decisions must be certified before execution

    Phrase: certificate_must_be_minted
    """

    default_regulation = "SOX Section 802"
    default_message = "Certificate must be minted before use"

    __slots__ = ("certificate_id", "current_status")

    def __init__(
        self,
        certificate_id: UUID,
        current_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize certificate not minted error.

        Args:
            certificate_id: UUID of the certificate that is not minted.
            current_status: Current status of the certificate.
            **kwargs: Additional arguments passed to parent.
        """
        self.certificate_id = certificate_id
        self.current_status = current_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "certificate_id": str(certificate_id),
            "current_status": current_status,
            "required_status": "MINTED",
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Certificate {certificate_id} has status '{current_status}' but must be MINTED",
            context=merged_context,
            **kwargs,
        )


class CertificateAlreadyExistsError(EvidenceViolation):
    """A certified certificate already exists for this case.

    Raised when: Attempting to create a new certificate when one already exists,
    violating immutability requirements.

    Regulatory basis:
    - SOX Section 802: Document immutability
    - Employment law: Decision certificates cannot be regenerated

    Phrase: certificate_must_not_exist
    """

    default_regulation = "SOX Section 802"
    default_message = "Certificate already exists for this case"

    __slots__ = ("case_id", "existing_certificate_id")

    def __init__(
        self,
        case_id: UUID,
        existing_certificate_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize certificate already exists error.

        Args:
            case_id: UUID of the case.
            existing_certificate_id: UUID of the existing certificate.
            **kwargs: Additional arguments passed to parent.
        """
        self.case_id = case_id
        self.existing_certificate_id = existing_certificate_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "case_id": str(case_id),
            "existing_certificate_id": str(existing_certificate_id),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Certificate already exists for case {case_id}. "
            f"Decision certificates cannot be regenerated (immutability). "
            f"Existing certificate: {existing_certificate_id}",
            context=merged_context,
            **kwargs,
        )


class CertificateNotFoundError(EvidenceViolation):
    """Certificate not found.

    Raised when: A certificate lookup fails to find the requested certificate.

    Regulatory basis:
    - Evidence integrity requirements
    """

    default_regulation = "SOX Section 802"
    default_message = "Certificate not found"

    __slots__ = ("certificate_id",)

    def __init__(
        self,
        certificate_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Initialize certificate not found error.

        Args:
            certificate_id: UUID of the certificate that was not found.
            **kwargs: Additional arguments passed to parent.
        """
        self.certificate_id = certificate_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"certificate_id": str(certificate_id)}
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Certificate {certificate_id} not found",
            context=merged_context,
            **kwargs,
        )


class CertificateImmutableError(EvidenceViolation):
    """Attempted to modify an immutable certificate.

    Raised when: An operation attempts to modify a MINTED or SUPERSEDED certificate.

    Regulatory basis:
    - SOX Section 802: Document integrity
    - FRCP Rule 37(e): ESI preservation

    Phrase: certificate_must_be_mutable
    """

    default_regulation = "SOX Section 802"
    default_message = "Certificate is immutable and cannot be modified"

    __slots__ = ("certificate_id", "operation", "status")

    def __init__(
        self,
        certificate_id: UUID,
        status: str,
        operation: str,
        **kwargs: Any,
    ) -> None:
        """Initialize certificate immutable error.

        Args:
            certificate_id: UUID of the immutable certificate.
            status: Current status of the certificate.
            operation: The operation that was attempted.
            **kwargs: Additional arguments passed to parent.
        """
        self.certificate_id = certificate_id
        self.status = status
        self.operation = operation
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "certificate_id": str(certificate_id),
            "status": status,
            "operation": operation,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Cannot {operation} certificate {certificate_id}: "
            f"certificate in status '{status}' is immutable. Use supersession instead.",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Attestation Errors
# =============================================================================


class AttestationRequiredError(AuthorizationViolation):
    """Required attestation is missing.

    Raised when: An operation requires an attestation that has not been provided.

    Regulatory basis:
    - SOX Section 302: Officer certification requirements
    - Employment law: Dual sign-off for terminations
    """

    default_regulation = "SOX Section 302"
    default_message = "Required attestation is missing"

    __slots__ = ("attestation_type", "certificate_id", "required_role")

    def __init__(
        self,
        certificate_id: UUID,
        attestation_type: str,
        required_role: str,
        **kwargs: Any,
    ) -> None:
        """Initialize attestation required error.

        Args:
            certificate_id: UUID of the certificate requiring attestation.
            attestation_type: Type of attestation required.
            required_role: Role required to provide the attestation.
            **kwargs: Additional arguments passed to parent.
        """
        self.certificate_id = certificate_id
        self.attestation_type = attestation_type
        self.required_role = required_role
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "certificate_id": str(certificate_id),
            "attestation_type": attestation_type,
            "required_role": required_role,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Certificate {certificate_id} requires '{attestation_type}' "
            f"attestation from role '{required_role}'",
            context=merged_context,
            **kwargs,
        )


class AttestationInvalidError(AuthorizationViolation):
    """Attestation is invalid or insufficient.

    Raised when: An attestation fails validation (e.g., too short, wrong format).

    Regulatory basis:
    - SOX Section 302: Attestation quality requirements
    """

    default_regulation = "SOX Section 302"
    default_message = "Attestation is invalid"

    __slots__ = ("attestation_id", "reason")

    def __init__(
        self,
        attestation_id: UUID | None,
        reason: str,
        **kwargs: Any,
    ) -> None:
        """Initialize attestation invalid error.

        Args:
            attestation_id: UUID of the invalid attestation (if any).
            reason: Reason why the attestation is invalid.
            **kwargs: Additional arguments passed to parent.
        """
        self.attestation_id = attestation_id
        self.reason = reason
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "attestation_id": str(attestation_id) if attestation_id else None,
            "reason": reason,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Attestation invalid: {reason}",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Timing Errors
# =============================================================================


class DisputeWindowNotClosedError(TimingViolation):
    """Dispute window has not yet closed.

    Raised when: Attempting to certify FCRA notice before dispute window ends.

    Regulatory basis:
    - FCRA Section 1681b(b)(3): Reasonable waiting period (typically 5 days)
    """

    default_regulation = "FCRA Section 1681b(b)(3)"
    default_message = "Dispute window has not closed"

    __slots__ = ("current_time", "dispute_window_end", "notice_id")

    def __init__(
        self,
        notice_id: UUID,
        dispute_window_end: datetime,
        current_time: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize dispute window not closed error.

        Args:
            notice_id: UUID of the notice.
            dispute_window_end: When the dispute window ends.
            current_time: Current time.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        self.dispute_window_end = dispute_window_end
        self.current_time = current_time
        remaining = dispute_window_end - current_time
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "notice_id": str(notice_id),
            "dispute_window_end": dispute_window_end.isoformat(),
            "current_time": current_time.isoformat(),
            "remaining_seconds": int(remaining.total_seconds()),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Dispute window for notice {notice_id} has not closed. "
            f"Wait until {dispute_window_end.isoformat()}",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Authorization Errors
# =============================================================================


class ERClearanceRequiredError(AuthorizationViolation):
    """Employee Relations clearance is required.

    Raised when: Attempting involuntary termination without ER clearance.

    Regulatory basis:
    - Employment law: ER review for termination decisions
    """

    default_regulation = "Employment Law"
    default_message = "ER clearance required for involuntary termination"

    __slots__ = ("subject_id", "termination_type")

    def __init__(
        self,
        subject_id: UUID,
        termination_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize ER clearance required error.

        Args:
            subject_id: UUID of the employee being terminated.
            termination_type: Type of termination.
            **kwargs: Additional arguments passed to parent.
        """
        self.subject_id = subject_id
        self.termination_type = termination_type
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "subject_id": str(subject_id),
            "termination_type": termination_type,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"ER clearance required for {termination_type} termination of {subject_id}",
            context=merged_context,
            **kwargs,
        )


class ParityAttestationRequiredError(AuthorizationViolation):
    """Parity attestation is required.

    Raised when: Attempting involuntary termination without parity attestation.

    Regulatory basis:
    - Employment law: Similar treatment verification
    - Anti-discrimination requirements
    """

    default_regulation = "Employment Law"
    default_message = "Parity attestation required for involuntary termination"

    __slots__ = ("subject_id", "termination_type")

    def __init__(
        self,
        subject_id: UUID,
        termination_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize parity attestation required error.

        Args:
            subject_id: UUID of the employee being terminated.
            termination_type: Type of termination.
            **kwargs: Additional arguments passed to parent.
        """
        self.subject_id = subject_id
        self.termination_type = termination_type
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "subject_id": str(subject_id),
            "termination_type": termination_type,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Parity attestation required for {termination_type} termination of {subject_id}. "
            "Verify similar situations have been treated similarly.",
            context=merged_context,
            **kwargs,
        )
