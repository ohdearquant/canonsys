"""Regex patterns for structured PII detection.

These are for the SAFETY GATE - patterns that should NEVER appear
in persisted data like evidence or logs.

References:
    - NIST SP 800-122 Appendix A: PII Examples
"""

from __future__ import annotations

import re
from enum import Enum
from typing import ClassVar

from .category import PIICategory

__all__ = [
    "PIIPatterns",
    "SpeakerRole",
]


class PIIPatterns:
    """Regex patterns for detecting structured PII.

    These are for the SAFETY GATE - patterns that should NEVER
    appear in persisted data like evidence or logs.
    """

    # Highly sensitive - MUST block
    SSN: ClassVar[re.Pattern[str]] = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD: ClassVar[re.Pattern[str]] = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    PASSPORT: ClassVar[re.Pattern[str]] = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")

    # Contact info - validate/redact
    EMAIL: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    )
    PHONE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )
    IP_ADDRESS: ClassVar[re.Pattern[str]] = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    @classmethod
    def get_patterns(cls) -> dict[PIICategory, re.Pattern[str]]:
        """Get all patterns mapped to categories."""
        return {
            PIICategory.SSN: cls.SSN,
            PIICategory.CREDIT_CARD: cls.CREDIT_CARD,
            PIICategory.PASSPORT: cls.PASSPORT,
            PIICategory.EMAIL: cls.EMAIL,
            PIICategory.PHONE: cls.PHONE,
            PIICategory.IP_ADDRESS: cls.IP_ADDRESS,
        }

    @classmethod
    def get_blocking_patterns(cls) -> dict[PIICategory, re.Pattern[str]]:
        """Get patterns that should BLOCK persistence."""
        return {
            PIICategory.SSN: cls.SSN,
            PIICategory.CREDIT_CARD: cls.CREDIT_CARD,
            PIICategory.PASSPORT: cls.PASSPORT,
        }


class SpeakerRole(str, Enum):
    """Speaker roles in a transcript.

    Uses conservative attribution - prefer uncertainty over false confidence.
    'lean_*' indicates probable but not certain attribution.
    'unsure' means the model couldn't determine speaker.

    Note: These are generic roles. Callers provide hints about who is who.
    """

    SPEAKER_A = "speaker_a"  # First speaker
    SPEAKER_B = "speaker_b"  # Second speaker
    LEAN_A = "lean_a"  # Probably speaker A, not certain
    LEAN_B = "lean_b"  # Probably speaker B, not certain
    UNSURE = "unsure"  # Cannot determine speaker
