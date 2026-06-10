"""SQL validation utilities - delegates to kron.utils.

Prevents SQL injection via identifier and clause validation.
Uses kron's validation logic, maps errors to canon's exception hierarchy.
"""

from __future__ import annotations

from canon.exceptions import OrderByValidationError, ValidationError
from kron.utils import (
    sanitize_order_by as _kron_sanitize_order_by,
    validate_identifier as _kron_validate_identifier,
)
from kron.utils.sql._sql_validation import SQLValidationError

__all__ = (
    "sanitize_order_by",
    "validate_identifier",
)


def validate_identifier(name: str, kind: str = "identifier") -> str:
    """Validate SQL identifier to prevent injection.

    Delegates to kron.utils.validate_identifier, maps exceptions to canon hierarchy.

    Args:
        name: The identifier to validate.
        kind: Description for error messages (e.g., "table", "column").

    Returns:
        The validated identifier (unchanged if valid).

    Raises:
        ValidationError: If identifier is empty, too long, or contains unsafe characters.
    """
    try:
        return _kron_validate_identifier(name, kind)
    except SQLValidationError as e:
        raise ValidationError(str(e), details=getattr(e, "details", {})) from e


def sanitize_order_by(order_by: str) -> str:
    """Sanitize ORDER BY clause to prevent SQL injection.

    Delegates to kron.utils.sanitize_order_by, maps exceptions to canon hierarchy.

    Args:
        order_by: The ORDER BY clause to sanitize.

    Returns:
        Sanitized ORDER BY clause with quoted identifiers.

    Raises:
        OrderByValidationError: If column name or direction is invalid.
    """
    try:
        return _kron_sanitize_order_by(order_by)
    except SQLValidationError as e:
        details = getattr(e, "details", {})
        clause = (
            details.get("clause") or details.get("column") or details.get("order_by") or order_by
        )
        reason = _extract_reason(str(e))
        raise OrderByValidationError(clause, reason) from e


def _extract_reason(message: str) -> str:
    """Extract concise reason from canon.kron's validation error message."""
    msg = message.lower()
    if "empty" in msg:
        return "empty clause"
    if "invalid column" in msg or ("alphanumeric" in msg and "column" in msg):
        return "must be alphanumeric/underscore identifier"
    if "invalid direction" in msg or ("must be asc" in msg):
        return "must be ASC or DESC"
    if "invalid order by" in msg or "expected" in msg:
        return "expected 'column' or 'column ASC/DESC'"
    if "alphanumeric" in msg or "identifier" in msg:
        return "must be alphanumeric/underscore identifier"
    return message
