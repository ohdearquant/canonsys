"""Scope feature result types.

All result dataclasses for scope operations:
- Manifest creation/verification
- Scope definition verification
- Snapshot verification (group, dataset)
- Allowlist verification (destination, channel)
- Environment scope checks
- Scope minimization derivation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

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


# =============================================================================
# Manifest Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class ManifestResult:
    """Result of scope manifest creation.

    Attributes:
        manifest_id: Unique identifier for this manifest.
        manifest_hash: SHA256 hash of sorted targets for integrity verification.
        target_count: Number of targets in scope.
        exclusions_count: Number of exclusions defined.
        created_at: Timestamp when manifest was created.
    """

    manifest_id: UUID
    manifest_hash: str
    target_count: int
    exclusions_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ManifestVerificationResult:
    """Result of scope manifest verification.

    Attributes:
        verified: True if current targets match manifest hash.
        manifest_id: The manifest being verified.
        expected_hash: Hash from the original manifest.
        actual_hash: Hash computed from current targets.
        drift_detected: True if scope has changed since manifest creation.
    """

    verified: bool
    manifest_id: UUID
    expected_hash: str
    actual_hash: str | None
    drift_detected: bool


# =============================================================================
# Definition Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class ScopeDefinitionResult:
    """Result of scope definition verification.

    Attributes:
        defined: True if scope meets definition requirements.
        scope_type: Type of scope (e.g., "users", "resources", "data").
        has_targets: True if scope has explicit targets.
        has_exclusions: True if scope has defined exclusions.
        is_explicit: True if scope is explicitly bounded (not "ALL" or "BROAD").
    """

    defined: bool
    scope_type: str
    has_targets: bool
    has_exclusions: bool
    is_explicit: bool


# =============================================================================
# Notification Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class StakeholderNotificationResult:
    """Result of stakeholder notification verification.

    Attributes:
        complete: True if all required stakeholders were notified.
        manifest_id: The scope manifest being checked.
        notified_count: Number of stakeholders successfully notified.
        required_count: Number of stakeholders requiring notification.
        missing: List of stakeholder IDs not yet notified.
    """

    complete: bool
    manifest_id: UUID
    notified_count: int
    required_count: int
    missing: tuple[str, ...]


# =============================================================================
# Snapshot Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class GroupSnapshotResult:
    """Result of group membership snapshot verification.

    Attributes:
        matches: True if current membership hash matches expected.
        group_id: The group being verified.
        expected_hash: Hash from the baseline snapshot.
        current_hash: Hash computed from current membership.
        member_delta: Difference in member count (positive=added, negative=removed).
    """

    matches: bool
    group_id: UUID
    expected_hash: str
    current_hash: str
    member_delta: int


@dataclass(frozen=True, slots=True)
class DatasetSnapshotResult:
    """Result of dataset snapshot verification.

    Attributes:
        matches: True if current dataset hash matches expected.
        dataset_id: The dataset being verified.
        expected_hash: Hash from the baseline snapshot.
        current_hash: Hash computed from current dataset contents.
    """

    matches: bool
    dataset_id: UUID
    expected_hash: str
    current_hash: str


# =============================================================================
# Allowlist Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class DestinationAllowlistResult:
    """Result of destination allowlist verification.

    Attributes:
        allowed: True if destination is on the allowlist.
        destination: The destination being checked.
        allowlist_version: Version/identifier of the allowlist used.
        reason: Explanation if destination is not allowed.
    """

    allowed: bool
    destination: str
    allowlist_version: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class ChannelAllowlistResult:
    """Result of channel allowlist verification.

    Attributes:
        allowed: True if channel is permitted for the channel type.
        channel: The channel being checked.
        channel_type: Type of channel (email, api, sftp, etc.).
        allowlist_version: Version/identifier of the allowlist used.
    """

    allowed: bool
    channel: str
    channel_type: str
    allowlist_version: str


# =============================================================================
# Environment Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class EnvironmentScopeResult:
    """Result of environment scope validation.

    Attributes:
        valid: True if operation is permitted in this environment.
        environment: The environment being validated.
        allowed_environments: Tuple of environments where operation is permitted.
        reason: Explanation if environment is not valid.
    """

    valid: bool
    environment: str
    allowed_environments: tuple[str, ...]
    reason: str | None


# =============================================================================
# Minimization Results
# =============================================================================


@dataclass(frozen=True, slots=True)
class ScopeMinimizationResult:
    """Result of scope minimization analysis.

    Attributes:
        is_minimal: True if requested scope equals minimum required.
        scope_size: Size of requested scope.
        minimum_required: Size of minimum required scope.
        excess_count: Number of excess items beyond minimum.
        recommendation: Suggestion for scope reduction if not minimal.
    """

    is_minimal: bool
    scope_size: int
    minimum_required: int
    excess_count: int
    recommendation: str | None
