"""Audience scope types for data protection domain.

Defines audience tiers for content sharing restrictions.

Regulatory context:
    - GDPR Art. 5(1)(f): Confidentiality
    - HIPAA 164.502: Minimum necessary
    - SOC 2 CC6.1: Access restrictions
"""

from __future__ import annotations

from enum import StrEnum


class AudienceScope(StrEnum):
    """Audience scope for content sharing.

    Defines the breadth of audience that can access content.
    """

    INDIVIDUAL = "individual"
    TEAM = "team"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    UNLIMITED = "unlimited"

    @classmethod
    def restricted_audiences(cls) -> frozenset[AudienceScope]:
        """Audiences that require special handling for confidential data."""
        return frozenset({cls.ORGANIZATION, cls.UNLIMITED})
