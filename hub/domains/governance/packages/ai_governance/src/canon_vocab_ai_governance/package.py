"""AI governance vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

AI_GOVERNANCE = VocabularyPackage(
    name="ai_governance",
    description="AI/ML model governance, bias assessment, and human review requirements.",
    feature_names=frozenset(
        {
            "require_bias_assessment_documented",
            "require_human_review_for_high_risk",
            "require_human_review_present",
            "verify_bias_assessment_complete",
            "verify_human_review_complete",
            "verify_same_tool",
        }
    ),
    schema_names=frozenset(
        {
            "BiasAssessmentStatus",
            "HumanReviewStatus",
            "RiskLevel",
        }
    ),
    regulatory_basis=(
        "EU AI Act",
        "NYC LL144",
        "Colorado SB24-205",
        "GDPR Art. 22",
    ),
    version="2026.01",
    domain_module="canon_vocab_ai_governance",
)
