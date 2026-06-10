"""Tests for deterministic hashing."""

import pytest
from pydantic import BaseModel

from kron.utils import MAX_HASH_INPUT_BYTES, compute_chain_hash, compute_hash


class TestComputeHash:
    def test_string_hash(self):
        h = compute_hash("hello")
        assert len(h) == 64  # SHA-256 hex
        assert h == compute_hash("hello")  # Deterministic

    def test_different_strings(self):
        assert compute_hash("hello") != compute_hash("world")

    def test_dict_hash(self):
        h = compute_hash({"a": 1, "b": 2})
        assert len(h) == 64
        # Order independent
        assert h == compute_hash({"b": 2, "a": 1})

    def test_nested_dict(self):
        h = compute_hash({"outer": {"inner": "value"}})
        assert len(h) == 64

    def test_pydantic_model(self):
        class TestModel(BaseModel):
            name: str
            value: int

        m = TestModel(name="test", value=42)
        h = compute_hash(m)
        assert len(h) == 64
        # Same data = same hash
        assert h == compute_hash(TestModel(name="test", value=42))

    def test_empty_string(self):
        h = compute_hash("")
        assert len(h) == 64

    def test_empty_dict(self):
        h = compute_hash({})
        assert len(h) == 64

    def test_list_in_dict(self):
        h = compute_hash({"items": [1, 2, 3]})
        assert len(h) == 64

    def test_set_deterministic(self):
        # Sets should hash deterministically
        h1 = compute_hash({"items": {3, 1, 2}})
        h2 = compute_hash({"items": {1, 2, 3}})
        assert h1 == h2

    def test_datetime_in_dict(self):
        from datetime import datetime

        dt = datetime(2025, 1, 15, 12, 0, 0)
        h = compute_hash({"ts": dt})
        assert len(h) == 64

    def test_uuid_in_dict(self):
        from uuid import UUID

        uid = UUID("12345678-1234-5678-1234-567812345678")
        h = compute_hash({"id": uid})
        assert len(h) == 64


class TestComputeChainHash:
    def test_genesis(self):
        h = compute_chain_hash("abc123", None)
        assert len(h) == 64
        # Should be hash of "abc123:GENESIS"
        assert h == compute_hash("abc123:GENESIS")

    def test_with_previous(self):
        h = compute_chain_hash("payload_hash", "previous_hash")
        assert len(h) == 64
        assert h == compute_hash("payload_hash:previous_hash")

    def test_chain_deterministic(self):
        h1 = compute_chain_hash("a", "b")
        h2 = compute_chain_hash("a", "b")
        assert h1 == h2

    def test_chain_different_inputs(self):
        h1 = compute_chain_hash("a", "b")
        h2 = compute_chain_hash("a", "c")
        assert h1 != h2


class TestSizeLimit:
    def test_constant_value(self):
        assert MAX_HASH_INPUT_BYTES == 10 * 1024 * 1024  # 10 MB

    def test_rejects_oversized(self):
        # Create payload just over limit
        big = "x" * (MAX_HASH_INPUT_BYTES + 1)
        with pytest.raises(ValueError, match="limit"):
            compute_hash(big)

    def test_accepts_under_limit(self):
        # Small payload ok
        h = compute_hash("small")
        assert len(h) == 64
