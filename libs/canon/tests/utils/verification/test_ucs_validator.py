"""Tests for canon.verification.ucs_validator module.

Tests cover:
- ValidationStatus enum values and semantics
- ValidationResult dataclass properties
- UCSValidator.validate_certificate() with mocked PolicyEngine
- Fail-closed semantics (any error -> BLOCKED)
- PolicyResult -> ValidationResult mapping

Architecture validation:
- UCS certificates validated via OPA/Rego policy (ucs.validator)
- Binary outcome mapped to ValidationStatus enum
- Fail-closed by default for compliance-critical validation
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from canon.enforcement.types import EnforcementLevel, PolicyResult
from canon.utils.verification.opa_data_provider import UCSDataProvider
from canon.utils.verification.ucs_validator import (
    UCSValidator,
    ValidationResult,
    ValidationStatus,
)
from kron.utils import now_utc

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_policy_engine() -> MagicMock:
    """Mock PolicyEngine for testing."""
    return MagicMock()


@pytest.fixture
def data_provider() -> UCSDataProvider:
    """UCSDataProvider with sample data."""
    provider = UCSDataProvider()
    provider.add_cep(
        cep_id="cep-001",
        final_hash="abc123",
        cep_type="POLICY_SIGN_OFF",
        status="ACTIVE",
        valid_until_utc=datetime(2026, 12, 31, tzinfo=UTC),
    )
    provider.add_signing_key(
        key_id="key-001",
        valid_from_utc=datetime(2025, 1, 1, tzinfo=UTC),
        valid_to_utc=datetime(2027, 12, 31, tzinfo=UTC),
    )
    return provider


@pytest.fixture
def valid_ucs_certificate() -> dict[str, Any]:
    """Sample valid UCS-v1 certificate."""
    return {
        "meta": {
            "schema_version": "1.0",
            "environment": "production",
        },
        "context": {
            "workflow_type": "TERMINATION_DECISION",
            "subject_token": "subj-token-001",
            "jurisdiction_code": "US-CA",
        },
        "authority": {
            "issuer_role": "HRBP_DIRECTOR",
        },
        "assertions": {
            "risk_acceptance": True,
            "parity_attested": True,
            "er_clearance": {"cleared": False},
        },
        "evidence_pointers": [
            {
                "cep_id": "cep-001",
                "hash": "abc123",
                "type": "POLICY_SIGN_OFF",
            }
        ],
        "seal": {
            "signing_key_id": "key-001",
            "signed_at_utc": "2026-01-14T10:00:00Z",
            "tsa_token": "tsa-token-001",
            "signature": "sig-base64",
            "payload_hash": "payload-hash-001",
        },
    }


@pytest.fixture
def approved_policy_result() -> PolicyResult:
    """PolicyResult representing approved validation."""
    return PolicyResult(
        policy_id="ucs.validator",
        allowed=True,
        enforcement=EnforcementLevel.HARD_MANDATORY,
        evaluated_at=now_utc(),
        evaluation_ms=5.2,
        raw_output={
            "allow": True,
            "decision": {"status": "APPROVED", "reason": "OK"},
        },
    )


@pytest.fixture
def blocked_policy_result() -> PolicyResult:
    """PolicyResult representing blocked validation."""
    return PolicyResult(
        policy_id="ucs.validator",
        allowed=False,
        enforcement=EnforcementLevel.HARD_MANDATORY,
        violation_code="WAITING_PERIOD_NOT_MET",
        violation_message="Signing key window violated",
        evaluated_at=now_utc(),
        evaluation_ms=4.8,
        raw_output={
            "allow": False,
            "decision": {"status": "BLOCKED", "reason": "DEFAULT_DENY"},
            "deny_reasons": ["schema_ok failed", "signing_ok failed"],
        },
    )


# =============================================================================
# ValidationStatus Enum Tests
# =============================================================================


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_status_values(self):
        """ValidationStatus should have APPROVED, BLOCKED, ESCALATION_REQUIRED."""
        assert ValidationStatus.APPROVED == "APPROVED"
        assert ValidationStatus.BLOCKED == "BLOCKED"
        assert ValidationStatus.ESCALATION_REQUIRED == "ESCALATION_REQUIRED"

    def test_status_is_string_enum(self):
        """ValidationStatus should be a string enum for JSON serialization."""
        assert isinstance(ValidationStatus.APPROVED, str)
        assert ValidationStatus.BLOCKED.value == "BLOCKED"


# =============================================================================
# ValidationResult Dataclass Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_creation_with_defaults(self):
        """ValidationResult should work with minimal args."""
        result = ValidationResult(
            status=ValidationStatus.APPROVED,
            reason="OK",
        )

        assert result.status == ValidationStatus.APPROVED
        assert result.reason == "OK"
        assert result.details == {}
        assert result.evaluation_ms == 0.0
        assert result.evaluated_at is not None

    def test_creation_with_details(self):
        """ValidationResult should accept details dict."""
        result = ValidationResult(
            status=ValidationStatus.BLOCKED,
            reason="Signing key expired",
            details={"conditions_missing": ["signing_ok"]},
            evaluation_ms=3.5,
        )

        assert result.details == {"conditions_missing": ["signing_ok"]}
        assert result.evaluation_ms == 3.5

    def test_is_approved_property(self):
        """is_approved should return True only for APPROVED status."""
        approved = ValidationResult(status=ValidationStatus.APPROVED, reason="OK")
        blocked = ValidationResult(status=ValidationStatus.BLOCKED, reason="Fail")
        escalation = ValidationResult(status=ValidationStatus.ESCALATION_REQUIRED, reason="Review")

        assert approved.is_approved is True
        assert blocked.is_approved is False
        assert escalation.is_approved is False

    def test_is_blocked_property(self):
        """is_blocked should return True only for BLOCKED status."""
        approved = ValidationResult(status=ValidationStatus.APPROVED, reason="OK")
        blocked = ValidationResult(status=ValidationStatus.BLOCKED, reason="Fail")
        escalation = ValidationResult(status=ValidationStatus.ESCALATION_REQUIRED, reason="Review")

        assert approved.is_blocked is False
        assert blocked.is_blocked is True
        assert escalation.is_blocked is False

    def test_requires_escalation_property(self):
        """requires_escalation should return True only for ESCALATION_REQUIRED."""
        approved = ValidationResult(status=ValidationStatus.APPROVED, reason="OK")
        blocked = ValidationResult(status=ValidationStatus.BLOCKED, reason="Fail")
        escalation = ValidationResult(status=ValidationStatus.ESCALATION_REQUIRED, reason="Review")

        assert approved.requires_escalation is False
        assert blocked.requires_escalation is False
        assert escalation.requires_escalation is True

    def test_frozen_dataclass(self):
        """ValidationResult should be immutable (frozen)."""
        result = ValidationResult(status=ValidationStatus.APPROVED, reason="OK")

        with pytest.raises(AttributeError):
            result.status = ValidationStatus.BLOCKED  # type: ignore[misc]


# =============================================================================
# UCSValidator Tests
# =============================================================================


class TestUCSValidator:
    """Tests for UCSValidator class."""

    def test_constructor(self, mock_policy_engine, data_provider):
        """UCSValidator should accept engine and data_provider."""
        validator = UCSValidator(mock_policy_engine, data_provider)

        assert validator._engine is mock_policy_engine
        assert validator._data_provider is data_provider

    def test_data_provider_property(self, mock_policy_engine, data_provider):
        """data_provider property should return current provider."""
        validator = UCSValidator(mock_policy_engine, data_provider)

        assert validator.data_provider is data_provider

    def test_set_data_provider(self, mock_policy_engine, data_provider):
        """set_data_provider should update the provider."""
        validator = UCSValidator(mock_policy_engine, data_provider)

        new_provider = UCSDataProvider()
        validator.set_data_provider(new_provider)

        assert validator.data_provider is new_provider


class TestUCSValidatorValidateCertificate:
    """Tests for UCSValidator.validate_certificate() method."""

    @pytest.mark.asyncio
    async def test_approved_certificate(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        approved_policy_result,
    ):
        """validate_certificate should return APPROVED for passing certificate."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=approved_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.APPROVED
        assert result.is_approved is True
        assert result.reason == "OK"

    @pytest.mark.asyncio
    async def test_blocked_certificate(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        blocked_policy_result,
    ):
        """validate_certificate should return BLOCKED for failing certificate."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=blocked_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.BLOCKED
        assert result.is_blocked is True

    @pytest.mark.asyncio
    async def test_blocked_preserves_reason(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        blocked_policy_result,
    ):
        """validate_certificate should preserve reason from Rego decision."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=blocked_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        # Should get reason from decision object
        assert result.reason == "DEFAULT_DENY"

    @pytest.mark.asyncio
    async def test_blocked_includes_deny_reasons(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        blocked_policy_result,
    ):
        """validate_certificate should include deny_reasons in details."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=blocked_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert "deny_reasons" in result.details
        assert "schema_ok failed" in result.details["deny_reasons"]

    @pytest.mark.asyncio
    async def test_blocked_includes_violation_code(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        blocked_policy_result,
    ):
        """validate_certificate should include violation_code in details."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=blocked_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.details.get("violation_code") == "WAITING_PERIOD_NOT_MET"

    @pytest.mark.asyncio
    async def test_calls_engine_with_certificate(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        approved_policy_result,
    ):
        """validate_certificate should pass certificate to engine."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=approved_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        await validator.validate_certificate(valid_ucs_certificate)

        # Verify engine was called
        mock_policy_engine.evaluate_single.assert_called_once()

        # Verify certificate was passed as input_data
        call_args = mock_policy_engine.evaluate_single.call_args
        input_data = call_args.kwargs.get("input_data") or call_args[1]["input_data"]
        assert input_data == valid_ucs_certificate

    @pytest.mark.asyncio
    async def test_calls_engine_with_ucs_policy(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
        approved_policy_result,
    ):
        """validate_certificate should use ucs.validator policy."""
        mock_policy_engine.evaluate_single = AsyncMock(return_value=approved_policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        await validator.validate_certificate(valid_ucs_certificate)

        # Verify policy was passed
        call_args = mock_policy_engine.evaluate_single.call_args
        policy = call_args.kwargs.get("policy") or call_args[0][0]
        assert policy.rego_package == "ucs.validator"
        assert policy.policy_id == "ucs.validator"


class TestUCSValidatorFailClosed:
    """Tests for fail-closed semantics."""

    @pytest.mark.asyncio
    async def test_engine_exception_returns_blocked(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """validate_certificate should return BLOCKED on engine exception."""
        mock_policy_engine.evaluate_single = AsyncMock(side_effect=Exception("Connection timeout"))

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.BLOCKED
        assert "Connection timeout" in result.reason
        assert result.details.get("error_type") == "Exception"

    @pytest.mark.asyncio
    async def test_any_error_returns_blocked(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """validate_certificate should return BLOCKED on any error."""
        mock_policy_engine.evaluate_single = AsyncMock(side_effect=ValueError("Invalid input"))

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.BLOCKED
        assert "Invalid input" in result.reason
        assert result.details.get("error_type") == "ValueError"

    @pytest.mark.asyncio
    async def test_error_result_has_evaluation_time(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """validate_certificate should track time even on error."""
        mock_policy_engine.evaluate_single = AsyncMock(side_effect=Exception("Error"))

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.evaluation_ms > 0


class TestUCSValidatorResultMapping:
    """Tests for PolicyResult -> ValidationResult mapping."""

    @pytest.mark.asyncio
    async def test_maps_allow_true_to_approved(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """allowed=True should map to APPROVED."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=True,
            evaluated_at=now_utc(),
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.APPROVED

    @pytest.mark.asyncio
    async def test_maps_allow_false_to_blocked(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """allowed=False should map to BLOCKED."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=False,
            evaluated_at=now_utc(),
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_maps_escalation_required_from_decision(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """ESCALATION_REQUIRED in decision should map correctly."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=False,
            evaluated_at=now_utc(),
            raw_output={
                "decision": {
                    "status": "ESCALATION_REQUIRED",
                    "reason": "Human review needed",
                }
            },
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.status == ValidationStatus.ESCALATION_REQUIRED
        assert result.requires_escalation is True

    @pytest.mark.asyncio
    async def test_preserves_evaluated_at(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """ValidationResult should preserve evaluated_at from PolicyResult."""
        timestamp = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=True,
            evaluated_at=timestamp,
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.evaluated_at == timestamp

    @pytest.mark.asyncio
    async def test_includes_decision_in_details(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """ValidationResult details should include decision object."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=True,
            evaluated_at=now_utc(),
            raw_output={
                "decision": {"status": "APPROVED", "reason": "OK"},
            },
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert "decision" in result.details
        assert result.details["decision"]["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_default_reason_when_no_decision(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """ValidationResult should have default reason when decision missing."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=True,
            evaluated_at=now_utc(),
            raw_output={},
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        # Should default to "OK" for approved
        assert result.reason == "OK"

    @pytest.mark.asyncio
    async def test_uses_violation_message_as_fallback_reason(
        self,
        mock_policy_engine,
        data_provider,
        valid_ucs_certificate,
    ):
        """ValidationResult should use violation_message if no decision.reason."""
        policy_result = PolicyResult(
            policy_id="ucs.validator",
            allowed=False,
            violation_message="Certificate expired",
            evaluated_at=now_utc(),
            raw_output={},
        )
        mock_policy_engine.evaluate_single = AsyncMock(return_value=policy_result)

        validator = UCSValidator(mock_policy_engine, data_provider)
        result = await validator.validate_certificate(valid_ucs_certificate)

        assert result.reason == "Certificate expired"


# =============================================================================
# Module Export Tests
# =============================================================================


class TestModuleExports:
    """Tests for module __all__ exports."""

    def test_exports(self):
        """Module should export expected symbols."""
        from canon.utils.verification import ucs_validator

        assert hasattr(ucs_validator, "ValidationStatus")
        assert hasattr(ucs_validator, "ValidationResult")
        assert hasattr(ucs_validator, "UCSValidator")

        assert "ValidationStatus" in ucs_validator.__all__
        assert "ValidationResult" in ucs_validator.__all__
        assert "UCSValidator" in ucs_validator.__all__
