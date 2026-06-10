"""PolicyAuthority - legal/regulatory citation backing policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyAuthority:
    """Legal/regulatory authority backing a policy.

    Every PolicyDefinition MUST cite its authority.
    A policy without citation is opinion - opinions lose lawsuits.

    Example:
        PolicyAuthority(
            citation="NYC Admin Code Section 8-107(11-a)",
            jurisdiction_code="US-NYC",
            effective_date=date(2024, 7, 5),
        )
    """

    citation: str
    """Legal citation (e.g., "FCRA 15 U.S.C. § 1681b(b)(3)")."""

    jurisdiction_code: str
    """ISO-style jurisdiction (e.g., US-NYC, US-CA, EU-DE)."""

    effective_date: date
    """When this authority became enforceable."""

    superseded_date: date | None = None
    """When this authority was superseded (if applicable)."""

    source_url: str | None = None
    """URL to authoritative source document."""

    notes: str | None = None
    """Additional context or interpretation guidance."""

    def is_effective(self, as_of: date | None = None) -> bool:
        """Check if authority is currently effective."""
        check_date = as_of or date.today()
        if check_date < self.effective_date:
            return False
        if self.superseded_date and check_date >= self.superseded_date:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSONB storage."""
        return {
            "citation": self.citation,
            "jurisdiction_code": self.jurisdiction_code,
            "effective_date": self.effective_date.isoformat(),
            "superseded_date": (self.superseded_date.isoformat() if self.superseded_date else None),
            "source_url": self.source_url,
            "notes": self.notes,
        }
