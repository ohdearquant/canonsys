"""Tests for kron utility functions."""

from __future__ import annotations

import datetime as dt
from datetime import UTC
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from kron.types import (
    Undefined,
    UndefinedType,
    Unset,
    UnsetType,
    is_sentinel,
    is_undefined,
    is_unset,
    not_sentinel,
)
from kron.utils import (
    coerce_created_at,
    compute_chain_hash,
    compute_hash,
    extract_types,
    hash_obj,
    now_utc,
    to_uuid,
)


class TestNowUtc:
    """Test now_utc utility."""

    def test_returns_datetime(self):
        """now_utc should return datetime."""
        result = now_utc()

        assert isinstance(result, dt.datetime)

    def test_is_utc_aware(self):
        """now_utc should return UTC-aware datetime."""
        result = now_utc()

        assert result.tzinfo is not None
        assert result.tzinfo == UTC


class TestToUuid:
    """Test to_uuid coercion utility."""

    def test_uuid_passthrough(self):
        """UUID input should pass through unchanged."""
        uid = uuid4()
        result = to_uuid(uid)

        assert result is uid

    def test_string_to_uuid(self):
        """String UUID should be converted."""
        str_uuid = "12345678-1234-5678-1234-567812345678"
        result = to_uuid(str_uuid)

        assert isinstance(result, UUID)
        assert str(result) == str_uuid

    def test_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            to_uuid("not-a-uuid")

    def test_invalid_type_raises(self):
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError):
            to_uuid(42)


class TestCoerceCreatedAt:
    """Test coerce_created_at datetime utility."""

    def test_datetime_passthrough(self):
        """UTC datetime should pass through."""
        original = dt.datetime.now(UTC)
        result = coerce_created_at(original)

        assert result == original

    def test_naive_datetime_gets_utc(self):
        """Naive datetime should get UTC timezone."""
        naive = dt.datetime(2024, 1, 1, 12, 0, 0)
        result = coerce_created_at(naive)

        assert result.tzinfo == UTC

    def test_unix_timestamp_int(self):
        """Unix timestamp int should be converted."""
        timestamp = 1704110400  # 2024-01-01 12:00:00 UTC
        result = coerce_created_at(timestamp)

        assert isinstance(result, dt.datetime)
        assert result.tzinfo == UTC

    def test_unix_timestamp_float(self):
        """Unix timestamp float should be converted."""
        timestamp = 1704110400.5
        result = coerce_created_at(timestamp)

        assert isinstance(result, dt.datetime)

    def test_iso_string(self):
        """ISO format string should be converted."""
        iso_str = "2024-01-01T12:00:00"
        result = coerce_created_at(iso_str)

        assert isinstance(result, dt.datetime)

    def test_timestamp_string(self):
        """Timestamp as string should be converted."""
        timestamp_str = "1704110400"
        result = coerce_created_at(timestamp_str)

        assert isinstance(result, dt.datetime)

    def test_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            coerce_created_at("not-a-date")

    def test_invalid_type_raises(self):
        """Invalid type should raise ValueError."""
        with pytest.raises(ValueError):
            coerce_created_at([2024, 1, 1])


class TestExtractTypes:
    """Test extract_types utility."""

    def test_single_type(self):
        """Single type should return set with one type."""
        result = extract_types(str)

        assert result == {str}

    def test_set_of_types(self):
        """Set of types should pass through."""
        types = {str, int}
        result = extract_types(types)

        assert result == types

    def test_list_of_types(self):
        """List of types should be converted to set."""
        types = [str, int, float]
        result = extract_types(types)

        assert result == {str, int, float}

    def test_union_type(self):
        """Union type should be extracted."""
        from typing import Union

        result = extract_types(Union[str, int])

        assert result == {str, int}

    def test_pipe_union(self):
        """Python 3.10+ pipe union should be extracted."""
        result = extract_types(str | int)

        assert result == {str, int}


