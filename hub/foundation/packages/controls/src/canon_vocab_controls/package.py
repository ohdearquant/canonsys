"""Controls vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CONTROLS = VocabularyPackage(
    name="controls",
    description="Control assessment, exploitability checks, logging coverage, and sanitization verification.",
    feature_names=frozenset(
        {
            "assess_control_coverage",
            "check_exploitability_status",
            "derive_compensating_logging_coverage",
            "derive_control_equivalence_score",
            "verify_required_controls_for_tool",
            "verify_sanitization_profile",
        }
    ),
    schema_names=frozenset(
        {
            "ControlCoverageResult",
            "ControlEquivalenceResult",
            "ExploitabilityResult",
            "LoggingCoverageResult",
            "SanitizationResult",
            "ToolControlResult",
        }
    ),
    regulatory_basis=(
        "SOX Section 404",
        "SOC 2 CC4.1",
        "SOC 2 CC6.1",
        "SOC 2 CC6.7",
        "SOC 2 CC7.1",
        "SOC 2 CC7.2",
        "ISO 27001 A.12.4",
        "ISO 27001 A.12.6.1",
        "ISO 27001 A.18.2.1",
        "CISA BOD 22-01",
        "NYC LL144",
        "GDPR Article 32",
        "NIST SP 800-88",
    ),
    version="2026.01",
    domain_module="canon_vocab_controls",
)
