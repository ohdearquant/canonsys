"""Tests for cumulative amount tracking.

Tests anti-gaming pattern detection functions:
- derive_cumulative_amount (base function)
- derive_cumulative_reallocation_amount
- derive_cumulative_exception_amount

These implement "5 small = 1 material" detection.
"""

from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_pattern import (
    derive_cumulative_amount,
    derive_cumulative_exception_amount,
    derive_cumulative_reallocation_amount,
)


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = None
    return ctx


@pytest.fixture
def mock_fetch():
    """Mock crud.fetch for DB isolation."""
    with patch(
        "canon_vocab_pattern.phrases.derive_cumulative_amount.crud.fetch",
        new_callable=AsyncMock,
    ) as mock:
        # Default: no records found
        mock.return_value = [{"total_amount": Decimal(0), "count": 0}]
        yield mock


# =============================================================================
# derive_cumulative_amount - Base Function
# =============================================================================


class TestDeriveCumulativeAmount:
    """Tests for derive_cumulative_amount function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_fetch):
        """Should return dict with correct structure."""
        entity_id = uuid4()
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["entity_id"] == entity_id
        assert result["metric"] == "exception"
        assert result["period_days"] == 90

    @pytest.mark.asyncio
    async def test_window_times_are_populated(self, mock_ctx, mock_fetch):
        """Should populate window_start and window_end."""
        entity_id = uuid4()
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["window_start"] is not None
        assert result["window_end"] is not None
        assert result["window_start"] < result["window_end"]

    @pytest.mark.asyncio
    async def test_window_duration_matches_period(self, mock_ctx, mock_fetch):
        """Window duration should match period_days."""
        entity_id = uuid4()
        period_days = 90
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": period_days,
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        expected_duration = timedelta(days=period_days)
        actual_duration = result["window_end"] - result["window_start"]
        # Allow small tolerance for execution time
        assert abs((actual_duration - expected_duration).total_seconds()) < 1

    @pytest.mark.asyncio
    async def test_zero_amount_no_records(self, mock_ctx, mock_fetch):
        """Should return zero total when no records found."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(0), "count": 0}]
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["total_amount"] == Decimal(0)
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_sums_amounts_from_multiple_records(self, mock_ctx, mock_fetch):
        """Should sum amounts from multiple evidence records."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal("15000.50"), "count": 5}]
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["total_amount"] == Decimal("15000.50")
        assert result["count"] == 5

    @pytest.mark.asyncio
    async def test_without_threshold(self, mock_ctx, mock_fetch):
        """Should work without threshold parameter."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(5000), "count": 3}]
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["threshold"] is None
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_with_threshold_not_exceeded(self, mock_ctx, mock_fetch):
        """Should report not exceeded when total < threshold."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(8000), "count": 4}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(10000),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["threshold"] == Decimal(10000)
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_with_threshold_exactly_at_threshold(self, mock_ctx, mock_fetch):
        """Should report exceeded when total == threshold (edge case)."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(10000), "count": 5}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(10000),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        # >= comparison, so exactly at threshold is exceeded
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_with_threshold_exceeded(self, mock_ctx, mock_fetch):
        """Should report exceeded when total > threshold."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(15000), "count": 7}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(10000),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_different_metric_types(self, mock_ctx, mock_fetch):
        """Should handle various metric types."""
        entity_id = uuid4()
        metrics = ["reallocation", "exception", "override", "transfer"]

        for metric in metrics:
            options = {"entity_id": entity_id, "metric": metric, "period_days": 90}
            result = await derive_cumulative_amount(options, mock_ctx)
            assert result["metric"] == metric

    @pytest.mark.asyncio
    async def test_different_period_days(self, mock_ctx, mock_fetch):
        """Should handle various period lengths."""
        entity_id = uuid4()
        periods = [7, 30, 90, 180, 365]

        for days in periods:
            options = {
                "entity_id": entity_id,
                "metric": "exception",
                "period_days": days,
            }
            result = await derive_cumulative_amount(options, mock_ctx)
            assert result["period_days"] == days

    @pytest.mark.asyncio
    async def test_fractional_amounts(self, mock_ctx, mock_fetch):
        """Should handle fractional currency amounts."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal("9999.99"), "count": 3}]
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["total_amount"] == Decimal("9999.99")

    @pytest.mark.asyncio
    async def test_large_amounts(self, mock_ctx, mock_fetch):
        """Should handle large currency amounts."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal("999999999.99"), "count": 100}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 365,
            "threshold": Decimal(1000000000),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["total_amount"] == Decimal("999999999.99")
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_empty_db_result(self, mock_ctx, mock_fetch):
        """Should handle empty result from DB gracefully."""
        entity_id = uuid4()
        mock_fetch.return_value = []  # No rows returned
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 90}

        result = await derive_cumulative_amount(options, mock_ctx)

        # Should default to zero values
        assert result["total_amount"] == Decimal(0)
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_queries_with_correct_sql_pattern(self, mock_ctx, mock_fetch):
        """Should query with correct SQL pattern."""
        entity_id = uuid4()
        options = {"entity_id": entity_id, "metric": "reallocation", "period_days": 90}

        await derive_cumulative_amount(options, mock_ctx)

        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args[0]
        sql = call_args[0]

        # Verify SQL structure
        assert "SUM" in sql
        assert "COUNT" in sql
        assert "evidence_type LIKE" in sql
        assert "data->>'entity_id'" in sql
        assert "collected_at >=" in sql
        assert "collected_at <=" in sql

    @pytest.mark.asyncio
    async def test_metric_pattern_matching(self, mock_ctx, mock_fetch):
        """Should use LIKE pattern for metric matching."""
        entity_id = uuid4()
        options = {"entity_id": entity_id, "metric": "reallocation", "period_days": 90}

        await derive_cumulative_amount(options, mock_ctx)

        call_args = mock_fetch.call_args[0]
        evidence_type_pattern = call_args[1]

        # Pattern should be "metric.%"
        assert evidence_type_pattern == "reallocation.%"


# =============================================================================
# this surface: Budget Reallocation Tracking
# =============================================================================


@pytest.fixture
def mock_cumulative_result():
    """Factory for derive_cumulative_amount mock results."""
    from datetime import datetime

    def _make(total_amount=Decimal(0), count=0, exceeds_threshold=False):
        now = datetime.now(UTC)
        return {
            "total_amount": total_amount,
            "count": count,
            "exceeds_threshold": exceeds_threshold,
            "window_start": now - timedelta(days=90),
            "window_end": now,
        }

    return _make


class TestDeriveCumulativeReallocationAmount:
    """Tests for derive_cumulative_reallocation_amount function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_cumulative_result):
        """Should return dict."""
        department_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"department_id": department_id, "period_days": 90}
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["department_id"] == department_id

    @pytest.mark.asyncio
    async def test_uses_provided_period(self, mock_ctx, mock_cumulative_result):
        """Should use provided period_days."""
        department_id = uuid4()
        period_days = 180

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"department_id": department_id, "period_days": period_days}
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        assert result["period_days"] == period_days

    @pytest.mark.asyncio
    async def test_without_threshold(self, mock_ctx, mock_cumulative_result):
        """Should work without threshold."""
        department_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"department_id": department_id, "period_days": 90}
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        assert result["threshold"] is None
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_with_threshold(self, mock_ctx, mock_cumulative_result):
        """Should accept and check threshold."""
        department_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(75000), count=12, exceeds_threshold=True
            ),
        ):
            options = {
                "department_id": department_id,
                "period_days": 90,
                "threshold": Decimal(50000),
            }
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        assert result["threshold"] == Decimal(50000)
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_budget_shuffling_scenario(self, mock_ctx, mock_cumulative_result):
        """Test this surface: Many small reallocations circumvent material threshold."""
        department_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(60000), count=15, exceeds_threshold=True
            ),
        ):
            options = {
                "department_id": department_id,
                "period_days": 90,
                "threshold": Decimal(50000),
            }
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        # Individual reallocations might be <$5K (under signing authority)
        # But cumulative exceeds $50K material threshold
        assert result["count"] == 15
        assert result["total_amount"] == Decimal(60000)
        assert result["exceeds_threshold"] is True
        # This triggers finance review for budget shuffling

    @pytest.mark.asyncio
    async def test_below_material_threshold(self, mock_ctx, mock_cumulative_result):
        """Should not flag when cumulative is below threshold."""
        department_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_reallocation_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(35000), count=8, exceeds_threshold=False
            ),
        ):
            options = {
                "department_id": department_id,
                "period_days": 90,
                "threshold": Decimal(50000),
            }
            result = await derive_cumulative_reallocation_amount(options, mock_ctx)

        assert result["exceeds_threshold"] is False


