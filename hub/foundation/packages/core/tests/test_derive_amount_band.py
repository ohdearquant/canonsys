"""Tests for derive_amount_band feature."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from canon_vocab_core import AmountBandConfig, derive_amount_band


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    return ctx


class TestDeriveAmountBand:
    """Tests for derive_amount_band function."""

    @pytest.mark.asyncio
    async def test_standard_band_classification(self, mock_ctx):
        """Amount below ELEVATED threshold should be STANDARD."""
        result = await derive_amount_band({"amount": Decimal(5000)}, mock_ctx)

        assert isinstance(result, dict)
        assert result["band"] == "STANDARD"
        assert result["amount"] == Decimal(5000)
        assert result["threshold"] == Decimal(0)
        assert result["next_band_at"] == Decimal(10000)
        assert result["config_version"] is not None
        assert len(result["config_version"]) == 8  # sha256[:8]

    @pytest.mark.asyncio
    async def test_elevated_band_classification(self, mock_ctx):
        """Amount >= 10000 but < 50000 should be ELEVATED."""
        result = await derive_amount_band({"amount": Decimal(25000)}, mock_ctx)

        assert result["band"] == "ELEVATED"
        assert result["amount"] == Decimal(25000)
        assert result["threshold"] == Decimal(10000)
        assert result["next_band_at"] == Decimal(50000)

    @pytest.mark.asyncio
    async def test_high_band_classification(self, mock_ctx):
        """Amount >= 50000 but < 250000 should be HIGH."""
        result = await derive_amount_band({"amount": Decimal(75000)}, mock_ctx)

        assert result["band"] == "HIGH"
        assert result["amount"] == Decimal(75000)
        assert result["threshold"] == Decimal(50000)
        assert result["next_band_at"] == Decimal(250000)

    @pytest.mark.asyncio
    async def test_critical_band_classification(self, mock_ctx):
        """Amount >= 250000 should be CRITICAL."""
        result = await derive_amount_band({"amount": Decimal(500000)}, mock_ctx)

        assert result["band"] == "CRITICAL"
        assert result["amount"] == Decimal(500000)
        assert result["threshold"] == Decimal(250000)
        assert result["next_band_at"] is None  # Highest band

    @pytest.mark.asyncio
    async def test_exactly_at_threshold(self, mock_ctx):
        """Amount exactly at threshold should be in that band."""
        result = await derive_amount_band({"amount": Decimal(10000)}, mock_ctx)

        assert result["band"] == "ELEVATED"
        assert result["threshold"] == Decimal(10000)

    @pytest.mark.asyncio
    async def test_zero_amount(self, mock_ctx):
        """Zero amount should be STANDARD."""
        result = await derive_amount_band({"amount": Decimal(0)}, mock_ctx)

        assert result["band"] == "STANDARD"
        assert result["threshold"] == Decimal(0)
        assert result["next_band_at"] == Decimal(10000)

    @pytest.mark.asyncio
    async def test_negative_amount_raises(self, mock_ctx):
        """Negative amount should raise ValueError."""
        with pytest.raises(ValueError, match="Amount cannot be negative"):
            await derive_amount_band({"amount": Decimal(-100)}, mock_ctx)

    @pytest.mark.asyncio
    async def test_config_version_consistency(self, mock_ctx):
        """Same config should produce same config_version."""
        result1 = await derive_amount_band({"amount": Decimal(1000)}, mock_ctx)
        result2 = await derive_amount_band({"amount": Decimal(5000)}, mock_ctx)

        # Same default config, same version
        assert result1["config_version"] == result2["config_version"]

    @pytest.mark.asyncio
    async def test_large_amount(self, mock_ctx):
        """Very large amounts should classify to highest band."""
        result = await derive_amount_band({"amount": Decimal(999999999)}, mock_ctx)

        assert result["band"] == "CRITICAL"
        assert result["next_band_at"] is None

    @pytest.mark.asyncio
    async def test_fractional_amount(self, mock_ctx):
        """Fractional amounts should work correctly."""
        result = await derive_amount_band({"amount": Decimal("9999.99")}, mock_ctx)

        assert result["band"] == "STANDARD"
        assert result["amount"] == Decimal("9999.99")

    def test_default_config_factory(self):
        """AmountBandConfig.default() should return expected configuration."""
        config = AmountBandConfig.default()

        assert len(config.bands) == 4
        assert config.bands[0] == ("STANDARD", Decimal(0))
        assert config.bands[1] == ("ELEVATED", Decimal(10000))
        assert config.bands[2] == ("HIGH", Decimal(50000))
        assert config.bands[3] == ("CRITICAL", Decimal(250000))
