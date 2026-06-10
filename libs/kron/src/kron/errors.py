"""Kron exception hierarchy with structured details and retryability.

All exceptions inherit from KronError and include:
    - message: Human-readable description
    - details: Structured context dict
    - retryable: Whether retry might succeed

Naming: KronConnectionError/KronTimeoutError avoid shadowing builtins.
"""

from __future__ import annotations

from typing import Any

__all__ = (
    "AccessError",
    "ConfigurationError",
    "ExecutionError",
    "ExistsError",
    "KronConnectionError",
    "KronError",
    "KronTimeoutError",
    "NotFoundError",
    "OperationError",
    "QueueFullError",
    "ValidationError",
)


class KronError(Exception):
    """Base exception for kron. Serializable with structured details.

    Subclasses set default_message and default_retryable.
    Use cause= to chain exceptions with preserved traceback.

    Attributes:
        message: Human-readable description.
        details: Structured context for debugging/logging.
        retryable: Whether retry might succeed.
    """

    default_message: str = "kron error"
    default_retryable: bool = True

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        cause: Exception | None = None,
    ):
        """Initialize with optional message, details, retryability, and cause."""
        self.message = message or self.default_message
        self.details = details or {}
        self.retryable = retryable if retryable is not None else self.default_retryable

        if cause:
            self.__cause__ = cause  # Preserve traceback

        super().__init__(self.message)

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize to dict: {error, message, retryable, details?}."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "retryable": self.retryable,
            **({"details": self.details} if self.details else {}),
        }


class ValidationError(KronError):
    """Data validation failure. Raise when input fails schema/constraint checks."""

    default_message = "Validation failed"
    default_retryable = False


class AccessError(KronError):
    """Permission denied. Raise when capability/resource access is blocked."""

    default_message = "Access denied"
    default_retryable = False


class ConfigurationError(KronError):
    """Invalid configuration. Raise when setup/config is incorrect."""

    default_message = "Configuration error"
    default_retryable = False


class ExecutionError(KronError):
    """Execution failure. Raise when Event/Calling invoke fails (often transient)."""

    default_message = "Execution failed"
    default_retryable = True


class KronConnectionError(KronError):
    """Network/connection failure. Named to avoid shadowing builtins."""

    default_message = "Connection error"
    default_retryable = True


class KronTimeoutError(KronError):
    """Operation timeout. Named to avoid shadowing builtins."""

    default_message = "Operation timed out"
    default_retryable = True


class NotFoundError(KronError):
    """Resource/item not found. Raise when lookup fails."""

    default_message = "Item not found"
    default_retryable = False


class ExistsError(KronError):
    """Duplicate item. Raise when creating item that already exists."""

    default_message = "Item already exists"
    default_retryable = False


class QueueFullError(KronError):
    """Capacity exceeded. Raise when queue/buffer is full."""

    default_message = "Queue is full"
    default_retryable = True


class OperationError(KronError):
    """Generic operation failure. Use for unclassified operation errors."""

    default_message = "Operation failed"
    default_retryable = False
