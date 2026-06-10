"""Redaction feature types.

Domain types for PII detection, redaction, and text segmentation.
"""

from .category import CATEGORY_SENSITIVITY, PIICategory, SensitivityLevel
from .chunk import RedactedChunk, SegmentBoundary, TextChunk
from .entity import PIIDetection, PIIEntity
from .options import RedactOptions, ScanOptions, SegmentOptions
from .patterns import PIIPatterns, SpeakerRole
from .result import PIIGateResult, PIIRedactionResult, ScanResult, SegmentationResult

__all__ = [
    # Category
    "PIICategory",
    "SensitivityLevel",
    "CATEGORY_SENSITIVITY",
    # Patterns
    "PIIPatterns",
    "SpeakerRole",
    # Entity
    "PIIEntity",
    "PIIDetection",
    # Chunk
    "TextChunk",
    "RedactedChunk",
    "SegmentBoundary",
    # Options
    "RedactOptions",
    "SegmentOptions",
    "ScanOptions",
    # Results
    "PIIRedactionResult",
    "ScanResult",
    "SegmentationResult",
    "PIIGateResult",
]
