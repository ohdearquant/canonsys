"""Certification feature types.

Exports all certification-related types:
- Certificate types (status, class, defensibility)
- Attestation types (method, type from actions)
- Workflow types (workflow type, events, signer roles)
"""

# Re-export phrase-defined types for convenience
# These are defined in phrases but exported here for consistent type access
from ..phrases import AttestationType, TerminationType
from .attestation import AttestationMethod
from .certificate import (
    CertificateClass,
    CertificateStatus,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
    InputFingerprint,
    IntegrityVerification,
    ModelIdentity,
    ProceduralIntegrity,
    ReviewBehavior,
)
from .workflow import CertificationEvent, SignerRole, WorkflowType

__all__ = (
    # Attestation types
    "AttestationMethod",
    "AttestationType",  # From actions
    # Certificate types (from core, re-exported)
    "CertificateClass",
    "CertificateStatus",
    "DecisionCertificate",
    "DecisionCertificateContent",
    "DefensibilityState",
    # Feature-specific certificate types
    "InputFingerprint",
    "IntegrityVerification",
    "ModelIdentity",
    "ProceduralIntegrity",
    "ReviewBehavior",
    # Workflow types
    "CertificationEvent",
    "SignerRole",
    # Termination types
    "TerminationType",  # From actions
    "WorkflowType",
)
