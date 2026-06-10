"""Data classification types for data protection domain.

Covers classification levels for data sensitivity and confidentiality.

Regulatory context:
    - SOC 2 CC6.1: Logical and physical access controls
    - ISO 27001: Information security management
    - NIST SP 800-53: Security and privacy controls
"""

from __future__ import annotations

from enum import StrEnum


class ClassificationLevel(StrEnum):
    """Data classification levels.

    Standard four-tier classification model for data sensitivity.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

    @classmethod
    def minimum_for_pii(cls) -> ClassificationLevel:
        """Minimum classification level for PII data."""
        return cls.INTERNAL

    @classmethod
    def minimum_for_pci(cls) -> ClassificationLevel:
        """Minimum classification level for PCI data."""
        return cls.CONFIDENTIAL

    @classmethod
    def minimum_for_phi(cls) -> ClassificationLevel:
        """Minimum classification level for PHI data."""
        return cls.CONFIDENTIAL


class ConfidentialityLevel(StrEnum):
    """Confidentiality levels for audience-based access control.

    Used for determining what audiences can access content.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
