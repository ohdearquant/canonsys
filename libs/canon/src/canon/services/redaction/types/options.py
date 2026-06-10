"""Option models for redaction service actions."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from .chunk import TextChunk

__all__ = [
    "RedactOptions",
    "ScanOptions",
    "SegmentOptions",
]


class RedactOptions(BaseModel):
    """Options for redacting PII from text (LLM-based).

    Can accept either:
    - Simple text (text field)
    - Structured chunks (chunks field) for transcripts

    The redaction uses an LLM (default: gemini-2.5-flash via OpenRouter)
    for high-accuracy entity extraction.

    This is domain-agnostic. Callers provide:
    - entity_hints: Known entities to look for (e.g., {"person": ["John Smith"]})
    - context: Domain context (e.g., "interview transcript", "resume")
    """

    # Input (one of these required)
    text: str | None = None  # Simple text input
    chunks: list[TextChunk] | None = None  # Structured transcript input

    # Entity hints (improve extraction accuracy)
    entity_hints: dict[str, list[str]] | None = None  # e.g., {"person": ["John Smith"]}

    # Context for LLM (domain-agnostic)
    context: str | None = None  # e.g., "interview transcript", "resume text"

    # Model configuration
    model: str = "google/gemini-2.5-flash"
    provider: str = "openrouter"

    # Audit context
    workflow_run_id: UUID | None = None
    subject_id: UUID | None = None


class SegmentOptions(BaseModel):
    """Options for segmenting raw text into speaker turns (LLM-based).

    Takes unformatted text and divides it into speaker-attributed chunks.
    No alteration of content - just identification of boundaries.

    This is domain-agnostic. Callers provide context hints.
    """

    # Input (required)
    raw_text: str  # Unformatted text

    # Context hints (improve accuracy)
    speaker_a_hint: str | None = None  # e.g., "interviewer", "customer"
    speaker_b_hint: str | None = None  # e.g., "candidate", "agent"
    context: str | None = None  # e.g., "job interview", "customer support call"

    # Model configuration
    model: str = "google/gemini-2.5-flash"
    provider: str = "openrouter"

    # Audit context
    workflow_run_id: UUID | None = None


class ScanOptions(BaseModel):
    """Options for regex-based PII scanning (SAFETY GATE).

    Use to validate that data doesn't contain highly sensitive PII
    like SSN, credit cards, etc. before persistence.

    Modes:
    - block_only: Only scan for blocking patterns (SSN, CC, passport)
    - all: Scan for all patterns including email, phone, IP
    """

    # Input (required)
    text: str  # Text to scan

    # Scan mode
    block_only: bool = True  # Only check for blocking patterns

    # Whether to fail on detection
    fail_on_detection: bool = True  # Return error if PII found

    # Context for evidence
    context: str | None = None  # e.g., "evidence.data", "audit_log.message"
    subject_id: UUID | None = None
