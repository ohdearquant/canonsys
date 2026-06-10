"""Canon exception hierarchy with retryable semantics.

Hierarchy:
    CanonError (base)
    ├── ValidationError (bad input)
    │   ├── OrderByValidationError
    │   └── DecodeError
    ├── ConfigurationError (setup/config)
    │   ├── DataSourceCycleError
    │   ├── PolicyNotEnforceableError
    │   ├── BundleError
    │   ├── TranspilationError
    │   └── RegistryCollisionError
    ├── AccessError (permission denied)
    │   ├── AuthenticationError
    │   ├── AuthorizationError
    │   └── TenantError
    ├── NotFoundError (entity not found)
    ├── ExistsError (entity exists)
    ├── ConflictError (version conflict, retryable)
    ├── ExecutionError (transient, retryable)
    │   ├── PolicyEvaluationError
    │   └── DataFetchError
    ├── OperationError (not allowed)
    │   └── ImmutableViolationError
    ├── PIIBlockedError (PII gate blocked)
    ├── IntegrityViolationError (hash mismatch)
    └── InvariantViolation (regulatory, never retryable)
        ├── ConsentViolation
        ├── TimingViolation
        ├── AuthorizationViolation
        ├── EvidenceViolation
        ├── DataProtectionViolation
        └── AIGovernanceViolation

Retryable: ConflictError, ExecutionError (and subclasses unless overridden).
Never retryable: InvariantViolation and all subclasses (regulatory violations).
"""

from __future__ import annotations

from typing import Any

__all__ = (
    "CanonError",
    # Validation
    "ValidationError",
    "OrderByValidationError",
    "DecodeError",
    # Configuration
    "ConfigurationError",
    "DataSourceCycleError",
    "PolicyNotEnforceableError",
    "BundleError",
    "TranspilationError",
    "RegistryCollisionError",
    # Access/Auth
    "AccessError",
    "AuthenticationError",
    "AuthorizationError",
    "TenantError",
    # CRUD
    "NotFoundError",
    "ExistsError",
    "ConflictError",
    # Execution
    "ExecutionError",
    "PolicyEvaluationError",
    "DataFetchError",
    # Operation
    "OperationError",
    "ImmutableViolationError",
    # PII
    "PIIBlockedError",
    # Integrity
    "IntegrityViolationError",
)


class CanonError(Exception):
    """Base exception for all Canon errors.

    Attributes:
        message: Human-readable error message
        details: Structured context for audit/logging
        retryable: Whether this error can be retried
    """

    default_message: str = "Canon error"
    default_retryable: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
        cause: Exception | None = None,
    ):
        self.message = message or self.default_message
        self.details = details or {}
        self.retryable = retryable if retryable is not None else self.default_retryable

        if cause:
            self.__cause__ = cause

        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize error for logging/audit."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "retryable": self.retryable,
            **({"details": self.details} if self.details else {}),
        }


# =============================================================================
# Validation Errors (bad input, not retryable)
# =============================================================================


class ValidationError(CanonError):
    """Validation failure - bad input."""

    default_message = "Validation failed"
    default_retryable = False


class OrderByValidationError(ValidationError):
    """Order-by clause contains invalid content.

    Raised when SQL order_by parameter fails sanitization.
    """

    default_message = "Invalid order-by clause"

    def __init__(
        self,
        clause: str,
        reason: str = "invalid format",
        **kwargs: Any,
    ):
        self.clause = clause
        self.reason = reason
        super().__init__(
            f"Invalid order-by clause '{clause}': {reason}",
            details={"clause": clause, "reason": reason},
            **kwargs,
        )


class DecodeError(ValidationError):
    """Decoding/parsing failed.

    Raised when structured data (OPA results, JSON, etc.) cannot be decoded.
    """

    default_message = "Decode failed"

    def __init__(
        self,
        source: str,
        reason: str = "decode failed",
        **kwargs: Any,
    ):
        self.source = source
        self.reason = reason
        super().__init__(
            f"Failed to decode {source}: {reason}",
            details={"source": source, "reason": reason},
            **kwargs,
        )


# =============================================================================
# Configuration Errors (setup/config, not retryable)
# =============================================================================


class ConfigurationError(CanonError):
    """Configuration error."""

    default_message = "Configuration error"
    default_retryable = False


class DataSourceCycleError(ConfigurationError):
    """Cyclic dependency detected in data sources.

    Raised at compile time when data source specs form a cycle.
    """

    default_message = "Cyclic dependency in data sources"

    def __init__(
        self,
        cycle: list[str],
        **kwargs: Any,
    ):
        self.cycle = cycle
        cycle_str = " -> ".join(cycle)
        super().__init__(
            f"Cyclic dependency in data sources: {cycle_str}",
            details={"cycle": cycle},
            **kwargs,
        )


