"""Export control vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

EXPORT_CONTROL = VocabularyPackage(
    name="export_control",
    description="ITAR, EAR, OFAC screening, BIS licensing, and destination country validation.",
    feature_names=frozenset(
        {
            "bis_license_must_be_valid",
            "check_enhanced_government_screening_complete",
            "check_military_end_use_license_obtained",
            "destination_must_not_be_prohibited",
            "itar_must_be_authorized",
            "ofac_must_be_cleared",
            "require_allowed_destination",
            "validate_destination_country",
            "verify_bis_approval",
            "verify_itar_authorization",
            "verify_ofac_clearance",
        }
    ),
    schema_names=frozenset(
        {
            "BISLicenseType",
            "ExportSubjectType",
            "ITARAuthorizationType",
            "OFACEntityType",
            "ScreeningScope",
        }
    ),
    regulatory_basis=(
        "ITAR (22 CFR Parts 120-130)",
        "EAR (15 CFR Parts 730-774)",
        "OFAC (31 CFR Parts 500-599)",
    ),
    version="2026.01",
    domain_module="canon_vocab_export_control",
)
