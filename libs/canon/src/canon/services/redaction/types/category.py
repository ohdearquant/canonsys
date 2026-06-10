"""PII categories and sensitivity levels.

Based on NIST SP 800-122 and GDPR Article 9 for sensitivity classification.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "CATEGORY_SENSITIVITY",
    "PIICategory",
    "SensitivityLevel",
]


class PIICategory(str, Enum):
    """Categories of PII that can be detected and redacted.

    Each category maps to a specific placeholder format in redacted output.
    These are general-purpose categories - callers provide domain context.
    """

    # Named entities (LLM-detected)
    PERSON = "person"  # -> [PERSON_N]
    COMPANY = "company"  # -> [COMPANY_N]
    SCHOOL = "school"  # -> [SCHOOL_N]

    # Contact info (regex + LLM)
    EMAIL = "email"  # -> [EMAIL]
    PHONE = "phone"  # -> [PHONE]
    ADDRESS = "address"  # -> [ADDRESS]

    # Location/time (LLM-detected)
    LOCATION = "location"  # -> [LOCATION]
    DATE = "date"  # -> [DATE]

    # Highly sensitive - REGEX ONLY (must NEVER persist)
    SSN = "ssn"  # -> [SSN] - Social Security Number
    CREDIT_CARD = "credit_card"  # -> [CREDIT_CARD]
    PASSPORT = "passport"  # -> [PASSPORT]
    DRIVERS_LICENSE = "drivers_license"  # -> [DRIVERS_LICENSE]
    IP_ADDRESS = "ip_address"  # -> [IP_ADDRESS]


class SensitivityLevel(str, Enum):
    """Sensitivity levels for PII categories.

    Based on NIST SP 800-122 and GDPR Article 9.
    """

    HIGHLY_SENSITIVE = "highly_sensitive"  # SSN, passport, biometric
    SENSITIVE = "sensitive"  # Health, race, religion (GDPR Art. 9)
    CONFIDENTIAL = "confidential"  # Email, phone, name
    INTERNAL = "internal"  # IP address, device ID


# Sensitivity mapping for categories
CATEGORY_SENSITIVITY: dict[PIICategory, SensitivityLevel] = {
    # Highly Sensitive - BLOCK persistence
    PIICategory.SSN: SensitivityLevel.HIGHLY_SENSITIVE,
    PIICategory.CREDIT_CARD: SensitivityLevel.HIGHLY_SENSITIVE,
    PIICategory.PASSPORT: SensitivityLevel.HIGHLY_SENSITIVE,
    PIICategory.DRIVERS_LICENSE: SensitivityLevel.HIGHLY_SENSITIVE,
    # Confidential - Redact before AI, validate before persist
    PIICategory.EMAIL: SensitivityLevel.CONFIDENTIAL,
    PIICategory.PHONE: SensitivityLevel.CONFIDENTIAL,
    PIICategory.ADDRESS: SensitivityLevel.CONFIDENTIAL,
    PIICategory.PERSON: SensitivityLevel.CONFIDENTIAL,
    PIICategory.DATE: SensitivityLevel.CONFIDENTIAL,
    # Internal
    PIICategory.IP_ADDRESS: SensitivityLevel.INTERNAL,
    PIICategory.LOCATION: SensitivityLevel.INTERNAL,
    PIICategory.COMPANY: SensitivityLevel.INTERNAL,
    PIICategory.SCHOOL: SensitivityLevel.INTERNAL,
}