class PolicyNotEnforceableError(ConfigurationError):
    """Required policy cannot be resolved to enforcement.

    Fail-closed error: if a constitution requires a policy that cannot
    be enforced, the system refuses to proceed.
    """

    default_message = "Policy cannot be enforced"

    def __init__(
        self,
        policy_id: str,
        reason: str = "no gate found",
        **kwargs: Any,
    ):
        self.policy_id = policy_id
        self.reason = reason
        super().__init__(
            f"Policy '{policy_id}' cannot be enforced: {reason}",
            details={"policy_id": policy_id, "reason": reason},
            **kwargs,
        )


class BundleError(ConfigurationError):
    """Policy bundle loading or validation failed.

    Raised when OPA/Rego bundle cannot be loaded or is invalid.
    """

    default_message = "Bundle error"

    def __init__(
        self,
        bundle_path: str | None,
        error: str,
        **kwargs: Any,
    ):
        self.bundle_path = bundle_path
        self.error = error
        msg = (
            f"Bundle error for {bundle_path}: {error}" if bundle_path else f"Bundle error: {error}"
        )
        super().__init__(
            msg,
            details={"bundle_path": bundle_path, "error": error},
            **kwargs,
        )


class TranspilationError(ConfigurationError):
    """Policy transpilation failed.

    Raised when PolicyDefinition to Rego transpilation fails.
    """

    default_message = "Transpilation failed"

    def __init__(
        self,
        policy_id: str,
        error: str,
        **kwargs: Any,
    ):
        self.policy_id = policy_id
        self.error = error
        super().__init__(
            f"Transpilation failed for {policy_id}: {error}",
            details={"policy_id": policy_id, "error": error},
            **kwargs,
        )


class RegistryCollisionError(ConfigurationError):
    """Entity registry collision - duplicate table name.

    Raised when two Entity subclasses attempt to register with the same
    table name. This prevents silent overwrites and makes conflicts explicit.
    """

    default_message = "Entity registry collision"

    def __init__(
        self,
        table_name: str,
        existing_class: str,
        new_class: str,
        **kwargs: Any,
    ):
        self.table_name = table_name
        self.existing_class = existing_class
        self.new_class = new_class
        super().__init__(
            f"Table '{table_name}' already registered by {existing_class}, "
            f"cannot register {new_class}",
            details={
                "table_name": table_name,
                "existing_class": existing_class,
                "new_class": new_class,
            },
            **kwargs,
        )


# =============================================================================
# Access Errors (permission denied, not retryable)
# =============================================================================


class AccessError(CanonError):
    """Access denied."""

    default_message = "Access denied"
    default_retryable = False


class AuthenticationError(AccessError):
    """Authentication failed - invalid or missing credentials."""

    default_message = "Authentication failed"


class AuthorizationError(AccessError):
    """Authorization failed - insufficient permissions."""

    default_message = "Authorization failed"

    def __init__(
        self,
        action: str | None = None,
        resource: str | None = None,
        **kwargs: Any,
    ):
        self.action = action
        self.resource = resource
        msg = "Authorization failed"
        if action and resource:
            msg = f"Not authorized to {action} on {resource}"
        elif action:
            msg = f"Not authorized to {action}"
        details = kwargs.pop("details", {}) or {}
        if action:
            details["action"] = action
        if resource:
            details["resource"] = resource
        super().__init__(msg, details=details, **kwargs)


class TenantError(AccessError):
    """Tenant context error - missing or invalid tenant."""

    default_message = "Tenant context error"

    def __init__(
        self,
        reason: str = "missing tenant context",
        **kwargs: Any,
    ):
        self.reason = reason
        super().__init__(
            f"Tenant error: {reason}",
            details={"reason": reason},
            **kwargs,
        )


# =============================================================================
# CRUD Errors
# =============================================================================


class NotFoundError(CanonError):
    """Entity not found."""

    default_message = "Not found"
    default_retryable = False


