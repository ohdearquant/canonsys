"""Scope feature - vertical slice for scope management.

This module provides the complete scope domain implementation:
- Types: ManifestResult, ScopeDefinitionResult, snapshot results, allowlist results
- Phrases: create, verify, derive, check operations
- Exceptions: ScopeDriftError, VagueScopeError, etc.

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization
    - SOC 2 CC6.1: Logical access controls
    - ISO 27001 A.9.1.1: Access control policy
    - HIPAA 164.502(b): Minimum necessary standard
    - GDPR Art. 44-49: Cross-border transfer restrictions

Usage:
    from canon_vocab_scope import (
        # Specs classes
        CreateScopeManifestSpecs,
        VerifyScopeManifestSpecs,
        # Phrases
        create_scope_manifest,
        verify_scope_manifest,
        # Exceptions
        ScopeDriftError,
        # Package metadata
        SCOPE,
    )
"""

# Exceptions
from .exceptions import (
    ChannelNotAllowedError,
    DatasetIntegrityError,
    DestinationNotAllowedError,
    EnvironmentNotAllowedError,
    ExcessiveScopeError,
    GroupMembershipDriftError,
    NotificationIncompleteError,
    ScopeDriftError,
    VagueScopeError,
)

# Package metadata
from .package import SCOPE

# Phrases (includes Specs classes and phrase functions)
from .phrases import (  # Specs classes; Phrase functions
    CheckEnvironmentScopeSpecs,
    CreateScopeManifestSpecs,
    DeriveScopeMinimizationSpecs,
    VerifyChannelAllowedSpecs,
    VerifyDatasetSnapshotSpecs,
    VerifyDestinationAllowedSpecs,
    VerifyGroupMembershipSnapshotSpecs,
    VerifyScopeDefinitionSpecs,
    VerifyScopeManifestSpecs,
    VerifyStakeholderNotificationSpecs,
    check_environment_scope,
    create_scope_manifest,
    derive_scope_minimization,
    verify_channel_allowed,
    verify_dataset_snapshot_match,
    verify_destination_allowed,
    verify_group_membership_snapshot,
    verify_scope_definition,
    verify_scope_manifest,
    verify_stakeholder_notification_complete,
)

# Service
from .service import ScopeService

# Types (result dataclasses - kept for backward compatibility)
from .types import (
    ChannelAllowlistResult,
    DatasetSnapshotResult,
    DestinationAllowlistResult,
    EnvironmentScopeResult,
    GroupSnapshotResult,
    ManifestResult,
    ManifestVerificationResult,
    ScopeDefinitionResult,
    ScopeMinimizationResult,
    StakeholderNotificationResult,
)

__all__ = [
    # Service
    "ScopeService",
    # Package metadata
    "SCOPE",
    # Types (result dataclasses - backward compatibility)
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
    # Exceptions
    "ChannelNotAllowedError",
    "DatasetIntegrityError",
    "DestinationNotAllowedError",
    "EnvironmentNotAllowedError",
    "ExcessiveScopeError",
    "GroupMembershipDriftError",
    "NotificationIncompleteError",
    "ScopeDriftError",
    "VagueScopeError",
    # Specs classes (Pydantic BaseModels)
    "CheckEnvironmentScopeSpecs",
    "CreateScopeManifestSpecs",
    "DeriveScopeMinimizationSpecs",
    "VerifyChannelAllowedSpecs",
    "VerifyDatasetSnapshotSpecs",
    "VerifyDestinationAllowedSpecs",
    "VerifyGroupMembershipSnapshotSpecs",
    "VerifyScopeDefinitionSpecs",
    "VerifyScopeManifestSpecs",
    "VerifyStakeholderNotificationSpecs",
    # Phrase functions
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
]
