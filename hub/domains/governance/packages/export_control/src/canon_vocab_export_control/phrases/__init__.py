"""Export control domain phrases.

All export control operations in one place:
- Require phrases: require_allowed_destination
- Verification phrases: verify_ofac, verify_bis, verify_itar
- Validation phrases: validate_destination_country (ISO-3166-1)
- Derived facts: military_end_use_license_obtained, enhanced_government_screening_complete
- Truth machine constraints: destination_must_not_be_prohibited, etc.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from .bis_license_must_be_valid import bis_license_must_be_valid
from .check_enhanced_screening import (
    CheckEnhancedScreeningSpecs,
    check_enhanced_government_screening_complete,
)
from .check_military_end_use_license import (
    CheckMilitaryEndUseLicenseSpecs,
    check_military_end_use_license_obtained,
)
from .destination_must_not_be_prohibited import destination_must_not_be_prohibited
from .itar_must_be_authorized import itar_must_be_authorized
from .ofac_must_be_cleared import ofac_must_be_cleared
from .require_allowed_destination import (
    RequireAllowedDestinationSpecs,
    require_allowed_destination,
)
from .require_export_clearance import (
    RequireExportClearanceSpecs,
    require_export_clearance,
)
from .validate_destination_country import (
    ValidateDestinationSpecs,
    validate_destination_country,
)
from .verify_bis_approval import VerifyBISSpecs, verify_bis_approval
from .verify_itar_authorization import VerifyITARSpecs, verify_itar_authorization
from .verify_ofac_clearance import VerifyOFACSpecs, verify_ofac_clearance

__all__ = [
    "CheckEnhancedScreeningSpecs",
    "CheckMilitaryEndUseLicenseSpecs",
    "RequireAllowedDestinationSpecs",
    "RequireExportClearanceSpecs",
    "ValidateDestinationSpecs",
    "VerifyBISSpecs",
    "VerifyITARSpecs",
    "VerifyOFACSpecs",
    "bis_license_must_be_valid",
    "check_enhanced_government_screening_complete",
    "check_military_end_use_license_obtained",
    "destination_must_not_be_prohibited",
    "itar_must_be_authorized",
    "ofac_must_be_cleared",
    "require_allowed_destination",
    "require_export_clearance",
    "validate_destination_country",
    "verify_bis_approval",
    "verify_itar_authorization",
    "verify_ofac_clearance",
]
