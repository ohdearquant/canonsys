"""Tests for Pile collection - thread-safe typed collection with rich query interface."""

from __future__ import annotations

from uuid import uuid4

import pytest

from kron.core.element import Element
from kron.core.pile import Pile
from kron.core.progression import Progression
from kron.errors import ExistsError, NotFoundError


class TestPileCreation:
    """Test Pile initialization."""

    def test_empty_pile_creation(self):
        """Empty Pile should be valid."""
        pile = Pile()

        assert len(pile) == 0
        assert pile.is_empty()

    def test_pile_with_items(self, multiple_elements):
        """Pile should accept initial items."""
        pile = Pile(items=multiple_elements)

        assert len(pile) == 5
        assert not pile.is_empty()

    def test_pile_with_item_type(self, multiple_elements):
        """Pile should validate item types."""
        pile = Pile(items=multiple_elements, item_type=Element)

        assert pile.item_type == {Element}

    def test_pile_with_strict_type(self, multiple_elements):
        """Pile with strict_type should reject subclasses."""
        pile = Pile(items=multiple_elements, item_type=Element, strict_type=True)

        assert pile.strict_type is True


class TestPileCoreOperations:
    """Test Pile core CRUD operations."""

    def test_add_item(self):
        """add() should append item to pile."""
        pile = Pile()
        elem = Element()

        pile.add(elem)

        assert len(pile) == 1
        assert elem in pile

    def test_add_duplicate_raises(self):
        """add() should raise ExistsError for duplicate."""
        pile = Pile()
        elem = Element()

        pile.add(elem)
        with pytest.raises(ExistsError):
            pile.add(elem)

    def test_remove_item(self):
        """remove() should remove and return item."""
        elem = Element()
        pile = Pile(items=[elem])

        removed = pile.remove(elem.id)

        assert removed.id == elem.id
        assert len(pile) == 0

    def test_remove_not_found_raises(self):
        """remove() should raise NotFoundError if not found."""
        pile = Pile()
        with pytest.raises(NotFoundError):
            pile.remove(uuid4())

    def test_get_item(self, multiple_elements):
        """get() should return item by ID."""
        pile = Pile(items=multiple_elements)
        target = multiple_elements[2]

        result = pile.get(target.id)

        assert result.id == target.id

    def test_get_not_found_with_default(self):
        """get() with default should return default if not found."""
        pile = Pile()
        result = pile.get(uuid4(), default="missing")

        assert result == "missing"

    def test_get_not_found_raises_without_default(self):
        """get() should raise NotFoundError if not found and no default."""
        pile = Pile()
        with pytest.raises(NotFoundError):
            pile.get(uuid4())

    def test_update_item(self, multiple_elements):
        """update() should replace existing item."""
        pile = Pile(items=multiple_elements)
        original = multiple_elements[0]

        # Create new element with same ID
        updated = Element(id=original.id, metadata={"updated": True})
        pile.update(updated)

        result = pile.get(original.id)
        assert result.metadata.get("updated") is True

    def test_update_not_found_raises(self):
        """update() should raise NotFoundError if not found."""
        pile = Pile()
        with pytest.raises(NotFoundError):
            pile.update(Element())

    def test_clear(self, multiple_elements):
        """clear() should remove all items."""
        pile = Pile(items=multiple_elements)

        pile.clear()

        assert len(pile) == 0
        assert pile.is_empty()

    def test_pop_item(self, multiple_elements):
        """pop() should remove and return item."""
        pile = Pile(items=multiple_elements)
        target = multiple_elements[0]

        result = pile.pop(target.id)

        assert result.id == target.id
        assert target.id not in pile

    def test_pop_with_default(self):
        """pop() with default should return default if not found."""
        pile = Pile()
        result = pile.pop(uuid4(), default="missing")

        assert result == "missing"


class TestPileSetLikeOperations:
    """Test Pile set-like operations (include, exclude)."""

    def test_include_adds_if_not_present(self):
        """include() should add item if not present."""
        pile = Pile()
        elem = Element()

        result = pile.include(elem)

        assert result is True
        assert elem in pile

    def test_include_idempotent_if_present(self):
        """include() should be idempotent for existing items."""
        elem = Element()
        pile = Pile(items=[elem])

        result = pile.include(elem)

        assert result is True
        assert len(pile) == 1

    def test_exclude_removes_if_present(self):
        """exclude() should remove item if present."""
        elem = Element()
        pile = Pile(items=[elem])

        result = pile.exclude(elem.id)

        assert result is True
        assert elem not in pile

    def test_exclude_idempotent_if_not_present(self):
        """exclude() should be idempotent for missing items."""
        pile = Pile()

        result = pile.exclude(uuid4())

        assert result is True


