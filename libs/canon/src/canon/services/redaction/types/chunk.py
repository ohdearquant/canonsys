"""Text chunk and segment boundary models.

Used for transcript processing with speaker attribution.
"""

from __future__ import annotations

from pydantic import BaseModel

from .patterns import SpeakerRole

__all__ = [
    "RedactedChunk",
    "SegmentBoundary",
    "TextChunk",
]


class TextChunk(BaseModel):
    """Input/output chunk for segmentation and redaction."""

    speaker: str
    text: str
    start_time: float | None = None
    end_time: float | None = None
    chunk_index: int = 0


class RedactedChunk(BaseModel):
    """A text chunk with PII redacted.

    Used for transcripts and other structured text.

    Note: original_text/original_speaker are used ONLY during the
    redaction transform for quality assurance. They must NOT be
    persisted to database or returned in API responses.
    """

    speaker: str  # Redacted speaker (e.g., "[SPEAKER_A]")
    text: str  # Redacted text with placeholders
    start_time: float | None = None
    end_time: float | None = None
    chunk_index: int = 0
    entities_redacted: int = 0

    # Transform-only fields - never persist these
    original_speaker: str | None = None
    original_text: str | None = None


class SegmentBoundary(BaseModel):
    """A segment boundary with character positions.

    Represents where one speaker turn starts and ends in raw text.
    The original text is never modified - we just record positions.
    """

    start_char: int  # Start character position (inclusive)
    end_char: int  # End character position (exclusive)
    speaker: SpeakerRole
    confidence: float = 1.0  # LLM confidence in attribution
