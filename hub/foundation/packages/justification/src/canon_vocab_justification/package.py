"""Justification vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

JUSTIFICATION = VocabularyPackage(
    name="justification",
    description="Business justification validation, classification, and evidence mapping for waivers and reason codes.",
    feature_names=frozenset(
        {
            "classify_justification",
            "map_reason_code_to_evidence",
            "map_waiver_reason_to_evidence",
            "require_type_specific_evidence",
            "validate_business_justification",
        }
    ),
    schema_names=frozenset(
        {
            "EvidenceRequirement",
            "JustificationClass",
            "ReasonEvidenceMapping",
            "WaiverEvidenceMapping",
        }
    ),
    regulatory_basis=(
        "SOX \u00a7 404",
        "COSO",
    ),
    version="2026.01",
    domain_module="canon_vocab_justification",
)
