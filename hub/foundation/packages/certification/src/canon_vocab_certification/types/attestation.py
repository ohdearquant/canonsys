"""Attestation-related types.

Attestation method and options for certification workflows.
"""

from __future__ import annotations

from kron.types import Enum

__all__ = ("AttestationMethod",)


class AttestationMethod(Enum):
    """Methods of capturing attestation.

    Represents how the attestation was physically captured.
    Used for audit trail completeness.
    """

    PORTAL_CLICK = "portal_click"
    """Attester clicked acknowledgment in web portal."""

    EMAIL_CONFIRM = "email_confirm"
    """Attester confirmed via email link."""

    WET_SIGNATURE = "wet_signature"
    """Physical ink signature on document."""

    DIGITAL_SIGNATURE = "digital_signature"
    """Cryptographic digital signature (e.g., DocuSign)."""

    VERBAL_RECORDED = "verbal_recorded"
    """Verbal attestation captured on recording."""

    SYSTEM = "system"
    """System-generated attestation (automated)."""
