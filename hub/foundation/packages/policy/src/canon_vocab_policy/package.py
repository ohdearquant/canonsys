"""Policy vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

POLICY = VocabularyPackage(
    name="policy",
    description="Policy definition, adapter creation, release lifecycle, evaluation, resolution, conditional evaluation, and exception management.",
    feature_names=frozenset(
        {
            "create_policy_adapter",
            "create_policy_definition",
            "create_policy_release",
            "derive_risk_tier",
            "evaluate_conditional_policy",
            "evaluate_policy",
            "get_applicable_policies",
            "publish_policy_release",
            "require_policy_active",
            "require_policy_pass",
            "require_policy_version_current",
            "resolve_policy",
            "verify_policy_not_overridden",
        }
    ),
    schema_names=frozenset(
        {
            "PolicyAdapter",
            "PolicyAdapterContent",
            "PolicyAuthority",
            "PolicyDecision",
            "PolicyDefinition",
            "PolicyDefinitionContent",
            "PolicyRelease",
            "PolicyReleaseContent",
            "PolicyScope",
            "PolicyStatus",
            "RiskTier",
        }
    ),
    regulatory_basis=(
        "SOX \u00a7 404",
        "SOC 2 CC1.1-1.4",
        "ISO 27001 A.5.1",
    ),
    version="2026.01",
    domain_module="canon_vocab_policy",
)
