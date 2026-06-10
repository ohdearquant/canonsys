"""Tests for require_valid_consent feature."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_consent.exceptions import ConsentExpiredError
from canon_vocab_consent.phrases import require_valid_consent


class TestRequireValidConsent:
    """Tests for require_valid_consent function."""

    @pytest.mark.asyncio
    async def test_valid_consent_returns_result(self, mock_ctx):
        """Active, non-expired consent should return result dict."""
        subject_id = uuid4()
        consent_id = uuid4()
        scope = "background_check"
        now = datetime.now(UTC)
        granted_at = now - timedelta(days=1)
        expires_at = now + timedelta(days=30)

        # Set subject_id on context (new pattern)
        mock_ctx.subject_id = subject_id

        mock_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "active",
            "granted_at": granted_at,
            "expires_at": expires_at,
        }

        with (
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.select_one",
                new_callable=AsyncMock,
                return_value=mock_row,
            ),
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.now_utc",
                return_value=now,
            ),
        ):
            result = await require_valid_consent({"scope": scope}, mock_ctx)

        assert isinstance(result, dict)
        assert result["subject_id"] == subject_id
        assert result["scope"] == scope
        assert result["consent_id"] == consent_id
        assert result["granted_at"] == granted_at
        assert result["expires_at"] == expires_at

    @pytest.mark.asyncio
    async def test_valid_consent_without_expiration(self, mock_ctx):
        """Active consent without expires_at should return result dict."""
        subject_id = uuid4()
        consent_id = uuid4()
        scope = "background_check"
        now = datetime.now(UTC)
        granted_at = now - timedelta(days=1)

        # Set subject_id on context (new pattern)
        mock_ctx.subject_id = subject_id

        mock_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "active",
            "granted_at": granted_at,
            "expires_at": None,
        }

        with (
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.select_one",
                new_callable=AsyncMock,
                return_value=mock_row,
            ),
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.now_utc",
                return_value=now,
            ),
        ):
            result = await require_valid_consent({"scope": scope}, mock_ctx)

        assert isinstance(result, dict)
        assert result["consent_id"] == consent_id
        assert result["expires_at"] is None

    @pytest.mark.asyncio
    async def test_expired_consent_raises_error(self, mock_ctx):
        """Consent with expires_at in past should raise ConsentExpiredError."""
        subject_id = uuid4()
        consent_id = uuid4()
        scope = "background_check"
        now = datetime.now(UTC)
        granted_at = now - timedelta(days=60)
        expires_at = now - timedelta(days=30)  # Expired 30 days ago

        # Set subject_id on context (new pattern)
        mock_ctx.subject_id = subject_id

        mock_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "active",
            "granted_at": granted_at,
            "expires_at": expires_at,
        }

        with (
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.select_one",
                new_callable=AsyncMock,
                return_value=mock_row,
            ),
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.now_utc",
                return_value=now,
            ),
            pytest.raises(ConsentExpiredError) as exc_info,
        ):
            await require_valid_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.subject_id == subject_id
        assert exc.scope == scope
        assert exc.expired_at == expires_at

    @pytest.mark.asyncio
    async def test_no_consent_record_raises_error(self, mock_ctx):
        """No consent record should raise ConsentExpiredError."""
        subject_id = uuid4()
        scope = "background_check"
        now = datetime.now(UTC)

        # Set subject_id on context (new pattern)
        mock_ctx.subject_id = subject_id

        # select_one returns None for both active and expired queries
        with (
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.select_one",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.now_utc",
                return_value=now,
            ),
            pytest.raises(ConsentExpiredError) as exc_info,
        ):
            await require_valid_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.subject_id == subject_id
        assert exc.scope == scope
        # Context should indicate no consent record found
        assert "No consent record found" in exc.context.get("reason", "")

    @pytest.mark.asyncio
    async def test_explicitly_expired_status_raises_error(self, mock_ctx):
        """Consent with status='expired' should raise ConsentExpiredError."""
        subject_id = uuid4()
        consent_id = uuid4()
        scope = "background_check"
        now = datetime.now(UTC)
        expires_at = now - timedelta(days=30)

        # Set subject_id on context (new pattern)
        mock_ctx.subject_id = subject_id

        expired_row = {
            "id": consent_id,
            "tenant_id": mock_ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": "expired",
            "expires_at": expires_at,
        }

        # First call for active returns None, second for expired returns row
        async def select_side_effect(table, where, **kwargs):
            if where.get("status") == "active":
                return None
            if where.get("status") == "expired":
                return expired_row
            return None

        with (
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.select_one",
                new_callable=AsyncMock,
                side_effect=select_side_effect,
            ),
            patch(
                "canon_vocab_consent.phrases.require_valid_consent.now_utc",
                return_value=now,
            ),
            pytest.raises(ConsentExpiredError) as exc_info,
        ):
            await require_valid_consent({"scope": scope}, mock_ctx)

        exc = exc_info.value
        assert exc.subject_id == subject_id
        assert exc.scope == scope
        assert exc.expired_at == expires_at
