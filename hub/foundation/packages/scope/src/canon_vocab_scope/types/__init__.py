"""Scope feature types."""

from .results import (
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
    "ChannelAllowlistResult",
    "DatasetSnapshotResult",
    # Allowlists
    "DestinationAllowlistResult",
    # Environment
    "EnvironmentScopeResult",
    # Snapshots
    "GroupSnapshotResult",
    # Manifest
    "ManifestResult",
    "ManifestVerificationResult",
    # Definition
    "ScopeDefinitionResult",
    # Minimization
    "ScopeMinimizationResult",
    # Notification
    "StakeholderNotificationResult",
]
