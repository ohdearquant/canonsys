"""Scope domain exceptions.

These exceptions are raised by scope operations when invariants are violated.
All inherit from the appropriate category in enforcement.exceptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import DataProtectionViolation, EvidenceViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "ChannelNotAllowedError",
    "DatasetIntegrityError",
    "DestinationNotAllowedError",
    "EnvironmentNotAllowedError",
    "ExcessiveScopeError",
    "GroupMembershipDriftError",
    "NotificationIncompleteError",
    "ScopeDriftError",
    "VagueScopeError",
]


# =============================================================================
# Scope Definition Errors
# =============================================================================


class VagueScopeError(DataProtectionViolation):
    """Scope definition is too vague to be enforceable.

    Raised when: verify_scope_definition finds scope with indicators like
    "ALL", "BROAD", "*", or no explicit targets.

    Regulatory basis:
    - GDPR Art. 5(1)(c): Data shall be limited to what is necessary
    - SOC 2 CC6.1: Logical access controls require explicit definitions

    Action: verify_scope_definition
    """

    default_regulation = "GDPR Art. 5(1)(c)"
    default_message = "Scope definition is too vague"

    __slots__ = ("scope_doc_id", "scope_type")

    def __init__(
        self,
        scope_doc_id: UUID,
        scope_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize vague scope error.

        Args:
            scope_doc_id: UUID of the scope document.
            scope_type: Type of scope being defined.
            **kwargs: Additional arguments passed to parent.
        """
        self.scope_doc_id = scope_doc_id
        self.scope_type = scope_type
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "scope_doc_id": str(scope_doc_id),
            "scope_type": scope_type,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Scope '{scope_type}' ({scope_doc_id}) is too vague - must enumerate explicit targets",
            context=merged_context,
            **kwargs,
        )


class ExcessiveScopeError(DataProtectionViolation):
    """Requested scope exceeds minimum required.

    Raised when: derive_scope_minimization finds excess items beyond
    the minimum required scope.

    Regulatory basis:
    - GDPR Art. 5(1)(c): Data minimization principle
    - HIPAA 164.502(b): Minimum necessary standard
    - CCPA 1798.100(c): Collection limitation

    Action: derive_scope_minimization
    """

    default_regulation = "GDPR Art. 5(1)(c)"
    default_message = "Requested scope exceeds minimum required"

    __slots__ = ("excess_count", "minimum_required", "recommendation", "scope_size")

    def __init__(
        self,
        scope_size: int,
        minimum_required: int,
        excess_count: int,
        recommendation: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize excessive scope error.

        Args:
            scope_size: Size of requested scope.
            minimum_required: Minimum required scope size.
            excess_count: Number of excess items.
            recommendation: Suggestion for reducing scope.
            **kwargs: Additional arguments passed to parent.
        """
        self.scope_size = scope_size
        self.minimum_required = minimum_required
        self.excess_count = excess_count
        self.recommendation = recommendation
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "scope_size": scope_size,
            "minimum_required": minimum_required,
            "excess_count": excess_count,
        }
        merged_context = {**base_context, **extra_context}
        msg = f"Scope has {excess_count} excess items beyond minimum required"
        if recommendation:
            msg += f". {recommendation}"
        super().__init__(msg, context=merged_context, **kwargs)


# =============================================================================
# Scope Drift Errors
# =============================================================================


class ScopeDriftError(EvidenceViolation):
    """Scope has drifted from original manifest.

    Raised when: verify_scope_manifest detects that current targets
    differ from the original manifest hash.

    Regulatory basis:
    - GDPR Art. 5(1)(c): Scope must not expand without review
    - SOC 2 CC6.1: Scope changes must be detected
    - ISO 27001 A.9.1.1: Scope drift is a control failure

    Action: verify_scope_manifest
    """

    default_regulation = "GDPR Art. 5(1)(c)"
    default_message = "Scope has drifted from manifest"

    __slots__ = ("actual_hash", "expected_hash", "manifest_id")

    def __init__(
        self,
        manifest_id: UUID,
        expected_hash: str,
        actual_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize scope drift error.

        Args:
            manifest_id: UUID of the manifest being verified.
            expected_hash: Expected hash from original manifest.
            actual_hash: Actual hash computed from current targets.
            **kwargs: Additional arguments passed to parent.
        """
        self.manifest_id = manifest_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "manifest_id": str(manifest_id),
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Scope manifest {manifest_id} drifted: "
            f"expected {expected_hash[:8]}..., got {actual_hash[:8]}...",
            context=merged_context,
            **kwargs,
        )


