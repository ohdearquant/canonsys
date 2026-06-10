"""Result models for redaction, scan, and segmentation operations."""

from __future__ import annotations

from pydantic import BaseModel

from .category import PIICategory
from .chunk import RedactedChunk, SegmentBoundary, TextChunk
from .entity import PIIDetection, PIIEntity

__all__ = [
    "PIIGateResult",
    "PIIRedactionResult",
    "ScanResult",
    "SegmentationResult",
]


class PIIRedactionResult(BaseModel):
    """Result of PII redaction operation.

    Contains the redacted content and a manifest of all detected entities.
    This provides an audit trail proving what was redacted before AI processing.

    Note: The detected_entities list contains entity metadata but the
    original_text values should be stripped before persistence.
    """

    # Redacted content
    redacted_text: str | None = None  # For simple text input
    redacted_chunks: list[RedactedChunk] | None = None  # For structured input

    # Entity manifest (for audit trail - placeholders only, not original text)
    detected_entities: list[PIIEntity] = []

    # Summary statistics
    total_entities_detected: int = 0
    total_redactions_applied: int = 0
    categories_detected: list[PIICategory] = []

    # Entity counts by category
    company_count: int = 0
    person_count: int = 0

    # Metadata
    model_used: str = "google/gemini-2.5-flash"
    processing_time_ms: int | None = None

    def for_persistence(self) -> PIIRedactionResult:
        """Return a copy safe for persistence (original_text stripped)."""
        # Strip original_text from entities
        safe_entities = [
            PIIEntity(
                category=e.category,
                original_text="[REDACTED]",  # Never persist actual PII
                placeholder=e.placeholder,
                confidence=e.confidence,
                occurrences=e.occurrences,
            )
            for e in self.detected_entities
        ]

        # Strip original_text/original_speaker from chunks
        safe_chunks = None
        if self.redacted_chunks:
            safe_chunks = [
                RedactedChunk(
                    speaker=c.speaker,
                    text=c.text,
                    start_time=c.start_time,
                    end_time=c.end_time,
                    chunk_index=c.chunk_index,
                    entities_redacted=c.entities_redacted,
                    # Explicitly exclude original_* fields
                )
                for c in self.redacted_chunks
            ]

        return PIIRedactionResult(
            redacted_text=self.redacted_text,
            redacted_chunks=safe_chunks,
            detected_entities=safe_entities,
            total_entities_detected=self.total_entities_detected,
            total_redactions_applied=self.total_redactions_applied,
            categories_detected=self.categories_detected,
            company_count=self.company_count,
            person_count=self.person_count,
            model_used=self.model_used,
            processing_time_ms=self.processing_time_ms,
        )


class ScanResult(BaseModel):
    """Result of regex-based PII scan.

    Used as a pre-persistence safety gate. If blocking_violations > 0,
    the data should NOT be persisted.
    """

    # Detections found
    detections: list[PIIDetection] = []

    # Summary
    total_detections: int = 0
    blocking_violations: int = 0  # Highly sensitive PII found
    categories_detected: list[PIICategory] = []

    # Decision
    safe_to_persist: bool = True  # False if blocking_violations > 0
    block_reason: str | None = None

    # Metadata
    text_length: int = 0
    scan_time_ms: int | None = None

    def has_blocking_pii(self) -> bool:
        """Check if any blocking PII was detected."""
        return self.blocking_violations > 0


class SegmentationResult(BaseModel):
    """Result of transcript segmentation.

    Contains boundaries that divide raw text into speaker turns.
    Original text is untouched - we just provide slicing instructions.
    """

    # The boundaries (slicing instructions)
    boundaries: list[SegmentBoundary] = []

    # The original text (preserved exactly)
    original_text: str = ""
    original_length: int = 0

    # Structured output (text sliced at boundaries)
    segments: list[TextChunk] = []

    # Summary
    total_segments: int = 0
    speaker_a_segments: int = 0
    speaker_b_segments: int = 0

    # Metadata
    model_used: str = "google/gemini-2.5-flash"
    processing_time_ms: int | None = None


class PIIGateResult(BaseModel):
    """Result of PII gate check.

    Binary: either passed or blocked. No transformations.
    """

    gate_id: str
    passed: bool
    block_reason: str | None = None
    detected_categories: list[PIICategory] = []
    detection_count: int = 0
    blocking_count: int = 0  # Count of highly sensitive PII
    scan_time_ms: int = 0

    @property
    def is_blocked(self) -> bool:
        return not self.passed
