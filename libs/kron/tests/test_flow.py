"""Tests for canon.kron.core.flow - Items + Progressions container."""

import pytest

from kron.core import Element, Flow, Pile, Progression
from kron.errors import ExistsError, NotFoundError

from .conftest import TestElement


class TestFlowCreation:
    """Test Flow instantiation."""

    def test_empty_flow(self):
        """Empty Flow should have empty items and progressions."""
        flow = Flow()
        assert len(flow.items) == 0
        assert len(flow.progressions) == 0

    def test_flow_with_items(self, test_elements):
        """Flow should accept items list."""
        flow = Flow(items=test_elements)
        assert len(flow.items) == len(test_elements)

    def test_flow_with_progressions(self):
        """Flow should accept progressions list."""
        prog1 = Progression(name="stage1")
        prog2 = Progression(name="stage2")
        flow = Flow(progressions=[prog1, prog2])

        assert len(flow.progressions) == 2

    def test_flow_with_name(self):
        """Flow should accept optional name."""
        flow = Flow(name="test_workflow")
        assert flow.name == "test_workflow"

    def test_flow_with_pile(self, test_elements):
        """Flow should accept Pile as items."""
        pile = Pile(items=test_elements)
        flow = Flow(items=pile)
        assert len(flow.items) == len(test_elements)

    def test_flow_with_item_type(self):
        """Flow should validate item types."""
        flow = Flow(item_type=TestElement)

        # Should accept TestElement
        elem = TestElement(value=1)
        flow.add_item(elem)

        # Should reject plain Element (via items pile)
        with pytest.raises(TypeError):
            flow.add_item(Element())


class TestFlowItemOperations:
    """Test Flow item management."""

    def test_add_item(self, test_flow):
        """Flow.add_item() should add to items pile."""
        initial_count = len(test_flow.items)
        new_item = TestElement(value=100)
        test_flow.add_item(new_item)

        assert len(test_flow.items) == initial_count + 1
        assert new_item in test_flow.items

    def test_add_item_to_progression(self, test_flow):
        """Flow.add_item() with progressions should update order."""
        new_item = TestElement(value=100)

        # Add progression first
        prog = Progression(name="my_stage")
        test_flow.add_progression(prog)

        # Add item to progression
        test_flow.add_item(new_item, progressions="my_stage")

        # Item should be in the progression
        retrieved_prog = test_flow.get_progression("my_stage")
        assert new_item.id in retrieved_prog

    def test_add_item_to_multiple_progressions(self, test_flow):
        """Flow.add_item() should add to multiple progressions."""
        prog1 = Progression(name="stage1")
        prog2 = Progression(name="stage2")
        test_flow.add_progression(prog1)
        test_flow.add_progression(prog2)

        new_item = TestElement(value=100)
        test_flow.add_item(new_item, progressions=["stage1", "stage2"])

        assert new_item.id in test_flow.get_progression("stage1")
        assert new_item.id in test_flow.get_progression("stage2")

    def test_remove_item(self, test_flow):
        """Flow.remove_item() should remove from items and progressions."""
        first_item = list(test_flow.items)[0]
        initial_count = len(test_flow.items)

        removed = test_flow.remove_item(first_item.id)

        assert removed.id == first_item.id
        assert len(test_flow.items) == initial_count - 1
        assert first_item not in test_flow.items


class TestFlowProgressionOperations:
    """Test Flow progression management."""

    def test_add_progression(self, test_flow):
        """Flow.add_progression() should add progression."""
        prog = Progression(name="new_stage")
        test_flow.add_progression(prog)

        assert prog in test_flow.progressions

    def test_add_progression_duplicate_name_raises(self, test_flow):
        """Flow should reject duplicate progression names."""
        prog1 = Progression(name="same_name")
        prog2 = Progression(name="same_name")

        test_flow.add_progression(prog1)

        with pytest.raises(ExistsError):
            test_flow.add_progression(prog2)

    def test_get_progression_by_name(self, test_flow):
        """Flow.get_progression() should retrieve by name."""
        prog = Progression(name="findable")
        test_flow.add_progression(prog)

        retrieved = test_flow.get_progression("findable")
        assert retrieved.id == prog.id

    def test_get_progression_by_id(self, test_flow):
        """Flow.get_progression() should retrieve by UUID."""
        prog = Progression(name="findable")
        test_flow.add_progression(prog)

        retrieved = test_flow.get_progression(prog.id)
        assert retrieved.id == prog.id

    def test_get_progression_not_found(self, test_flow):
        """Flow.get_progression() should raise KeyError if not found."""
        with pytest.raises(KeyError):
            test_flow.get_progression("nonexistent")

    def test_remove_progression(self, test_flow):
        """Flow.remove_progression() should remove progression."""
        prog = Progression(name="removable")
        test_flow.add_progression(prog)
        initial_count = len(test_flow.progressions)

        removed = test_flow.remove_progression("removable")

        assert removed.id == prog.id
        assert len(test_flow.progressions) == initial_count - 1

    def test_remove_progression_by_id(self, test_flow):
        """Flow.remove_progression() should work with UUID."""
        prog = Progression(name="removable")
        test_flow.add_progression(prog)

        removed = test_flow.remove_progression(prog.id)
        assert removed.id == prog.id


class TestFlowReferentialIntegrity:
    """Test Flow referential integrity validation."""

    def test_progression_with_invalid_uuid_rejected(self, test_flow):
        """Flow should reject progression with UUIDs not in items."""
        from uuid import uuid4

        prog = Progression(name="invalid", order=[uuid4(), uuid4()])

        with pytest.raises(NotFoundError):
            test_flow.add_progression(prog)

    def test_progression_with_valid_uuid_accepted(self, test_flow):
        """Flow should accept progression with valid item UUIDs."""
        item_ids = [item.id for item in list(test_flow.items)[:2]]
        prog = Progression(name="valid", order=item_ids)

        test_flow.add_progression(prog)

        assert prog in test_flow.progressions


class TestFlowSerialization:
    """Test Flow serialization."""

    def test_to_dict(self, test_flow):
        """Flow.to_dict() should serialize items and progressions."""
        data = test_flow.to_dict()

        assert "items" in data
        assert "progressions" in data
        assert "name" in data

    def test_roundtrip(self, test_flow):
        """Serialization roundtrip should preserve flow state."""
        # Add a progression with items
        item_ids = [item.id for item in list(test_flow.items)[:2]]
        prog = Progression(name="test_stage", order=item_ids)
        test_flow.add_progression(prog)

        data = test_flow.to_dict(mode="json")
        restored = Flow.from_dict(data)

        assert len(restored.items) == len(test_flow.items)
        assert len(restored.progressions) == len(test_flow.progressions)


class TestFlowRepr:
    """Test Flow string representation."""

    def test_repr_with_name(self, test_flow):
        """Flow repr should show name if set."""
        test_flow.name = "test_workflow"
        repr_str = repr(test_flow)
        assert "Flow" in repr_str
        assert "test_workflow" in repr_str

    def test_repr_without_name(self):
        """Flow repr should work without name."""
        flow = Flow()
        repr_str = repr(flow)
        assert "Flow" in repr_str
        assert "items=0" in repr_str
