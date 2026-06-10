"""Tests for verify_ofac_clearance feature."""

from __future__ import annotations

import pytest
from canon_vocab_export_control.phrases import verify_ofac_clearance
from canon_vocab_export_control.types import OFACEntityType


class TestVerifyOFACClearance:
    """Tests for verify_ofac_clearance function."""

    @pytest.mark.asyncio
    async def test_clearance_check_returns_result(self, mock_ctx):
        """Should return dict with clearance details."""
        result = await verify_ofac_clearance(
            {"entity_name": "ACME Corporation"},
            mock_ctx,
        )

        assert isinstance(result, dict)
        assert result["entity_name"] == "ACME Corporation"
        assert result["entity_type"] == OFACEntityType.INDIVIDUAL
        assert result["screening_timestamp"] is not None
        assert result["sanctions_list_version"] is not None

    @pytest.mark.asyncio
    async def test_clearance_with_entity_type_enum(self, mock_ctx):
        """Should accept OFACEntityType enum."""
        result = await verify_ofac_clearance(
            {
                "entity_name": "ACME Corporation",
                "entity_type": OFACEntityType.ENTITY,
            },
            mock_ctx,
        )

        assert result["entity_type"] == OFACEntityType.ENTITY

    @pytest.mark.asyncio
    async def test_clearance_with_entity_type_string(self, mock_ctx):
        """Should accept entity_type as string."""
        result = await verify_ofac_clearance(
            {
                "entity_name": "USS Enterprise",
                "entity_type": "VESSEL",
            },
            mock_ctx,
        )

        assert result["entity_type"] == OFACEntityType.VESSEL

    @pytest.mark.asyncio
    async def test_clearance_with_country_code(self, mock_ctx):
        """Should accept optional country_code."""
        result = await verify_ofac_clearance(
            {
                "entity_name": "John Doe",
                "country_code": "US",
            },
            mock_ctx,
        )

        assert result["cleared"] is True

    @pytest.mark.asyncio
    async def test_placeholder_returns_cleared(self, mock_ctx):
        """Placeholder implementation returns cleared (NOT for production)."""
        result = await verify_ofac_clearance(
            {"entity_name": "Any Name"},
            mock_ctx,
        )

        # Placeholder always returns cleared
        assert result["cleared"] is True
        assert result["match_score"] is None
        assert result["matched_program"] is None
        assert result["matched_sdn_id"] is None

    @pytest.mark.asyncio
    async def test_aircraft_entity_type(self, mock_ctx):
        """Should handle AIRCRAFT entity type."""
        result = await verify_ofac_clearance(
            {
                "entity_name": "N12345",
                "entity_type": OFACEntityType.AIRCRAFT,
            },
            mock_ctx,
        )

        assert result["entity_type"] == OFACEntityType.AIRCRAFT
