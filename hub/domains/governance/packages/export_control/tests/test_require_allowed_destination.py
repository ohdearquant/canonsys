"""Tests for require_allowed_destination feature."""

from __future__ import annotations

import pytest
from canon_vocab_export_control.exceptions import ProhibitedDestinationError
from canon_vocab_export_control.phrases import require_allowed_destination
from canon_vocab_export_control.types import PROHIBITED_DESTINATIONS


class TestRequireAllowedDestination:
    """Tests for require_allowed_destination function."""

    @pytest.mark.asyncio
    async def test_allowed_destination_returns_result(self, mock_ctx):
        """Allowed destination should return dict with country_code."""
        result = await require_allowed_destination({"country_code": "DE"}, mock_ctx)

        assert isinstance(result, dict)
        assert result["country_code"] == "DE"

    @pytest.mark.asyncio
    async def test_cuba_is_prohibited(self, mock_ctx):
        """Cuba should raise ProhibitedDestinationError."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": "CU"}, mock_ctx)

        exc = exc_info.value
        assert exc.country_code == "CU"
        assert exc.country_name == "Cuba"
        assert "Cuba" in exc.prohibition_basis
        assert "31 CFR Part 515" in exc.prohibition_basis

    @pytest.mark.asyncio
    async def test_iran_is_prohibited(self, mock_ctx):
        """Iran should raise ProhibitedDestinationError."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": "IR"}, mock_ctx)

        exc = exc_info.value
        assert exc.country_code == "IR"
        assert exc.country_name == "Iran"
        assert "Iran" in exc.prohibition_basis
        assert "31 CFR Part 560" in exc.prohibition_basis

    @pytest.mark.asyncio
    async def test_north_korea_is_prohibited(self, mock_ctx):
        """North Korea should raise ProhibitedDestinationError."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": "KP"}, mock_ctx)

        exc = exc_info.value
        assert exc.country_code == "KP"
        assert exc.country_name == "North Korea"
        assert "DPRK" in exc.prohibition_basis
        assert "31 CFR Part 510" in exc.prohibition_basis

    @pytest.mark.asyncio
    async def test_syria_is_prohibited(self, mock_ctx):
        """Syria should raise ProhibitedDestinationError."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": "SY"}, mock_ctx)

        exc = exc_info.value
        assert exc.country_code == "SY"
        assert exc.country_name == "Syria"
        assert "Syria" in exc.prohibition_basis
        assert "31 CFR Part 542" in exc.prohibition_basis

    @pytest.mark.asyncio
    async def test_country_code_normalized_to_uppercase(self, mock_ctx):
        """Should normalize country code to uppercase."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": "ir"}, mock_ctx)

        assert exc_info.value.country_code == "IR"

    @pytest.mark.asyncio
    async def test_country_code_strips_whitespace(self, mock_ctx):
        """Should strip whitespace from country code."""
        with pytest.raises(ProhibitedDestinationError) as exc_info:
            await require_allowed_destination({"country_code": " IR "}, mock_ctx)

        assert exc_info.value.country_code == "IR"

    @pytest.mark.asyncio
    async def test_prohibited_destinations_constant(self):
        """PROHIBITED_DESTINATIONS should contain known sanctioned countries."""
        assert "CU" in PROHIBITED_DESTINATIONS
        assert "IR" in PROHIBITED_DESTINATIONS
        assert "KP" in PROHIBITED_DESTINATIONS
        assert "SY" in PROHIBITED_DESTINATIONS
        assert len(PROHIBITED_DESTINATIONS) == 4

    @pytest.mark.asyncio
    async def test_us_is_allowed(self, mock_ctx):
        """US should be an allowed destination."""
        result = await require_allowed_destination({"country_code": "US"}, mock_ctx)
        assert result["country_code"] == "US"

    @pytest.mark.asyncio
    async def test_russia_is_allowed_for_comprehensive_check(self, mock_ctx):
        """Russia has extensive but not comprehensive sanctions."""
        # Russia is not in PROHIBITED_DESTINATIONS (comprehensive only)
        result = await require_allowed_destination({"country_code": "RU"}, mock_ctx)
        assert result["country_code"] == "RU"
