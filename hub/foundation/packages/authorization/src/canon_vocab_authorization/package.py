"""Authorization vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

AUTHORIZATION = VocabularyPackage(
    name="authorization",
    description="Access control, role-based approval chains, dual approval, delegation, time-bounded access, and segregation of duties.",
    feature_names=frozenset(
        {
            "check_er_clearance",
            "get_approval_chain",
            "require_access_justification",
            "require_distinct_identities",
            "require_dual_approval",
            "require_release_clearance",
            "require_role_authorized",
            "require_segregation_analysis",
            "require_separation_of_duties",
            "require_time_bounded_access",
            "verify_approval_chain_complete",
            "verify_board_approval",
            "verify_cfo_approval",
            "verify_ciso_approval",
            "verify_compliance_approval",
            "verify_cto_approval",
            "verify_delegation_valid",
            "verify_dpo_approval",
            "verify_executive_approval",
            "verify_gc_approval",
            "verify_hr_approval",
            "verify_role_approval",
        }
    ),
    schema_names=frozenset(
        {
            "ApprovalChainStatus",
            "ApproverStatus",
            "ClearanceLevel",
            "ERClearanceResult",
            "ERClearanceStatus",
            "RequireDistinctIdentitiesResult",
            "RequireDualApprovalResult",
            "RequireSegregationAnalysisResult",
            "RoleApprovalResult",
            "SegregationStatus",
            "VerifyApprovalChainCompleteResult",
        }
    ),
    regulatory_basis=(
        "SOC 2 CC6.1-6.3",
        "SOX Section 404",
        "GDPR Art. 37-39",
        "ITAR/EAR",
        "NISPOM",
        "ISO 27001 A.9.2",
        "NIST SP 800-53 AC-2",
    ),
    version="2026.01",
    domain_module="canon_vocab_authorization",
)