class TestPileGetitem:
    """Test Pile __getitem__ type dispatch."""

    def test_getitem_by_uuid(self, multiple_elements):
        """pile[uuid] should return single item."""
        pile = Pile(items=multiple_elements)
        target = multiple_elements[2]

        result = pile[target.id]

        assert result.id == target.id

    def test_getitem_by_string_uuid(self, multiple_elements):
        """pile[str_uuid] should return single item."""
        pile = Pile(items=multiple_elements)
        target = multiple_elements[2]

        result = pile[str(target.id)]

        assert result.id == target.id

    def test_getitem_by_index(self, multiple_elements):
        """pile[int] should return item by position."""
        pile = Pile(items=multiple_elements)

        result = pile[0]

        assert result.id == multiple_elements[0].id

    def test_getitem_by_negative_index(self, multiple_elements):
        """pile[-1] should return last item."""
        pile = Pile(items=multiple_elements)

        result = pile[-1]

        assert result.id == multiple_elements[-1].id

    def test_getitem_by_slice(self, multiple_elements):
        """pile[slice] should return new Pile."""
        pile = Pile(items=multiple_elements)

        result = pile[1:3]

        assert isinstance(result, Pile)
        assert len(result) == 2

    def test_getitem_by_list_of_indices(self, multiple_elements):
        """pile[[0, 2]] should return Pile with selected items."""
        pile = Pile(items=multiple_elements)

        result = pile[[0, 2, 4]]

        assert isinstance(result, Pile)
        assert len(result) == 3

    def test_getitem_by_callable(self, multiple_elements):
        """pile[lambda] should filter items."""
        pile = Pile(items=multiple_elements)

        # Filter items where metadata index is even
        result = pile[lambda x: x.metadata.get("index", 0) % 2 == 0]

        assert isinstance(result, Pile)
        assert len(result) == 3  # indices 0, 2, 4

    def test_getitem_by_progression(self, multiple_elements):
        """pile[Progression] should return items in progression order."""
        pile = Pile(items=multiple_elements)
        prog = Progression(order=[multiple_elements[2].id, multiple_elements[0].id])

        result = pile[prog]

        assert isinstance(result, Pile)
        assert len(result) == 2


class TestPileIteration:
    """Test Pile iteration and queries."""

    def test_iter_yields_items_in_order(self, multiple_elements):
        """Iteration should yield items in insertion order."""
        pile = Pile(items=multiple_elements)

        iterated = list(pile)

        assert len(iterated) == 5
        for i, elem in enumerate(iterated):
            assert elem.metadata.get("index") == i

    def test_contains_by_id(self, multiple_elements):
        """'in' operator should work with UUID."""
        pile = Pile(items=multiple_elements)
        target = multiple_elements[2]

        assert target.id in pile
        assert target in pile
        assert uuid4() not in pile

    def test_keys_iterator(self, multiple_elements):
        """keys() should yield UUIDs in order."""
        pile = Pile(items=multiple_elements)

        keys = list(pile.keys())

        assert len(keys) == 5
        assert all(isinstance(k, type(multiple_elements[0].id)) for k in keys)

    def test_items_iterator(self, multiple_elements):
        """items() should yield (UUID, item) pairs."""
        pile = Pile(items=multiple_elements)

        for uid, item in pile.items():
            assert uid == item.id


class TestPileSerialization:
    """Test Pile serialization."""

    def test_to_dict_includes_items(self, multiple_elements):
        """to_dict should include serialized items."""
        pile = Pile(items=multiple_elements)

        data = pile.to_dict(mode="json")

        assert "items" in data
        assert len(data["items"]) == 5

    def test_from_dict_roundtrip(self, multiple_elements):
        """from_dict should restore Pile from to_dict output."""
        pile = Pile(items=multiple_elements, item_type=Element)

        data = pile.to_dict(mode="json")
        restored = Pile.from_dict(data)

        assert len(restored) == 5


class TestPileTypeValidation:
    """Test Pile type validation."""

    def test_add_wrong_type_raises(self):
        """Adding wrong type should raise TypeError."""
        pile = Pile(item_type=Element)

        with pytest.raises(TypeError):
            pile.add("not an element")

    def test_filter_by_type(self, multiple_elements):
        """filter_by_type should return items of specified type."""
        pile = Pile(items=multiple_elements)

        result = pile.filter_by_type(Element)

        assert len(result) == 5
