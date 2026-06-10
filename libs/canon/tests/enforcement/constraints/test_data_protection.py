"""Tests for data protection truth machine constraints.

Tests cover:
- pii_must_not_be_public: PII visibility validation
- transmission_must_be_encrypted: Encryption requirement validation
- data_classification_must_allow: Operation permission validation
- retention_must_not_be_exceeded: Retention period validation

Truth Machine Semantics:
    Each constraint returns Literal[True] on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from canon.enforcement.constraints import (
    data_classification_must_allow,
    pii_must_not_be_public,
    retention_must_not_be_exceeded,
    transmission_must_be_encrypted,
)
from canon.enforcement.exceptions import (
    ClassificationViolationError,
    PIIExposureError,
    RetentionExceededError,
    UnencryptedTransmissionError,
)

# =============================================================================
# pii_must_not_be_public Tests
# =============================================================================


class TestPiiMustNotBePublic:
    """Tests for pii_must_not_be_public constraint."""

    def test_internal_pii_succeeds(self):
        """Test PII with internal visibility passes."""
        result = pii_must_not_be_public(visibility="internal", contains_pii=True)
        assert result is True

    def test_public_non_pii_succeeds(self):
        """Test public visibility without PII passes."""
        result = pii_must_not_be_public(visibility="public", contains_pii=False)
        assert result is True

    def test_public_pii_raises(self):
        """Test public PII raises PIIExposureError."""
        with pytest.raises(PIIExposureError) as exc_info:
            pii_must_not_be_public(visibility="public", contains_pii=True)

        exc = exc_info.value
        assert exc.visibility == "public"
        assert exc.contains_pii is True
        assert "GDPR Article 5" in exc.regulation

    def test_confidential_pii_succeeds(self):
        """Test PII with confidential visibility passes."""
        result = pii_must_not_be_public(visibility="confidential", contains_pii=True)
        assert result is True

    def test_restricted_pii_succeeds(self):
        """Test PII with restricted visibility passes."""
        result = pii_must_not_be_public(visibility="restricted", contains_pii=True)
        assert result is True

    def test_private_visibility_succeeds(self):
        """Test any non-public visibility passes."""
        non_public_visibilities = ["internal", "private", "confidential", "restricted"]

        for visibility in non_public_visibilities:
            result = pii_must_not_be_public(visibility=visibility, contains_pii=True)
            assert result is True

    def test_error_contains_context(self):
        """Test error contains useful context."""
        with pytest.raises(PIIExposureError) as exc_info:
            pii_must_not_be_public(visibility="public", contains_pii=True)

        context = exc_info.value.context
        assert context["visibility"] == "public"
        assert context["contains_pii"] is True


# =============================================================================
# transmission_must_be_encrypted Tests
# =============================================================================


class TestTransmissionMustBeEncrypted:
    """Tests for transmission_must_be_encrypted constraint."""

    def test_encrypted_pii_succeeds(self):
        """Test encrypted PII transmission passes."""
        result = transmission_must_be_encrypted(is_encrypted=True, data_classification="pii")
        assert result is True

    def test_unencrypted_public_succeeds(self):
        """Test unencrypted public data transmission passes."""
        result = transmission_must_be_encrypted(is_encrypted=False, data_classification="public")
        assert result is True

    def test_unencrypted_confidential_raises(self):
        """Test unencrypted confidential data raises UnencryptedTransmissionError."""
        with pytest.raises(UnencryptedTransmissionError) as exc_info:
            transmission_must_be_encrypted(is_encrypted=False, data_classification="confidential")

        exc = exc_info.value
        assert exc.is_encrypted is False
        assert exc.data_classification == "confidential"
        assert "GDPR Article 32" in exc.regulation

    def test_unencrypted_restricted_raises(self):
        """Test unencrypted restricted data raises error."""
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="restricted")

    def test_unencrypted_pii_raises(self):
        """Test unencrypted PII raises error."""
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="pii")

    def test_encrypted_all_classifications_succeeds(self):
        """Test encrypted transmission passes for all classifications."""
        classifications = ["public", "internal", "confidential", "restricted", "pii"]

        for classification in classifications:
            result = transmission_must_be_encrypted(
                is_encrypted=True, data_classification=classification
            )
            assert result is True

    def test_case_insensitive_classification(self):
        """Test classification comparison is case-insensitive."""
        # Uppercase should still trigger encryption requirement
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="CONFIDENTIAL")

        # Mixed case
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="Pii")

    def test_internal_unencrypted_succeeds(self):
        """Test unencrypted internal data passes (not sensitive)."""
        result = transmission_must_be_encrypted(is_encrypted=False, data_classification="internal")
        assert result is True


# =============================================================================
# data_classification_must_allow Tests
# =============================================================================


class TestDataClassificationMustAllow:
    """Tests for data_classification_must_allow constraint."""

    def test_allowed_operation_succeeds(self):
        """Test allowed operation returns True."""
        allowed_ops = {"read", "write", "delete"}
        result = data_classification_must_allow(
            classification="internal",
            operation="read",
            allowed_operations=allowed_ops,
        )
        assert result is True

    def test_disallowed_operation_raises(self):
        """Test disallowed operation raises ClassificationViolationError."""
        allowed_ops = {"read"}

        with pytest.raises(ClassificationViolationError) as exc_info:
            data_classification_must_allow(
                classification="restricted",
                operation="export",
                allowed_operations=allowed_ops,
            )

        exc = exc_info.value
        assert exc.classification == "restricted"
        assert exc.operation == "export"
        assert exc.allowed_operations == allowed_ops
        assert "SOC 2 CC6.1" in exc.regulation

    def test_empty_allowed_operations_raises(self):
        """Test empty allowed operations always raises."""
        with pytest.raises(ClassificationViolationError):
            data_classification_must_allow(
                classification="confidential",
                operation="read",
                allowed_operations=set(),
            )

    def test_multiple_operations_check(self):
        """Test checking multiple operations against same classification."""
        restricted_ops = {"read", "audit_view"}

        # Allowed operations pass
        for op in restricted_ops:
            result = data_classification_must_allow(
                classification="restricted",
                operation=op,
                allowed_operations=restricted_ops,
            )
            assert result is True

        # Disallowed operations fail
        for op in ["write", "delete", "export", "share"]:
            with pytest.raises(ClassificationViolationError):
                data_classification_must_allow(
                    classification="restricted",
                    operation=op,
                    allowed_operations=restricted_ops,
                )

    def test_classification_levels_have_different_permissions(self):
        """Test different classification levels have different allowed operations."""
        # Public can do almost anything
        public_ops = {"read", "write", "share", "export", "delete"}
        data_classification_must_allow("public", "export", public_ops)

        # Internal has restricted sharing
        internal_ops = {"read", "write", "delete"}
        with pytest.raises(ClassificationViolationError):
            data_classification_must_allow("internal", "export", internal_ops)

        # Confidential is very restricted
        confidential_ops = {"read"}
        with pytest.raises(ClassificationViolationError):
            data_classification_must_allow("confidential", "write", confidential_ops)

    def test_error_shows_allowed_operations(self):
        """Test error message shows what operations are allowed."""
        allowed = {"read", "write"}

        with pytest.raises(ClassificationViolationError) as exc_info:
            data_classification_must_allow("internal", "export", allowed)

        # Allowed operations should be in context for debugging
        assert set(exc_info.value.context["allowed_operations"]) == allowed


# =============================================================================
# retention_must_not_be_exceeded Tests
# =============================================================================


class TestRetentionMustNotBeExceeded:
    """Tests for retention_must_not_be_exceeded constraint."""

    def test_within_retention_period_succeeds(self, utc_now):
        """Test data within retention period passes."""
        retention_end = utc_now + timedelta(days=30)
        result = retention_must_not_be_exceeded(retention_end, utc_now)
        assert result is True

    def test_at_exact_retention_end_succeeds(self, utc_now):
        """Test data at exact retention end passes (not exceeded yet)."""
        result = retention_must_not_be_exceeded(utc_now, utc_now)
        assert result is True

    def test_past_retention_raises(self, utc_now):
        """Test data past retention period raises RetentionExceededError."""
        retention_end = utc_now - timedelta(days=30)

        with pytest.raises(RetentionExceededError) as exc_info:
            retention_must_not_be_exceeded(retention_end, utc_now)

        exc = exc_info.value
        assert exc.retention_end == retention_end
        assert exc.current_time == utc_now
        assert "GDPR Article 5(1)(e)" in exc.regulation

    def test_one_second_past_raises(self, utc_now):
        """Test one second past retention raises."""
        retention_end = utc_now - timedelta(seconds=1)

        with pytest.raises(RetentionExceededError) as exc_info:
            retention_must_not_be_exceeded(retention_end, utc_now)

        assert exc_info.value.context["exceeded_by_seconds"] == 1

    def test_far_past_retention(self, utc_now):
        """Test data far past retention period."""
        retention_end = utc_now - timedelta(days=365)  # 1 year past

        with pytest.raises(RetentionExceededError) as exc_info:
            retention_must_not_be_exceeded(retention_end, utc_now)

        # Should show large exceeded_by_seconds
        assert exc_info.value.context["exceeded_by_seconds"] >= 365 * 24 * 3600

    def test_naive_datetime_handled(self):
        """Test naive datetime is handled (assumed UTC)."""
        now = datetime.utcnow()  # Naive
        retention_end = now + timedelta(days=30)  # Naive

        result = retention_must_not_be_exceeded(retention_end, now)
        assert result is True

    def test_mixed_timezone_aware_naive(self):
        """Test mixed timezone-aware and naive datetimes."""
        now = datetime.now(UTC)
        retention_end = datetime.utcnow() + timedelta(days=30)  # Naive

        result = retention_must_not_be_exceeded(retention_end, now)
        assert result is True

    def test_error_contains_timestamps(self):
        """Test error contains both timestamps for audit."""
        now = datetime(2024, 6, 15, tzinfo=UTC)
        retention_end = datetime(2024, 6, 1, tzinfo=UTC)

        with pytest.raises(RetentionExceededError) as exc_info:
            retention_must_not_be_exceeded(retention_end, now)

        context = exc_info.value.context
        assert "retention_end" in context
        assert "current_time" in context
        assert "exceeded_by_seconds" in context


# =============================================================================
# Truth Machine Composition Tests
# =============================================================================


class TestDataProtectionComposition:
    """Tests for composing multiple data protection constraints."""

    def test_all_data_protection_checks_pass(self, utc_now):
        """Test all data protection constraints pass in sequence."""
        retention_end = utc_now + timedelta(days=365)
        allowed_ops = {"read", "write", "process"}

        # If all execute without raising, all invariants hold
        result1 = pii_must_not_be_public(visibility="internal", contains_pii=True)
        result2 = transmission_must_be_encrypted(is_encrypted=True, data_classification="pii")
        result3 = data_classification_must_allow("internal", "read", allowed_ops)
        result4 = retention_must_not_be_exceeded(retention_end, utc_now)

        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert result4 is True

    def test_fails_at_first_violation(self, utc_now):
        """Test composition fails at first violation."""
        with pytest.raises(PIIExposureError):
            pii_must_not_be_public(visibility="public", contains_pii=True)
            # Remaining constraints never execute
            transmission_must_be_encrypted(is_encrypted=True, data_classification="pii")

    def test_realistic_data_access_flow(self, utc_now):
        """Test realistic data access validation flow."""
        # Scenario: Processing HR records with PII

        # 1. Check data retention is valid
        retention_end = utc_now + timedelta(days=2555)  # 7 years for HR records
        retention_must_not_be_exceeded(retention_end, utc_now)

        # 2. Check visibility is appropriate for PII
        pii_must_not_be_public(visibility="confidential", contains_pii=True)

        # 3. Check transmission is encrypted
        transmission_must_be_encrypted(is_encrypted=True, data_classification="pii")

        # 4. Check operation is allowed for classification
        hr_allowed_ops = {"read", "process", "audit_view"}
        data_classification_must_allow("confidential", "process", hr_allowed_ops)

        # All checks passed - data access is compliant

    def test_data_export_blocked_scenario(self, utc_now):
        """Test data export is blocked for restricted classification."""
        # Scenario: Attempting to export restricted data

        # Data is within retention
        retention_end = utc_now + timedelta(days=365)
        retention_must_not_be_exceeded(retention_end, utc_now)

        # Data is not publicly visible
        pii_must_not_be_public(visibility="restricted", contains_pii=True)

        # Transmission is encrypted
        transmission_must_be_encrypted(is_encrypted=True, data_classification="restricted")

        # BUT export is not allowed for restricted data
        restricted_ops = {"read", "audit_view"}  # No export
        with pytest.raises(ClassificationViolationError):
            data_classification_must_allow("restricted", "export", restricted_ops)

    def test_expired_data_access_blocked(self, utc_now):
        """Test access to expired data is blocked."""
        # Data has exceeded retention period
        retention_end = utc_now - timedelta(days=30)

        # First check should fail - no need to check other constraints
        with pytest.raises(RetentionExceededError):
            retention_must_not_be_exceeded(retention_end, utc_now)

    def test_unencrypted_sensitive_transfer_blocked(self):
        """Test unencrypted sensitive data transfer is blocked."""
        # Attempting to send PII over unencrypted channel
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="pii")

        # Same for confidential
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="confidential")

        # Same for restricted
        with pytest.raises(UnencryptedTransmissionError):
            transmission_must_be_encrypted(is_encrypted=False, data_classification="restricted")
