"""Tests for consent constraint phrases.

Tests cover:
- consent_must_be_valid: Token status must be ACTIVE
- consent_must_not_be_expired: Token must not be past expiration
- consent_must_not_be_withdrawn: Token status must not be REVOKED
- consent_scope_must_cover: Token scope must match required scope

Truth Machine Semantics:
    Each phrase returns None on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from canon_vocab_consent.exceptions import (
    ConsentExpiredError,
    ConsentNotValidError,
    ConsentWithdrawnError,
)
from canon_vocab_consent.phrases.constraints import (
    consent_must_be_valid,
    consent_must_not_be_expired,
    consent_must_not_be_withdrawn,
    consent_scope_must_cover,
)
from canon_vocab_consent.types import ConsentScope, ConsentStatus

# =============================================================================
# Mock types that match the interface consent phrases expect
# =============================================================================
#
# The constraint functions use duck-typing, accessing:
#   - token.id (UUID)
#   - token.content.status (ConsentStatus enum)
#   - token.content.subject_id (UUID)
#   - token.content.scope (ConsentScope enum with .value)
#   - token.content.expires_at (datetime | None)
#   - token.content.revoked_at (datetime | None)
#   - token.content.revocation_reason (str | None)
# =============================================================================


@dataclass
class MockConsentTokenContent:
    """Mock ConsentTokenContent for testing.

    Matches the interface expected by consent constraint phrases.
    """

    subject_id: UUID
    scope: ConsentScope
    status: ConsentStatus = ConsentStatus.ACTIVE
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None


@dataclass
class MockConsentToken:
    """Mock ConsentToken entity for testing.

    The consent phrases access:
    - token.id (UUID)
    - token.content (MockConsentTokenContent)
    """

    id: UUID
    content: MockConsentTokenContent


# =============================================================================
# Fixtures using mock types
# =============================================================================


@pytest.fixture
def subject_id():
    """Fixed subject ID for tests."""
    return uuid4()


@pytest.fixture
def tenant_id():
    """Fixed tenant ID for tests."""
    return uuid4()


@pytest.fixture
def token_id():
    """Fixed token ID for tests."""
    return uuid4()


@pytest.fixture
def active_token(token_id, subject_id):
    """Create an active consent token."""
    content = MockConsentTokenContent(
        subject_id=subject_id,
        scope=ConsentScope.BACKGROUND_CHECK,
        status=ConsentStatus.ACTIVE,
    )
    return MockConsentToken(id=token_id, content=content)


@pytest.fixture
def revoked_token(token_id, subject_id):
    """Create a revoked consent token."""
    content = MockConsentTokenContent(
        subject_id=subject_id,
        scope=ConsentScope.BACKGROUND_CHECK,
        status=ConsentStatus.REVOKED,
        revoked_at=datetime.now(UTC) - timedelta(days=1),
        revocation_reason="User requested withdrawal",
    )
    return MockConsentToken(id=token_id, content=content)


@pytest.fixture
def expired_token(token_id, subject_id):
    """Create an expired consent token."""
    content = MockConsentTokenContent(
        subject_id=subject_id,
        scope=ConsentScope.BACKGROUND_CHECK,
        status=ConsentStatus.ACTIVE,
        expires_at=datetime.now(UTC) - timedelta(days=30),
    )
    return MockConsentToken(id=token_id, content=content)


@pytest.fixture
def non_expiring_token(token_id, subject_id):
    """Create a consent token without expiration."""
    content = MockConsentTokenContent(
        subject_id=subject_id,
        scope=ConsentScope.BACKGROUND_CHECK,
        status=ConsentStatus.ACTIVE,
        expires_at=None,
    )
    return MockConsentToken(id=token_id, content=content)


@pytest.fixture
def future_expiry_token(token_id, subject_id):
    """Create a consent token with future expiration."""
    content = MockConsentTokenContent(
        subject_id=subject_id,
        scope=ConsentScope.BACKGROUND_CHECK,
        status=ConsentStatus.ACTIVE,
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )
    return MockConsentToken(id=token_id, content=content)


# =============================================================================
# consent_must_be_valid Tests
# =============================================================================


class TestConsentMustBeValid:
    """Tests for consent_must_be_valid phrase."""

    def test_valid_active_token_succeeds(self, active_token):
        """Test active consent token passes validation - returns None (truth machine)."""
        result = consent_must_be_valid(active_token)
        assert result is None  # Successful execution = invariant holds

    def test_revoked_token_raises(self, revoked_token):
        """Test revoked consent token raises ConsentNotValidError."""
        with pytest.raises(ConsentNotValidError) as exc_info:
            consent_must_be_valid(revoked_token)

        assert exc_info.value.subject_id == revoked_token.content.subject_id
        assert "background_check" in exc_info.value.scope
        assert "FCRA Section 1681b(b)(2)" in exc_info.value.regulation

    def test_expired_status_token_raises(self, token_id, subject_id):
        """Test token with EXPIRED status raises ConsentNotValidError."""
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.EXPIRED,
        )
        token = MockConsentToken(id=token_id, content=content)

        with pytest.raises(ConsentNotValidError) as exc_info:
            consent_must_be_valid(token)

        assert "expired" in exc_info.value.context.get("current_status", "")

    def test_superseded_status_token_raises(self, token_id, subject_id):
        """Test token with SUPERSEDED status raises ConsentNotValidError."""
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.SUPERSEDED,
        )
        token = MockConsentToken(id=token_id, content=content)

        with pytest.raises(ConsentNotValidError):
            consent_must_be_valid(token)

    def test_exception_contains_context(self, revoked_token):
        """Test exception contains useful context for debugging."""
        with pytest.raises(ConsentNotValidError) as exc_info:
            consent_must_be_valid(revoked_token)

        context = exc_info.value.context
        assert "token_id" in context
        assert "current_status" in context
        assert "expected_status" in context
        assert context["expected_status"] == "ACTIVE"


# =============================================================================
# consent_must_not_be_expired Tests
# =============================================================================


class TestConsentMustNotBeExpired:
    """Tests for consent_must_not_be_expired phrase."""

    def test_non_expiring_token_succeeds(self, non_expiring_token):
        """Test token without expiration passes - perpetual consent."""
        result = consent_must_not_be_expired(non_expiring_token)
        assert result is None  # Successful execution

    def test_future_expiry_token_succeeds(self, future_expiry_token):
        """Test token with future expiration passes."""
        result = consent_must_not_be_expired(future_expiry_token)
        assert result is None

    def test_expired_token_raises(self, expired_token):
        """Test expired token raises ConsentExpiredError."""
        with pytest.raises(ConsentExpiredError) as exc_info:
            consent_must_not_be_expired(expired_token)

        assert exc_info.value.subject_id == expired_token.content.subject_id
        assert exc_info.value.expired_at == expired_token.content.expires_at

    def test_expiry_at_exact_time_raises(self, token_id, subject_id):
        """Test token expires exactly at check time raises ConsentExpiredError."""
        now = datetime.now(UTC)
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.ACTIVE,
            expires_at=now,
        )
        token = MockConsentToken(id=token_id, content=content)

        with pytest.raises(ConsentExpiredError):
            consent_must_not_be_expired(token, now=now)

    def test_custom_check_time_in_future(self, future_expiry_token):
        """Test with custom check time far in the future."""
        far_future = datetime.now(UTC) + timedelta(days=400)

        with pytest.raises(ConsentExpiredError):
            consent_must_not_be_expired(future_expiry_token, now=far_future)

    def test_custom_check_time_in_past(self, expired_token):
        """Test with custom check time before expiration passes."""
        expires_at = expired_token.content.expires_at
        past_time = expires_at - timedelta(days=60)

        result = consent_must_not_be_expired(expired_token, now=past_time)
        assert result is None

    def test_naive_datetime_handled(self, token_id, subject_id):
        """Test naive datetime is handled (assumed UTC)."""
        expires_at = datetime.now(UTC) - timedelta(hours=1)
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.ACTIVE,
            expires_at=expires_at,
        )
        token = MockConsentToken(id=token_id, content=content)

        # Pass naive datetime as check time
        naive_now = datetime.utcnow()  # Naive datetime

        with pytest.raises(ConsentExpiredError):
            consent_must_not_be_expired(token, now=naive_now)

    def test_exception_contains_check_time(self, expired_token):
        """Test exception context contains the check time."""
        check_time = datetime.now(UTC)

        with pytest.raises(ConsentExpiredError) as exc_info:
            consent_must_not_be_expired(expired_token, now=check_time)

        assert "check_time" in exc_info.value.context


# =============================================================================
# consent_must_not_be_withdrawn Tests
# =============================================================================


class TestConsentMustNotBeWithdrawn:
    """Tests for consent_must_not_be_withdrawn phrase."""

    def test_active_token_succeeds(self, active_token):
        """Test active consent token passes - not withdrawn."""
        result = consent_must_not_be_withdrawn(active_token)
        assert result is None

    def test_revoked_token_raises(self, revoked_token):
        """Test revoked token raises ConsentWithdrawnError."""
        with pytest.raises(ConsentWithdrawnError) as exc_info:
            consent_must_not_be_withdrawn(revoked_token)

        exc = exc_info.value
        assert exc.subject_id == revoked_token.content.subject_id
        assert exc.withdrawn_at == revoked_token.content.revoked_at
        assert "GDPR Article 7(3)" in exc.regulation

    def test_revoked_without_timestamp_uses_current_time(self, token_id, subject_id):
        """Test revoked token without revoked_at uses current time."""
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.REVOKED,
            revoked_at=None,
            revocation_reason="Unknown reason",
        )
        token = MockConsentToken(id=token_id, content=content)

        with pytest.raises(ConsentWithdrawnError) as exc_info:
            consent_must_not_be_withdrawn(token)

        assert exc_info.value.withdrawn_at is not None

    def test_exception_contains_revocation_reason(self, revoked_token):
        """Test exception context contains revocation reason."""
        with pytest.raises(ConsentWithdrawnError) as exc_info:
            consent_must_not_be_withdrawn(revoked_token)

        assert "revocation_reason" in exc_info.value.context

    def test_expired_status_not_withdrawn(self, token_id, subject_id):
        """Test EXPIRED status does not count as withdrawn."""
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.EXPIRED,
        )
        token = MockConsentToken(id=token_id, content=content)

        result = consent_must_not_be_withdrawn(token)
        assert result is None


# =============================================================================
# consent_scope_must_cover Tests
# =============================================================================


class TestConsentScopeMustCover:
    """Tests for consent_scope_must_cover phrase."""

    def test_matching_scope_succeeds(self, active_token):
        """Test token with matching scope passes."""
        required_scope = ConsentScope.BACKGROUND_CHECK
        result = consent_scope_must_cover(active_token, required_scope)
        assert result is None

    def test_mismatched_scope_raises(self, active_token):
        """Test token with mismatched scope raises ConsentNotValidError."""
        required_scope = ConsentScope.AI_SCORING

        with pytest.raises(ConsentNotValidError) as exc_info:
            consent_scope_must_cover(active_token, required_scope)

        exc = exc_info.value
        assert exc.scope == "ai_scoring"
        assert "FCRA Section 1681b(b)(2)" in exc.regulation

    def test_exception_contains_both_scopes(self, active_token):
        """Test exception context contains token scope and required scope."""
        required_scope = ConsentScope.DATA_PROCESSING

        with pytest.raises(ConsentNotValidError) as exc_info:
            consent_scope_must_cover(active_token, required_scope)

        context = exc_info.value.context
        assert "token_scope" in context
        assert "required_scope" in context
        assert context["token_scope"] == "background_check"
        assert context["required_scope"] == "data_processing"

    def test_all_standard_scopes(self, token_id, subject_id):
        """Test with all standard consent scopes."""
        scopes = [
            ConsentScope.BACKGROUND_CHECK,
            ConsentScope.DATA_PROCESSING,
            ConsentScope.AI_SCORING,
            ConsentScope.COMMUNICATIONS,
        ]

        for scope in scopes:
            content = MockConsentTokenContent(
                subject_id=subject_id,
                scope=scope,
                status=ConsentStatus.ACTIVE,
            )
            token = MockConsentToken(id=token_id, content=content)

            # Same scope should succeed
            result = consent_scope_must_cover(token, scope)
            assert result is None

            # Different scope should fail
            other_scope = (
                ConsentScope.THIRD_PARTY_SHARING
                if scope != ConsentScope.THIRD_PARTY_SHARING
                else ConsentScope.BACKGROUND_CHECK
            )
            with pytest.raises(ConsentNotValidError):
                consent_scope_must_cover(token, other_scope)


# =============================================================================
# Truth Machine Composition Tests
# =============================================================================


class TestTruthMachineComposition:
    """Tests for composing multiple consent phrases."""

    def test_all_phrases_pass_for_valid_token(self, active_token):
        """Test all consent phrases pass for a fully valid token."""
        # If all phrases execute without raising, invariants hold
        consent_must_be_valid(active_token)
        consent_must_not_be_expired(active_token)
        consent_must_not_be_withdrawn(active_token)
        consent_scope_must_cover(active_token, ConsentScope.BACKGROUND_CHECK)
        # Reaching here means all invariants are satisfied

    def test_composition_fails_at_first_violation(self, revoked_token):
        """Test composition stops at first violation."""
        # First phrase should fail for revoked token
        with pytest.raises(ConsentNotValidError):
            consent_must_be_valid(revoked_token)
            # Following phrases never execute
            consent_must_not_be_withdrawn(revoked_token)

    def test_expired_then_withdrawn_check(self, token_id, subject_id):
        """Test that expired tokens still check withdrawal status."""
        content = MockConsentTokenContent(
            subject_id=subject_id,
            scope=ConsentScope.BACKGROUND_CHECK,
            status=ConsentStatus.REVOKED,
            expires_at=datetime.now(UTC) - timedelta(days=30),
            revoked_at=datetime.now(UTC) - timedelta(days=10),
        )
        token = MockConsentToken(id=token_id, content=content)

        # Both should fail
        with pytest.raises(ConsentExpiredError):
            consent_must_not_be_expired(token)

        with pytest.raises(ConsentWithdrawnError):
            consent_must_not_be_withdrawn(token)