# =============================================================================
# this surface: Expense Exception Tracking
# =============================================================================


class TestDeriveCumulativeExceptionAmount:
    """Tests for derive_cumulative_exception_amount function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_correct_structure(self, mock_ctx, mock_cumulative_result):
        """Should return dict."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"manager_id": manager_id, "period_days": 365}
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["manager_id"] == manager_id

    @pytest.mark.asyncio
    async def test_uses_provided_period(self, mock_ctx, mock_cumulative_result):
        """Should use provided period_days."""
        manager_id = uuid4()
        period_days = 90

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"manager_id": manager_id, "period_days": period_days}
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        assert result["period_days"] == period_days

    @pytest.mark.asyncio
    async def test_without_threshold(self, mock_ctx, mock_cumulative_result):
        """Should work without threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(),
        ):
            options = {"manager_id": manager_id, "period_days": 365}
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        assert result["threshold"] is None
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_with_threshold(self, mock_ctx, mock_cumulative_result):
        """Should accept and check threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(12000), count=8, exceeds_threshold=True
            ),
        ):
            options = {
                "manager_id": manager_id,
                "period_days": 365,
                "threshold": Decimal(10000),
            }
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        assert result["threshold"] == Decimal(10000)
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_five_small_equals_one_material_scenario(self, mock_ctx, mock_cumulative_result):
        """Test this surface: 5 small exceptions = 1 material exception."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(10500), count=5, exceeds_threshold=True
            ),
        ):
            options = {
                "manager_id": manager_id,
                "period_days": 365,
                "threshold": Decimal(10000),
            }
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        # Individual exceptions might be under manager's signing authority
        # But 5 of them cumulatively exceed material threshold
        assert result["count"] == 5
        assert result["total_amount"] > Decimal(10000)
        assert result["exceeds_threshold"] is True
        # This would raise PatternDetected("exception_stacking", result)

    @pytest.mark.asyncio
    async def test_exception_stacking_with_count_check(self, mock_ctx, mock_cumulative_result):
        """Test combined threshold + count check for stacking pattern."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(12000), count=6, exceeds_threshold=True
            ),
        ):
            options = {
                "manager_id": manager_id,
                "period_days": 365,
                "threshold": Decimal(10000),
            }
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        # Both conditions for "5 small = 1 material" pattern
        assert result["exceeds_threshold"] is True
        assert result["count"] >= 5
        # Pattern confirmed: high count + high cumulative = stacking abuse

    @pytest.mark.asyncio
    async def test_high_amount_but_low_count(self, mock_ctx, mock_cumulative_result):
        """Test scenario: high amount but few exceptions (legitimate large exception)."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(15000), count=2, exceeds_threshold=True
            ),
        ):
            options = {
                "manager_id": manager_id,
                "period_days": 365,
                "threshold": Decimal(10000),
            }
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        # Threshold exceeded but only 2 exceptions
        # This is different from stacking - might be legitimate large exceptions
        assert result["exceeds_threshold"] is True
        assert result["count"] < 5
        # Different treatment than 5 small stacked exceptions

    @pytest.mark.asyncio
    async def test_low_amount_high_count(self, mock_ctx, mock_cumulative_result):
        """Test scenario: many small exceptions but below threshold."""
        manager_id = uuid4()

        with patch(
            "canon_vocab_pattern.phrases.derive_cumulative_exception_amount.derive_cumulative_amount",
            new_callable=AsyncMock,
            return_value=mock_cumulative_result(
                total_amount=Decimal(8000), count=10, exceeds_threshold=False
            ),
        ):
            options = {
                "manager_id": manager_id,
                "period_days": 365,
                "threshold": Decimal(10000),
            }
            result = await derive_cumulative_exception_amount(options, mock_ctx)

        # Many exceptions but total below threshold
        # Still might warrant attention for pattern, but not material threshold breach
        assert result["exceeds_threshold"] is False
        assert result["count"] > 5


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestCumulativeEdgeCases:
    """Edge cases for cumulative amount tracking."""

    @pytest.mark.asyncio
    async def test_zero_threshold(self, mock_ctx, mock_fetch):
        """Zero threshold should always be exceeded with any positive amount."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal("0.01"), "count": 1}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(0),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_zero_amount_with_zero_threshold(self, mock_ctx, mock_fetch):
        """Zero amount equals zero threshold - should be exceeded."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(0), "count": 0}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(0),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        # 0 >= 0 = True
        assert result["exceeds_threshold"] is True

    @pytest.mark.asyncio
    async def test_negative_values_in_db(self, mock_ctx, mock_fetch):
        """Should handle negative values from DB (credit/reversal scenarios)."""
        entity_id = uuid4()
        mock_fetch.return_value = [{"total_amount": Decimal(-500), "count": 3}]
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 90,
            "threshold": Decimal(10000),
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        # Negative total is below any positive threshold
        assert result["total_amount"] == Decimal(-500)
        assert result["exceeds_threshold"] is False

    @pytest.mark.asyncio
    async def test_very_small_period(self, mock_ctx, mock_fetch):
        """Should handle very small lookback periods."""
        entity_id = uuid4()
        options = {"entity_id": entity_id, "metric": "exception", "period_days": 1}

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["period_days"] == 1

    @pytest.mark.asyncio
    async def test_very_large_period(self, mock_ctx, mock_fetch):
        """Should handle very large lookback periods."""
        entity_id = uuid4()
        options = {
            "entity_id": entity_id,
            "metric": "exception",
            "period_days": 3650,  # 10 years
        }

        result = await derive_cumulative_amount(options, mock_ctx)

        assert result["period_days"] == 3650
