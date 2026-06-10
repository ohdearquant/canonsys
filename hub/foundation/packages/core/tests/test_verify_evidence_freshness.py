"""Tests for verify_evidence_freshness feature."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_core import verify_evidence_freshness


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    return ctx


class TestVerifyEvidenceFreshness:
    """Tests for verify_evidence_freshness function."""

    @pytest.mark.asyncio
    async def test_fresh_evidence_within_limit(self, mock_ctx):
        """Evidence collected recently should be fresh."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        collected_at = now - timedelta(hours=12)
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": collected_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert isinstance(result, dict)
        assert result["fresh"] is True
        assert result["found"] is True
        assert result["evidence_id"] == evidence_id
        assert result["max_age_seconds"] == int(max_age.total_seconds())
        assert result["reason"] is None

    @pytest.mark.asyncio
    async def test_stale_evidence_exceeds_limit(self, mock_ctx):
        """Evidence older than max_age should be stale."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        collected_at = now - timedelta(hours=48)
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": collected_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is False
        assert result["found"] is True
        assert result["evidence_id"] == evidence_id
        assert "stale" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_evidence_not_found(self, mock_ctx):
        """Missing evidence should return not found."""
        evidence_id = uuid4()
        max_age = timedelta(hours=24)

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is False
        assert result["found"] is False
        assert "not found" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_deleted_evidence(self, mock_ctx):
        """Deleted evidence should return not found."""
        evidence_id = uuid4()
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": datetime.now(UTC),
            "is_deleted": True,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is False
        assert result["found"] is False
        assert "deleted" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_evidence_exactly_at_limit(self, mock_ctx):
        """Evidence at exactly max_age should be considered fresh."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        # Use slightly less than max_age to avoid timing drift between
        # this now and the now inside the function
        collected_at = now - timedelta(hours=23, minutes=59, seconds=59)
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": collected_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        # Just under max_age, should still be fresh (<=)
        assert result["fresh"] is True

    @pytest.mark.asyncio
    async def test_days_based_max_age(self, mock_ctx):
        """Should work with days-based timedelta."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        collected_at = now - timedelta(days=15)
        max_age = timedelta(days=30)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": collected_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is True
        assert result["max_age_seconds"] == int(max_age.total_seconds())

    @pytest.mark.asyncio
    async def test_fallback_to_created_at(self, mock_ctx):
        """Should fallback to created_at if collected_at is None."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        created_at = now - timedelta(hours=12)
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": None,
            "created_at": created_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is True
        assert result["collected_at"] == created_at

    @pytest.mark.asyncio
    async def test_no_timestamp_available(self, mock_ctx):
        """Should handle missing timestamps gracefully."""
        evidence_id = uuid4()
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": None,
            "created_at": None,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["fresh"] is False
        assert result["found"] is True
        assert "no collection timestamp" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_result_has_expires_at(self, mock_ctx):
        """Result should include calculated expiration time."""
        evidence_id = uuid4()
        now = datetime.now(UTC)
        collected_at = now - timedelta(hours=12)
        max_age = timedelta(hours=24)

        mock_row = {
            "id": evidence_id,
            "tenant_id": mock_ctx.tenant_id,
            "collected_at": collected_at,
            "is_deleted": False,
        }

        with patch(
            "canon_vocab_core.phrases.verify_evidence_freshness.select_one",
            new_callable=AsyncMock,
            return_value=mock_row,
        ):
            result = await verify_evidence_freshness(
                {
                    "evidence_id": evidence_id,
                    "max_age_seconds": int(max_age.total_seconds()),
                },
                mock_ctx,
            )

        assert result["expires_at"] is not None
        expected_expires = collected_at + max_age
        assert result["expires_at"] == expected_expires
