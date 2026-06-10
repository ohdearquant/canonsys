"""Tests for validate_destination_country feature.

Tests ISO-3166-1 country code validation, alias normalization,
and prohibited destination detection.
"""

from __future__ import annotations

import pytest
from canon_vocab_export_control.phrases import validate_destination_country
from canon_vocab_export_control.phrases.validate_destination_country import (
    COUNTRY_ALIASES,
    ISO_3166_1_ALPHA_2,
)
from canon_vocab_export_control.types import PROHIBITED_DESTINATIONS


class TestValidateDestinationCountry:
    """Tests for validate_destination_country function."""

    # =========================================================================
    # Valid Country Codes
    # =========================================================================

    @pytest.mark.asyncio
    async def test_valid_country_us(self, mock_ctx):
        """US should be valid ISO-3166-1 alpha-2 code."""
        result = await validate_destination_country({"country_code": "US"}, mock_ctx)

        assert isinstance(result, dict)
        assert result["valid"] is True
        assert result["normalized_code"] == "US"
        assert result["prohibited"] is False
        assert result["original_input"] == "US"

    @pytest.mark.asyncio
    async def test_valid_country_gb(self, mock_ctx):
        """GB should be valid ISO-3166-1 alpha-2 code."""
        result = await validate_destination_country({"country_code": "GB"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "GB"
        assert result["prohibited"] is False

    @pytest.mark.asyncio
    async def test_valid_country_de(self, mock_ctx):
        """DE should be valid ISO-3166-1 alpha-2 code."""
        result = await validate_destination_country({"country_code": "DE"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "DE"
        assert result["prohibited"] is False

    @pytest.mark.asyncio
    async def test_valid_country_jp(self, mock_ctx):
        """JP should be valid ISO-3166-1 alpha-2 code."""
        result = await validate_destination_country({"country_code": "JP"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "JP"
        assert result["prohibited"] is False

    @pytest.mark.asyncio
    async def test_valid_country_cn(self, mock_ctx):
        """CN should be valid but not prohibited (comprehensive)."""
        result = await validate_destination_country({"country_code": "CN"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "CN"
        assert result["prohibited"] is False  # China not comprehensively sanctioned

    # =========================================================================
    # Invalid Country Codes
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalid_country_code_xx(self, mock_ctx):
        """XX is not a valid ISO-3166-1 alpha-2 code."""
        result = await validate_destination_country({"country_code": "XX"}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None
        assert result["prohibited"] is False
        assert result["original_input"] == "XX"

    @pytest.mark.asyncio
    async def test_invalid_country_code_zzz(self, mock_ctx):
        """ZZZ is not a valid code (3 characters)."""
        result = await validate_destination_country({"country_code": "ZZZ"}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None

    @pytest.mark.asyncio
    async def test_invalid_country_code_empty(self, mock_ctx):
        """Empty string should be invalid."""
        result = await validate_destination_country({"country_code": ""}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None

    @pytest.mark.asyncio
    async def test_invalid_country_code_single_char(self, mock_ctx):
        """Single character should be invalid."""
        result = await validate_destination_country({"country_code": "A"}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None

    @pytest.mark.asyncio
    async def test_invalid_country_code_numeric(self, mock_ctx):
        """Numeric codes should be invalid for alpha-2."""
        result = await validate_destination_country({"country_code": "12"}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None

    # =========================================================================
    # Alias Normalization
    # =========================================================================

    @pytest.mark.asyncio
    async def test_alias_usa_to_us(self, mock_ctx):
        """USA should normalize to US."""
        result = await validate_destination_country({"country_code": "USA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "US"
        assert result["original_input"] == "USA"

    @pytest.mark.asyncio
    async def test_alias_uk_to_gb(self, mock_ctx):
        """UK should normalize to GB."""
        result = await validate_destination_country({"country_code": "UK"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "GB"
        assert result["original_input"] == "UK"

    @pytest.mark.asyncio
    async def test_alias_britain_to_gb(self, mock_ctx):
        """BRITAIN should normalize to GB."""
        result = await validate_destination_country({"country_code": "BRITAIN"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "GB"

    @pytest.mark.asyncio
    async def test_alias_england_to_gb(self, mock_ctx):
        """ENGLAND should normalize to GB (common usage)."""
        result = await validate_destination_country({"country_code": "ENGLAND"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "GB"

    @pytest.mark.asyncio
    async def test_alias_korea_to_kr(self, mock_ctx):
        """KOREA should default to South Korea (KR)."""
        result = await validate_destination_country({"country_code": "KOREA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "KR"

    @pytest.mark.asyncio
    async def test_alias_south_korea_to_kr(self, mock_ctx):
        """SOUTH KOREA should normalize to KR."""
        result = await validate_destination_country({"country_code": "SOUTH KOREA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "KR"

    @pytest.mark.asyncio
    async def test_alias_north_korea_to_kp(self, mock_ctx):
        """NORTH KOREA should normalize to KP (prohibited)."""
        result = await validate_destination_country({"country_code": "NORTH KOREA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "KP"
        assert result["prohibited"] is True

    @pytest.mark.asyncio
    async def test_alias_dprk_to_kp(self, mock_ctx):
        """DPRK should normalize to KP (prohibited)."""
        result = await validate_destination_country({"country_code": "DPRK"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "KP"
        assert result["prohibited"] is True

    @pytest.mark.asyncio
    async def test_alias_uae_to_ae(self, mock_ctx):
        """UAE should normalize to AE."""
        result = await validate_destination_country({"country_code": "UAE"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "AE"

    @pytest.mark.asyncio
    async def test_alias_russia_to_ru(self, mock_ctx):
        """RUSSIA should normalize to RU."""
        result = await validate_destination_country({"country_code": "RUSSIA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "RU"
        assert result["prohibited"] is False  # Not comprehensively sanctioned

    @pytest.mark.asyncio
    async def test_alias_iran_to_ir(self, mock_ctx):
        """IRAN should normalize to IR (prohibited)."""
        result = await validate_destination_country({"country_code": "IRAN"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "IR"
        assert result["prohibited"] is True

    @pytest.mark.asyncio
    async def test_alias_syria_to_sy(self, mock_ctx):
        """SYRIA should normalize to SY (prohibited)."""
        result = await validate_destination_country({"country_code": "SYRIA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "SY"
        assert result["prohibited"] is True

    @pytest.mark.asyncio
    async def test_alias_cuba_to_cu(self, mock_ctx):
        """CUBA should normalize to CU (prohibited)."""
        result = await validate_destination_country({"country_code": "CUBA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "CU"
        assert result["prohibited"] is True

    @pytest.mark.asyncio
    async def test_alias_china_to_cn(self, mock_ctx):
        """CHINA should normalize to CN."""
        result = await validate_destination_country({"country_code": "CHINA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "CN"

    @pytest.mark.asyncio
    async def test_alias_prc_to_cn(self, mock_ctx):
        """PRC should normalize to CN."""
        result = await validate_destination_country({"country_code": "PRC"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "CN"

    @pytest.mark.asyncio
    async def test_alias_holland_to_nl(self, mock_ctx):
        """HOLLAND should normalize to NL."""
        result = await validate_destination_country({"country_code": "HOLLAND"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "NL"

    @pytest.mark.asyncio
    async def test_alias_ksa_to_sa(self, mock_ctx):
        """KSA should normalize to SA."""
        result = await validate_destination_country({"country_code": "KSA"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "SA"

    # =========================================================================
    # Case Normalization
    # =========================================================================

    @pytest.mark.asyncio
    async def test_lowercase_normalized_to_uppercase(self, mock_ctx):
        """Lowercase country codes should be normalized to uppercase."""
        result = await validate_destination_country({"country_code": "us"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "US"
        assert result["original_input"] == "us"

    @pytest.mark.asyncio
    async def test_mixed_case_normalized(self, mock_ctx):
        """Mixed case should be normalized."""
        result = await validate_destination_country({"country_code": "Gb"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "GB"

    @pytest.mark.asyncio
    async def test_lowercase_alias_normalized(self, mock_ctx):
        """Lowercase aliases should be normalized."""
        result = await validate_destination_country({"country_code": "usa"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "US"

    # =========================================================================
    # Whitespace Handling
    # =========================================================================

    @pytest.mark.asyncio
    async def test_leading_whitespace_stripped(self, mock_ctx):
        """Leading whitespace should be stripped."""
        result = await validate_destination_country({"country_code": "  US"}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "US"

    @pytest.mark.asyncio
    async def test_trailing_whitespace_stripped(self, mock_ctx):
        """Trailing whitespace should be stripped."""
        result = await validate_destination_country({"country_code": "US  "}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "US"

    @pytest.mark.asyncio
    async def test_both_whitespace_stripped(self, mock_ctx):
        """Both leading and trailing whitespace should be stripped."""
        result = await validate_destination_country({"country_code": "  DE  "}, mock_ctx)

        assert result["valid"] is True
        assert result["normalized_code"] == "DE"

    @pytest.mark.asyncio
    async def test_whitespace_only_invalid(self, mock_ctx):
        """Whitespace-only input should be invalid."""
        result = await validate_destination_country({"country_code": "   "}, mock_ctx)

        assert result["valid"] is False
        assert result["normalized_code"] is None

    # =========================================================================
    # Prohibited Destinations
    # =========================================================================

    @pytest.mark.asyncio
    async def test_prohibited_cu_cuba(self, mock_ctx):
        """CU (Cuba) should be marked as prohibited."""
        result = await validate_destination_country({"country_code": "CU"}, mock_ctx)

        assert result["valid"] is True
        assert result["prohibited"] is True
        assert result["normalized_code"] == "CU"

    @pytest.mark.asyncio
    async def test_prohibited_ir_iran(self, mock_ctx):
        """IR (Iran) should be marked as prohibited."""
        result = await validate_destination_country({"country_code": "IR"}, mock_ctx)

        assert result["valid"] is True
        assert result["prohibited"] is True
        assert result["normalized_code"] == "IR"

    @pytest.mark.asyncio
    async def test_prohibited_kp_north_korea(self, mock_ctx):
        """KP (North Korea) should be marked as prohibited."""
        result = await validate_destination_country({"country_code": "KP"}, mock_ctx)

        assert result["valid"] is True
        assert result["prohibited"] is True
        assert result["normalized_code"] == "KP"

    @pytest.mark.asyncio
    async def test_prohibited_sy_syria(self, mock_ctx):
        """SY (Syria) should be marked as prohibited."""
        result = await validate_destination_country({"country_code": "SY"}, mock_ctx)

        assert result["valid"] is True
        assert result["prohibited"] is True
        assert result["normalized_code"] == "SY"

    @pytest.mark.asyncio
    async def test_all_prohibited_destinations_detected(self, mock_ctx):
        """All countries in PROHIBITED_DESTINATIONS should be detected."""
        for country_code in PROHIBITED_DESTINATIONS:
            result = await validate_destination_country({"country_code": country_code}, mock_ctx)
            assert result["prohibited"] is True, f"{country_code} should be prohibited"

    # =========================================================================
    # Original Input Preservation
    # =========================================================================

    @pytest.mark.asyncio
    async def test_original_input_preserved_valid(self, mock_ctx):
        """Original input should be preserved for audit trail (valid code)."""
        result = await validate_destination_country({"country_code": "  usa  "}, mock_ctx)

        assert result["original_input"] == "  usa  "
        assert result["normalized_code"] == "US"

    @pytest.mark.asyncio
    async def test_original_input_preserved_invalid(self, mock_ctx):
        """Original input should be preserved for audit trail (invalid code)."""
        result = await validate_destination_country({"country_code": "INVALID"}, mock_ctx)

        assert result["original_input"] == "INVALID"
        assert result["normalized_code"] is None


class TestCountryCodeConstants:
    """Tests for country code constants."""

    def test_iso_3166_1_alpha_2_is_frozenset(self):
        """ISO codes should be in a frozenset (immutable)."""
        assert isinstance(ISO_3166_1_ALPHA_2, frozenset)

    def test_iso_3166_1_alpha_2_contains_major_countries(self):
        """Should contain all major country codes."""
        major_countries = ["US", "GB", "DE", "FR", "JP", "CN", "IN", "BR", "AU", "CA"]
        for code in major_countries:
            assert code in ISO_3166_1_ALPHA_2, f"{code} should be in ISO codes"

    def test_iso_3166_1_alpha_2_all_uppercase(self):
        """All codes should be uppercase."""
        for code in ISO_3166_1_ALPHA_2:
            assert code == code.upper(), f"{code} should be uppercase"

    def test_iso_3166_1_alpha_2_all_two_chars(self):
        """All codes should be exactly 2 characters."""
        for code in ISO_3166_1_ALPHA_2:
            assert len(code) == 2, f"{code} should be 2 characters"

    def test_country_aliases_is_dict(self):
        """Country aliases should be a dict."""
        assert isinstance(COUNTRY_ALIASES, dict)

    def test_country_aliases_values_are_iso_codes(self):
        """All alias values should be valid ISO codes."""
        for alias, code in COUNTRY_ALIASES.items():
            assert code in ISO_3166_1_ALPHA_2, (
                f"Alias {alias} -> {code} should map to valid ISO code"
            )

    def test_prohibited_destinations_is_frozenset(self):
        """Prohibited destinations should be frozenset."""
        assert isinstance(PROHIBITED_DESTINATIONS, frozenset)

    def test_prohibited_destinations_count(self):
        """Should have exactly 4 comprehensively sanctioned destinations."""
        assert len(PROHIBITED_DESTINATIONS) == 4

    def test_prohibited_destinations_are_valid_iso_codes(self):
        """All prohibited destinations should be valid ISO codes."""
        for code in PROHIBITED_DESTINATIONS:
            assert code in ISO_3166_1_ALPHA_2, f"{code} should be valid ISO code"
