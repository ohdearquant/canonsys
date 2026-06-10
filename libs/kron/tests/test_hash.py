"""Tests for canon.kron.utils._hash - Hash utilities."""

import pytest
from pydantic import BaseModel

from kron.utils._hash import (
    _TYPE_MARKER_DICT,
    _TYPE_MARKER_FROZENSET,
    _TYPE_MARKER_LIST,
    _TYPE_MARKER_PYDANTIC,
    _TYPE_MARKER_SET,
    _TYPE_MARKER_TUPLE,
    _generate_hashable_representation,
    compute_hash,
    hash_obj,
)


class TestGenerateHashableRepresentation:
    """Tests for _generate_hashable_representation."""

    def test_primitives(self):
        assert _generate_hashable_representation(123) == 123
        assert _generate_hashable_representation("abc") == "abc"
        assert _generate_hashable_representation(True) is True
        assert _generate_hashable_representation(None) is None
        assert _generate_hashable_representation(12.34) == 12.34

    def test_list(self):
        rep = _generate_hashable_representation([1, "a", True])
        assert rep == (_TYPE_MARKER_LIST, (1, "a", True))
        rep_empty = _generate_hashable_representation([])
        assert rep_empty == (_TYPE_MARKER_LIST, tuple())
        rep_nested = _generate_hashable_representation([1, [2, 3]])
        expected_nested_list_rep = (_TYPE_MARKER_LIST, (2, 3))
        assert rep_nested == (
            _TYPE_MARKER_LIST,
            (1, expected_nested_list_rep),
        )

    def test_tuple(self):
        rep = _generate_hashable_representation((1, "a", True))
        assert rep == (_TYPE_MARKER_TUPLE, (1, "a", True))
        rep_empty = _generate_hashable_representation(tuple())
        assert rep_empty == (_TYPE_MARKER_TUPLE, tuple())

    def test_dict(self):
        rep = _generate_hashable_representation({"b": 2, "a": 1})
        # Keys are stringified and sorted: ("a",1), ("b",2)
        expected_dict_rep = (
            _TYPE_MARKER_DICT,
            (("a", 1), ("b", 2)),
        )
        assert rep == expected_dict_rep
        rep_empty = _generate_hashable_representation({})
        assert rep_empty == (_TYPE_MARKER_DICT, tuple())

    def test_set_comparable_elements(self):
        rep = _generate_hashable_representation({3, 1, 2})
        assert rep == (_TYPE_MARKER_SET, (1, 2, 3))

    def test_set_uncomparable_elements_fallback_sort(self):
        # Create a set with types that would normally cause TypeError on direct sort
        # For example, int and str.
        # The lambda key sorts by (str(type(x)), str(x))
        # str(type(1)) -> "<class 'int'>", str(1) -> "1"
        # str(type("a")) -> "<class 'str'>", str("a") -> "a"
        # "<class 'int'>" sorts before "<class 'str'>"
        mixed_set = {1, "a"}
        rep = _generate_hashable_representation(mixed_set)
        # Expected order: 1 (as int), then "a" (as str)
        assert rep == (_TYPE_MARKER_SET, (1, "a"))

        mixed_set_2 = {
            "b",
            2,
            True,
        }  # True will be 1 for sorting purposes with int
        # Order: True (bool, treated like int 1), 2 (int), "b" (str)
        rep2 = _generate_hashable_representation(mixed_set_2)
        assert rep2 == (_TYPE_MARKER_SET, (True, 2, "b"))

    def test_frozenset_comparable_elements(self):
        rep = _generate_hashable_representation(frozenset({3, 1, 2}))
        assert rep == (_TYPE_MARKER_FROZENSET, (1, 2, 3))

    def test_frozenset_uncomparable_elements_fallback_sort(self):
        mixed_frozenset = frozenset({1, "a"})
        rep = _generate_hashable_representation(mixed_frozenset)
        assert rep == (_TYPE_MARKER_FROZENSET, (1, "a"))

    class CustomObjectStr:
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return f"CustomStr({self.value})"

    class CustomObjectRepr:
        def __init__(self, value):
            self.value = value

        def __str__(self):  # Make str fail
            raise TypeError("str failed")

        def __repr__(self):
            return f"CustomRepr({self.value})"

    def test_other_types_str_fallback(self):
        obj = TestGenerateHashableRepresentation.CustomObjectStr("data")
        assert _generate_hashable_representation(obj) == "CustomStr(data)"

    def test_other_types_repr_fallback(self):
        obj = TestGenerateHashableRepresentation.CustomObjectRepr("data")
        assert _generate_hashable_representation(obj) == "CustomRepr(data)"

    class CustomObjectBothFail:
        """Object that fails both str() and repr()."""

        def __init__(self, value):
            self.value = value

        def __str__(self):
            raise RuntimeError("str failed")

        def __repr__(self):
            raise RuntimeError("repr failed")

    def test_other_types_both_str_and_repr_fail(self):
        # Covers fallback when both str() and repr() fail
        obj = TestGenerateHashableRepresentation.CustomObjectBothFail("data")
        result = _generate_hashable_representation(obj)
        # Should return fallback format: "<unhashable:ClassName:id>"
        assert result.startswith("<unhashable:CustomObjectBothFail:")
        assert result.endswith(">")
        assert "CustomObjectBothFail" in result

    def test_pydantic_model_representation(self):
        # Trigger lazy initialization by calling hash_obj (not compute_hash)
        # compute_hash uses JSON serialization, hash_obj uses _generate_hashable_representation
        hash_obj({})

        class MyPydanticModel(BaseModel):
            x: int
            y: str

        model_instance = MyPydanticModel(x=1, y="test")
        # model_dump() -> {"x": 1, "y": "test"}
        # _generate_hashable_representation of this dict:
        # (_TYPE_MARKER_DICT, (("x",1), ("y","test")))
        # Final result: (_TYPE_MARKER_PYDANTIC, above_dict_rep)

        expected_inner_dict_rep = (
            _TYPE_MARKER_DICT,
            (("x", 1), ("y", "test")),  # Keys sorted
        )
        expected_rep = (
            _TYPE_MARKER_PYDANTIC,
            expected_inner_dict_rep,
        )

        assert _generate_hashable_representation(model_instance) == expected_rep


