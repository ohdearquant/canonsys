"""Tests for AI governance constraints.

Tests cover:
- human_review_must_be_present: Human oversight validation
- bias_assessment_must_be_documented: Bias audit validation
- same_tool_must_be_verified: Tool configuration consistency
- disclosure_must_be_provided: AI disclosure timing validation

Truth Machine Semantics:
    Each constraint returns Literal[True] on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from canon.enforcement.constraints import (
    bias_assessment_must_be_documented,
    disclosure_must_be_provided,
    human_review_must_be_present,
    same_tool_must_be_verified,
)
from canon.enforcement.exceptions import (
    BiasAssessmentMissingError,
    DisclosureMissingError,
    HumanReviewMissingError,
    ToolConfigMismatchError,
)

# =============================================================================
# human_review_must_be_present Tests
# =============================================================================


class TestHumanReviewMustBePresent:
    """Tests for human_review_must_be_present constraint."""

    def test_review_present_succeeds(self):
        """Test human review ID present returns True."""
        review_id = uuid4()
        result = human_review_must_be_present(review_id)
        assert result is True

    def test_string_review_id_succeeds(self):
        """Test string review ID is accepted."""
        review_id = str(uuid4())
        result = human_review_must_be_present(review_id)
        assert result is True

    def test_none_raises(self):
        """Test None review ID raises HumanReviewMissingError."""
        with pytest.raises(HumanReviewMissingError) as exc_info:
            human_review_must_be_present(None)

        exc = exc_info.value
        assert exc.risk_level == "high"
        assert "EU AI Act Article 14" in exc.regulation

    def test_error_contains_regulatory_context(self):
        """Test error contains regulatory context for audit."""
        with pytest.raises(HumanReviewMissingError) as exc_info:
            human_review_must_be_present(None)

        # Error should be useful for compliance auditors
        exc = exc_info.value
        assert "human review" in exc.message.lower()
        assert exc.context.get("risk_level") == "high"

    def test_non_empty_string_succeeds(self):
        """Test non-empty string (non-UUID) is accepted."""
        result = human_review_must_be_present("review-12345")
        assert result is True


# =============================================================================
# bias_assessment_must_be_documented Tests
# =============================================================================


class TestBiasAssessmentMustBeDocumented:
    """Tests for bias_assessment_must_be_documented constraint."""

    def test_assessment_documented_succeeds(self):
        """Test documented assessment ID returns True."""
        assessment_id = uuid4()
        result = bias_assessment_must_be_documented(assessment_id)
        assert result is True

    def test_string_assessment_id_succeeds(self):
        """Test string assessment ID is accepted."""
        assessment_id = str(uuid4())
        result = bias_assessment_must_be_documented(assessment_id)
        assert result is True

    def test_none_raises(self):
        """Test None assessment ID raises BiasAssessmentMissingError."""
        with pytest.raises(BiasAssessmentMissingError) as exc_info:
            bias_assessment_must_be_documented(None)

        exc = exc_info.value
        assert exc.assessment_type == "disparate_impact"
        assert "NYC LL144" in exc.regulation

    def test_error_contains_assessment_type(self):
        """Test error contains assessment type context."""
        with pytest.raises(BiasAssessmentMissingError) as exc_info:
            bias_assessment_must_be_documented(None)

        assert exc_info.value.context.get("assessment_type") == "disparate_impact"

    def test_multiple_tools_can_be_assessed(self):
        """Test multiple distinct tool assessments can pass."""
        tools = [uuid4() for _ in range(5)]

        for tool_assessment in tools:
            result = bias_assessment_must_be_documented(tool_assessment)
            assert result is True


# =============================================================================
# same_tool_must_be_verified Tests
# =============================================================================


class TestSameToolMustBeVerified:
    """Tests for same_tool_must_be_verified constraint."""

    def test_matching_hashes_succeeds(self):
        """Test matching configuration hashes returns True."""
        config_hash = "abc123def456789"
        result = same_tool_must_be_verified(config_hash, config_hash)
        assert result is True

    def test_mismatched_hashes_raises(self):
        """Test mismatched hashes raises ToolConfigMismatchError."""
        tool_hash = "abc123"
        expected_hash = "def456"

        with pytest.raises(ToolConfigMismatchError) as exc_info:
            same_tool_must_be_verified(tool_hash, expected_hash)

        exc = exc_info.value
        assert exc.expected_config_hash == expected_hash
        assert exc.actual_config_hash == tool_hash
        assert "NYC LL144" in exc.regulation

    def test_case_sensitive_comparison(self):
        """Test hash comparison is case-sensitive."""
        # Unlike evidence hashes, tool config hashes should be exact
        lower_hash = "abc123"
        upper_hash = "ABC123"

        with pytest.raises(ToolConfigMismatchError):
            same_tool_must_be_verified(lower_hash, upper_hash)

    def test_empty_hashes_match(self):
        """Test empty hashes are considered matching."""
        result = same_tool_must_be_verified("", "")
        assert result is True

    def test_long_hash_comparison(self):
        """Test long hash string comparison."""
        long_hash = "a" * 256
        result = same_tool_must_be_verified(long_hash, long_hash)
        assert result is True

    def test_error_message_contains_hash_preview(self):
        """Test error message shows hash previews for debugging."""
        with pytest.raises(ToolConfigMismatchError) as exc_info:
            same_tool_must_be_verified("abc123456789", "xyz987654321")

        # Message should contain truncated hash previews
        assert "abc12345" in exc_info.value.message or "abc123" in str(exc_info.value)

    def test_realistic_config_hash_scenario(self):
        """Test realistic configuration hash scenario."""
        # Simulate SHA256 config hashes
        audited_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        current_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        result = same_tool_must_be_verified(current_hash, audited_hash)
        assert result is True

        # Tool was updated - hash changed
        updated_hash = "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592"
        with pytest.raises(ToolConfigMismatchError):
            same_tool_must_be_verified(updated_hash, audited_hash)


# =============================================================================
# disclosure_must_be_provided Tests
# =============================================================================


class TestDisclosureMustBeProvided:
    """Tests for disclosure_must_be_provided constraint."""

    def test_disclosure_before_action_succeeds(self):
        """Test disclosure before action returns True."""
        disclosure = datetime(2024, 1, 1, tzinfo=UTC)
        action = datetime(2024, 1, 15, tzinfo=UTC)

        result = disclosure_must_be_provided(disclosure, action)
        assert result is True

    def test_no_disclosure_raises(self):
        """Test missing disclosure raises DisclosureMissingError."""
        action = datetime(2024, 1, 15, tzinfo=UTC)

        with pytest.raises(DisclosureMissingError) as exc_info:
            disclosure_must_be_provided(None, action)

        exc = exc_info.value
        assert exc.disclosure_status == "not_provided"
        assert "NYC LL144 Section 20-871(b)" in exc.regulation

    def test_disclosure_after_action_raises(self):
        """Test disclosure after action raises DisclosureMissingError."""
        disclosure = datetime(2024, 1, 20, tzinfo=UTC)
        action = datetime(2024, 1, 15, tzinfo=UTC)

        with pytest.raises(DisclosureMissingError) as exc_info:
            disclosure_must_be_provided(disclosure, action)

        assert exc_info.value.disclosure_status == "provided_after_action"

    def test_disclosure_at_exact_action_time_raises(self):
        """Test disclosure at exact action time raises (must strictly precede)."""
        same_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        with pytest.raises(DisclosureMissingError):
            disclosure_must_be_provided(same_time, same_time)

    def test_one_second_before_succeeds(self):
        """Test disclosure one second before action passes."""
        action = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        disclosure = action - timedelta(seconds=1)

        result = disclosure_must_be_provided(disclosure, action)
        assert result is True

    def test_naive_datetime_handled(self):
        """Test naive datetime is handled (assumed UTC)."""
        disclosure = datetime(2024, 1, 1, 12, 0, 0)  # Naive
        action = datetime(2024, 1, 15, 12, 0, 0)  # Naive

        result = disclosure_must_be_provided(disclosure, action)
        assert result is True

    def test_mixed_timezone_naive(self):
        """Test mixed timezone-aware and naive datetimes."""
        disclosure = datetime(2024, 1, 1, tzinfo=UTC)
        action = datetime(2024, 1, 15)  # Naive

        result = disclosure_must_be_provided(disclosure, action)
        assert result is True

    def test_ll144_ten_day_requirement_scenario(self):
        """Test NYC LL144 10 business day disclosure requirement."""
        # LL144 requires disclosure at least 10 business days before AEDT use
        action_date = datetime(2024, 1, 22, tzinfo=UTC)  # Monday

        # 10 business days before (excluding weekends) would be ~Jan 8
        # For simplicity, test with 14 calendar days
        disclosure_date = datetime(2024, 1, 8, tzinfo=UTC)

        result = disclosure_must_be_provided(disclosure_date, action_date)
        assert result is True

        # Disclosure only 5 days before - still passes (constraint only checks precedence)
        late_disclosure = datetime(2024, 1, 17, tzinfo=UTC)
        result = disclosure_must_be_provided(late_disclosure, action_date)
        assert result is True  # Constraint doesn't enforce 10-day minimum

    def test_error_action_type(self):
        """Test error contains action type context."""
        with pytest.raises(DisclosureMissingError) as exc_info:
            disclosure_must_be_provided(None, datetime.now(UTC))

        assert exc_info.value.action_type == "aedt_decision"


# =============================================================================
# Truth Machine Composition Tests
# =============================================================================


class TestAIGovernanceComposition:
    """Tests for composing multiple AI governance constraints."""

    def test_all_ai_governance_checks_pass(self):
        """Test all AI governance constraints pass in sequence."""
        review_id = uuid4()
        assessment_id = uuid4()
        config_hash = "sha256_config_hash_abc123"
        disclosure = datetime(2024, 1, 1, tzinfo=UTC)
        action = datetime(2024, 1, 15, tzinfo=UTC)

        # If all execute without raising, all invariants hold
        result1 = human_review_must_be_present(review_id)
        result2 = bias_assessment_must_be_documented(assessment_id)
        result3 = same_tool_must_be_verified(config_hash, config_hash)
        result4 = disclosure_must_be_provided(disclosure, action)

        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert result4 is True

    def test_fails_at_first_violation(self):
        """Test composition fails at first violation."""
        with pytest.raises(HumanReviewMissingError):
            human_review_must_be_present(None)
            # Remaining constraints never execute
            bias_assessment_must_be_documented(uuid4())

    def test_realistic_aedt_compliance_flow(self):
        """Test realistic AEDT compliance validation flow."""
        # NYC LL144 compliance for AEDT (Automated Employment Decision Tool)

        # 1. Verify disclosure was provided before using AEDT
        disclosure_date = datetime(2024, 1, 1, tzinfo=UTC)
        screening_date = datetime(2024, 1, 15, tzinfo=UTC)
        disclosure_must_be_provided(disclosure_date, screening_date)

        # 2. Verify bias audit exists for the tool
        bias_audit_id = uuid4()
        bias_assessment_must_be_documented(bias_audit_id)

        # 3. Verify tool hasn't changed since audit
        audited_config_hash = "config_hash_at_audit_time"
        current_config_hash = "config_hash_at_audit_time"
        same_tool_must_be_verified(current_config_hash, audited_config_hash)

        # 4. Verify human review for high-risk decisions
        human_review_id = uuid4()
        human_review_must_be_present(human_review_id)

        # All LL144 requirements verified - AEDT use is compliant

    def test_tool_drift_detection(self):
        """Test detecting tool configuration drift after audit."""
        audited_hash = "original_tool_config_hash_from_bias_audit"
        drifted_hash = "modified_tool_config_hash_after_update"

        # Audit was documented
        audit_id = uuid4()
        bias_assessment_must_be_documented(audit_id)

        # But tool has drifted - audit no longer valid
        with pytest.raises(ToolConfigMismatchError):
            same_tool_must_be_verified(drifted_hash, audited_hash)

    def test_partial_compliance_scenario(self):
        """Test scenario where some checks pass but others fail."""
        # Human review exists
        human_review_must_be_present(uuid4())

        # Bias audit exists
        bias_assessment_must_be_documented(uuid4())

        # Tool verified
        same_tool_must_be_verified("hash", "hash")

        # BUT disclosure was never provided
        with pytest.raises(DisclosureMissingError):
            disclosure_must_be_provided(None, datetime.now(UTC))

        # Even partial compliance failure means overall non-compliance
