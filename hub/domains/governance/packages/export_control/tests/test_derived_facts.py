"""Tests for export control derived facts.

Tests check_military_end_use_license_obtained and
check_enhanced_government_screening_complete functions.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_export_control.phrases import (
    check_enhanced_government_screening_complete,
    check_military_end_use_license_obtained,
)
from canon_vocab_export_control.phrases.check_enhanced_screening import (
    SCREENING_VALIDITY_DAYS,
)
from canon_vocab_export_control.types import ScreeningScope

from kron.utils import now_utc


class TestCheckMilitaryEndUseLicenseObtained:
    """Tests for check_military_end_use_license_obtained function."""

    # =========================================================================
    # No License Found
    # =========================================================================

    @pytest.mark.asyncio
    async def test_no_license_returns_not_obtained(self, mock_ctx):
        """Should return obtained=False when no license exists."""
        transaction_id = uuid4()

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = None

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "CN"},
                mock_ctx,
            )

        assert isinstance(result, dict)
        assert result["obtained"] is False
        assert result["license_id"] is None
        assert result["license_type"] is None
        assert result["issued_at"] is None
        assert result["expires_at"] is None
        assert result["end_user_verified"] is False
        assert result["destination_country"] == "CN"

    # =========================================================================
    # Valid License
    # =========================================================================

    @pytest.mark.asyncio
    async def test_valid_license_returns_obtained(self, mock_ctx):
        """Should return obtained=True when valid license exists."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()
        future = now + timedelta(days=365)

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "BIS_MU",
                "issued_at": now,
                "expires_at": future,
                "end_user_verified": True,
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "RU"},
                mock_ctx,
            )

        assert result["obtained"] is True
        assert result["license_id"] == license_id
        assert result["license_type"] == "BIS_MU"
        assert result["issued_at"] == now
        assert result["expires_at"] == future
        assert result["end_user_verified"] is True
        assert result["destination_country"] == "RU"

    @pytest.mark.asyncio
    async def test_license_without_expiration_is_valid(self, mock_ctx):
        """Perpetual license (no expiration) should be valid."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "SPECIFIC_LICENSE",
                "issued_at": now,
                "expires_at": None,  # Perpetual
                "end_user_verified": True,
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "VE"},
                mock_ctx,
            )

        assert result["obtained"] is True
        assert result["expires_at"] is None

    # =========================================================================
    # Expired License
    # =========================================================================

    @pytest.mark.asyncio
    async def test_expired_license_returns_not_obtained(self, mock_ctx):
        """Should return obtained=False when license is expired."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()
        past = now - timedelta(days=30)  # Expired 30 days ago

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "BIS_MU",
                "issued_at": now - timedelta(days=400),
                "expires_at": past,
                "end_user_verified": True,
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "CN"},
                mock_ctx,
            )

        assert result["obtained"] is False
        assert result["license_id"] == license_id  # Still shows ID for audit
        assert result["expires_at"] == past

    @pytest.mark.asyncio
    async def test_expired_today_returns_not_obtained(self, mock_ctx):
        """License expiring exactly now should be treated as expired."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()
        # Expired 1 second ago
        just_expired = now - timedelta(seconds=1)

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "BIS_MU",
                "issued_at": now - timedelta(days=365),
                "expires_at": just_expired,
                "end_user_verified": True,
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "MM"},
                mock_ctx,
            )

        assert result["obtained"] is False

    # =========================================================================
    # End User Verification
    # =========================================================================

    @pytest.mark.asyncio
    async def test_end_user_not_verified(self, mock_ctx):
        """Should report end_user_verified status accurately."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "BIS_MU",
                "issued_at": now,
                "expires_at": now + timedelta(days=365),
                "end_user_verified": False,
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "CN"},
                mock_ctx,
            )

        assert result["obtained"] is True
        assert result["end_user_verified"] is False

    @pytest.mark.asyncio
    async def test_end_user_verified_defaults_to_false(self, mock_ctx):
        """Missing end_user_verified should default to False."""
        transaction_id = uuid4()
        license_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "license_id": license_id,
                "license_type": "BIS_MU",
                "issued_at": now,
                "expires_at": now + timedelta(days=365),
                # end_user_verified not provided
            }

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "RU"},
                mock_ctx,
            )

        assert result["end_user_verified"] is False

    # =========================================================================
    # Destination Countries
    # =========================================================================

    @pytest.mark.asyncio
    async def test_destination_country_preserved(self, mock_ctx):
        """Destination country should be preserved in result."""
        transaction_id = uuid4()

        with patch(
            "canon_vocab_export_control.phrases.check_military_end_use_license.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = None

            result = await check_military_end_use_license_obtained(
                {"transaction_id": transaction_id, "destination_country": "VE"},
                mock_ctx,
            )

        assert result["destination_country"] == "VE"


class TestCheckEnhancedGovernmentScreeningComplete:
    """Tests for check_enhanced_government_screening_complete function."""

    # =========================================================================
    # No Screening Results
    # =========================================================================

    @pytest.mark.asyncio
    async def test_no_screening_returns_incomplete(self, mock_ctx):
        """Should return complete=False when no screening exists."""
        transaction_id = uuid4()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = None

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert isinstance(result, dict)
        assert result["complete"] is False
        assert result["screening_scope"] == ScreeningScope.DIRECT_PARTY
        assert result["ofac_cleared"] is False
        assert result["bis_entity_list_cleared"] is False
        assert result["bis_denied_persons_cleared"] is False
        assert result["bis_unverified_list_cleared"] is False
        assert result["ddtc_debarred_cleared"] is False
        assert result["screening_timestamp"] is None
        assert result["expires_at"] is None

    # =========================================================================
    # Complete Screening (All Cleared)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_all_cleared_returns_complete(self, mock_ctx):
        """Should return complete=True when all screenings cleared."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is True
        assert result["ofac_cleared"] is True
        assert result["bis_entity_list_cleared"] is True
        assert result["bis_denied_persons_cleared"] is True
        assert result["bis_unverified_list_cleared"] is True
        assert result["ddtc_debarred_cleared"] is True
        assert result["screening_timestamp"] == now
        assert result["expires_at"] == now + timedelta(days=SCREENING_VALIDITY_DAYS)

    # =========================================================================
    # Partial Screening (Some Not Cleared)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_ofac_not_cleared_returns_incomplete(self, mock_ctx):
        """Should return complete=False when OFAC not cleared."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": False,  # Not cleared
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["ofac_cleared"] is False

    @pytest.mark.asyncio
    async def test_bis_entity_list_not_cleared_returns_incomplete(self, mock_ctx):
        """Should return complete=False when BIS Entity List not cleared."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": True,
                "bis_entity_list_cleared": False,  # Not cleared
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["bis_entity_list_cleared"] is False

    @pytest.mark.asyncio
    async def test_ddtc_debarred_not_cleared_returns_incomplete(self, mock_ctx):
        """Should return complete=False when DDTC Debarred not cleared."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": False,  # Not cleared
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["ddtc_debarred_cleared"] is False

    # =========================================================================
    # Expired Screening
    # =========================================================================

    @pytest.mark.asyncio
    async def test_expired_screening_returns_incomplete(self, mock_ctx):
        """Should return complete=False when screening is expired (>30 days)."""
        transaction_id = uuid4()
        now = now_utc()
        # Screening was done 31 days ago (expired)
        expired_time = now - timedelta(days=SCREENING_VALIDITY_DAYS + 1)

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": expired_time,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["screening_timestamp"] == expired_time
        assert result["expires_at"] == expired_time + timedelta(days=SCREENING_VALIDITY_DAYS)

    @pytest.mark.asyncio
    async def test_screening_at_validity_boundary_is_valid(self, mock_ctx):
        """Screening exactly at validity boundary should be valid."""
        transaction_id = uuid4()
        now = now_utc()
        # Screening done exactly 29 days ago (still valid)
        boundary_time = now - timedelta(days=SCREENING_VALIDITY_DAYS - 1)

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": boundary_time,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is True

    # =========================================================================
    # Scope Coverage
    # =========================================================================

    @pytest.mark.asyncio
    async def test_full_chain_scope_required_direct_performed_incomplete(self, mock_ctx):
        """FULL_CHAIN required but DIRECT_PARTY performed should be incomplete."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",  # Only direct party screened
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.FULL_CHAIN,  # Requires full chain
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["screening_scope"] == ScreeningScope.DIRECT_PARTY

    @pytest.mark.asyncio
    async def test_full_chain_performed_covers_direct_party_required(self, mock_ctx):
        """FULL_CHAIN performed should satisfy DIRECT_PARTY requirement."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "FULL_CHAIN",  # Full chain screened
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,  # Only requires direct
                },
                mock_ctx,
            )

        assert result["complete"] is True
        assert result["screening_scope"] == ScreeningScope.FULL_CHAIN

    @pytest.mark.asyncio
    async def test_full_chain_required_and_performed_is_complete(self, mock_ctx):
        """FULL_CHAIN required and performed should be complete."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "FULL_CHAIN",
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.FULL_CHAIN,
                },
                mock_ctx,
            )

        assert result["complete"] is True

    # =========================================================================
    # Missing/Default Values
    # =========================================================================

    @pytest.mark.asyncio
    async def test_missing_cleared_fields_default_to_false(self, mock_ctx):
        """Missing cleared fields should default to False."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                "screening_scope": "DIRECT_PARTY",
                "screening_timestamp": now,
                # All cleared fields missing
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["complete"] is False
        assert result["ofac_cleared"] is False
        assert result["bis_entity_list_cleared"] is False
        assert result["bis_denied_persons_cleared"] is False
        assert result["bis_unverified_list_cleared"] is False
        assert result["ddtc_debarred_cleared"] is False

    @pytest.mark.asyncio
    async def test_missing_screening_scope_defaults_to_direct_party(self, mock_ctx):
        """Missing screening_scope should default to DIRECT_PARTY."""
        transaction_id = uuid4()
        now = now_utc()

        with patch(
            "canon_vocab_export_control.phrases.check_enhanced_screening.select_one",
            new_callable=AsyncMock,
        ) as mock_select:
            mock_select.return_value = {
                # screening_scope missing
                "ofac_cleared": True,
                "bis_entity_list_cleared": True,
                "bis_denied_persons_cleared": True,
                "bis_unverified_list_cleared": True,
                "ddtc_debarred_cleared": True,
                "screening_timestamp": now,
            }

            result = await check_enhanced_government_screening_complete(
                {
                    "transaction_id": transaction_id,
                    "screening_scope": ScreeningScope.DIRECT_PARTY,
                },
                mock_ctx,
            )

        assert result["screening_scope"] == ScreeningScope.DIRECT_PARTY


class TestScreeningValidityConstant:
    """Tests for SCREENING_VALIDITY_DAYS constant."""

    def test_screening_validity_is_30_days(self):
        """OFAC recommends 30-day refresh."""
        assert SCREENING_VALIDITY_DAYS == 30

    def test_screening_validity_is_int(self):
        """Validity should be an integer."""
        assert isinstance(SCREENING_VALIDITY_DAYS, int)
