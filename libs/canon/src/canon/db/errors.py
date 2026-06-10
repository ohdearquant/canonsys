"""Database error mapping to CanonError hierarchy.

Maps asyncpg and SQLite exceptions to typed Canon errors.
"""

from __future__ import annotations

from ..exceptions import (
    CanonError,
    ConflictError,
    ExecutionError,
    ExistsError,
    ValidationError,
)

__all__ = (
    "SQLSTATE_CONNECTION_CLASS",
    "SQLSTATE_DEADLOCK_DETECTED",
    "SQLSTATE_FOREIGN_KEY_VIOLATION",
    "SQLSTATE_QUERY_CANCELED",
    "SQLSTATE_SERIALIZATION_FAILURE",
    "SQLSTATE_UNIQUE_VIOLATION",
    "map_db_error",
)

# PostgreSQL SQLSTATE codes
# https://www.postgresql.org/docs/current/errcodes-appendix.html
SQLSTATE_UNIQUE_VIOLATION = "23505"
SQLSTATE_FOREIGN_KEY_VIOLATION = "23503"
SQLSTATE_SERIALIZATION_FAILURE = "40001"
SQLSTATE_DEADLOCK_DETECTED = "40P01"
SQLSTATE_QUERY_CANCELED = "57014"
# Connection class (08xxx)
SQLSTATE_CONNECTION_CLASS = "08"


def map_db_error(
    exc: Exception,
) -> ConflictError | ExecutionError | ExistsError | ValidationError:
    """Map a database exception to a typed CanonError.

    Per D3.9, maps asyncpg errors to Canon hierarchy:
    - UniqueViolationError (23505) → ExistsError (not retryable)
    - ForeignKeyViolationError (23503) → ValidationError (not retryable)
    - SerializationError (40001) → ConflictError (retryable)
    - DeadlockDetected (40P01) → ConflictError (retryable)
    - QueryCanceledError (57014) → ExecutionError (retryable)
    - Connection errors (08xxx) → ExecutionError (retryable)
    - Unknown → ExecutionError (not retryable)

    Args:
        exc: The database exception to map.

    Returns:
        A typed CanonError with appropriate retryable semantics.

    Example:
        try:
            await insert_row(...)
        except Exception as e:
            raise map_db_error(e) from e
    """
    # Try to get SQLSTATE from asyncpg exception
    sqlstate = getattr(exc, "sqlstate", None)

    if sqlstate:
        return _map_sqlstate(sqlstate, exc)

    # Try asyncpg exception types directly
    try:
        import asyncpg

        if isinstance(exc, asyncpg.UniqueViolationError):
            return _unique_violation_error(exc)

        if isinstance(exc, asyncpg.ForeignKeyViolationError):
            return _foreign_key_error(exc)

        if isinstance(exc, asyncpg.SerializationError):
            return ConflictError(
                message=f"Serialization conflict: {exc}",
                details={"original": str(exc)},
                retryable=True,
            )

        if isinstance(exc, asyncpg.DeadlockDetectedError):
            return ConflictError(
                message=f"Deadlock detected: {exc}",
                details={"original": str(exc)},
                retryable=True,
            )

        if isinstance(exc, asyncpg.QueryCanceledError):
            return ExecutionError(
                message=f"Query canceled: {exc}",
                details={"original": str(exc)},
                retryable=True,
            )

        # Connection errors
        if isinstance(
            exc,
            (
                asyncpg.ConnectionDoesNotExistError,
                asyncpg.ConnectionFailureError,
                asyncpg.InterfaceError,
            ),
        ):
            return ExecutionError(
                message=f"Database connection error: {exc}",
                details={"original": str(exc)},
                retryable=True,
            )

    except ImportError:
        pass

    # SQLite unique constraint (for testing)
    msg = str(exc).lower()
    if "unique" in msg and "constraint" in msg:
        return _unique_violation_error(exc)

    # Unknown error - not retryable by default
    return ExecutionError(
        message=f"Database error: {exc}",
        details={"original": str(exc), "type": type(exc).__name__},
        retryable=False,
    )


def _map_sqlstate(sqlstate: str, exc: Exception) -> CanonError:
    """Map SQLSTATE code to CanonError."""
    if sqlstate == SQLSTATE_UNIQUE_VIOLATION:
        return _unique_violation_error(exc)

    if sqlstate == SQLSTATE_FOREIGN_KEY_VIOLATION:
        return _foreign_key_error(exc)

    if sqlstate == SQLSTATE_SERIALIZATION_FAILURE:
        return ConflictError(
            message=f"Serialization conflict: {exc}",
            details={"sqlstate": sqlstate, "original": str(exc)},
            retryable=True,
        )

    if sqlstate == SQLSTATE_DEADLOCK_DETECTED:
        return ConflictError(
            message=f"Deadlock detected: {exc}",
            details={"sqlstate": sqlstate, "original": str(exc)},
            retryable=True,
        )

    if sqlstate == SQLSTATE_QUERY_CANCELED:
        return ExecutionError(
            message=f"Query canceled: {exc}",
            details={"sqlstate": sqlstate, "original": str(exc)},
            retryable=True,
        )

    # Connection class (08xxx)
    if sqlstate.startswith(SQLSTATE_CONNECTION_CLASS):
        return ExecutionError(
            message=f"Database connection error: {exc}",
            details={"sqlstate": sqlstate, "original": str(exc)},
            retryable=True,
        )

    # Unknown SQLSTATE - not retryable
    return ExecutionError(
        message=f"Database error: {exc}",
        details={"sqlstate": sqlstate, "original": str(exc)},
        retryable=False,
    )


def _unique_violation_error(exc: Exception) -> ExistsError:
    """Create ExistsError from unique violation."""
    # Try to extract constraint details
    constraint_name = getattr(exc, "constraint_name", None)
    detail = getattr(exc, "detail", str(exc))

    return ExistsError(
        message=f"Unique constraint violated: {detail}",
        details={
            "original": str(exc),
            **({"constraint": constraint_name} if constraint_name else {}),
        },
    )


def _foreign_key_error(exc: Exception) -> ValidationError:
    """Create ValidationError from foreign key violation."""
    constraint_name = getattr(exc, "constraint_name", None)
    detail = getattr(exc, "detail", str(exc))

    return ValidationError(
        message=f"Foreign key constraint violated: {detail}",
        details={
            "original": str(exc),
            **({"constraint": constraint_name} if constraint_name else {}),
        },
    )
