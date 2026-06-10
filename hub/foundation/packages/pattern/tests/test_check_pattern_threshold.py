"""Tests for check_pattern_threshold feature."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_pattern import check_pattern_threshold


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = None
    return ctx


@pytest.fixture
def mock_count_result():
    """Factory for count result dicts."""

    def _make(entity_id, count=0, action_type="TEST", days=365):
        now = datetime.now(UTC)
        return {
            "count": count,
            "entity_id": entity_id,
            "action_type": action_type,
            "lookback_days": days,
            "window_start": now,
            "window_end": now,
        }

    return _make


class TestCheckPatternThreshold:
    """Tests for check_pattern_threshold function."""

    @pytest.mark.asyncio
    async def test_threshold_not_exceeded_when_count_below(self, mock_ctx, mock_count_result):
        """Should return exceeded=False when count < threshold."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(entity_id, count=2),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "SALARY_EXCEPTION",
                "threshold": 3,
                "lookback_days": 365,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["exceeded"] is False
        assert result["count"] < result["threshold"]

    @pytest.mark.asyncio
    async def test_threshold_exceeded_when_count_equals(self, mock_ctx, mock_count_result):
        """Should return exceeded=True when count == threshold."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(entity_id, count=3),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "SALARY_EXCEPTION",
                "threshold": 3,
                "lookback_days": 365,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert result["exceeded"] is True
        assert result["count"] == result["threshold"]

    @pytest.mark.asyncio
    async def test_threshold_exceeded_when_count_above(self, mock_ctx, mock_count_result):
        """Should return exceeded=True when count > threshold."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(entity_id, count=5),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "SALARY_EXCEPTION",
                "threshold": 3,
                "lookback_days": 365,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert result["exceeded"] is True
        assert result["count"] > result["threshold"]

    @pytest.mark.asyncio
    async def test_result_contains_all_metadata(self, mock_ctx, mock_count_result):
        """Result should include all input parameters."""
        entity_id = uuid4()
        action_type = "PROMOTION_BYPASS"
        threshold = 5
        lookback_days = 180

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(
                entity_id, count=0, action_type=action_type, days=lookback_days
            ),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": action_type,
                "threshold": threshold,
                "lookback_days": lookback_days,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert result["entity_id"] == entity_id
        assert result["action_type"] == action_type
        assert result["threshold"] == threshold
        assert result["lookback_days"] == lookback_days

    @pytest.mark.asyncio
    async def test_various_threshold_values(self, mock_ctx, mock_count_result):
        """Should handle various threshold values."""
        entity_id = uuid4()
        thresholds = [1, 2, 3, 5, 10, 100]

        for threshold in thresholds:
            with patch(
                "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
                new_callable=AsyncMock,
                return_value=mock_count_result(entity_id, count=0),
            ):
                options = {
                    "entity_id": entity_id,
                    "action_type": "TEST_ACTION",
                    "threshold": threshold,
                    "lookback_days": 365,
                }
                result = await check_pattern_threshold(options, mock_ctx)
            assert result["threshold"] == threshold

    @pytest.mark.asyncio
    async def test_zero_threshold_always_exceeded_with_any_count(self, mock_ctx, mock_count_result):
        """Threshold of 0 should be exceeded even with count=0."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(entity_id, count=0),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "TEST_ACTION",
                "threshold": 0,
                "lookback_days": 365,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        # count=0 >= threshold=0, so exceeded=True
        assert result["exceeded"] is True

    @pytest.mark.asyncio
    async def test_progressive_discipline_scenario(self, mock_ctx, mock_count_result):
        """Test progressive discipline use case: 2 warnings in 6 months."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(
                entity_id, count=2, action_type="FORMAL_WARNING", days=180
            ),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "FORMAL_WARNING",
                "threshold": 2,
                "lookback_days": 180,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert result["exceeded"] is True
        assert result["count"] == 2
        assert result["threshold"] == 2

    @pytest.mark.asyncio
    async def test_anti_gaming_scenario(self, mock_ctx, mock_count_result):
        """Test anti-gaming: 5 small exceptions = 1 material."""
        entity_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.check_pattern_threshold.derive_prior_action_count",
            new_callable=AsyncMock,
            return_value=mock_count_result(
                entity_id, count=5, action_type="SMALL_EXCEPTION", days=365
            ),
        ):
            options = {
                "entity_id": entity_id,
                "action_type": "SMALL_EXCEPTION",
                "threshold": 5,
                "lookback_days": 365,
            }
            result = await check_pattern_threshold(options, mock_ctx)

        assert result["exceeded"] is True
        assert result["count"] == 5