class TestComputeHash:
    """Tests for the main compute_hash function."""

    def test_hash_primitives(self):
        # compute_hash returns hex string, not int
        assert isinstance(compute_hash(123), str)
        assert isinstance(compute_hash("abc"), str)
        assert compute_hash(1) == compute_hash(1)
        assert compute_hash("a") != compute_hash("b")

    def test_hash_dict_deterministic(self):
        d1 = {"a": 1, "b": 2}
        d2 = {"b": 2, "a": 1}  # Same content, different order
        d3 = {"a": 1, "c": 3}
        assert compute_hash(d1) == compute_hash(d2)
        assert compute_hash(d1) != compute_hash(d3)

    def test_hash_list_tuple_deterministic(self):
        l1 = [1, {"a": 10, "b": 20}, 3]
        l2 = [1, {"b": 20, "a": 10}, 3]  # Inner dict order changed
        t1 = (1, {"a": 10, "b": 20}, 3)
        t2 = (1, {"b": 20, "a": 10}, 3)

        assert compute_hash(l1) == compute_hash(l2)
        assert compute_hash(t1) == compute_hash(t2)
        # Note: compute_hash uses JSON serialization, so list and tuple
        # both become JSON arrays and hash the same. Use hash_obj if
        # type-distinguishing hashes are needed.
        assert compute_hash(l1) == compute_hash(t1)

    def test_hash_set_frozenset_deterministic(self):
        s1 = {1, "a", (True, None)}
        s2 = {"a", (True, None), 1}  # Different order
        fs1 = frozenset(s1)
        fs2 = frozenset(s2)

        assert compute_hash(s1) == compute_hash(s2)
        assert compute_hash(fs1) == compute_hash(fs2)
        # Note: compute_hash uses JSON serialization (deterministic_sets=True),
        # so set and frozenset both become sorted JSON arrays and hash the same.
        # Use hash_obj if type-distinguishing hashes are needed.
        assert compute_hash(s1) == compute_hash(fs1)

    def test_hash_pydantic_model_deterministic(self):
        class Model(BaseModel):
            name: str
            value: int

        m1 = Model(name="test", value=1)
        m2 = Model(value=1, name="test")  # Different field order in instantiation
        m3 = Model(name="test", value=2)

        assert compute_hash(m1) == compute_hash(m2)
        assert compute_hash(m1) != compute_hash(m3)

    def test_hash_dict_determinism_across_calls(self):
        # compute_hash is deterministic across calls
        data = {"a": [1, 2]}
        hash1 = compute_hash(data)
        hash2 = compute_hash(data)
        assert hash1 == hash2

        # Mutation changes the hash
        data["a"].append(3)
        hash3 = compute_hash(data)
        assert hash1 != hash3