class ExistsError(CanonError):
    """Entity already exists."""

    default_message = "Already exists"
    default_retryable = False

    def __init__(
        self,
        message: str | None = None,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        **kwargs: Any,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        if message is None and entity_type and entity_id:
            message = f"{entity_type} already exists: {entity_id}"
        details = kwargs.pop("details", {}) or {}
        if entity_type:
            details["entity_type"] = entity_type
        if entity_id:
            details["entity_id"] = entity_id
        super().__init__(message, details=details, **kwargs)


class ConflictError(CanonError):
    """Version conflict - retryable (client can refresh)."""

    default_message = "Version conflict"
    default_retryable = True


# =============================================================================
# Execution Errors (transient, retryable)
# =============================================================================


class ExecutionError(CanonError):
    """Execution failure - retryable."""

    default_message = "Execution failed"
    default_retryable = True


class PolicyEvaluationError(ExecutionError):
    """Policy evaluation failed.

    Raised when OPA/policy evaluation encounters an error.
    Triggers fail-closed behavior (deny on error).

    Note: Most policy failures are permanent (syntax errors, missing rules,
    type mismatches) and should NOT be retried. Only transient failures
    (network timeouts, temporary unavailability) should pass retryable=True.
    """

    default_message = "Policy evaluation failed"
    default_retryable = False  # Override: most policy failures are permanent

    def __init__(
        self,
        policy_id: str,
        error: str,
        *,
        input_hash: str | None = None,
        **kwargs: Any,
    ):
        self.policy_id = policy_id
        self.error = error
        self.input_hash = input_hash
        super().__init__(
            f"Policy evaluation failed for {policy_id}: {error}",
            details={
                "policy_id": policy_id,
                "error": error,
                **({"input_hash": input_hash} if input_hash else {}),
            },
            **kwargs,
        )


class DataFetchError(ExecutionError):
    """Required data source could not be fetched.

    Retryable because data sources may be temporarily unavailable.
    """

    default_message = "Data fetch failed"

    def __init__(
        self,
        source_id: str,
        detail: str,
        **kwargs: Any,
    ):
        self.source_id = source_id
        self.detail = detail
        super().__init__(
            f"Missing required data source {source_id}: {detail}",
            details={"source_id": source_id, "detail": detail},
            **kwargs,
        )


# =============================================================================
# Operation Errors (not allowed, not retryable)
# =============================================================================


class OperationError(CanonError):
    """Generic operation failure."""

    default_message = "Operation failed"
    default_retryable = False


class ImmutableViolationError(OperationError):
    """Immutable entity modification attempted.

    Raised when attempting to modify or delete immutable entities
    (Evidence, Chain). Corrections use supersession, not mutation.
    """

    default_message = "Immutable entity violation"

    def __init__(
        self,
        entity_type: str,
        operation: str,
        *,
        entity_id: str | None = None,
        detail: str = "",
        **kwargs: Any,
    ):
        self.entity_type = entity_type
        self.operation = operation
        self.entity_id = entity_id
        self.detail = detail
        msg = f"{entity_type} is immutable: cannot {operation}"
        if entity_id:
            msg += f" {entity_id}"
        if detail:
            msg += f" ({detail})"
        super().__init__(
            msg,
            details={
                "entity_type": entity_type,
                "operation": operation,
                **({"entity_id": entity_id} if entity_id else {}),
                **({"detail": detail} if detail else {}),
            },
            **kwargs,
        )


# =============================================================================
# PII Errors (compliance, not retryable)
# =============================================================================


class PIIBlockedError(CanonError):
    """PII gate blocked evidence persistence.

    Indicates a bug in upstream redaction - PII should have been
    stripped before reaching Evidence. Fix the upstream code.
    """

    default_message = "PII gate blocked"
    default_retryable = False

    def __init__(
        self,
        block_reason: str,
        categories: list[str],
        **kwargs: Any,
    ):
        self.block_reason = block_reason
        self.categories = categories
        super().__init__(
            message=f"PII gate blocked: {block_reason}",
            details={"block_reason": block_reason, "categories": categories},
            **kwargs,
        )


# =============================================================================
# Integrity Errors (tampering detected, not retryable)
# =============================================================================


class IntegrityViolationError(CanonError):
    """Content hash mismatch detected - possible tampering.

    Raised when verify_integrity() detects that stored content_hash
    does not match recomputed hash. This indicates either:
    - Data corruption
    - Unauthorized modification (tampering)
    - Bug in hash computation

    This is a security incident that should be logged and investigated.
    """

    default_message = "Integrity verification failed"
    default_retryable = False

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        *,
        expected_hash: str | None = None,
        actual_hash: str | None = None,
        **kwargs: Any,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"Integrity check failed for {entity_type} {entity_id}: content hash mismatch",
            details={
                "entity_type": entity_type,
                "entity_id": entity_id,
                **(
                    {
                        "expected_hash": expected_hash,
                        "actual_hash": actual_hash,
                    }
                    if expected_hash and actual_hash
                    else {}
                ),
            },
            **kwargs,
        )
