"""Freshness vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

FRESHNESS = VocabularyPackage(
    name="freshness",
    description="Data and review freshness checks, staleness detection, and regulatory deadline derivation.",
    feature_names=frozenset(
        {
            "check_equity_staleness",
            "check_legal_review_freshness",
            "check_privilege_review",
            "check_receipt_freshness",
            "check_tia_freshness",
            "derive_extension_days",
            "derive_filing_deadline",
            "derive_quarter_end",
            "derive_regulatory_deadline",
            "verify_credit_freshness",
        }
    ),
    schema_names=frozenset(
        {
            "FreshnessStatus",
        }
    ),
    regulatory_basis=(
        "SOX Section 404",
        "GDPR Art. 5(1)(d)",
        "FCRA Section 604",
        "PCI DSS 7.2",
    ),
    version="2026.01",
    domain_module="canon_vocab_freshness",
)
