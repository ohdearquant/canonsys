"""Pattern vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

PATTERN = VocabularyPackage(
    name="pattern",
    description="Pattern detection for compliance monitoring: prior action counts, thresholds, and cumulative amount tracking.",
    feature_names=frozenset(
        {
            "check_pattern_threshold",
            "check_prior_bypasses",
            "check_prior_escalations",
            "check_prior_exemptions",
            "derive_cumulative_amount",
            "derive_cumulative_exception_amount",
            "derive_cumulative_reallocation_amount",
            "derive_manager_bypass_count_12m",
            "derive_manager_salary_exception_count_12m",
            "derive_prior_action_count",
        }
    ),
    schema_names=frozenset(
        {
            "CumulativeAmountResult",
            "PatternThresholdResult",
            "PriorActionCountResult",
        }
    ),
    regulatory_basis=(
        "SOX \u00a7 404",
        "SOC 2 CC4.1",
        "BSA/AML",
    ),
    version="2026.01",
    domain_module="canon_vocab_pattern",
)
