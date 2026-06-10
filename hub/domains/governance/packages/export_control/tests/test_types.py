"""Tests for export control types (enums and constants).

Tests ExportSubjectType, ScreeningScope, and other export control enums.
"""

from __future__ import annotations

import pytest
from canon_vocab_export_control.types import (
    PROHIBITED_DESTINATIONS,
    PROHIBITION_INFO,
    BISLicenseType,
    ExportSubjectType,
    ITARAuthorizationType,
    OFACEntityType,
    ScreeningScope,
)


class TestExportSubjectType:
    """Tests for ExportSubjectType enum."""

    def test_technical_data_value(self):
        """TECHNICAL_DATA should have correct value."""
        assert ExportSubjectType.TECHNICAL_DATA.value == "TECHNICAL_DATA"

    def test_source_code_value(self):
        """SOURCE_CODE should have correct value."""
        assert ExportSubjectType.SOURCE_CODE.value == "SOURCE_CODE"

    def test_product_value(self):
        """PRODUCT should have correct value."""
        assert ExportSubjectType.PRODUCT.value == "PRODUCT"

    def test_service_value(self):
        """SERVICE should have correct value."""
        assert ExportSubjectType.SERVICE.value == "SERVICE"

    def test_all_members_present(self):
        """Should have exactly 4 members."""
        assert len(ExportSubjectType) == 4

    def test_can_construct_from_string(self):
        """Should be able to construct from string value."""
        assert ExportSubjectType("TECHNICAL_DATA") == ExportSubjectType.TECHNICAL_DATA
        assert ExportSubjectType("SOURCE_CODE") == ExportSubjectType.SOURCE_CODE
        assert ExportSubjectType("PRODUCT") == ExportSubjectType.PRODUCT
        assert ExportSubjectType("SERVICE") == ExportSubjectType.SERVICE

    def test_invalid_value_raises(self):
        """Invalid value should raise ValueError."""
        with pytest.raises(ValueError):
            ExportSubjectType("INVALID")


class TestScreeningScope:
    """Tests for ScreeningScope enum."""

    def test_direct_party_value(self):
        """DIRECT_PARTY should have correct value."""
        assert ScreeningScope.DIRECT_PARTY.value == "DIRECT_PARTY"

    def test_full_chain_value(self):
        """FULL_CHAIN should have correct value."""
        assert ScreeningScope.FULL_CHAIN.value == "FULL_CHAIN"

    def test_all_members_present(self):
        """Should have exactly 2 members."""
        assert len(ScreeningScope) == 2

    def test_can_construct_from_string(self):
        """Should be able to construct from string value."""
        assert ScreeningScope("DIRECT_PARTY") == ScreeningScope.DIRECT_PARTY
        assert ScreeningScope("FULL_CHAIN") == ScreeningScope.FULL_CHAIN

    def test_invalid_value_raises(self):
        """Invalid value should raise ValueError."""
        with pytest.raises(ValueError):
            ScreeningScope("PARTIAL")


class TestBISLicenseType:
    """Tests for BISLicenseType enum."""

    def test_license_value(self):
        """LICENSE should have correct value."""
        assert BISLicenseType.LICENSE.value == "LICENSE"

    def test_license_exception_value(self):
        """LICENSE_EXCEPTION should have correct value."""
        assert BISLicenseType.LICENSE_EXCEPTION.value == "LICENSE_EXCEPTION"

    def test_no_license_required_value(self):
        """NO_LICENSE_REQUIRED should have correct value."""
        assert BISLicenseType.NO_LICENSE_REQUIRED.value == "NO_LICENSE_REQUIRED"

    def test_all_members_present(self):
        """Should have exactly 3 members."""
        assert len(BISLicenseType) == 3

    def test_can_construct_from_string(self):
        """Should be able to construct from string value."""
        assert BISLicenseType("LICENSE") == BISLicenseType.LICENSE
        assert BISLicenseType("LICENSE_EXCEPTION") == BISLicenseType.LICENSE_EXCEPTION
        assert BISLicenseType("NO_LICENSE_REQUIRED") == BISLicenseType.NO_LICENSE_REQUIRED


class TestITARAuthorizationType:
    """Tests for ITARAuthorizationType enum."""

    def test_dsp_5_value(self):
        """DSP_5 should have correct value."""
        assert ITARAuthorizationType.DSP_5.value == "DSP-5"

    def test_dsp_73_value(self):
        """DSP_73 should have correct value."""
        assert ITARAuthorizationType.DSP_73.value == "DSP-73"

    def test_dsp_85_value(self):
        """DSP_85 should have correct value."""
        assert ITARAuthorizationType.DSP_85.value == "DSP-85"

    def test_taa_value(self):
        """TAA should have correct value."""
        assert ITARAuthorizationType.TAA.value == "TAA"

    def test_mla_value(self):
        """MLA should have correct value."""
        assert ITARAuthorizationType.MLA.value == "MLA"

    def test_exemption_value(self):
        """EXEMPTION should have correct value."""
        assert ITARAuthorizationType.EXEMPTION.value == "EXEMPTION"

    def test_all_members_present(self):
        """Should have exactly 6 members."""
        assert len(ITARAuthorizationType) == 6

    def test_can_construct_from_string(self):
        """Should be able to construct from string value."""
        assert ITARAuthorizationType("DSP-5") == ITARAuthorizationType.DSP_5
        assert ITARAuthorizationType("TAA") == ITARAuthorizationType.TAA
        assert ITARAuthorizationType("EXEMPTION") == ITARAuthorizationType.EXEMPTION


