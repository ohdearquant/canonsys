"""Export control constants.

Prohibited destinations and sanction program mappings
for OFAC comprehensive sanctions compliance.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

__all__ = [
    "PROHIBITED_DESTINATIONS",
    "PROHIBITION_INFO",
]

# Comprehensively sanctioned destinations (ISO-3166-1 alpha-2)
# These are countries under comprehensive US sanctions programs
PROHIBITED_DESTINATIONS: frozenset[str] = frozenset(
    {
        "CU",  # Cuba - OFAC Cuba Sanctions
        "IR",  # Iran - OFAC Iran Sanctions
        "KP",  # North Korea - OFAC DPRK Sanctions
        "SY",  # Syria - OFAC Syria Sanctions
        # Note: Crimea region (part of UA) requires special handling
        # Note: Russia (RU) has extensive but not comprehensive sanctions
    }
)

# Mapping of country codes to (name, legal basis)
PROHIBITION_INFO: dict[str, tuple[str, str]] = {
    "CU": ("Cuba", "OFAC Comprehensive Sanctions - Cuba (31 CFR Part 515)"),
    "IR": ("Iran", "OFAC Comprehensive Sanctions - Iran (31 CFR Part 560)"),
    "KP": ("North Korea", "OFAC Comprehensive Sanctions - DPRK (31 CFR Part 510)"),
    "SY": ("Syria", "OFAC Comprehensive Sanctions - Syria (31 CFR Part 542)"),
}