class TestHashObj:
    """Tests for hash_obj function (Python __hash__ protocol)."""

    def test_hash_obj_returns_int(self):
        # hash_obj returns int for Python hash protocol
        assert isinstance(hash_obj(123), int)
        assert isinstance(hash_obj("abc"), int)
        assert hash_obj(1) == hash_obj(1)
        assert hash_obj("a") != hash_obj("b")

    def test_hash_obj_strict_mode(self):
        # Create a mutable object (list) inside a dict
        data_copy_for_hash = {"a": [1, 2]}  # Ensure we hash a copy for comparison

        # Hash with strict=True
        hash_obj(data_copy_for_hash, strict=True)

        # Test it properly, we need to see if the hash of the original, modified object is different.
        original_data_mutated = {"a": [1, 2]}  # Start fresh for this
        hash_before_mutation_strict = hash_obj(original_data_mutated, strict=True)
        original_data_mutated["a"].append(3)  # Mutate it
        hash_after_mutation_strict = hash_obj(original_data_mutated, strict=True)

        assert hash_before_mutation_strict != hash_after_mutation_strict

        # And confirm that if strict was False, the hash would be based on the current state
        original_data_mutated_nostrict = {"a": [1, 2]}
        hash_nostrict_before = hash_obj(original_data_mutated_nostrict, strict=False)
        original_data_mutated_nostrict["a"].append(3)
        hash_nostrict_after = hash_obj(original_data_mutated_nostrict, strict=False)
        assert hash_nostrict_before != hash_nostrict_after

        # Check that the initial strict hash is repeatable
        data_for_repeat = {"a": [1, 2]}
        assert hash_obj(data_for_repeat, strict=True) == hash_obj({"a": [1, 2]}, strict=True)

    def test_unhashable_representation_raises_typeerror(self):
        # This requires _generate_hashable_representation to return something unhashable.
        # The current _generate_hashable_representation is designed to always return hashable tuples/primitives.
        # To test this, we would need to mock _generate_hashable_representation.
        # NOTE: This test is for hash_obj, not compute_hash (which uses JSON serialization).
        import kron.utils._hash as hash_module

        original_generator = hash_module._generate_hashable_representation
        try:
            # Mock _generate_hashable_representation to return a list (which is unhashable)
            def mock_unhashable_generator(item):
                if item == "trigger_unhashable":
                    return [
                        "this",
                        "is",
                        "a",
                        "list",
                    ]  # Lists are not hashable
                return original_generator(item)  # Fallback for other calls

            hash_module._generate_hashable_representation = mock_unhashable_generator

            with pytest.raises(
                TypeError,
                match="The generated representation for the input data was not hashable",
            ):
                hash_obj("trigger_unhashable")

        finally:
            # Restore original function
            hash_module._generate_hashable_representation = original_generator