class TestComputeHash:
    """Test compute_hash cryptographic hash utility."""

    def test_hash_dict(self):
        """Dict should be hashed deterministically."""
        data = {"key": "value", "number": 42}

        result = compute_hash(data)

        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex

    def test_hash_string(self):
        """String should be hashed."""
        data = "test string"

        result = compute_hash(data)

        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_bytes(self):
        """Bytes should be hashed."""
        data = b"test bytes"

        result = compute_hash(data)

        assert isinstance(result, str)
        assert len(result) == 64

    def test_hash_none_with_flag(self):
        """None should be hashable with none_as_valid=True."""
        result = compute_hash(None, none_as_valid=True)

        assert isinstance(result, str)

    def test_hash_deterministic(self):
        """Same input should produce same hash."""
        data = {"a": 1, "b": 2}

        hash1 = compute_hash(data)
        hash2 = compute_hash(data)

        assert hash1 == hash2

    def test_hash_order_independent(self):
        """Dict order should not affect hash."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}

        hash1 = compute_hash(data1)
        hash2 = compute_hash(data2)

        assert hash1 == hash2


class TestComputeChainHash:
    """Test compute_chain_hash for tamper-evident chains."""

    def test_chain_hash_with_previous(self):
        """Chain hash should incorporate previous hash."""
        payload_hash = compute_hash({"data": "test"})
        previous_hash = compute_hash({"prev": "data"})

        result = compute_chain_hash(payload_hash, previous_hash)

        assert isinstance(result, str)
        assert len(result) == 64

    def test_chain_hash_genesis(self):
        """Genesis entry should use GENESIS sentinel."""
        payload_hash = compute_hash({"data": "test"})

        result = compute_chain_hash(payload_hash, None)

        assert isinstance(result, str)

    def test_chain_hash_deterministic(self):
        """Same inputs should produce same chain hash."""
        payload_hash = compute_hash({"data": "test"})
        previous_hash = compute_hash({"prev": "data"})

        hash1 = compute_chain_hash(payload_hash, previous_hash)
        hash2 = compute_chain_hash(payload_hash, previous_hash)

        assert hash1 == hash2


class TestHashObj:
    """Test hash_obj for Python __hash__ protocol."""

    def test_hash_simple_dict(self):
        """Simple dict should be hashable."""
        data = {"key": "value"}

        result = hash_obj(data)

        assert isinstance(result, int)

    def test_hash_nested_dict(self):
        """Nested dict should be hashable."""
        data = {"outer": {"inner": {"deep": 42}}}

        result = hash_obj(data)

        assert isinstance(result, int)

    def test_hash_list(self):
        """List should be hashable."""
        data = [1, 2, 3, "test"]

        result = hash_obj(data)

        assert isinstance(result, int)

    def test_hash_pydantic_model(self):
        """Pydantic model should be hashable."""

        class TestModel(BaseModel):
            name: str
            value: int

        model = TestModel(name="test", value=42)

        result = hash_obj(model)

        assert isinstance(result, int)

    def test_hash_stable_for_same_data(self):
        """Same data should produce same hash."""
        data = {"a": [1, 2, 3], "b": {"nested": True}}

        hash1 = hash_obj(data)
        hash2 = hash_obj(data)

        assert hash1 == hash2


class TestSentinels:
    """Test sentinel types (Undefined, Unset)."""

    def test_undefined_is_singleton(self):
        """Undefined should be singleton."""
        u1 = UndefinedType()
        u2 = UndefinedType()

        assert u1 is u2
        assert u1 is Undefined

    def test_unset_is_singleton(self):
        """Unset should be singleton."""
        u1 = UnsetType()
        u2 = UnsetType()

        assert u1 is u2
        assert u1 is Unset

    def test_undefined_is_falsy(self):
        """Undefined should be falsy."""
        assert bool(Undefined) is False

    def test_unset_is_falsy(self):
        """Unset should be falsy."""
        assert bool(Unset) is False

    def test_is_undefined(self):
        """is_undefined should detect Undefined."""
        assert is_undefined(Undefined) is True
        assert is_undefined(Unset) is False
        assert is_undefined(None) is False
        assert is_undefined("value") is False

    def test_is_unset(self):
        """is_unset should detect Unset."""
        assert is_unset(Unset) is True
        assert is_unset(Undefined) is False
        assert is_unset(None) is False
        assert is_unset("value") is False

    def test_is_sentinel_detects_both(self):
        """is_sentinel should detect both sentinels."""
        assert is_sentinel(Undefined) is True
        assert is_sentinel(Unset) is True
        assert is_sentinel(None) is False

    def test_is_sentinel_with_none_addition(self):
        """is_sentinel with none addition should detect None."""
        assert is_sentinel(None, additions={"none"}) is True
        assert is_sentinel(None, additions=frozenset()) is False

    def test_is_sentinel_with_empty_addition(self):
        """is_sentinel with empty addition should detect empty containers."""
        assert is_sentinel([], additions={"empty"}) is True
        assert is_sentinel({}, additions={"empty"}) is True
        assert is_sentinel("", additions={"empty"}) is True
        assert is_sentinel([1], additions={"empty"}) is False

    def test_not_sentinel_type_guard(self):
        """not_sentinel should be type guard."""
        value = "real value"

        if not_sentinel(value):
            # Type narrowing should work
            assert len(value) == 10

    def test_undefined_repr(self):
        """Undefined should have readable repr."""
        assert repr(Undefined) == "Undefined"
        assert str(Undefined) == "Undefined"

    def test_unset_repr(self):
        """Unset should have readable repr."""
        assert repr(Unset) == "Unset"
        assert str(Unset) == "Unset"

    def test_sentinels_survive_copy(self):
        """Sentinels should maintain identity after copy."""
        import copy

        assert copy.copy(Undefined) is Undefined
        assert copy.deepcopy(Undefined) is Undefined
        assert copy.copy(Unset) is Unset
        assert copy.deepcopy(Unset) is Unset
