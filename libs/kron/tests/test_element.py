"""Tests for Element base class - the foundation for all persistent entities."""

from __future__ import annotations

import datetime as dt
from datetime import UTC
from uuid import UUID, uuid4

import pytest

from kron.core.element import Element


class TestElementCreation:
    """Test Element initialization and default values."""

    def test_element_creation_with_defaults(self):
        """Element should auto-generate id and created_at."""
        elem = Element()

        assert isinstance(elem.id, UUID)
        assert isinstance(elem.created_at, dt.datetime)
        assert elem.created_at.tzinfo is not None  # Should be UTC-aware
        assert elem.metadata == {}

    def test_element_creation_with_custom_id(self):
        """Element should accept custom UUID."""
        custom_id = uuid4()
        elem = Element(id=custom_id)

        assert elem.id == custom_id

    def test_element_creation_with_string_id(self):
        """Element should coerce string to UUID."""
        str_id = "12345678-1234-5678-1234-567812345678"
        elem = Element(id=str_id)

        assert isinstance(elem.id, UUID)
        assert str(elem.id) == str_id

    def test_element_creation_with_metadata(self):
        """Element should accept metadata dict."""
        metadata = {"key": "value", "nested": {"inner": 42}}
        elem = Element(metadata=metadata)

        assert elem.metadata["key"] == "value"
        assert elem.metadata["nested"]["inner"] == 42

    def test_element_creation_with_custom_created_at(self):
        """Element should accept custom created_at datetime."""
        custom_time = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        elem = Element(created_at=custom_time)

        assert elem.created_at == custom_time


class TestElementSerialization:
    """Test Element serialization (to_dict) and deserialization (from_dict)."""

    def test_to_dict_python_mode(self, sample_element):
        """to_dict with python mode should return native types."""
        data = sample_element.to_dict(mode="python")

        assert isinstance(data["id"], UUID)
        assert isinstance(data["created_at"], dt.datetime)
        assert data["metadata"]["test_key"] == "test_value"
        assert "kron_class" in data["metadata"]

    def test_to_dict_json_mode(self, sample_element):
        """to_dict with json mode should return JSON-serializable types."""
        data = sample_element.to_dict(mode="json")

        assert isinstance(data["id"], str)
        assert isinstance(data["created_at"], str)

    def test_to_dict_db_mode(self, sample_element):
        """to_dict with db mode should rename metadata to node_metadata."""
        data = sample_element.to_dict(mode="db")

        assert "node_metadata" in data
        assert "metadata" not in data

    def test_to_dict_custom_meta_key(self, sample_element):
        """to_dict should support custom metadata key name."""
        data = sample_element.to_dict(meta_key="custom_meta")

        assert "custom_meta" in data
        assert "metadata" not in data

    def test_from_dict_roundtrip(self, sample_element):
        """from_dict should restore Element from to_dict output."""
        data = sample_element.to_dict(mode="json")
        restored = Element.from_dict(data)

        assert restored.id == sample_element.id
        assert restored.metadata["test_key"] == "test_value"

    def test_from_dict_with_node_metadata_key(self, sample_element):
        """from_dict should handle node_metadata key from db mode."""
        data = sample_element.to_dict(mode="db")
        restored = Element.from_dict(data, meta_key="node_metadata")

        assert restored.id == sample_element.id
        assert "test_key" in restored.metadata


class TestElementEquality:
    """Test Element equality and hashing."""

    def test_elements_with_same_id_are_equal(self):
        """Elements with same ID should be equal."""
        shared_id = uuid4()
        elem1 = Element(id=shared_id, metadata={"a": 1})
        elem2 = Element(id=shared_id, metadata={"b": 2})

        assert elem1 == elem2

    def test_elements_with_different_id_are_not_equal(self):
        """Elements with different IDs should not be equal."""
        elem1 = Element()
        elem2 = Element()

        assert elem1 != elem2

    def test_element_hash_is_based_on_id(self):
        """Element hash should be based on ID."""
        shared_id = uuid4()
        elem1 = Element(id=shared_id)
        elem2 = Element(id=shared_id)

        assert hash(elem1) == hash(elem2)

    def test_elements_can_be_used_in_set(self):
        """Elements should work in sets based on ID."""
        shared_id = uuid4()
        elem1 = Element(id=shared_id)
        elem2 = Element(id=shared_id)
        elem3 = Element()

        elements = {elem1, elem2, elem3}
        assert len(elements) == 2  # elem1 and elem2 are same ID


class TestElementPolymorphism:
    """Test Element polymorphic serialization via kron_class."""

    def test_kron_class_is_injected_in_metadata(self):
        """to_dict should inject kron_class in metadata."""
        elem = Element()
        data = elem.to_dict()

        assert "kron_class" in data["metadata"]
        assert "Element" in data["metadata"]["kron_class"]

    def test_class_name_short(self):
        """class_name() should return short class name."""
        assert Element.class_name() == "Element"

    def test_class_name_full(self):
        """class_name(full=True) should return full module path."""
        full_name = Element.class_name(full=True)
        assert "kron.core.element.Element" in full_name

    def test_element_is_always_truthy(self):
        """Element should always be truthy."""
        elem = Element()
        assert bool(elem) is True


class TestElementValidation:
    """Test Element field validation."""

    def test_invalid_id_raises_error(self):
        """Invalid UUID string should raise ValueError."""
        with pytest.raises(ValueError):
            Element(id="not-a-uuid")

    def test_invalid_metadata_type_raises_error(self):
        """Non-dict metadata should raise ValueError."""
        with pytest.raises(ValueError):
            Element(metadata="not-a-dict")

    def test_frozen_id_cannot_be_changed(self):
        """id field should be frozen (immutable)."""
        elem = Element()
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            elem.id = uuid4()

    def test_frozen_created_at_cannot_be_changed(self):
        """created_at field should be frozen (immutable)."""
        elem = Element()
        with pytest.raises(Exception):
            elem.created_at = dt.datetime.now(UTC)