class GroupMembershipDriftError(EvidenceViolation):
    """Group membership has changed from baseline snapshot.

    Raised when: verify_group_membership_snapshot detects membership
    differs from the baseline hash.

    Regulatory basis:
    - SOC 2 CC6.1: Group membership changes must be controlled
    - SOC 2 CC6.2: Membership drift indicates control bypass
    - ISO 27001 A.9.2.5: Access rights must be reviewed

    Action: verify_group_membership_snapshot
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Group membership has drifted from baseline"

    __slots__ = ("group_id", "member_delta")

    def __init__(
        self,
        group_id: UUID,
        member_delta: int,
        **kwargs: Any,
    ) -> None:
        """Initialize group membership drift error.

        Args:
            group_id: UUID of the group.
            member_delta: Net change in membership count.
            **kwargs: Additional arguments passed to parent.
        """
        self.group_id = group_id
        self.member_delta = member_delta
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "group_id": str(group_id),
            "member_delta": member_delta,
        }
        merged_context = {**base_context, **extra_context}
        direction = "increased" if member_delta > 0 else "decreased"
        super().__init__(
            f"Group {group_id} membership {direction} by {abs(member_delta)}",
            context=merged_context,
            **kwargs,
        )


class DatasetIntegrityError(EvidenceViolation):
    """Dataset contents have been modified from baseline.

    Raised when: verify_dataset_snapshot_match detects the dataset
    hash differs from the baseline.

    Regulatory basis:
    - SOC 2 CC6.7: Dataset integrity must be verified
    - ISO 27001 A.12.1.2: Changes must be controlled
    - GDPR Art. 5(1)(f): Integrity principle

    Action: verify_dataset_snapshot_match
    """

    default_regulation = "SOC 2 CC6.7"
    default_message = "Dataset integrity compromised"

    __slots__ = ("current_hash", "dataset_id", "expected_hash")

    def __init__(
        self,
        dataset_id: UUID,
        expected_hash: str,
        current_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize dataset integrity error.

        Args:
            dataset_id: UUID of the dataset.
            expected_hash: Expected hash from baseline.
            current_hash: Current computed hash.
            **kwargs: Additional arguments passed to parent.
        """
        self.dataset_id = dataset_id
        self.expected_hash = expected_hash
        self.current_hash = current_hash
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "dataset_id": str(dataset_id),
            "expected_hash": expected_hash,
            "current_hash": current_hash,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Dataset {dataset_id} modified: "
            f"expected {expected_hash[:8]}..., got {current_hash[:8]}...",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Allowlist Errors
# =============================================================================


class DestinationNotAllowedError(DataProtectionViolation):
    """Destination is not on the allowlist.

    Raised when: verify_destination_allowed finds the destination
    is not in the approved allowlist.

    Regulatory basis:
    - GDPR Art. 44-49: Cross-border transfer restrictions
    - SOC 2 CC6.7: Transmission restrictions
    - ITAR/EAR: Export destination controls

    Action: verify_destination_allowed
    """

    default_regulation = "GDPR Art. 44"
    default_message = "Destination not on allowlist"

    __slots__ = ("allowlist_version", "destination")

    def __init__(
        self,
        destination: str,
        allowlist_version: str,
        **kwargs: Any,
    ) -> None:
        """Initialize destination not allowed error.

        Args:
            destination: The destination being denied.
            allowlist_version: Version of the allowlist used.
            **kwargs: Additional arguments passed to parent.
        """
        self.destination = destination
        self.allowlist_version = allowlist_version
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "destination": destination,
            "allowlist_version": allowlist_version,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Destination '{destination}' not on allowlist (version: {allowlist_version})",
            context=merged_context,
            **kwargs,
        )


