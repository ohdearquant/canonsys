"""Tests for export control truth machine phrases (constraints).

Tests the assertion functions that enforce regulatory invariants.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from canon_vocab_export_control.exceptions import (
    BISLicenseRequiredError,
    ITARAuthorizationRequiredError,
    OFACSanctionsMatchError,
)
from canon_vocab_export_control.phrases import (
    bis_license_must_be_valid,
    destination_must_not_be_prohibited,
    itar_must_be_authorized,
    ofac_must_be_cleared,
)
from canon_vocab_export_control.types import (
    BISLicenseType,
    ITARAuthorizationType,
    OFACEntityType,
)


class TestDestinationMustNotBeProhibited:
    """Tests for destination_must_not_be_prohibited constraint.

    Note: The actual prohibition check happens in require_allowed_destination().
    This constraint function is a passthrough that validates the result type.
    The tests for prohibition logic are in test_require_allowed_destination.py.
    """

    def test_allowed_destination_passes(self):
        """Allowed destination result should pass through."""
        result = {"country_code": "DE"}

        # Should not raise
        destination_must_not_be_prohibited(result)

    def test_allowed_destination_us_passes(self):
        """US destination should pass."""
        result = {"country_code": "US"}
        destination_must_not_be_prohibited(result)

    def test_allowed_destination_uk_passes(self):
        """UK destination should pass."""
        result = {"country_code": "GB"}
        destination_must_not_be_prohibited(result)


class TestOFACMustBeCleared:
    """Tests for ofac_must_be_cleared constraint."""

    def test_cleared_entity_passes(self):
        """Cleared entity should not raise."""
        result = {
            "cleared": True,
            "entity_name": "ACME Corporation",
            "entity_type": OFACEntityType.ENTITY,
            "screening_timestamp": datetime.now(),
            "sanctions_list_version": "2024-01",
            "match_score": None,
            "matched_program": None,
            "matched_sdn_id": None,
        }

        # Should not raise
        ofac_must_be_cleared(result)

    def test_not_cleared_raises(self):
        """Entity not cleared should raise OFACSanctionsMatchError."""
        result = {
            "cleared": False,
            "entity_name": "Bad Actor Inc",
            "entity_type": OFACEntityType.ENTITY,
            "screening_timestamp": datetime.now(),
            "sanctions_list_version": "2024-01",
            "match_score": 0.95,
            "matched_program": "IRAN",
            "matched_sdn_id": "12345",
        }

        with pytest.raises(OFACSanctionsMatchError) as exc_info:
            ofac_must_be_cleared(result)

        error = exc_info.value
        assert error.entity_name == "Bad Actor Inc"
        assert error.entity_type == "ENTITY"
        assert error.matched_program == "IRAN"
        assert error.matched_sdn_id == "12345"
        assert error.match_score == 0.95

    def test_individual_not_cleared_raises(self):
        """Individual not cleared should raise error."""
        result = {
            "cleared": False,
            "entity_name": "John Doe",
            "entity_type": OFACEntityType.INDIVIDUAL,
            "screening_timestamp": datetime.now(),
            "sanctions_list_version": "2024-01",
            "match_score": 0.88,
            "matched_program": "SDGT",
            "matched_sdn_id": "67890",
        }

        with pytest.raises(OFACSanctionsMatchError) as exc_info:
            ofac_must_be_cleared(result)

        assert exc_info.value.entity_type == "INDIVIDUAL"

    def test_vessel_not_cleared_raises(self):
        """Vessel not cleared should raise error."""
        result = {
            "cleared": False,
            "entity_name": "MV Suspicious",
            "entity_type": OFACEntityType.VESSEL,
            "screening_timestamp": datetime.now(),
            "sanctions_list_version": "2024-01",
            "match_score": 0.99,
            "matched_program": "CUBA",
            "matched_sdn_id": "V12345",
        }

        with pytest.raises(OFACSanctionsMatchError) as exc_info:
            ofac_must_be_cleared(result)

        assert exc_info.value.entity_type == "VESSEL"


class TestBISLicenseMustBeValid:
    """Tests for bis_license_must_be_valid constraint."""

    def test_approved_passes(self):
        """Approved result should not raise."""
        result = {
            "approved": True,
            "license_number": None,
            "license_type": BISLicenseType.LICENSE_EXCEPTION,
            "eccn": "5D992",
            "destination_country": "DE",
            "expiry_date": None,
            "exception_code": "ENC",
            "end_user_verified": True,
        }

        # Should not raise
        bis_license_must_be_valid(result)

    def test_not_approved_raises(self):
        """Not approved result should raise BISLicenseRequiredError."""
        result = {
            "approved": False,
            "license_number": None,
            "license_type": BISLicenseType.LICENSE,
            "eccn": "5A002",
            "destination_country": "CN",
            "expiry_date": None,
            "exception_code": None,
            "end_user_verified": False,
        }

        with pytest.raises(BISLicenseRequiredError) as exc_info:
            bis_license_must_be_valid(result)

        error = exc_info.value
        assert error.eccn == "5A002"
        assert error.destination_country == "CN"

    def test_not_approved_no_eccn_uses_unknown(self):
        """Missing ECCN should default to UNKNOWN."""
        result = {
            "approved": False,
            "license_number": None,
            "license_type": BISLicenseType.LICENSE,
            "eccn": None,  # Unknown ECCN
            "destination_country": "RU",
            "expiry_date": None,
            "exception_code": None,
            "end_user_verified": False,
        }

        with pytest.raises(BISLicenseRequiredError) as exc_info:
            bis_license_must_be_valid(result)

        assert exc_info.value.eccn == "UNKNOWN"


class TestITARMustBeAuthorized:
    """Tests for itar_must_be_authorized constraint."""

    def test_authorized_passes(self):
        """Authorized result should not raise."""
        result = {
            "authorized": True,
            "authorization_type": ITARAuthorizationType.DSP_5,
            "ddtc_reference": "DSP-5-123456",
            "usml_category": "XI",
            "destination_country": "GB",
            "expiry_date": None,
            "provisos": (),
        }

        # Should not raise
        itar_must_be_authorized(result)

    def test_not_authorized_raises(self):
        """Not authorized result should raise ITARAuthorizationRequiredError."""
        result = {
            "authorized": False,
            "authorization_type": None,
            "ddtc_reference": None,
            "usml_category": "XV",
            "destination_country": "CN",
            "expiry_date": None,
            "provisos": (),
        }

        with pytest.raises(ITARAuthorizationRequiredError) as exc_info:
            itar_must_be_authorized(result)

        error = exc_info.value
        assert error.usml_category == "XV"
        assert error.destination_country == "CN"

    def test_taa_not_authorized_raises(self):
        """TAA-related unauthorized should raise error."""
        result = {
            "authorized": False,
            "authorization_type": None,
            "ddtc_reference": None,
            "usml_category": "VIII",
            "destination_country": "IN",
            "expiry_date": None,
            "provisos": (),
        }

        with pytest.raises(ITARAuthorizationRequiredError) as exc_info:
            itar_must_be_authorized(result)

        assert exc_info.value.usml_category == "VIII"
