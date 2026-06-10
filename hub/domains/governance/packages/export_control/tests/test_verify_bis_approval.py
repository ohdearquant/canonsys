"""Tests for verify_bis_approval feature."""

from __future__ import annotations

import pytest
from canon_vocab_export_control.phrases import verify_bis_approval
from canon_vocab_export_control.types import BISLicenseType


class TestVerifyBISApproval:
    """Tests for verify_bis_approval function."""

    @pytest.mark.asyncio
    async def test_approval_check_returns_result(self, mock_ctx):
        """Should return dict with approval details."""
        result = await verify_bis_approval(
            {"eccn": "5A002", "destination_country": "DE"},
            mock_ctx,
        )

        assert isinstance(result, dict)
        assert result["eccn"] == "5A002"
        assert result["destination_country"] == "DE"

    @pytest.mark.asyncio
    async def test_country_code_normalized_to_uppercase(self, mock_ctx):
        """Should normalize country code to uppercase."""
        result = await verify_bis_approval(
            {"eccn": "5A002", "destination_country": "de"},
            mock_ctx,
        )

        assert result["destination_country"] == "DE"

    @pytest.mark.asyncio
    async def test_placeholder_returns_no_license_required(self, mock_ctx):
        """Placeholder implementation returns NO_LICENSE_REQUIRED."""
        result = await verify_bis_approval(
            {"eccn": "5A002", "destination_country": "DE"},
            mock_ctx,
        )

        assert result["approved"] is True
        assert result["license_type"] == BISLicenseType.NO_LICENSE_REQUIRED
        assert result["license_number"] is None
        assert result["exception_code"] is None

    @pytest.mark.asyncio
    async def test_with_end_use_and_end_user(self, mock_ctx):
        """Should accept optional end_use and end_user."""
        result = await verify_bis_approval(
            {
                "eccn": "5A002",
                "destination_country": "DE",
                "end_use": "Research and development",
                "end_user": "University of Munich",
            },
            mock_ctx,
        )

        assert result["approved"] is True
        assert result["end_user_verified"] is True

    @pytest.mark.asyncio
    async def test_without_end_user(self, mock_ctx):
        """Should return end_user_verified=False when no end_user provided."""
        result = await verify_bis_approval(
            {"eccn": "5A002", "destination_country": "DE"},
            mock_ctx,
        )

        assert result["end_user_verified"] is False

    @pytest.mark.asyncio
    async def test_license_types_enum(self):
        """Should have correct BISLicenseType values."""
        assert BISLicenseType.LICENSE == "LICENSE"
        assert BISLicenseType.LICENSE_EXCEPTION == "LICENSE_EXCEPTION"
        assert BISLicenseType.NO_LICENSE_REQUIRED == "NO_LICENSE_REQUIRED"
