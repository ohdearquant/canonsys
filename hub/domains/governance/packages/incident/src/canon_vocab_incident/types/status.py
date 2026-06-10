"""Incident lifecycle status types.

Covers the full lifecycle of security/data incidents from initial
draft through closure.

Regulatory context:
    - GDPR Art. 33: Breach notification timing (72 hours)
    - HIPAA 164.308(a)(6): Security incident procedures
    - SOC 2 CC7.2-CC7.4: Incident lifecycle
    - NIST SP 800-61: Incident handling phases
"""

from __future__ import annotations

from enum import StrEnum


class IncidentStatus(StrEnum):
    """Incident lifecycle status values.

    Tracks the incident through its full lifecycle:
    draft -> declared -> investigating -> contained -> resolved -> closed
    """

    DRAFT = "draft"  # Initial creation, not yet formally declared
    DECLARED = "declared"  # Formally declared as an incident
    INVESTIGATING = "investigating"  # Under active investigation
    CONTAINED = "contained"  # Incident contained, under remediation
    RESOLVED = "resolved"  # Root cause addressed, remediation complete
    CLOSED = "closed"  # Formally closed after post-incident review
