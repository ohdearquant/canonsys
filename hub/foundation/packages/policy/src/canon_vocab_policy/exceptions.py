"""Policy domain exceptions.

Specific exceptions for policy lifecycle and evaluation errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon.exceptions import CanonError

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    "PolicyError",
    # Definition errors
    "PolicyDefinitionNotFoundError",
    "PolicyDefinitionNotEffectiveError",
    "PolicyDefinitionAlreadyExistsError",
    # Adapter errors
    "PolicyAdapterNotFoundError",
    "PolicyAdapterVersionMismatchError",
    # Release errors
    "PolicyReleaseNotFoundError",
    "PolicyReleaseAlreadyPublishedError",
    "PolicyReleaseNotPublishedError",
    # Evaluation errors
    "PolicyEvaluationError",
    "PolicyDeniedError",
]


class PolicyError(CanonError):
    """Base exception for policy domain errors."""

    domain: str = "policy"


# =============================================================================
# Definition Errors
# =============================================================================


class PolicyDefinitionNotFoundError(PolicyError):
    """Policy definition not found."""

    def __init__(
        self,
        policy_id: str,
        version: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.version = version
        version_suffix = f" version {version}" if version else ""
        super().__init__(
            message=f"Policy definition '{policy_id}'{version_suffix} not found",
            context=context,
        )


class PolicyDefinitionNotEffectiveError(PolicyError):
    """Policy definition is not currently effective."""

    def __init__(
        self,
        policy_id: str,
        status: str,
        effective_from: datetime | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.status = status
        self.effective_from = effective_from
        super().__init__(
            message=f"Policy '{policy_id}' is not effective (status: {status})",
            context=context,
        )


class PolicyDefinitionAlreadyExistsError(PolicyError):
    """Policy definition already exists with this ID and version."""

    def __init__(
        self,
        policy_id: str,
        version: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.version = version
        super().__init__(
            message=f"Policy definition '{policy_id}' version {version} already exists",
            context=context,
        )


# =============================================================================
# Adapter Errors
# =============================================================================


class PolicyAdapterNotFoundError(PolicyError):
    """Policy adapter not found."""

    def __init__(
        self,
        adapter_id: str | None = None,
        policy_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.policy_id = policy_id
        if adapter_id:
            msg = f"Policy adapter '{adapter_id}' not found"
        elif policy_id:
            msg = f"No adapter found for policy '{policy_id}'"
        else:
            msg = "Policy adapter not found"
        super().__init__(message=msg, context=context)


class PolicyAdapterVersionMismatchError(PolicyError):
    """Adapter's policy_definition_version doesn't match the definition."""

    def __init__(
        self,
        adapter_id: str,
        adapter_version: str,
        definition_version: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self.definition_version = definition_version
        super().__init__(
            message=(
                f"Adapter '{adapter_id}' references definition version "
                f"'{adapter_version}' but definition is at '{definition_version}'"
            ),
            context=context,
        )


# =============================================================================
# Release Errors
# =============================================================================


class PolicyReleaseNotFoundError(PolicyError):
    """Policy release not found."""

    def __init__(
        self,
        release_id: str | UUID | None = None,
        version: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.release_id = release_id
        self.version = version
        if version:
            msg = f"Policy release version '{version}' not found"
        elif release_id:
            msg = f"Policy release '{release_id}' not found"
        else:
            msg = "Policy release not found"
        super().__init__(message=msg, context=context)


class PolicyReleaseAlreadyPublishedError(PolicyError):
    """Cannot modify a published release."""

    def __init__(
        self,
        release_id: str | UUID,
        version: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.release_id = release_id
        self.version = version
        version_suffix = f" ({version})" if version else ""
        super().__init__(
            message=f"Release '{release_id}'{version_suffix} is already published and cannot be modified",
            context=context,
        )


class PolicyReleaseNotPublishedError(PolicyError):
    """Release must be published before it can be activated."""

    def __init__(
        self,
        release_id: str | UUID,
        current_status: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.release_id = release_id
        self.current_status = current_status
        super().__init__(
            message=f"Release '{release_id}' must be published before activation (current: {current_status})",
            context=context,
        )


# =============================================================================
# Evaluation Errors
# =============================================================================


class PolicyEvaluationError(PolicyError):
    """Error during policy evaluation."""

    def __init__(
        self,
        policy_id: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.reason = reason
        super().__init__(
            message=f"Policy evaluation failed for '{policy_id}': {reason}",
            context=context,
        )


class PolicyDeniedError(PolicyError):
    """Policy evaluation returned DENY."""

    def __init__(
        self,
        policy_id: str,
        deny_reasons: tuple[str, ...],
        conditions_missing: tuple[str, ...] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.policy_id = policy_id
        self.deny_reasons = deny_reasons
        self.conditions_missing = conditions_missing or ()
        super().__init__(
            message=f"Policy '{policy_id}' denied: {', '.join(deny_reasons)}",
            context={
                **(context or {}),
                "deny_reasons": list(deny_reasons),
                "conditions_missing": list(self.conditions_missing),
            },
        )
