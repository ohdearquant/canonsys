"""Data protection domain phrases.

All data protection operations in one place:
- Classification phrases: require_pii_classification, require_pci_classification, require_phi_classification
- Transmission phrases: require_encrypted_transmission
- Audience phrases: require_limited_audience
- Retention phrases: require_retention_compliance
- Publication phrases: require_internal_publication
- Processor phrases: require_processor_terms_verified
- Verification phrases: verify_data_minimization, verify_purpose_limitation
"""

from .require_data_classification_assigned import (
    RequireDataClassificationAssignedSpecs,
    require_data_classification_assigned,
)
from .require_encrypted_transmission import (
    RequireEncryptedTransmissionSpecs,
    require_encrypted_transmission,
)
from .require_internal_publication import (
    RequireInternalPublicationSpecs,
    require_internal_publication,
)
from .require_limited_audience import (
    RequireLimitedAudienceSpecs,
    require_limited_audience,
)
from .require_pci_classification import (
    RequirePCIClassificationSpecs,
    require_pci_classification,
)
from .require_phi_classification import (
    RequirePHIClassificationSpecs,
    require_phi_classification,
)
from .require_pii_classification import (
    RequirePIIClassificationSpecs,
    require_pii_classification,
)
from .require_processor_terms_verified import (
    RequireProcessorTermsVerifiedSpecs,
    require_processor_terms_verified,
)
from .require_retention_compliance import (
    RequireRetentionComplianceSpecs,
    require_retention_compliance,
)
from .verify_data_minimization import (
    VerifyDataMinimizationSpecs,
    verify_data_minimization,
)
from .verify_purpose_limitation import (
    VerifyPurposeLimitationSpecs,
    verify_purpose_limitation,
)

__all__ = [
    # Specs classes (Pydantic BaseModels)
    "RequireDataClassificationAssignedSpecs",
    "RequireEncryptedTransmissionSpecs",
    "RequireInternalPublicationSpecs",
    "RequireLimitedAudienceSpecs",
    "RequirePCIClassificationSpecs",
    "RequirePHIClassificationSpecs",
    "RequirePIIClassificationSpecs",
    "RequireProcessorTermsVerifiedSpecs",
    "RequireRetentionComplianceSpecs",
    "VerifyDataMinimizationSpecs",
    "VerifyPurposeLimitationSpecs",
    # Phrase functions
    "require_data_classification_assigned",
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
