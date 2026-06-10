"""Certification feature - vertical slice for certificate management.

This module provides the complete certification domain implementation:
- Types: CertificateStatus, CertificateClass, AttestationType, TerminationType, etc.
- Phrases: emit, mint, sign, supersede, certify_fcra_notice, certify_termination, etc.
- Exceptions: CertificateNotMintedError, AttestationRequiredError, etc.
- Service: CertificationService with protected operations

Regulatory context:
    - FCRA Section 1681m (Adverse action notices)
    - Employment law (Termination documentation)
    - SOX Section 302 (Officer certifications)
    - EU AI Act Article 12 (Record-keeping for AI systems)

Usage:
    from canon_vocab_certification import (
        # Types
        CertificateStatus,
        CertificateClass,
        TerminationType,
        AttestationType,
        # Phrases
        emit_certificate,
        mint_certificate,
        certify_fcra_notice,
        certify_termination,
        record_attestation,
        verify_certificate_integrity,
        revoke_certificate,
        # Specs
        CertifyFcraNoticeSpecs,
        CertifyTerminationSpecs,
        VerifyCertificateIntegritySpecs,
        RevokeCertificateSpecs,
        # Exceptions
        CertificateNotMintedError,
        AttestationRequiredError,
        # Service
        CertificationService,
    )
"""

# Package metadata
# Exceptions
from .exceptions import (
    AttestationInvalidError,
    AttestationRequiredError,
    CertificateAlreadyExistsError,
    CertificateImmutableError,
    CertificateNotFoundError,
    CertificateNotMintedError,
    DisputeWindowNotClosedError,
    ERClearanceRequiredError,
    ParityAttestationRequiredError,
)
from .package import CERTIFICATION

# Phrases (all phrase exports)
from .phrases import (  # Domain types from phrases; Specs classes; Phrase functions
    AttestationType,
    BuildCertificateSummarySpecs,
    CertifyFcraNoticeSpecs,
    CertifyTerminationSpecs,
    CheckCertificateExistsSpecs,
    EmitCertificateSpecs,
    MintCertificateSpecs,
    RecordAttestationSpecs,
    RequestTimestampAttestationSpecs,
    RevokeCertificateSpecs,
    SignCertificateSpecs,
    SupersedeCertificateSpecs,
    TerminationType,
    VerifyCertificateIntegritySpecs,
    build_certificate_summary,
    certify_fcra_notice,
    certify_termination,
    check_certificate_exists,
    emit_certificate,
    mint_certificate,
    record_attestation,
    request_timestamp_attestation,
    revoke_certificate,
    sign_certificate,
    supersede_certificate,
    verify_certificate_integrity,
)

# Service
from .service import CertificationService

# Types
from .types import (  # Attestation types; Certificate types (from core, re-exported); Workflow types
    AttestationMethod,
    CertificateClass,
    CertificateStatus,
    CertificationEvent,
    DecisionCertificate,
    DecisionCertificateContent,
    DefensibilityState,
    InputFingerprint,
    IntegrityVerification,
    ModelIdentity,
    ProceduralIntegrity,
    ReviewBehavior,
    SignerRole,
    WorkflowType,
)

__all__ = [
    # =========================================================================
    # Package metadata
    # =========================================================================
    "CERTIFICATION",
    # =========================================================================
    # Exceptions
    # =========================================================================
    "AttestationInvalidError",
    "AttestationRequiredError",
    "CertificateAlreadyExistsError",
    "CertificateImmutableError",
    "CertificateNotFoundError",
    "CertificateNotMintedError",
    "DisputeWindowNotClosedError",
    "ERClearanceRequiredError",
    "ParityAttestationRequiredError",
    # =========================================================================
    # Types
    # =========================================================================
    # Attestation types
    "AttestationMethod",
    "AttestationType",
    # Certificate types (from core)
    "CertificateClass",
    "CertificateStatus",
    "DecisionCertificate",
    "DecisionCertificateContent",
    "DefensibilityState",
    "InputFingerprint",
    "IntegrityVerification",
    "ModelIdentity",
    "ProceduralIntegrity",
    "ReviewBehavior",
    # Workflow types
    "CertificationEvent",
    "SignerRole",
    "TerminationType",
    "WorkflowType",
    # =========================================================================
    # Specs Classes (Pydantic BaseModels)
    # =========================================================================
    "BuildCertificateSummarySpecs",
    "CertifyFcraNoticeSpecs",
    "CertifyTerminationSpecs",
    "CheckCertificateExistsSpecs",
    "EmitCertificateSpecs",
    "MintCertificateSpecs",
    "RecordAttestationSpecs",
    "RequestTimestampAttestationSpecs",
    "RevokeCertificateSpecs",
    "SignCertificateSpecs",
    "SupersedeCertificateSpecs",
    "VerifyCertificateIntegritySpecs",
    # =========================================================================
    # Phrases
    # =========================================================================
    "build_certificate_summary",
    "certify_fcra_notice",
    "certify_termination",
    "check_certificate_exists",
    "emit_certificate",
    "mint_certificate",
    "record_attestation",
    "request_timestamp_attestation",
    "revoke_certificate",
    "sign_certificate",
    "supersede_certificate",
    "verify_certificate_integrity",
    # =========================================================================
    # Service
    # =========================================================================
    "CertificationService",
]
