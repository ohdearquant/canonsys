"""Tests for database error mapping."""

from __future__ import annotations

from canon.db.errors import (
    SQLSTATE_CONNECTION_CLASS,
    SQLSTATE_DEADLOCK_DETECTED,
    SQLSTATE_FOREIGN_KEY_VIOLATION,
    SQLSTATE_QUERY_CANCELED,
    SQLSTATE_SERIALIZATION_FAILURE,
    SQLSTATE_UNIQUE_VIOLATION,
    map_db_error,
)
from canon.exceptions import ConflictError, ExecutionError, ExistsError, ValidationError


class MockException(Exception):
    """Mock exception with SQLSTATE."""

    def __init__(self, message: str, sqlstate: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate


class TestMapDbErrorSQLSTATE:
    """Tests for SQLSTATE-based error mapping."""

    def test_unique_violation(self):
        """Unique violation should map to ExistsError."""
        exc = MockException("duplicate key", SQLSTATE_UNIQUE_VIOLATION)
        result = map_db_error(exc)

        assert isinstance(result, ExistsError)
        assert result.retryable is False
        assert "constraint" in result.message.lower()

    def test_foreign_key_violation(self):
        """Foreign key violation should map to ValidationError."""
        exc = MockException("fk violation", SQLSTATE_FOREIGN_KEY_VIOLATION)
        result = map_db_error(exc)

        assert isinstance(result, ValidationError)
        assert result.retryable is False

    def test_serialization_failure(self):
        """Serialization failure should map to retryable ConflictError."""
        exc = MockException("serialization", SQLSTATE_SERIALIZATION_FAILURE)
        result = map_db_error(exc)

        assert isinstance(result, ConflictError)
        assert result.retryable is True

    def test_deadlock_detected(self):
        """Deadlock should map to retryable ConflictError."""
        exc = MockException("deadlock", SQLSTATE_DEADLOCK_DETECTED)
        result = map_db_error(exc)

        assert isinstance(result, ConflictError)
        assert result.retryable is True

    def test_query_canceled(self):
        """Query canceled should map to retryable ExecutionError."""
        exc = MockException("canceled", SQLSTATE_QUERY_CANCELED)
        result = map_db_error(exc)

        assert isinstance(result, ExecutionError)
        assert result.retryable is True

    def test_connection_error(self):
        """Connection errors (08xxx) should map to retryable ExecutionError."""
        exc = MockException("connection lost", f"{SQLSTATE_CONNECTION_CLASS}006")
        result = map_db_error(exc)

        assert isinstance(result, ExecutionError)
        assert result.retryable is True

    def test_unknown_sqlstate(self):
        """Unknown SQLSTATE should map to non-retryable ExecutionError."""
        exc = MockException("unknown error", "99999")
        result = map_db_error(exc)

        assert isinstance(result, ExecutionError)
        assert result.retryable is False


class TestMapDbErrorSQLite:
    """Tests for SQLite error detection (for testing)."""

    def test_sqlite_unique_constraint(self):
        """SQLite UNIQUE constraint failed should map to ExistsError."""
        exc = Exception("UNIQUE constraint failed: users.email")
        result = map_db_error(exc)

        assert isinstance(result, ExistsError)
        assert result.retryable is False


class TestMapDbErrorUnknown:
    """Tests for unknown error handling."""

    def test_plain_exception(self):
        """Plain exception should map to non-retryable ExecutionError."""
        exc = Exception("something went wrong")
        result = map_db_error(exc)

        assert isinstance(result, ExecutionError)
        assert result.retryable is False
        assert "something went wrong" in result.message

    def test_preserves_original_in_details(self):
        """Original error should be preserved in details."""
        exc = Exception("original message")
        result = map_db_error(exc)

        assert result.details.get("original") == "original message"


class TestMapDbErrorDetails:
    """Tests for error detail extraction."""

    def test_constraint_name_extracted(self):
        """Constraint name should be extracted if available."""

        class ConstraintError(Exception):
            def __init__(self):
                super().__init__("constraint error")
                self.sqlstate = SQLSTATE_UNIQUE_VIOLATION
                self.constraint_name = "uq_users_email"

        exc = ConstraintError()
        result = map_db_error(exc)

        assert result.details.get("constraint") == "uq_users_email"
