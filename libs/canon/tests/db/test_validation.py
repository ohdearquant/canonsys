"""Tests for SQL validation utilities."""

from __future__ import annotations

import pytest

from canon.db.validation import sanitize_order_by, validate_identifier
from canon.exceptions import OrderByValidationError, ValidationError

# -----------------------------------------------------------------------------
# validate_identifier Tests
# -----------------------------------------------------------------------------


class TestValidateIdentifier:
    """Tests for validate_identifier function."""

    # Valid identifiers
    def test_simple_name(self) -> None:
        """Simple alphanumeric name is valid."""
        validate_identifier("users")  # Should not raise

    def test_with_underscore(self) -> None:
        """Name with underscore is valid."""
        validate_identifier("user_name")

    def test_starts_with_underscore(self) -> None:
        """Name starting with underscore is valid."""
        validate_identifier("_private")

    def test_mixed_case(self) -> None:
        """Mixed case name is valid."""
        validate_identifier("UserName")

    def test_with_numbers(self) -> None:
        """Name with numbers (not at start) is valid."""
        validate_identifier("user123")

    def test_single_letter(self) -> None:
        """Single letter is valid."""
        validate_identifier("x")

    # Invalid identifiers
    def test_empty_string_raises(self) -> None:
        """Empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="Empty identifier name"):
            validate_identifier("")

    def test_starts_with_number_raises(self) -> None:
        """Starting with number raises ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("123abc")

    def test_contains_spaces_raises(self) -> None:
        """Spaces raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("user name")

    def test_contains_dash_raises(self) -> None:
        """Dashes raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("user-name")

    def test_contains_semicolon_raises(self) -> None:
        """Semicolons raise ValidationError (SQL injection attempt)."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("users;DROP TABLE")

    def test_contains_quotes_raises(self) -> None:
        """Quotes raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("users'--")

    def test_contains_parentheses_raises(self) -> None:
        """Parentheses raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("users()")

    def test_sql_injection_attempt(self) -> None:
        """SQL injection attempts are blocked."""
        with pytest.raises(ValidationError):
            validate_identifier("users; DROP TABLE users; --")

    # Custom kind parameter
    def test_custom_kind_in_error_message(self) -> None:
        """Custom kind appears in error message."""
        with pytest.raises(ValidationError, match="Empty table name"):
            validate_identifier("", kind="table")

        with pytest.raises(ValidationError, match="Unsafe column identifier"):
            validate_identifier("bad-col", kind="column")


# -----------------------------------------------------------------------------
# sanitize_order_by Tests
# -----------------------------------------------------------------------------


class TestSanitizeOrderBy:
    """Tests for sanitize_order_by function."""

    # Valid order_by clauses
    def test_single_column(self) -> None:
        """Single column name."""
        result = sanitize_order_by("name")
        assert result == '"name" ASC'

    def test_column_with_asc(self) -> None:
        """Column with explicit ASC."""
        result = sanitize_order_by("name ASC")
        assert result == '"name" ASC'

    def test_column_with_desc(self) -> None:
        """Column with DESC."""
        result = sanitize_order_by("created_at DESC")
        assert result == '"created_at" DESC'

    def test_lowercase_direction(self) -> None:
        """Lowercase direction is normalized."""
        result = sanitize_order_by("name desc")
        assert result == '"name" DESC'

    def test_multiple_columns(self) -> None:
        """Multiple columns separated by comma."""
        result = sanitize_order_by("name ASC, created_at DESC")
        assert result == '"name" ASC, "created_at" DESC'

    def test_whitespace_handling(self) -> None:
        """Extra whitespace is handled."""
        result = sanitize_order_by("  name  ,  created_at DESC  ")
        assert result == '"name" ASC, "created_at" DESC'

    def test_underscore_column(self) -> None:
        """Column with underscore."""
        result = sanitize_order_by("created_at")
        assert result == '"created_at" ASC'

    # Invalid order_by clauses
    def test_empty_raises(self) -> None:
        """Empty string raises error."""
        with pytest.raises(OrderByValidationError, match="empty clause"):
            sanitize_order_by("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace only raises error."""
        with pytest.raises(OrderByValidationError, match="empty clause"):
            sanitize_order_by("   ")

    def test_invalid_column_name(self) -> None:
        """Invalid column name raises error."""
        with pytest.raises(OrderByValidationError, match="must be alphanumeric"):
            sanitize_order_by("bad-column")

    def test_invalid_direction(self) -> None:
        """Invalid direction raises error."""
        with pytest.raises(OrderByValidationError, match="must be ASC or DESC"):
            sanitize_order_by("name ASCENDING")

    def test_too_many_tokens(self) -> None:
        """Too many tokens raises error."""
        with pytest.raises(OrderByValidationError, match="expected 'column' or 'column ASC/DESC'"):
            sanitize_order_by("name ASC NULLS FIRST")

    def test_sql_injection_in_column(self) -> None:
        """SQL injection in column name is blocked."""
        with pytest.raises(OrderByValidationError):
            sanitize_order_by("name; DROP TABLE users; --")

    def test_sql_injection_in_direction(self) -> None:
        """SQL injection in direction is blocked."""
        with pytest.raises(OrderByValidationError, match="expected 'column' or 'column ASC/DESC'"):
            sanitize_order_by("name DESC; DROP TABLE")

    def test_quotes_in_column(self) -> None:
        """Quotes in column name are blocked."""
        with pytest.raises(OrderByValidationError):
            sanitize_order_by("'name'")

    def test_column_starting_with_number(self) -> None:
        """Column starting with number is blocked."""
        with pytest.raises(OrderByValidationError, match="must be alphanumeric"):
            sanitize_order_by("123column")


