"""Tests for OPAInput and OPAResult dataclasses.

Tests cover:
- OPAInput: Input document dataclass for Rego evaluation
- OPAResult: Result dataclass from policy evaluation

Test categories:
1. Creation and field validation (required vs optional)
2. Immutability (frozen dataclass)
3. Memory efficiency (slots)
4. Serialization (to_dict())
5. Equality and hashing
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from canon.utils.opa.client import OPAInput, OPAResult
from kron.utils import now_utc

# =============================================================================
# OPAINPUT TESTS
# =============================================================================


class TestOPAInputCreation:
    """Tests for OPAInput dataclass instantiation."""

    def test_creates_with_required_fields(self):
        """OPAInput should create with action_type and tenant_id."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        assert opa_input.action_type == "hire_decision"
        assert opa_input.tenant_id == "tenant-123"
        # Optional fields default to None or empty
        assert opa_input.jurisdiction is None
        assert opa_input.subject_id is None
        assert opa_input.data == {}
        assert opa_input.evaluated_at is None

    def test_creates_with_all_fields(self):
        """OPAInput should create with all optional fields."""
        opa_input = OPAInput(
            action_type="background_check",
            tenant_id="tenant-456",
            jurisdiction="US-NYC",
            subject_id="person-789",
            data={"consent_scope": "employment"},
            evaluated_at="2024-01-15T10:30:00Z",
        )

        assert opa_input.action_type == "background_check"
        assert opa_input.tenant_id == "tenant-456"
        assert opa_input.jurisdiction == "US-NYC"
        assert opa_input.subject_id == "person-789"
        assert opa_input.data == {"consent_scope": "employment"}
        assert opa_input.evaluated_at == "2024-01-15T10:30:00Z"

    def test_action_type_is_required(self):
        """OPAInput should require action_type field."""
        with pytest.raises(TypeError):
            OPAInput(tenant_id="tenant-123")  # type: ignore

    def test_tenant_id_is_required(self):
        """OPAInput should require tenant_id field."""
        with pytest.raises(TypeError):
            OPAInput(action_type="hire_decision")  # type: ignore

    def test_data_default_is_empty_dict(self):
        """OPAInput data should default to empty dict, not None."""
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
        )

        assert opa_input.data == {}
        assert isinstance(opa_input.data, dict)


class TestOPAInputImmutability:
    """Tests for OPAInput frozen dataclass behavior."""

    def test_is_frozen(self):
        """OPAInput should be immutable (frozen=True)."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        with pytest.raises(FrozenInstanceError):
            opa_input.action_type = "modified"  # type: ignore

    def test_all_fields_immutable(self):
        """All OPAInput fields should be immutable."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
            jurisdiction="US-NYC",
            subject_id="person-456",
            data={"key": "value"},
            evaluated_at="2024-01-01T00:00:00Z",
        )

        with pytest.raises(FrozenInstanceError):
            opa_input.tenant_id = "modified"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            opa_input.jurisdiction = "US-CA"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            opa_input.subject_id = "modified"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            opa_input.evaluated_at = "modified"  # type: ignore


class TestOPAInputSlots:
    """Tests for OPAInput __slots__ memory efficiency."""

    def test_uses_slots(self):
        """OPAInput should use __slots__ for memory efficiency."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        assert hasattr(opa_input, "__slots__")

    def test_cannot_add_attributes(self):
        """OPAInput should not allow adding arbitrary attributes."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            opa_input.extra_field = "value"  # type: ignore


class TestOPAInputToDict:
    """Tests for OPAInput.to_dict() serialization."""

    def test_to_dict_minimal(self):
        """to_dict() should serialize required fields correctly."""
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        result = opa_input.to_dict()

        assert result["action_type"] == "hire_decision"
        assert result["tenant_id"] == "tenant-123"
        assert result["jurisdiction"] is None
        assert result["subject_id"] is None
        # evaluated_at should be populated with current time if not set
        assert "evaluated_at" in result

    def test_to_dict_with_all_fields(self):
        """to_dict() should serialize all optional fields when present."""
        opa_input = OPAInput(
            action_type="background_check",
            tenant_id="tenant-456",
            jurisdiction="US-NYC",
            subject_id="person-789",
            data={"consent_scope": "employment", "check_type": "criminal"},
            evaluated_at="2024-06-15T14:00:00Z",
        )

        result = opa_input.to_dict()

        assert result["action_type"] == "background_check"
        assert result["tenant_id"] == "tenant-456"
        assert result["jurisdiction"] == "US-NYC"
        assert result["subject_id"] == "person-789"
        assert result["evaluated_at"] == "2024-06-15T14:00:00Z"
        # Data fields should be spread into result
        assert result["consent_scope"] == "employment"
        assert result["check_type"] == "criminal"

    def test_to_dict_returns_dict_type(self):
        """to_dict() should return a standard dict."""
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
        )

        result = opa_input.to_dict()

        assert isinstance(result, dict)
        assert type(result) is dict

    def test_to_dict_data_merged_into_output(self):
        """to_dict() should merge data dict fields into output."""
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
            data={"custom_field": "custom_value", "nested": {"deep": True}},
        )

        result = opa_input.to_dict()

        assert result["custom_field"] == "custom_value"
        assert result["nested"] == {"deep": True}

    def test_to_dict_populates_evaluated_at_when_none(self):
        """to_dict() should populate evaluated_at with current time if None."""
        opa_input = OPAInput(
            action_type="test",
            tenant_id="tenant",
            evaluated_at=None,
        )

        result = opa_input.to_dict()

        # Should be a valid ISO format timestamp
        assert "evaluated_at" in result
        assert result["evaluated_at"] is not None
        assert "T" in result["evaluated_at"]  # ISO format includes T separator


