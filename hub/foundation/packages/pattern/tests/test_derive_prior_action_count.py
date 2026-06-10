"""Tests for derive_prior_action_count feature."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_pattern import derive_prior_action_count


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = None
    return ctx


@pytest.fixture
def mock_fetchval():
    """Mock fetchval for DB isolation."""
    with patch(
        "canon_vocab_pattern.phrases.derive_prior_action_count.fetchval",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = 0  # Default: no prior actions
        yield mock


class TestDerivePriorActionCount:
    """Tests for derive_prior_action_count function."""

    @pytest.mark.asyncio
    async def test_returns_result_with_correct_metadata(self, mock_ctx, mock_fetchval):
        """Should return result with all metadata fields populated."""
        entity_id = uuid4()
        action_type = "SALARY_EXCEPTION"
        lookback_days = 365
        options = {
            "entity_id": entity_id,
            "action_type": action_type,
            "lookback_days": lookback_days,
        }

        result = await derive_prior_action_count(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["entity_id"] == entity_id
        assert result["action_type"] == action_type
        assert result["lookback_days"] == lookback_days
        assert result["window_start"] is not None
        assert result["window_end"] is not None

    @pytest.mark.asyncio
    async def test_window_start_is_before_window_end(self, mock_ctx, mock_fetchval):
        """Window start should be before window end."""
        entity_id = uuid4()
        lookback_days = 30
        options = {
            "entity_id": entity_id,
            "action_type": "TEST_ACTION",
            "lookback_days": lookback_days,
        }

        result = await derive_prior_action_count(options, mock_ctx)

        assert result["window_start"] < result["window_end"]

    @pytest.mark.asyncio
    async def test_window_duration_matches_lookback(self, mock_ctx, mock_fetchval):
        """Window duration should match lookback_days."""
        entity_id = uuid4()
        lookback_days = 90
        options = {
            "entity_id": entity_id,
            "action_type": "TEST_ACTION",
            "lookback_days": lookback_days,
        }

        result = await derive_prior_action_count(options, mock_ctx)

        expected_duration = timedelta(days=lookback_days)
        actual_duration = result["window_end"] - result["window_start"]
        # Allow small tolerance for execution time
        assert abs((actual_duration - expected_duration).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_returns_count_from_db(self, mock_ctx, mock_fetchval):
        """Should return count from DB query."""
        entity_id = uuid4()
        mock_fetchval.return_value = 5  # Simulate 5 prior actions
        options = {
            "entity_id": entity_id,
            "action_type": "SALARY_EXCEPTION",
            "lookback_days": 365,
        }

        result = await derive_prior_action_count(options, mock_ctx)

        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_handles_none_count_from_db(self, mock_ctx, mock_fetchval):
        """Should handle None return from DB (no matches)."""
        entity_id = uuid4()
        mock_fetchval.return_value = None  # DB returns None for no matches
        options = {
            "entity_id": entity_id,
            "action_type": "NONEXISTENT_ACTION",
            "lookback_days": 365,
        }

        result = await derive_prior_action_count(options, mock_ctx)

        assert result["count"] == 0  # None becomes 0

    @pytest.mark.asyncio
    async def test_different_action_types(self, mock_ctx, mock_fetchval):
        """Should handle various action types."""
        entity_id = uuid4()
        action_types = [
            "SALARY_EXCEPTION",
            "MFA_EXEMPTION",
            "PROMOTION_BYPASS",
            "OVERRIDE_APPROVAL",
        ]

        for action_type in action_types:
            options = {
                "entity_id": entity_id,
                "action_type": action_type,
                "lookback_days": 365,
            }
            result = await derive_prior_action_count(options, mock_ctx)
            assert result["action_type"] == action_type
            assert isinstance(result["count"], int)

    @pytest.mark.asyncio
    async def test_different_lookback_periods(self, mock_ctx, mock_fetchval):
        """Should handle various lookback periods."""
        entity_id = uuid4()
        lookback_values = [7, 30, 90, 180, 365, 730]

        for days in lookback_values:
            options = {
                "entity_id": entity_id,
                "action_type": "TEST_ACTION",
                "lookback_days": days,
            }
            result = await derive_prior_action_count(options, mock_ctx)
            assert result["lookback_days"] == days

    @pytest.mark.asyncio
    async def test_queries_correct_table_and_conditions(self, mock_ctx, mock_fetchval):
        """Should query evidences with correct conditions."""
        entity_id = uuid4()
        action_type = "pattern.salary_exception"
        options = {
            "entity_id": entity_id,
            "action_type": action_type,
            "lookback_days": 365,
        }

        await derive_prior_action_count(options, mock_ctx)

        # Verify fetchval was called
        mock_fetchval.assert_called_once()

        # Check SQL contains expected clauses
        call_args = mock_fetchval.call_args
        sql = call_args[0][0]
        assert "FROM evidences" in sql
        assert "tenant_id = $1" in sql
        assert "evidence_type = $2" in sql
        assert "subject_id = $3" in sql
        assert "data->>'actor_id'" in sql
        assert "collected_at >= $5" in sql
        assert "collected_at <= $6" in sql
        assert "is_deleted = false" in sql
