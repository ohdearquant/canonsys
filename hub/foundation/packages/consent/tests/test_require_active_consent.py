"""Tests for require_active_consent phrase.

Tests cover:
- Active consent returns result dict
- Revoked (withdrawn) consent raises ConsentWithdrawnError
- No consent record raises ConsentWithdrawnError with reason context

Regulatory Context:
    - GDPR Art. 7(3): "Data subject has right to withdraw consent at any time"
    - FCRA 15 U.S.C. Section 1681b(b)(2): "Consent required before procuring consumer report"
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_consent.exceptions import ConsentWithdrawnError
from canon_vocab_consent.phrases.require_active_consent import require_active_consent

# Access auto-generated result type via phrase function attribute
ActiveConsentResult = require_active_consent.result_type


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext with subject_id and conn."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.subject_id = uuid4()  # Required for @phrase pattern
    ctx.conn = None  # Connection from context
    return ctx


@pytest.fixture
def subject_id(mock_ctx):
    """Return the subject ID from the context."""
    return mock_ctx.subject_id


@pytest.fixture
def consent_id():
    """Generate a test consent token ID."""
    return uuid4()


# =============================================================================
# require_active_consent Tests
# =============================================================================


class TestRequireActiveConsent:
    """Tests for require_active_consent phrase."""

    @pytest.mark.asyncio
    async def test_active_consent_returns_result(self, mock_ctx, subject_id, consent_id):
        """Test that active consent returns result dict."""
        scope = "background_check"
        granted_at = datetime.now(UTC) - timedelta(days=30)

        # First call: check for revoked consent (returns None - no revoked found)
        # Second call: check for active consent (returns active record)
        active_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "active",
            "granted_at": granted_at,
        }

        async def select_one_side_effect(table, where, **kwargs):
            """Mock select_one to return None for revoked, row for active."""
            if where.get("status") == "revoked":
                return None  # No revoked consent found
            elif where.get("status") == "active":
                return active_row  # Active consent found
            return None

        with patch(
            "canon_vocab_consent.phrases.require_active_consent.select_one",
            new_callable=AsyncMock,
            side_effect=select_one_side_effect,
        ):
            result = await require_active_consent({"scope": scope}, mock_ctx)

        assert result["subject_id"] == subject_id
        assert result["scope"] == scope
        assert result["consent_id"] == consent_id
        assert result["granted_at"] == granted_at

    @pytest.mark.asyncio
    async def test_revoked_consent_raises_error(self, mock_ctx, subject_id):
        """Test that revoked consent raises ConsentWithdrawnError."""
        scope = "background_check"
        revoked_at = datetime.now(UTC) - timedelta(days=5)

        revoked_row = {
            "id": uuid4(),
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "revoked",
            "revoked_at": revoked_at,
        }

        with patch(
            "canon_vocab_consent.phrases.require_active_consent.select_one",
            new_callable=AsyncMock,
            return_value=revoked_row,  # First query finds revoked consent
        ):
            with pytest.raises(ConsentWithdrawnError) as exc_info:
                await require_active_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.subject_id == subject_id
        assert exc.scope == scope
        assert exc.withdrawn_at == revoked_at

    @pytest.mark.asyncio
    async def test_revoked_consent_without_timestamp_uses_current_time(self, mock_ctx, subject_id):
        """Test that revoked consent without revoked_at uses current time."""
        scope = "background_check"

        # Row with revoked status but no revoked_at timestamp
        revoked_row = {
            "id": uuid4(),
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "revoked",
            "revoked_at": None,
        }

        with (
            patch(
                "canon_vocab_consent.phrases.require_active_consent.select_one",
                new_callable=AsyncMock,
                return_value=revoked_row,
            ),
            pytest.raises(ConsentWithdrawnError) as exc_info,
        ):
            await require_active_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.withdrawn_at is not None
        # withdrawn_at should be approximately now
        assert (datetime.now(UTC) - exc.withdrawn_at).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_no_consent_record_raises_error(self, mock_ctx, subject_id):
        """Test that no consent record raises ConsentWithdrawnError with reason."""
        scope = "background_check"

        # Both queries return None (no revoked, no active)
        with (
            patch(
                "canon_vocab_consent.phrases.require_active_consent.select_one",
                new_callable=AsyncMock,
                return_value=None,
            ),
            pytest.raises(ConsentWithdrawnError) as exc_info,
        ):
            await require_active_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.subject_id == subject_id
        assert exc.scope == scope
        # Should have context explaining the reason
        assert "reason" in exc.context
        assert "No consent record" in exc.context["reason"]

    @pytest.mark.asyncio
    async def test_different_scopes(self, mock_ctx, subject_id, consent_id):
        """Test require_active_consent with different consent scopes."""
        scopes = ["background_check", "ai_scoring", "data_processing", "communications"]

        for scope in scopes:
            active_row = {
                "id": consent_id,
                "tenant_id": mock_ctx.tenant_id,
                "subject_id": subject_id,
                "scope": scope,
                "status": "active",
                "granted_at": datetime.now(UTC),
            }

            async def select_one_side_effect(table, where, **kwargs):
                if where.get("status") == "revoked":
                    return None
                elif where.get("status") == "active":
                    return active_row
                return None

            with patch(
                "canon_vocab_consent.phrases.require_active_consent.select_one",
                new_callable=AsyncMock,
                side_effect=select_one_side_effect,
            ):
                result = await require_active_consent({"scope": scope}, mock_ctx)

            assert result["scope"] == scope

    @pytest.mark.asyncio
    async def test_uses_connection_from_context(self, mock_ctx, subject_id, consent_id):
        """Test that ctx.conn is used for database queries."""
        scope = "background_check"
        mock_conn = AsyncMock()
        mock_ctx.conn = mock_conn

        active_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "active",
            "granted_at": datetime.now(UTC),
        }

        call_args_list = []

        async def select_one_capture(table, where, **kwargs):
            call_args_list.append((table, where, kwargs))
            if where.get("status") == "revoked":
                return None
            return active_row

        with patch(
            "canon_vocab_consent.phrases.require_active_consent.select_one",
            new_callable=AsyncMock,
            side_effect=select_one_capture,
        ):
            await require_active_consent({"scope": scope}, mock_ctx)

        # Verify conn from ctx was passed to both select_one calls
        assert len(call_args_list) == 2
        for _, _, kwargs in call_args_list:
            assert kwargs.get("conn") is mock_conn


# =============================================================================
# ActiveConsentResult Tests
# =============================================================================


class TestActiveConsentResult:
    """Tests for ActiveConsentResult type (auto-generated by @phrase)."""

    def test_result_type_exists(self):
        """Test that result_type is accessible."""
        assert require_active_consent.result_type is not None
        assert require_active_consent.result_type is ActiveConsentResult

    def test_result_creation(self, consent_id):
        """Test creating an ActiveConsentResult."""
        subject_id = uuid4()
        granted_at = datetime.now(UTC)
        result = ActiveConsentResult(
            subject_id=subject_id,
            scope="background_check",
            consent_id=consent_id,
            granted_at=granted_at,
        )

        assert result.subject_id == subject_id
        assert result.scope == "background_check"
        assert result.consent_id == consent_id
        assert result.granted_at == granted_at

    def test_result_without_granted_at(self, consent_id):
        """Test creating result without granted_at (default None)."""
        subject_id = uuid4()
        result = ActiveConsentResult(
            subject_id=subject_id,
            scope="background_check",
            consent_id=consent_id,
        )

        assert result.granted_at is None

    def test_result_is_frozen(self, consent_id):
        """Test that ActiveConsentResult is immutable (frozen)."""
        subject_id = uuid4()
        result = ActiveConsentResult(
            subject_id=subject_id,
            scope="background_check",
            consent_id=consent_id,
        )

        with pytest.raises(AttributeError):
            result.scope = "other_scope"  # type: ignore[misc]


# =============================================================================
# Import Tests
# =============================================================================


class TestImports:
    """Tests for proper module exports."""

    def test_import_from_phrases_module(self):
        """Test importing from require_active_consent module."""
        from canon_vocab_consent.phrases.require_active_consent import (
            require_active_consent,
        )

        assert require_active_consent is not None
        # Result type is accessed via phrase function attribute, not direct import
        assert require_active_consent.result_type is not None

    def test_import_from_consent_package(self):
        """Test importing from consent package."""
        from canon_vocab_consent import require_active_consent

        assert require_active_consent is not None
        # Result type is accessed via phrase function attribute, not direct import
        assert require_active_consent.result_type is not None

    def test_phrase_has_options_and_result_types(self):
        """Test that phrase exposes options_type and result_type."""
        assert hasattr(require_active_consent, "options_type")
        assert hasattr(require_active_consent, "result_type")
        assert require_active_consent.options_type is not None
        assert require_active_consent.result_type is not None