# -----------------------------------------------------------------------------
# Edge Cases and Integration Tests
# -----------------------------------------------------------------------------


class TestValidationEdgeCases:
    """Edge cases for validation functions."""

    def test_order_by_with_trailing_comma(self) -> None:
        """Trailing comma is handled (empty clause ignored)."""
        result = sanitize_order_by("name,")
        assert result == '"name" ASC'

    def test_order_by_with_leading_comma(self) -> None:
        """Leading comma is handled (empty clause ignored)."""
        result = sanitize_order_by(",name")
        assert result == '"name" ASC'

    def test_identifier_max_length_valid(self) -> None:
        """63-char identifier is valid (PostgreSQL limit)."""
        max_name = "a" * 63
        validate_identifier(max_name)  # Should not raise

    def test_identifier_too_long_raises(self) -> None:
        """Identifier exceeding 63 chars raises ValidationError."""
        long_name = "a" * 64
        with pytest.raises(ValidationError, match="too long"):
            validate_identifier(long_name)

    def test_identifier_with_unicode_raises(self) -> None:
        """Unicode characters raise ValidationError."""
        with pytest.raises(ValidationError, match="Unsafe identifier"):
            validate_identifier("naméé")

    def test_order_by_multiple_same_column(self) -> None:
        """Multiple same column (weird but valid SQL)."""
        result = sanitize_order_by("name ASC, name DESC")
        assert result == '"name" ASC, "name" DESC'


class TestValidationSecurityCoverage:
    """Security-focused validation tests."""

    @pytest.mark.parametrize(
        "payload",
        [
            "'; DROP TABLE users; --",
            "1; SELECT * FROM passwords",
            "name OR 1=1",
            "name UNION SELECT password FROM users",
            "name; TRUNCATE users",
            "name\n; DROP TABLE",
            "name/**/OR/**/1=1",
        ],
    )
    def test_sql_injection_payloads_blocked(self, payload: str) -> None:
        """Common SQL injection payloads are blocked."""
        with pytest.raises((ValidationError, OrderByValidationError)):
            validate_identifier(payload)

    @pytest.mark.parametrize(
        "payload",
        [
            "name; DROP TABLE",
            "name' OR '1'='1",
            "name--",
            "name/*comment*/",
            "1=1 OR name",
        ],
    )
    def test_order_by_injection_payloads_blocked(self, payload: str) -> None:
        """SQL injection in order_by is blocked."""
        with pytest.raises(OrderByValidationError):
            sanitize_order_by(payload)
