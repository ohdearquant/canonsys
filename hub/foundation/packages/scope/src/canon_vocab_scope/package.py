"""Scope vocabulary package metadata."""

from canon.hub.package import VocabularyPackage

SCOPE = VocabularyPackage(
    name="scope",
    description="Scope management: destination and channel allowlists, dataset snapshots, group membership, and minimization.",
    feature_names=frozenset(
        {
            "check_environment_scope",
            "create_scope_manifest",
            "derive_scope_minimization",
            "verify_channel_allowed",
            "verify_dataset_snapshot_match",
            "verify_destination_allowed",
            "verify_group_membership_snapshot",
            "verify_scope_definition",
            "verify_scope_manifest",
            "verify_stakeholder_notification_complete",
        }
    ),
    schema_names=frozenset(
        {
            "ChannelAllowlistResult",
            "DatasetSnapshotResult",
            "DestinationAllowlistResult",
            "EnvironmentScopeResult",
            "GroupSnapshotResult",
            "ManifestResult",
            "ManifestVerificationResult",
            "ScopeDefinitionResult",
            "ScopeMinimizationResult",
            "StakeholderNotificationResult",
        }
    ),
    regulatory_basis=(
        "GDPR Art. 5(1)(c)",
        "SOC 2 CC6.1",
        "ISO 27001 A.9.1.1",
        "HIPAA 164.502(b)",
        "GDPR Art. 44-49",
    ),
    version="2026.01",
    domain_module="canon_vocab_scope",
)
