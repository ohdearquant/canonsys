"""Derive regulatory notification deadline based on incident details.

This is a compliance timing primitive. Deadlines MUST be derived
from incident characteristics, not user-asserted.

Regulatory Context:
    GDPR Art. 33 requires 72-hour notification to supervisory authority.
    HIPAA varies by breach size. State laws vary significantly.
    SEC cybersecurity rules require 4-day Form 8-K for material incidents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveRegulatoryDeadlineSpecs", "derive_regulatory_deadline"]


# Deadline matrix: (incident_type, jurisdiction, severity) -> hours
_DEADLINE_HOURS: dict[tuple[str, str, str], int] = {
    # GDPR - 72 hours regardless of severity
    ("data_breach", "EU", "low"): 72,
    ("data_breach", "EU", "medium"): 72,
    ("data_breach", "EU", "high"): 72,
    ("data_breach", "EU", "critical"): 72,
    # HIPAA - 60 days but immediate for large breaches
    ("data_breach", "US-HIPAA", "low"): 1440,  # 60 days
    ("data_breach", "US-HIPAA", "medium"): 1440,
    ("data_breach", "US-HIPAA", "high"): 168,  # 7 days for >500 individuals
    ("data_breach", "US-HIPAA", "critical"): 24,  # Immediate for critical
    # SEC Cybersecurity - 4 business days (96 hours)
    ("cyber_incident", "US-SEC", "low"): 96,
    ("cyber_incident", "US-SEC", "medium"): 96,
    ("cyber_incident", "US-SEC", "high"): 96,
    ("cyber_incident", "US-SEC", "critical"): 96,
    # California - 72 hours
    ("data_breach", "US-CA", "low"): 72,
    ("data_breach", "US-CA", "medium"): 72,
    ("data_breach", "US-CA", "high"): 72,
    ("data_breach", "US-CA", "critical"): 24,  # AG notification expedited
    # New York - 72 hours
    ("data_breach", "US-NY", "low"): 72,
    ("data_breach", "US-NY", "medium"): 72,
    ("data_breach", "US-NY", "high"): 72,
    ("data_breach", "US-NY", "critical"): 24,
    # Default US - reasonable promptness (~45 days)
    ("data_breach", "US", "low"): 1080,
    ("data_breach", "US", "medium"): 720,
    ("data_breach", "US", "high"): 168,
    ("data_breach", "US", "critical"): 72,
}

# Default by severity when no specific rule exists
_DEFAULT_BY_SEVERITY: dict[str, int] = {
    "low": 720,  # 30 days
    "medium": 168,  # 7 days
    "high": 72,  # 3 days
    "critical": 24,  # 1 day
}


class DeriveRegulatoryDeadlineSpecs(BaseModel):
    """Specs for regulatory deadline derivation phrase."""

    # inputs
    incident_type: str
    jurisdiction: str
    severity: str
    # outputs
    deadline_hours: int | None = None


@canon_phrase(
    Operable.from_structure(DeriveRegulatoryDeadlineSpecs),
    inputs={"incident_type", "jurisdiction", "severity"},
    outputs={"deadline_hours", "incident_type", "jurisdiction", "severity"},
)
async def derive_regulatory_deadline(
    options,
    ctx: RequestContext,
) -> dict:
    """Derive regulatory notification deadline based on incident details.

    Args:
        options: Derivation options (incident_type, jurisdiction, severity)
        ctx: Request context for audit trail

    Returns:
        dict with deadline_hours, incident_type, jurisdiction, severity
    """
    incident_type: str = options.incident_type
    jurisdiction: str = options.jurisdiction
    severity: str = options.severity

    key = (incident_type, jurisdiction, severity)

    if key in _DEADLINE_HOURS:
        deadline_hours = _DEADLINE_HOURS[key]
    else:
        # Fall back to severity-based default
        deadline_hours = _DEFAULT_BY_SEVERITY.get(severity, 168)  # Default 7 days

    return {
        "deadline_hours": deadline_hours,
        "incident_type": incident_type,
        "jurisdiction": jurisdiction,
        "severity": severity,
    }
