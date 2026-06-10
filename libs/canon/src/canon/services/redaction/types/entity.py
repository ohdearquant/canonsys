"""PII entity models for detection results.

PIIEntity is used for LLM-based semantic detection.
PIIDetection is used for regex-based pattern detection.
"""

from __future__ import annotations

from pydantic import BaseModel

from .category import PIICategory, SensitivityLevel

__all__ = [
    "PIIDetection",
    "PIIEntity",
]


class PIIEntity(BaseModel):
    """A detected PII entity with its redaction placeholder.

    Represents a single piece of PII found in text,
    with the original text and the placeholder used to replace it.

    Note: original_text is used ONLY during the redaction transform.
    It must NOT be persisted to database or returned in API responses.
    """

    category: PIICategory
    original_text: str  # Only for transform - never persist
    placeholder: str
    confidence: float = 1.0
    occurrences: int = 1


class PIIDetection(BaseModel):
    """A detected PII pattern match.

    Used by the regex-based scanner for safety gate checks.
    """

    category: PIICategory
    sensitivity: SensitivityLevel
    start_pos: int  # Character position in text
    end_pos: int  # End position in text
    matched_value: str  # The matched text (for logging/debugging only)
    confidence: float = 0.95  # Pattern match confidence
