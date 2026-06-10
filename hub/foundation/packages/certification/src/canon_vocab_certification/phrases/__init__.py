"""Certification domain phrases.

All certification operations in one place:
- FCRA: certify_fcra_notice
- Termination: certify_termination
- Certificates: emit, mint, sign, supersede, check_exists, verify_integrity, revoke
- Attestations: record_attestation, request_timestamp_attestation
- Display: build_certificate_summary

Regulatory context:
    - FCRA Section 1681m (Adverse action notices)
    - Employment law (Termination documentation)
    - SOX Section 302 (Officer certifications)
    - SOX Section 802 (Document integrity)
"""

from .build_certificate_summary import (
    BuildCertificateSummarySpecs,
    build_certificate_summary,
)
from .certify_decision import CertifyDecisionSpecs, certify_decision
from .certify_fcra_notice import CertifyFcraNoticeSpecs, certify_fcra_notice
from .certify_termination import (
    CertifyTerminationSpecs,
    TerminationType,
    certify_termination,
)
from .check_certificate_exists import (
    CheckCertificateExistsSpecs,
    check_certificate_exists,
)
from .emit_certificate import (
    EmitCertificateSpecs,
    MintCertificateSpecs,
    emit_certificate,
    mint_certificate,
)
from .record_attestation import (
    AttestationType,
    RecordAttestationSpecs,
    record_attestation,
)
from .request_timestamp_attestation import (
    RequestTimestampAttestationSpecs,
    request_timestamp_attestation,
)
from .revoke_certificate import RevokeCertificateSpecs, revoke_certificate
from .sign_certificate import SignCertificateSpecs, sign_certificate
from .supersede_certificate import SupersedeCertificateSpecs, supersede_certificate
from .verify_certificate_integrity import (
    VerifyCertificateIntegritySpecs,
    verify_certificate_integrity,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
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
    # Domain types
    "AttestationType",
    "TerminationType",
    # Phrase functions
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
    # P0 additions
    "CertifyDecisionSpecs",
    "certify_decision",
]
