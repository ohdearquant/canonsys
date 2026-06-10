"""PII detection - regex-based safety net before data persistence.

Blocking patterns (SSN, credit card, passport) MUST NOT be stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "PIIMatch",
    "PIIPattern",
    "PIIScanResult",
    "has_blocking_pii",
    "scan_for_pii",
]


class PIIPattern(StrEnum):
    """PII patterns with regex and sensitivity level."""

    # Highly sensitive - BLOCK persistence
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    PASSPORT = "passport"

    # Confidential - validate/redact
    EMAIL = "email"
    PHONE = "phone"
    IP_ADDRESS = "ip_address"

    @property
    def regex(self) -> re.Pattern[str]:
        """Compiled regex pattern for this PII type."""
        return _REGEX_MAP[self]

    @property
    def is_blocking(self) -> bool:
        """True if this pattern should block persistence."""
        return self in _BLOCKING

    @classmethod
    def blocking(cls) -> frozenset[PIIPattern]:
        """All blocking patterns."""
        return _BLOCKING

    @classmethod
    def all_patterns(cls) -> frozenset[PIIPattern]:
        """All available patterns."""
        return frozenset(cls)


# Pattern regex definitions (compiled once at module load)
_REGEX_MAP: dict[PIIPattern, re.Pattern[str]] = {
    PIIPattern.SSN: re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    PIIPattern.CREDIT_CARD: re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    PIIPattern.PASSPORT: re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    PIIPattern.EMAIL: re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    PIIPattern.PHONE: re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    PIIPattern.IP_ADDRESS: re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_BLOCKING: frozenset[PIIPattern] = frozenset(
    {
        PIIPattern.SSN,
        PIIPattern.CREDIT_CARD,
        PIIPattern.PASSPORT,
    }
)


@dataclass(frozen=True, slots=True)
class PIIMatch:
    """A single PII match. Stores position only, never the matched value."""

    pattern: PIIPattern
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class PIIScanResult:
    """Result of PII scan."""

    matches: list[PIIMatch] = field(default_factory=list)
    text_length: int = 0

    @property
    def blocking_count(self) -> int:
        """Count of blocking matches."""
        return sum(1 for m in self.matches if m.pattern.is_blocking)

    @property
    def safe_to_persist(self) -> bool:
        """True if no blocking PII was detected."""
        return self.blocking_count == 0

    @property
    def blocking_types(self) -> list[PIIPattern]:
        """Blocking patterns that were detected."""
        return [m.pattern for m in self.matches if m.pattern.is_blocking]

    def block_reason(self) -> str | None:
        """Human-readable reason for blocking, or None if safe."""
        if self.safe_to_persist:
            return None
        types = sorted({t.value for t in self.blocking_types})
        return f"Blocking PII detected: {', '.join(types)}"


def scan_for_pii(text: str, *, blocking_only: bool = True) -> PIIScanResult:
    """Scan text for PII patterns. Returns PIIScanResult."""
    if not text:
        return PIIScanResult(text_length=0)

    patterns = PIIPattern.blocking() if blocking_only else PIIPattern.all_patterns()
    matches: list[PIIMatch] = []

    for pii in patterns:
        for match in pii.regex.finditer(text):
            matches.append(PIIMatch(pattern=pii, start=match.start(), end=match.end()))

    matches.sort(key=lambda m: m.start)
    return PIIScanResult(matches=matches, text_length=len(text))


def has_blocking_pii(text: str) -> bool:
    """Quick check if text contains blocking PII."""
    if not text:
        return False
    return any(pii.regex.search(text) for pii in PIIPattern.blocking())