class ChannelNotAllowedError(DataProtectionViolation):
    """Communication channel is not on the allowlist.

    Raised when: verify_channel_allowed finds the channel
    is not in the approved allowlist for its type.

    Regulatory basis:
    - SOC 2 CC6.7: Transmission channel restrictions
    - HIPAA 164.312(e)(1): Transmission security
    - PCI DSS 4.1: Secure transmission channels

    Action: verify_channel_allowed
    """

    default_regulation = "SOC 2 CC6.7"
    default_message = "Channel not on allowlist"

    __slots__ = ("allowlist_version", "channel", "channel_type")

    def __init__(
        self,
        channel: str,
        channel_type: str,
        allowlist_version: str,
        **kwargs: Any,
    ) -> None:
        """Initialize channel not allowed error.

        Args:
            channel: The channel being denied.
            channel_type: Type of channel (email, api, etc.).
            allowlist_version: Version of the allowlist used.
            **kwargs: Additional arguments passed to parent.
        """
        self.channel = channel
        self.channel_type = channel_type
        self.allowlist_version = allowlist_version
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "channel": channel,
            "channel_type": channel_type,
            "allowlist_version": allowlist_version,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Channel '{channel}' ({channel_type}) not on allowlist (version: {allowlist_version})",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Environment Errors
# =============================================================================


class EnvironmentNotAllowedError(DataProtectionViolation):
    """Operation not permitted in this environment.

    Raised when: check_environment_scope finds the current environment
    is not in the allowed list.

    Regulatory basis:
    - SOC 2 CC6.1: Environment separation controls
    - SOC 2 CC8.1: Change management / deployment controls
    - ISO 27001 A.12.1.4: Separation of environments

    Action: check_environment_scope
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Operation not permitted in this environment"

    __slots__ = ("allowed_environments", "environment")

    def __init__(
        self,
        environment: str,
        allowed_environments: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize environment not allowed error.

        Args:
            environment: The current environment.
            allowed_environments: Tuple of allowed environments.
            **kwargs: Additional arguments passed to parent.
        """
        self.environment = environment
        self.allowed_environments = allowed_environments
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "environment": environment,
            "allowed_environments": list(allowed_environments),
        }
        merged_context = {**base_context, **extra_context}
        allowed_str = ", ".join(sorted(allowed_environments))
        super().__init__(
            f"Environment '{environment}' not permitted. Allowed: {allowed_str}",
            context=merged_context,
            **kwargs,
        )


# =============================================================================
# Notification Errors
# =============================================================================


class NotificationIncompleteError(DataProtectionViolation):
    """Required stakeholder notifications are incomplete.

    Raised when: verify_stakeholder_notification_complete finds
    some required stakeholders have not been notified.

    Regulatory basis:
    - GDPR Art. 13/14: Data subject notification requirements
    - WARN Act: Employee notification requirements
    - SOC 2 CC2.2: Communication to external parties

    Action: verify_stakeholder_notification_complete
    """

    default_regulation = "GDPR Art. 13"
    default_message = "Stakeholder notifications incomplete"

    __slots__ = ("manifest_id", "missing", "missing_count")

    def __init__(
        self,
        manifest_id: UUID,
        missing: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize notification incomplete error.

        Args:
            manifest_id: UUID of the scope manifest.
            missing: Tuple of stakeholder IDs not yet notified.
            **kwargs: Additional arguments passed to parent.
        """
        self.manifest_id = manifest_id
        self.missing_count = len(missing)
        self.missing = missing
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "manifest_id": str(manifest_id),
            "missing_count": len(missing),
            "missing": list(missing[:10]),  # Limit to first 10 for logging
        }
        merged_context = {**base_context, **extra_context}
        missing_preview = ", ".join(missing[:3])
        if len(missing) > 3:
            missing_preview += f" and {len(missing) - 3} more"
        super().__init__(
            f"Notification incomplete for manifest {manifest_id}: missing {missing_preview}",
            context=merged_context,
            **kwargs,
        )
