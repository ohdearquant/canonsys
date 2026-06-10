"""Tests for verify_itar_authorization feature."""

from __future__ import annotations

import pytest
from canon_vocab_export_control.phrases import verify_itar_authorization
from canon_vocab_export_control.types import ITARAuthorizationType


class TestVerifyITARAuthorization:
    """Tests for verify_itar_authorization function."""

    @pytest.mark.asyncio
    async def test_authorization_check_returns_result(self, mock_ctx):
        """Should return dict with authorization details."""
        result = await verify_itar_authorization(
            {"usml_category": "IV", "destination_country": "GB"},
            mock_ctx,
        )

        assert isinstance(result, dict)
        assert result["usml_category"] == "IV"
        assert result["destination_country"] == "GB"

    @pytest.mark.asyncio
    async def test_usml_category_normalized_to_uppercase(self, mock_ctx):
        """Should normalize USML category to uppercase."""
        result = await verify_itar_authorization(
            {"usml_category": "iv", "destination_country": "GB"},
            mock_ctx,
        )

        assert result["usml_category"] == "IV"

    @pytest.mark.asyncio
    async def test_country_code_normalized_to_uppercase(self, mock_ctx):
        """Should normalize country code to uppercase."""
        result = await verify_itar_authorization(
            {"usml_category": "IV", "destination_country": "gb"},
            mock_ctx,
        )

        assert result["destination_country"] == "GB"

    @pytest.mark.asyncio
    async def test_placeholder_returns_authorized(self, mock_ctx):
        """Placeholder implementation returns authorized (NOT for production)."""
        result = await verify_itar_authorization(
            {"usml_category": "IV", "destination_country": "GB"},
            mock_ctx,
        )

        assert result["authorized"] is True
        assert result["authorization_type"] is None
        assert result["ddtc_reference"] is None
        assert result["expiry_date"] is None
        assert result["provisos"] == ()

    @pytest.mark.asyncio
    async def test_with_defense_service_flag(self, mock_ctx):
        """Should accept defense_service flag."""
        result = await verify_itar_authorization(
            {
                "usml_category": "IV",
                "destination_country": "GB",
                "defense_service": True,
            },
            mock_ctx,
        )

        assert result["authorized"] is True

    @pytest.mark.asyncio
    async def test_with_technical_data_flag(self, mock_ctx):
        """Should accept technical_data flag."""
        result = await verify_itar_authorization(
            {
                "usml_category": "IV",
                "destination_country": "GB",
                "technical_data": True,
            },
            mock_ctx,
        )

        assert result["authorized"] is True

    @pytest.mark.asyncio
    async def test_authorization_types_enum(self):
        """Should have correct ITARAuthorizationType values."""
        assert ITARAuthorizationType.DSP_5 == "DSP-5"
        assert ITARAuthorizationType.DSP_73 == "DSP-73"
        assert ITARAuthorizationType.DSP_85 == "DSP-85"
        assert ITARAuthorizationType.TAA == "TAA"
        assert ITARAuthorizationType.MLA == "MLA"
        assert ITARAuthorizationType.EXEMPTION == "EXEMPTION"
