"""Consent vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

CONSENT = VocabularyPackage(
    name="consent",
    description="Consent collection, verification, revocation, renewal, and audit history.",
    feature_names=frozenset(
        {
            # CRUD operations
            "cascade_revoke_consent_token",
            "find_consent_token",
            "grant_consent_token",
            "list_consent_tokens",
            "renew_consent_token",
            "revoke_consent_token",
            # Verification phrases
            "verify_consent_scope_covers",
            "verify_consent_token",
            # Requirement (gate) phrases
            "require_active_consent",
            "require_consent_not_expired",
            "require_consent_not_withdrawn",
            "require_valid_consent",
            # Query phrases
            "get_consent_history",
            # Truth machine constraints
            "consent_must_be_valid",
            "consent_must_not_be_expired",
            "consent_must_not_be_withdrawn",
            "consent_scope_must_cover",
        }
    ),
    schema_names=frozenset(
        {
            "ConsentScope",
            "ConsentStatus",
            "ConsentToken",
            "ConsentTokenContent",
            "ConsentStatusFilter",
            "ConsentHistoryEntry",
            # Specs classes
            "CascadeRevokeSpecs",
            "FindConsentSpecs",
            "GetConsentHistorySpecs",
            "GrantConsentSpecs",
            "ListConsentSpecs",
            "RenewConsentSpecs",
            "RequireActiveConsentSpecs",
            "RequireConsentNotExpiredSpecs",
            "RequireConsentNotWithdrawnSpecs",
            "RequireValidConsentSpecs",
            "RevokeConsentSpecs",
            "VerifyConsentScopeCoversSpecs",
            "VerifyConsentSpecs",
        }
    ),
    regulatory_basis=(
        "FCRA \u00a7 1681b(b)(3)",
        "GDPR Art. 6-7",
        "CCPA Section 1798.120",
    ),
    version="2026.01",
    domain_module="canon_vocab_consent",
)
