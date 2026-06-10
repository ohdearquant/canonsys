"""Tests for pattern domain exceptions.

Tests exception classes used for pattern detection violations.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from canon_vocab_pattern import PatternThresholdExceededError


class TestPatternThresholdExceededError:
    """Tests for PatternThresholdExceededError exception."""

    def test_exception_stores_entity_id(self):
        """Should store entity_id attribute."""
        entity_id = uuid4()

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="SALARY_EXCEPTION",
            count=5,
            threshold=3,
            lookback_days=365,
        )

        assert exc.entity_id == entity_id

    def test_exception_stores_action_type(self):
        """Should store action_type attribute."""
        entity_id = uuid4()
        action_type = "POSTING_BYPASS"

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type=action_type,
            count=5,
            threshold=3,
            lookback_days=365,
        )

        assert exc.action_type == action_type

    def test_exception_stores_count(self):
        """Should store count attribute."""
        entity_id = uuid4()
        count = 7

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST_ACTION",
            count=count,
            threshold=3,
            lookback_days=365,
        )

        assert exc.count == count

    def test_exception_stores_threshold(self):
        """Should store threshold attribute."""
        entity_id = uuid4()
        threshold = 5

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST_ACTION",
            count=10,
            threshold=threshold,
            lookback_days=365,
        )

        assert exc.threshold == threshold

    def test_exception_stores_lookback_days(self):
        """Should store lookback_days attribute."""
        entity_id = uuid4()
        lookback_days = 180

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST_ACTION",
            count=5,
            threshold=3,
            lookback_days=lookback_days,
        )

        assert exc.lookback_days == lookback_days

    def test_exception_message_format(self):
        """Should format message with all parameters."""
        entity_id = uuid4()

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="SALARY_EXCEPTION",
            count=5,
            threshold=3,
            lookback_days=365,
        )

        message = str(exc)
        assert "Pattern threshold exceeded" in message
        assert "SALARY_EXCEPTION" in message
        assert "5" in message
        assert "365" in message
        assert "3" in message

    def test_exception_is_authorization_violation(self):
        """Should be an AuthorizationViolation subclass."""
        from canon.enforcement.exceptions import AuthorizationViolation

        entity_id = uuid4()

        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST_ACTION",
            count=5,
            threshold=3,
            lookback_days=365,
        )

        assert isinstance(exc, AuthorizationViolation)

    def test_exception_can_be_raised_and_caught(self):
        """Should be raisable and catchable."""
        entity_id = uuid4()

        with pytest.raises(PatternThresholdExceededError) as exc_info:
            raise PatternThresholdExceededError(
                entity_id=entity_id,
                action_type="SALARY_EXCEPTION",
                count=5,
                threshold=3,
                lookback_days=365,
            )

        exc = exc_info.value
        assert exc.entity_id == entity_id
        assert exc.count == 5

    def test_exception_default_regulation(self):
        """Should have default regulation set."""
        assert PatternThresholdExceededError.default_regulation == "SOX Section 302"

    def test_exception_default_message(self):
        """Should have default message set."""
        assert PatternThresholdExceededError.default_message == "Pattern threshold exceeded"

    def test_exception_with_various_action_types(self):
        """Should handle various action types correctly."""
        entity_id = uuid4()
        action_types = [
            "SALARY_EXCEPTION",
            "POSTING_BYPASS",
            "MFA_EXEMPTION",
            "PRIVILEGE_ESCALATION",
            "APP_BYPASS:12345678-1234-5678-1234-567812345678",
        ]

        for action_type in action_types:
            exc = PatternThresholdExceededError(
                entity_id=entity_id,
                action_type=action_type,
                count=5,
                threshold=3,
                lookback_days=365,
            )
            assert exc.action_type == action_type

    def test_exception_with_edge_case_values(self):
        """Should handle edge case values."""
        entity_id = uuid4()

        # Zero threshold (always exceeded)
        exc = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST",
            count=0,
            threshold=0,
            lookback_days=1,
        )
        assert exc.count == 0
        assert exc.threshold == 0
        assert exc.lookback_days == 1

        # Large values
        exc2 = PatternThresholdExceededError(
            entity_id=entity_id,
            action_type="TEST",
            count=99999,
            threshold=99998,
            lookback_days=3650,
        )
        assert exc2.count == 99999
        assert exc2.lookback_days == 3650
