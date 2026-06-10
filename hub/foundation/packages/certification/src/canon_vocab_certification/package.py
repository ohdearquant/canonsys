"""Certification vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CERTIFICATION = VocabularyPackage(
    name="certification",
    description="Decision certificates, FCRA notices, termination certification, and attestations.",
    feature_names=frozenset(
        {
            "build_certificate_summary",
            "certify_fcra_notice",
            "certify_termination",
            "check_certificate_exists",
            "emit_certificate",
            "mint_certificate",
            "record_attestation",
            "request_timestamp_attestation",
            "sign_certificate",
            "supersede_certificate",
        }
    ),
    schema_names=frozenset(
        {
            # Attestation types
            "AttestationMethod",
            "AttestationType",
            # Certificate types
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
            # Specs classes
            "BuildCertificateSummarySpecs",
            "CertifyFcraNoticeSpecs",
            "CertifyTerminationSpecs",
            "CheckCertificateExistsSpecs",
            "EmitCertificateSpecs",
            "MintCertificateSpecs",
            "RecordAttestationSpecs",
            "RequestTimestampAttestationSpecs",
            "SignCertificateSpecs",
            "SupersedeCertificateSpecs",
        }
    ),
    regulatory_basis=(
        "FCRA \u00a7 1681m",
        "SOX \u00a7 302",
        "Employment law",
    ),
    version="2026.01",
    domain_module="canon_vocab_certification",
)
