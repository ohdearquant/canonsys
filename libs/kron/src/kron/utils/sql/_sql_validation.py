"""SQL validation utilities for injection prevention.

Validates SQL identifiers and clauses before interpolation into DDL/queries.
"""

from __future__ import annotations

import re

__all__ = (
    "MAX_IDENTIFIER_LENGTH",
    "SAFE_IDENTIFIER_PATTERN",
    "sanitize_order_by",
    "validate_identifier",
)

# SQL identifier: alphanumeric and underscores, starting with letter/underscore
SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
VALID_DIRECTIONS = frozenset({"ASC", "DESC"})
MAX_IDENTIFIER_LENGTH = 63  # PostgreSQL limit


class SQLValidationError(ValueError):
    """SQL validation failure with structured details."""

    def __init__(self, message: str, *, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validate_identifier(name: str, kind: str = "identifier") -> str:
    """Validate SQL identifier to prevent injection.

    Checks that identifier:
    - Is non-empty
    - Does not exceed PostgreSQL's 63 character limit
    - Contains only alphanumeric characters and underscores
    - Starts with a letter or underscore

    Args:
        name: The identifier to validate.
        kind: Description for error messages (e.g., "table", "column").

    Returns:
        The validated identifier (unchanged if valid).

    Raises:
        SQLValidationError: If identifier is empty, too long, or contains unsafe chars.

    Example:
        >>> validate_identifier("user_name", "column")
        'user_name'
        >>> validate_identifier("123bad", "table")  # Raises SQLValidationError
    """
    if not name:
        raise SQLValidationError(
            f"Empty {kind} name not allowed",
            details={"kind": kind, "value": name},
        )

    if len(name) > MAX_IDENTIFIER_LENGTH:
        raise SQLValidationError(
            f"{kind.capitalize()} identifier too long: {name!r} ({len(name)} chars). "
            f"Maximum is {MAX_IDENTIFIER_LENGTH} characters.",
            details={"kind": kind, "value": name, "length": len(name)},
        )

    if not SAFE_IDENTIFIER_PATTERN.match(name):
        raise SQLValidationError(
            f"Unsafe {kind} identifier: {name!r}. "
            f"Must be alphanumeric/underscore, starting with letter or underscore.",
            details={"kind": kind, "value": name},
        )

    return name


def sanitize_order_by(order_by: str) -> str:
    """Sanitize ORDER BY clause to prevent SQL injection.

    Accepts formats:
        - "column"
        - "column ASC"
        - "column DESC"
        - "column1, column2 DESC"

    Returns safely quoted SQL fragment.

    Args:
        order_by: The ORDER BY clause to sanitize.

    Returns:
        Sanitized ORDER BY clause with quoted identifiers.

    Raises:
        SQLValidationError: If column name or direction is invalid.

    Example:
        >>> sanitize_order_by("name, created_at DESC")
        '"name" ASC, "created_at" DESC'
    """
    parts: list[str] = []

    for clause in order_by.split(","):
        clause = clause.strip()
        if not clause:
            continue

        tokens = clause.split()
        if len(tokens) == 1:
            column = tokens[0]
            direction = "ASC"
        elif len(tokens) == 2:
            column, direction = tokens
            direction = direction.upper()
        else:
            raise SQLValidationError(
                f"Invalid ORDER BY clause: {clause!r}. Expected 'column' or 'column ASC/DESC'.",
                details={"clause": clause},
            )

        # Validate column name
        if not SAFE_IDENTIFIER_PATTERN.match(column):
            raise SQLValidationError(
                f"Invalid column in ORDER BY: {column!r}. "
                "Must be alphanumeric/underscore identifier.",
                details={"column": column},
            )

        # Validate direction
        if direction not in VALID_DIRECTIONS:
            raise SQLValidationError(
                f"Invalid direction in ORDER BY: {direction!r}. Must be ASC or DESC.",
                details={"direction": direction},
            )

        parts.append(f'"{column}" {direction}')

    if not parts:
        raise SQLValidationError(
            f"Empty ORDER BY clause: {order_by!r}",
            details={"order_by": order_by},
        )

    return ", ".join(parts)
