"""Data protection domain types."""

from .audience import AudienceScope
from .classification import ClassificationLevel, ConfidentialityLevel
from .encryption import EncryptionStandard, EncryptionStatus
from .processor import ProcessorTermsStatus
from .publication import PublicationRestriction
from .retention import RetentionStatus

__all__ = [
    # Audience
    "AudienceScope",
    # Classification
    "ClassificationLevel",
    "ConfidentialityLevel",
    "EncryptionStandard",
    # Encryption
    "EncryptionStatus",
    # Processor
    "ProcessorTermsStatus",
    # Publication
    "PublicationRestriction",
    # Retention
    "RetentionStatus",
]