class TestOFACEntityType:
    """Tests for OFACEntityType enum."""

    def test_individual_value(self):
        """INDIVIDUAL should have correct value."""
        assert OFACEntityType.INDIVIDUAL.value == "INDIVIDUAL"

    def test_entity_value(self):
        """ENTITY should have correct value."""
        assert OFACEntityType.ENTITY.value == "ENTITY"

    def test_vessel_value(self):
        """VESSEL should have correct value."""
        assert OFACEntityType.VESSEL.value == "VESSEL"

    def test_aircraft_value(self):
        """AIRCRAFT should have correct value."""
        assert OFACEntityType.AIRCRAFT.value == "AIRCRAFT"

    def test_all_members_present(self):
        """Should have exactly 4 members."""
        assert len(OFACEntityType) == 4

    def test_can_construct_from_string(self):
        """Should be able to construct from string value."""
        assert OFACEntityType("INDIVIDUAL") == OFACEntityType.INDIVIDUAL
        assert OFACEntityType("ENTITY") == OFACEntityType.ENTITY
        assert OFACEntityType("VESSEL") == OFACEntityType.VESSEL
        assert OFACEntityType("AIRCRAFT") == OFACEntityType.AIRCRAFT


class TestProhibitedDestinationsConstant:
    """Tests for PROHIBITED_DESTINATIONS constant."""

    def test_is_frozenset(self):
        """Should be a frozenset (immutable)."""
        assert isinstance(PROHIBITED_DESTINATIONS, frozenset)

    def test_contains_cuba(self):
        """Should contain CU (Cuba)."""
        assert "CU" in PROHIBITED_DESTINATIONS

    def test_contains_iran(self):
        """Should contain IR (Iran)."""
        assert "IR" in PROHIBITED_DESTINATIONS

    def test_contains_north_korea(self):
        """Should contain KP (North Korea)."""
        assert "KP" in PROHIBITED_DESTINATIONS

    def test_contains_syria(self):
        """Should contain SY (Syria)."""
        assert "SY" in PROHIBITED_DESTINATIONS

    def test_exactly_four_destinations(self):
        """Should have exactly 4 comprehensively sanctioned destinations."""
        assert len(PROHIBITED_DESTINATIONS) == 4

    def test_does_not_contain_russia(self):
        """Russia has extensive but not comprehensive sanctions."""
        assert "RU" not in PROHIBITED_DESTINATIONS

    def test_does_not_contain_china(self):
        """China is not comprehensively sanctioned."""
        assert "CN" not in PROHIBITED_DESTINATIONS

    def test_does_not_contain_us(self):
        """US should not be in prohibited destinations."""
        assert "US" not in PROHIBITED_DESTINATIONS

    def test_all_codes_are_uppercase(self):
        """All codes should be uppercase."""
        for code in PROHIBITED_DESTINATIONS:
            assert code == code.upper()

    def test_all_codes_are_two_chars(self):
        """All codes should be exactly 2 characters."""
        for code in PROHIBITED_DESTINATIONS:
            assert len(code) == 2


class TestProhibitionInfoConstant:
    """Tests for PROHIBITION_INFO constant."""

    def test_is_dict(self):
        """Should be a dictionary."""
        assert isinstance(PROHIBITION_INFO, dict)

    def test_cuba_info(self):
        """Should have Cuba info with legal basis."""
        assert "CU" in PROHIBITION_INFO
        name, basis = PROHIBITION_INFO["CU"]
        assert name == "Cuba"
        assert "31 CFR Part 515" in basis

    def test_iran_info(self):
        """Should have Iran info with legal basis."""
        assert "IR" in PROHIBITION_INFO
        name, basis = PROHIBITION_INFO["IR"]
        assert name == "Iran"
        assert "31 CFR Part 560" in basis

    def test_north_korea_info(self):
        """Should have North Korea info with legal basis."""
        assert "KP" in PROHIBITION_INFO
        name, basis = PROHIBITION_INFO["KP"]
        assert name == "North Korea"
        assert "31 CFR Part 510" in basis

    def test_syria_info(self):
        """Should have Syria info with legal basis."""
        assert "SY" in PROHIBITION_INFO
        name, basis = PROHIBITION_INFO["SY"]
        assert name == "Syria"
        assert "31 CFR Part 542" in basis

    def test_all_prohibited_destinations_have_info(self):
        """All prohibited destinations should have info entries."""
        for code in PROHIBITED_DESTINATIONS:
            assert code in PROHIBITION_INFO, f"Missing info for {code}"

    def test_info_values_are_tuples(self):
        """All values should be (name, legal_basis) tuples."""
        for code, info in PROHIBITION_INFO.items():
            assert isinstance(info, tuple)
            assert len(info) == 2
            name, basis = info
            assert isinstance(name, str)
            assert isinstance(basis, str)

    def test_legal_basis_mentions_cfr(self):
        """All legal basis strings should reference CFR."""
        for code, (name, basis) in PROHIBITION_INFO.items():
            assert "CFR" in basis, f"Legal basis for {code} should reference CFR"
