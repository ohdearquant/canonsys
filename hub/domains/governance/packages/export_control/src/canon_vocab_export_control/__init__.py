"""Export control feature - vertical slice for export control compliance.

This module provides the complete export control domain implementation:
- Types: BISLicenseType, ITARAuthorizationType, OFACEntityType, constants
- Phrases: require_allowed_destination, verify_ofac, verify_bis, verify_itar
- Constraints: Truth machine phrases for regulatory invariants
- Exceptions: ProhibitedDestinationError, OFACSanctionsMatchError, etc.

WARNING: Export control violations carry CRIMINAL penalties up to
$1M fine and 20 years imprisonment. These are serious regulatory
requirements.

Regulatory context:
    - OFAC (Office of Foreign Assets Control) - Treasury Department
    - BIS (Bureau of Industry and Security) - Commerce Department
    - DDTC (Directorate of Defense Trade Controls) - State Department
    - EAR (Export Administration Regulations) - 15 CFR Parts 730-774
    - ITAR (International Traffic in Arms Regulations) - 22 CFR Parts 120-130

Usage:
    from canon_vocab_export_control import (
        # Types
        BISLicenseType,
        OFACEntityType,
        PROHIBITED_DESTINATIONS,
        # Phrases
        verify_ofac_clearance,
        require_allowed_destination,
        # Constraints
        ofac_must_be_cleared,
        destination_must_not_be_prohibited,
        # Package metadata
        EXPORT_CONTROL,
    )
"""

from .exceptions import (
    BISLicenseRequiredError,
    ExportControlViolation,
    ITARAuthorizationRequiredError,
    OFACSanctionsMatchError,
    ProhibitedDestinationError,
)
from .package import EXPORT_CONTROL
from .phrases import (
    CheckEnhancedScreeningSpecs,
    CheckMilitaryEndUseLicenseSpecs,
    RequireAllowedDestinationSpecs,
    ValidateDestinationSpecs,
    VerifyBISSpecs,
    VerifyITARSpecs,
    VerifyOFACSpecs,
    bis_license_must_be_valid,
    check_enhanced_government_screening_complete,
    check_military_end_use_license_obtained,
    destination_must_not_be_prohibited,
    itar_must_be_authorized,
    ofac_must_be_cleared,
    require_allowed_destination,
    validate_destination_country,
    verify_bis_approval,
    verify_itar_authorization,
    verify_ofac_clearance,
)
from .service import ExportControlService
from .types import (
    PROHIBITED_DESTINATIONS,
    PROHIBITION_INFO,
    BISLicenseType,
    ExportSubjectType,
    ITARAuthorizationType,
    OFACEntityType,
    ScreeningScope,
)

__all__ = [
    # Service
    "ExportControlService",
    # Package metadata
    "EXPORT_CONTROL",
    # Constants
    "PROHIBITED_DESTINATIONS",
    "PROHIBITION_INFO",
    # Exceptions
    "BISLicenseRequiredError",
    "ExportControlViolation",
    "ITARAuthorizationRequiredError",
    "OFACSanctionsMatchError",
    "ProhibitedDestinationError",
    # Types (enums)
    "BISLicenseType",
    "ExportSubjectType",
    "ITARAuthorizationType",
    "OFACEntityType",
    "ScreeningScope",
    # Specs classes
    "CheckEnhancedScreeningSpecs",
    "CheckMilitaryEndUseLicenseSpecs",
    "RequireAllowedDestinationSpecs",
    "ValidateDestinationSpecs",
    "VerifyBISSpecs",
    "VerifyITARSpecs",
    "VerifyOFACSpecs",
    # Truth machine constraints
    "bis_license_must_be_valid",
    "destination_must_not_be_prohibited",
    "itar_must_be_authorized",
    "ofac_must_be_cleared",
    # Phrase functions
    "check_enhanced_government_screening_complete",
    "check_military_end_use_license_obtained",
    "require_allowed_destination",
    "validate_destination_country",
    "verify_bis_approval",
    "verify_itar_authorization",
    "verify_ofac_clearance",
]