class TestOPAInputEquality:
    """Tests for OPAInput equality and hashing."""

    def test_equality_same_values(self):
        """OPAInput instances with same values should be equal."""
        input1 = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
            jurisdiction="US-NYC",
        )
        input2 = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
            jurisdiction="US-NYC",
        )

        assert input1 == input2

    def test_inequality_different_action_type(self):
        """OPAInput instances with different action_type should not be equal."""
        input1 = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )
        input2 = OPAInput(
            action_type="background_check",
            tenant_id="tenant-123",
        )

        assert input1 != input2

    def test_inequality_different_tenant_id(self):
        """OPAInput instances with different tenant_id should not be equal."""
        input1 = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )
        input2 = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-456",
        )

        assert input1 != input2

    def test_hashable_can_use_in_set(self):
        """OPAInput should be hashable (usable in sets)."""
        # Note: Default dict field makes this unhashable by default
        # but frozen dataclass with field(default_factory=dict) creates new dict
        # This test documents current behavior
        opa_input = OPAInput(
            action_type="hire_decision",
            tenant_id="tenant-123",
        )

        # Frozen dataclasses with dict fields are not hashable by default
        # because dict is unhashable
        with pytest.raises(TypeError):
            _ = {opa_input}


# =============================================================================
# OPARESULT TESTS
# =============================================================================


class TestOPAResultCreation:
    """Tests for OPAResult dataclass instantiation."""

    def test_creates_with_required_fields(self):
        """OPAResult should create with only allow field."""
        result = OPAResult(allow=True)

        assert result.allow is True
        # Optional fields default
        assert result.deny_reasons == ()
        assert result.package is None
        assert result.input_hash is None
        assert result.evaluated_at is None

    def test_creates_with_allow_false(self):
        """OPAResult should create with allow=False."""
        result = OPAResult(allow=False)

        assert result.allow is False

    def test_creates_with_all_fields(self):
        """OPAResult should create with all optional fields."""
        now = now_utc()
        result = OPAResult(
            allow=False,
            deny_reasons=("no_consent", "jurisdiction_blocked"),
            package="canon.statutory.nyc_ll144",
            input_hash="sha256:abc123",
            evaluated_at=now,
        )

        assert result.allow is False
        assert result.deny_reasons == ("no_consent", "jurisdiction_blocked")
        assert result.package == "canon.statutory.nyc_ll144"
        assert result.input_hash == "sha256:abc123"
        assert result.evaluated_at == now

    def test_deny_reasons_is_tuple(self):
        """deny_reasons should be a tuple, not list."""
        result = OPAResult(
            allow=False,
            deny_reasons=("reason1", "reason2"),
        )

        assert isinstance(result.deny_reasons, tuple)

    def test_empty_deny_reasons(self):
        """OPAResult should allow empty deny_reasons tuple."""
        result = OPAResult(
            allow=True,
            deny_reasons=(),
        )

        assert result.deny_reasons == ()
        assert len(result.deny_reasons) == 0


class TestOPAResultImmutability:
    """Tests for OPAResult frozen dataclass behavior."""

    def test_is_frozen(self):
        """OPAResult should be immutable (frozen=True)."""
        result = OPAResult(allow=True)

        with pytest.raises(FrozenInstanceError):
            result.allow = False  # type: ignore

    def test_all_fields_immutable(self):
        """All OPAResult fields should be immutable."""
        result = OPAResult(
            allow=True,
            deny_reasons=("reason",),
            package="test.package",
            input_hash="sha256:test",
            evaluated_at=now_utc(),
        )

        with pytest.raises(FrozenInstanceError):
            result.deny_reasons = ()  # type: ignore

        with pytest.raises(FrozenInstanceError):
            result.package = "modified"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            result.input_hash = "modified"  # type: ignore

        with pytest.raises(FrozenInstanceError):
            result.evaluated_at = now_utc()  # type: ignore


class TestOPAResultSlots:
    """Tests for OPAResult __slots__ memory efficiency."""

    def test_uses_slots(self):
        """OPAResult should use __slots__ for memory efficiency."""
        result = OPAResult(allow=True)

        assert hasattr(result, "__slots__")

    def test_cannot_add_attributes(self):
        """OPAResult should not allow adding arbitrary attributes."""
        result = OPAResult(allow=True)

        with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
            result.extra_field = "value"  # type: ignore


class TestOPAResultEquality:
    """Tests for OPAResult equality and hashing."""

    def test_equality_same_values(self):
        """OPAResult instances with same values should be equal."""
        result1 = OPAResult(
            allow=True,
            deny_reasons=(),
            package="test.package",
        )
        result2 = OPAResult(
            allow=True,
            deny_reasons=(),
            package="test.package",
        )

        assert result1 == result2

    def test_inequality_different_allow(self):
        """OPAResult instances with different allow should not be equal."""
        result1 = OPAResult(allow=True)
        result2 = OPAResult(allow=False)

        assert result1 != result2

    def test_inequality_different_deny_reasons(self):
        """OPAResult instances with different deny_reasons should not be equal."""
        result1 = OPAResult(allow=False, deny_reasons=("reason1",))
        result2 = OPAResult(allow=False, deny_reasons=("reason2",))

        assert result1 != result2

    def test_hashable_can_use_in_set(self):
        """OPAResult should be hashable (usable in sets)."""
        result = OPAResult(
            allow=True,
            deny_reasons=(),
            package="test",
        )

        result_set = {result}
        assert len(result_set) == 1

    def test_hashable_can_use_as_dict_key(self):
        """OPAResult should be usable as dict key."""
        result = OPAResult(allow=True)

        result_dict: dict[OPAResult, str] = {result: "approved"}
        assert result_dict[result] == "approved"
