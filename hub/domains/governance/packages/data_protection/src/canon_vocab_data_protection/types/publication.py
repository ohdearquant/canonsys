"""Publication restriction types for data protection domain.

Defines publication restriction levels for external content sharing.

Regulatory context:
    - SEC Regulation FD: Fair disclosure
    - ITAR 22 CFR 120-130: Export controls
    - Trade secret law (DTSA)
"""

from __future__ import annotations

from enum import StrEnum


class PublicationRestriction(StrEnum):
    """Publication restriction levels for external sharing."""

    NONE = "none"
    INTERNAL_ONLY = "internal_only"
    EMBARGO = "embargo"
    PROHIBITED = "prohibited"
