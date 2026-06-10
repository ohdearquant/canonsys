"""Data Protection feature - vertical slice for data protection compliance.

This module provides the complete data protection domain implementation:
- Types: ClassificationLevel, EncryptionStatus, RetentionStatus, etc.
- Phrases: require_pii_classification, verify_data_minimization, etc.
- Exceptions: ProcessorTermsNotVerifiedError, DataMinimizationError, etc.
- Service: DataProtectionService with evidence emission

Regulatory context:
    - GDPR (Data protection principles)
    - HIPAA (PHI safeguards)
    - PCI DSS (Cardholder data protection)
    - CCPA (Consumer privacy rights)

Usage:
    from canon_vocab_data_protection import (
        # Types
        ClassificationLevel,
        EncryptionStatus,
        # Specs classes
        RequirePIIClassificationSpecs,
        VerifyDataMinimizationSpecs,
        # Phrases
        require_pii_classification,
        verify_data_minimization,
        # Service
        DataProtectionService,
        # Exceptions
        ProcessorTermsNotVerifiedError,
        # Package metadata
        DATA_PROTECTION,
    )
"""

# Exceptions
from .exceptions import (
    DataMinimizationError,
    LimitedAudienceRequiredError,
    ProcessorTermsNotVerifiedError,
    PublicationRestrictedError,
    PurposeLimitationError,
    RetentionComplianceRequiredError,
)

# Package metadata
from .package import DATA_PROTECTION

# Phrases (includes Specs classes and phrase functions)
from .phrases import (  # Specs classes; Phrase functions
    RequireEncryptedTransmissionSpecs,
    RequireInternalPublicationSpecs,
    RequireLimitedAudienceSpecs,
    RequirePCIClassificationSpecs,
    RequirePHIClassificationSpecs,
    RequirePIIClassificationSpecs,
    RequireProcessorTermsVerifiedSpecs,
    RequireRetentionComplianceSpecs,
    VerifyDataMinimizationSpecs,
    VerifyPurposeLimitationSpecs,
    require_encrypted_transmission,
    require_internal_publication,
    require_limited_audience,
    require_pci_classification,
    require_phi_classification,
    require_pii_classification,
    require_processor_terms_verified,
    require_retention_compliance,
    verify_data_minimization,
    verify_purpose_limitation,
)

# Service
from .service import DataProtectionService

# Types
from .types import (
    AudienceScope,
    ClassificationLevel,
    ConfidentialityLevel,
    EncryptionStandard,
    EncryptionStatus,
    ProcessorTermsStatus,
    PublicationRestriction,
    RetentionStatus,
)

__all__ = [
    # Package metadata
    "DATA_PROTECTION",
    # Service
    "DataProtectionService",
    # Types - Audience
    "AudienceScope",
    # Types - Classification
    "ClassificationLevel",
    "ConfidentialityLevel",
    # Exceptions
    "DataMinimizationError",
    # Types - Encryption
    "EncryptionStandard",
    "EncryptionStatus",
    "LimitedAudienceRequiredError",
    "ProcessorTermsNotVerifiedError",
    # Types - Processor
    "ProcessorTermsStatus",
    # Types - Publication
    "PublicationRestriction",
    "PublicationRestrictedError",
    "PurposeLimitationError",
    # Specs classes (Pydantic BaseModels)
    "RequireEncryptedTransmissionSpecs",
    "RequireInternalPublicationSpecs",
    "RequireLimitedAudienceSpecs",
    "RequirePCIClassificationSpecs",
    "RequirePHIClassificationSpecs",
    "RequirePIIClassificationSpecs",
    "RequireProcessorTermsVerifiedSpecs",
    "RequireRetentionComplianceSpecs",
    "RetentionComplianceRequiredError",
    # Types - Retention
    "RetentionStatus",
    "VerifyDataMinimizationSpecs",
    "VerifyPurposeLimitationSpecs",
    # Phrase functions
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
]
