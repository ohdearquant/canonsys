"""Core vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CORE = VocabularyPackage(
    name="core",
    description="Core compliance primitives: audit verification, charter management, break glass, and SOX review.",
    feature_names=frozenset(
        {
            "activate_charter",
            "derive_amount_band",
            "get_charter_by_id",
            "get_charter_history",
            "invoke_break_glass",
            "invoke_executive_override",
            "ratify_charter",
            "require_alternative_reviewed",
            "require_fraud_screening_pass",
            "require_provenance_documented",
            "require_sox_compliance_review",
            "require_value_within_limit",
            "resolve_charter",
            "verify_audit_complete",
            "verify_audit_current",
            "verify_evidence_freshness",
            "verify_signer_identity",
            "verify_values_match",
        }
    ),
    schema_names=frozenset(
        {
            "AlternativeReviewStatus",
            "AmountBandConfig",
            "AmountBandResult",
            "AuditStatus",
            "BreakGlassCertificate",
            "BreakGlassReason",
            "ExecutiveOverride",
            "FraudScreeningResult",
            "FreshnessResult",
            "OverrideAuthority",
            "RequireAlternativeReviewedResult",
            "RequireFraudScreeningPassResult",
            "RequireProvenanceDocumentedResult",
            "RequireSOXComplianceReviewResult",
            "SOXReviewStatus",
            "Signatory",
            "SignerIdentityResult",
            "ValueWithinLimitResult",
            "ValuesMatchResult",
            "VerifyAuditCompleteResult",
            "VerifyAuditCurrentResult",
        }
    ),
    regulatory_basis=(
        "SOX Section 302/404",
        "SOC 2 CC4.1",
        "ISO 27001 A.18.2",
        "COSO Framework",
        "BSA/AML",
        "PCI DSS",
    ),
    version="2026.01",
    domain_module="canon_vocab_core",
)
