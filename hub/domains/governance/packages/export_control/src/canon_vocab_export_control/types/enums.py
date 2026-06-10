"""Export control enumeration types.

Types of licenses, authorizations, and entity classifications
for BIS/EAR, ITAR/DDTC, and OFAC compliance.
"""

from __future__ import annotations

from kron.types import Enum

__all__ = [
    "BISLicenseType",
    "ExportSubjectType",
    "ITARAuthorizationType",
    "OFACEntityType",
    "ScreeningScope",
]


class BISLicenseType(Enum):
    """Types of BIS export authorization.

    Bureau of Industry and Security (Commerce Dept) license types
    for EAR-controlled items under 15 CFR Parts 730-774.
    """

    LICENSE = "LICENSE"  # Individual validated license
    LICENSE_EXCEPTION = "LICENSE_EXCEPTION"  # Qualifies for exception
    NO_LICENSE_REQUIRED = "NO_LICENSE_REQUIRED"  # EAR99 or not controlled


class ITARAuthorizationType(Enum):
    """Types of ITAR authorization.

    State Department (DDTC) authorization types for defense
    articles/services under 22 CFR Parts 120-130.
    """

    DSP_5 = "DSP-5"  # Permanent export license
    DSP_73 = "DSP-73"  # Temporary export license
    DSP_85 = "DSP-85"  # Manufacturing license agreement
    TAA = "TAA"  # Technical Assistance Agreement
    MLA = "MLA"  # Manufacturing License Agreement
    EXEMPTION = "EXEMPTION"  # Statutory exemption applies


class OFACEntityType(Enum):
    """Types of entities that can be screened against OFAC lists.

    Entity types for OFAC SDN (Specially Designated Nationals)
    and related sanctions screening.
    """

    INDIVIDUAL = "INDIVIDUAL"
    ENTITY = "ENTITY"
    VESSEL = "VESSEL"
    AIRCRAFT = "AIRCRAFT"


class ExportSubjectType(Enum):
    """Types of export subjects requiring classification.

    Determines which export control regime applies:
    - Technical data and source code may have enhanced controls
    - Products and services have different licensing requirements
    """

    TECHNICAL_DATA = "TECHNICAL_DATA"  # Engineering drawings, specs, manuals
    SOURCE_CODE = "SOURCE_CODE"  # Software source code (may be EAR-controlled)
    PRODUCT = "PRODUCT"  # Physical goods (CCL/USML classification)
    SERVICE = "SERVICE"  # Defense services, technical assistance


class ScreeningScope(Enum):
    """Scope of party screening for export transactions.

    Determines how deeply to screen transaction parties:
    - DIRECT_PARTY: Screen only immediate parties (buyer, consignee)
    - FULL_CHAIN: Screen entire transaction chain (intermediaries, end-users)

    Full chain screening required for:
    - High-risk destinations
    - Controlled items (ECCN/USML)
    - Military end-use concerns
    """

    DIRECT_PARTY = "DIRECT_PARTY"  # Screen immediate parties only
    FULL_CHAIN = "FULL_CHAIN"  # Screen entire transaction chain
