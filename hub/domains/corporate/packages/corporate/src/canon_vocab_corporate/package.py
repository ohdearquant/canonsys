"""Corporate vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CORPORATE = VocabularyPackage(
    name="corporate",
    description="M&A compliance: clean team requirements, carve-out readiness, condition satisfaction, and findings.",
    feature_names=frozenset(
        {
            "derive_carve_out_readiness",
            "derive_clean_team_required",
            "derive_condition_satisfaction_status",
            "derive_conditional_findings_addressed",
        }
    ),
    schema_names=frozenset(
        {
            "CarveOutReadinessResult",
            "CarveOutStatus",
            "CleanTeamReason",
            "CleanTeamRequiredResult",
            "ConditionalFindingsAddressedResult",
            "ConditionSatisfactionResult",
            "ConditionSatisfactionStatus",
            "ConditionType",
            "DataSensitivityLevel",
            "DealPhase",
            "FindingStatus",
            "SensitiveDataCategory",
        }
    ),
    regulatory_basis=(
        "Hart-Scott-Rodino Act",
        "Sherman Act \u00a7 1",
        "FTC/DOJ Merger Guidelines",
        "SEC M&A disclosure rules",
    ),
    version="2026.01",
    domain_module="canon_vocab_corporate",
)
