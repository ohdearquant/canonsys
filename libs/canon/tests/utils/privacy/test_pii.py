"""Tests for PII detection."""

import pytest

from canon.utils.pii import (
    PIIMatch,
    PIIPattern,
    PIIScanResult,
    has_blocking_pii,
    scan_for_pii,
)


class TestPIIPattern:
    """Tests for PIIPattern enum."""

    def test_blocking_patterns(self):
        """Blocking patterns are SSN, credit card, passport."""
        blocking = PIIPattern.blocking()

        assert PIIPattern.SSN in blocking
        assert PIIPattern.CREDIT_CARD in blocking
        assert PIIPattern.PASSPORT in blocking
        assert len(blocking) == 3

    def test_non_blocking_patterns(self):
        """Email, phone, IP are not blocking."""
        assert PIIPattern.EMAIL.is_blocking is False
        assert PIIPattern.PHONE.is_blocking is False
        assert PIIPattern.IP_ADDRESS.is_blocking is False

    def test_all_patterns(self):
        """All patterns returns all enum members."""
        all_p = PIIPattern.all_patterns()

        assert len(all_p) == 6
        assert PIIPattern.SSN in all_p
        assert PIIPattern.EMAIL in all_p

    def test_regex_property(self):
        """Each pattern has a compiled regex."""
        for pattern in PIIPattern:
            assert pattern.regex is not None
            assert hasattr(pattern.regex, "search")


class TestPIIMatch:
    """Tests for PIIMatch dataclass."""

    def test_frozen(self):
        """PIIMatch is immutable."""
        match = PIIMatch(pattern=PIIPattern.SSN, start=0, end=11)

        with pytest.raises(Exception):
            match.start = 5

    def test_attributes(self):
        """PIIMatch stores pattern and positions."""
        match = PIIMatch(pattern=PIIPattern.EMAIL, start=10, end=30)

        assert match.pattern == PIIPattern.EMAIL
        assert match.start == 10
        assert match.end == 30


class TestPIIScanResult:
    """Tests for PIIScanResult dataclass."""

    def test_empty_result(self):
        """Empty result is safe to persist."""
        result = PIIScanResult()

        assert result.safe_to_persist is True
        assert result.blocking_count == 0
        assert result.block_reason() is None

    def test_with_blocking_match(self):
        """Result with blocking match is not safe."""
        result = PIIScanResult(
            matches=[PIIMatch(pattern=PIIPattern.SSN, start=0, end=11)],
            text_length=100,
        )

        assert result.safe_to_persist is False
        assert result.blocking_count == 1
        assert "ssn" in result.block_reason()

    def test_with_non_blocking_match(self):
        """Result with only non-blocking matches is safe."""
        result = PIIScanResult(
            matches=[PIIMatch(pattern=PIIPattern.EMAIL, start=0, end=20)],
            text_length=100,
        )

        assert result.safe_to_persist is True
        assert result.blocking_count == 0

    def test_blocking_types(self):
        """blocking_types returns only blocking patterns."""
        result = PIIScanResult(
            matches=[
                PIIMatch(pattern=PIIPattern.SSN, start=0, end=11),
                PIIMatch(pattern=PIIPattern.EMAIL, start=20, end=40),
                PIIMatch(pattern=PIIPattern.CREDIT_CARD, start=50, end=70),
            ],
        )

        blocking = result.blocking_types
        assert PIIPattern.SSN in blocking
        assert PIIPattern.CREDIT_CARD in blocking
        assert PIIPattern.EMAIL not in blocking


class TestScanForPII:
    """Tests for scan_for_pii function."""

    def test_empty_text(self):
        """Empty text returns empty result."""
        result = scan_for_pii("")

        assert result.text_length == 0
        assert len(result.matches) == 0

    def test_detects_ssn(self):
        """Detects SSN pattern."""
        text = "My SSN is 123-45-6789"
        result = scan_for_pii(text)

        assert len(result.matches) == 1
        assert result.matches[0].pattern == PIIPattern.SSN
        assert result.safe_to_persist is False

    def test_detects_credit_card(self):
        """Detects credit card pattern."""
        text = "Card: 4111-1111-1111-1111"
        result = scan_for_pii(text)

        assert len(result.matches) == 1
        assert result.matches[0].pattern == PIIPattern.CREDIT_CARD

    def test_detects_passport(self):
        """Detects passport pattern."""
        text = "Passport: AB1234567"
        result = scan_for_pii(text)

        assert len(result.matches) == 1
        assert result.matches[0].pattern == PIIPattern.PASSPORT

    def test_blocking_only_default(self):
        """Default only scans blocking patterns."""
        text = "Email: test@example.com SSN: 123-45-6789"
        result = scan_for_pii(text)

        # Only SSN detected (blocking_only=True by default)
        assert len(result.matches) == 1
        assert result.matches[0].pattern == PIIPattern.SSN

    def test_all_patterns(self):
        """Can scan all patterns."""
        text = "Email: test@example.com SSN: 123-45-6789"
        result = scan_for_pii(text, blocking_only=False)

        assert len(result.matches) == 2
        patterns = {m.pattern for m in result.matches}
        assert PIIPattern.SSN in patterns
        assert PIIPattern.EMAIL in patterns

    def test_multiple_matches(self):
        """Detects multiple occurrences."""
        text = "SSN1: 111-22-3333 SSN2: 444-55-6666"
        result = scan_for_pii(text)

        assert len(result.matches) == 2
        assert result.blocking_count == 2

    def test_matches_sorted_by_position(self):
        """Matches are sorted by start position."""
        text = "End: 999-88-7777 Start: 111-22-3333"
        result = scan_for_pii(text)

        assert result.matches[0].start < result.matches[1].start

    def test_clean_text(self):
        """Clean text has no matches."""
        text = "This is clean text with no PII."
        result = scan_for_pii(text)

        assert len(result.matches) == 0
        assert result.safe_to_persist is True


class TestHasBlockingPII:
    """Tests for has_blocking_pii function."""

    def test_empty_text(self):
        """Empty text returns False."""
        assert has_blocking_pii("") is False

    def test_with_ssn(self):
        """Returns True for SSN."""
        assert has_blocking_pii("SSN: 123-45-6789") is True

    def test_with_credit_card(self):
        """Returns True for credit card."""
        assert has_blocking_pii("Card: 4111111111111111") is True

    def test_with_passport(self):
        """Returns True for passport."""
        assert has_blocking_pii("Passport: A123456789") is True

    def test_with_email_only(self):
        """Returns False for email (non-blocking)."""
        assert has_blocking_pii("Email: test@example.com") is False

    def test_clean_text(self):
        """Returns False for clean text."""
        assert has_blocking_pii("No PII here") is False
