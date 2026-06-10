"""Legal vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

LEGAL = VocabularyPackage(
    name="legal",
    description="Legal holds, NDA management, appeal channels, clean team, criteria locking, and privilege review.",
    feature_names=frozenset(
        {
            "lock_criteria",
            "require_appeal_exhausted",
            "require_clean_team_for_competitive_intel",
            "require_deletion_clearance",
            "require_legal_review_complete",
            "require_modification_clearance",
            "require_nda_valid",
            "require_proceedings_closed",
            "verify_appeal_channel_available",
            "verify_clean_team_membership",
            "verify_nda_status",
            "verify_privileged_review_complete",
        }
    ),
    schema_names=frozenset(
        {
            "AppealChannelType",
            "AppealStatus",
            "CleanTeamStatus",
            "CriteriaLock",
            "HoldType",
            "NDAStatus",
            "PrivilegedReviewStatus",
            "ProceedingsStatus",
        }
    ),
    regulatory_basis=(
        "SOX Section 802",
        "FRCP 37(e)",
        "Hart-Scott-Rodino Act",
        "Attorney-Client Privilege",
        "Administrative Procedure Act",
        "Defend Trade Secrets Act (DTSA)",
    ),
    version="2026.01",
    domain_module="canon_vocab_legal",
)
