"""Data protection vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

DATA_PROTECTION = VocabularyPackage(
    name="data_protection",
    description="Data classification, encryption, minimization, purpose limitation, and retention compliance.",
    feature_names=frozenset(
        {
            "require_encrypted_transmission",
            "require_internal_publication",
            "require_limited_audience",
            "require_pci_classification",
            "require_phi_classification",
            "require_pii_classification",
            "require_processor_terms_verified",
            "require_retention_compliance",
            "verify_data_minimization",
            "verify_purpose_limitation",
        }
    ),
    schema_names=frozenset(
        {
            "AudienceScope",
            "ClassificationLevel",
            "ConfidentialityLevel",
            "EncryptionStandard",
            "EncryptionStatus",
            "ProcessorTermsStatus",
            "PublicationRestriction",
            "RetentionStatus",
        }
    ),
    regulatory_basis=(
        "GDPR Art. 32",
        "HIPAA \u00a7 164.312",
        "PCI DSS",
    ),
    version="2026.01",
    domain_module="canon_vocab_data_protection",
)
