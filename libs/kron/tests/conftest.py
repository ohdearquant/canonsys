"""Root conftest.py - shared test fixtures for all kron tests.

This module provides reusable test fixtures, factories, and strategies for
testing kron runtime primitives.

Usage:
    def test_with_element(element_fixture):
        assert element_fixture.id is not None

    def test_with_pile(test_pile):
        assert len(test_pile) == 5
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel

from kron.core import Edge, Element, Event, Flow, Graph, Node, Pile, Progression
from kron.core.event import EventStatus

# Add tests/ directory to sys.path
_tests_dir = Path(__file__).parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))


# =============================================================================
# Security: Register test module prefixes for dynamic type loading
# =============================================================================


@pytest.fixture(autouse=True, scope="session")
def register_test_type_prefixes():
    """Register test module prefixes for dynamic type loading (session-scoped)."""
    from kron.utils._utils import _ALLOWED_MODULE_PREFIXES

    test_prefixes = {"test_", "tests.", "conftest."}
    for prefix in test_prefixes:
        _ALLOWED_MODULE_PREFIXES.add(prefix)
    yield
    for prefix in test_prefixes:
        _ALLOWED_MODULE_PREFIXES.discard(prefix)


# =============================================================================
# Test Classes
# =============================================================================


class TestElement(Element):
    """Simple Element subclass for testing."""

    __test__ = False  # Tell pytest not to collect this as a test class

    value: int = 0
    name: str = "test"


class SimpleTestEvent(Event):
    """Simple Event that returns a configurable value."""

    return_value: Any = None
    streaming: bool = False

    async def _invoke(self) -> Any:
        return self.return_value


class FailingTestEvent(Event):
    """Event that raises a configurable exception."""

    error_message: str = "Test error"
    error_type: type[Exception] = ValueError
    streaming: bool = False

    async def _invoke(self) -> Any:
        raise self.error_type(self.error_message)


class SlowTestEvent(Event):
    """Event that takes time to complete."""

    delay: float = 0.1
    return_value: Any = "completed"
    streaming: bool = False

    async def _invoke(self) -> Any:
        import anyio

        await anyio.sleep(self.delay)
        return self.return_value


class StreamingTestEvent(Event):
    """Event that yields values via async generator."""

    stream_count: int = 3
    streaming: bool = True

    async def _invoke(self) -> Any:
        raise NotImplementedError("Use stream() instead")

    async def stream(self):
        import anyio

        for i in range(self.stream_count):
            await anyio.sleep(0.01)
            yield i
        self.execution.status = EventStatus.COMPLETED
        self.execution.response = f"streamed {self.stream_count} items"


class SampleContent(BaseModel):
    """Sample content model for testing."""

    title: str
    count: int = 0
    tags: list[str] | None = None


__all__ = (
    "FailingTestEvent",
    "SampleContent",
    "SimpleTestEvent",
    "SlowTestEvent",
    "StreamingTestEvent",
    "TestElement",
    "create_cyclic_graph",
    "create_dag_graph",
    "create_empty_graph",
    "create_simple_graph",
    "create_test_elements",
    "create_test_flow",
    "create_test_nodes",
    "create_test_pile",
    "create_test_progression",
    "create_typed_pile",
    "mock_element",
    "mock_node",
)


# =============================================================================
# Factory Functions
# =============================================================================


def mock_element(
    *,
    value: int = 0,
    name: str = "test",
    metadata: dict[str, Any] | None = None,
) -> TestElement:
    """Create a single mock Element for testing."""
    elem = TestElement(value=value, name=name)
    if metadata:
        elem.metadata.update(metadata)
    return elem


def mock_node(
    *,
    content: dict[str, Any] | BaseModel | None = None,
    value: str = "test",
) -> Node:
    """Create a single mock Node for testing."""
    if content is None:
        content = {"value": value}
    return Node(content=content)


def create_test_elements(count: int = 5, start_value: int = 0) -> list[TestElement]:
    """Create a list of test Elements."""
    return [TestElement(value=start_value + i, name=f"element_{i}") for i in range(count)]


def create_test_nodes(count: int = 5) -> list[Node]:
    """Create a list of test Nodes."""
    return [Node(content={"value": f"node_{i}"}) for i in range(count)]


def create_test_pile(
    count: int = 5,
    *,
    item_type: type | None = None,
    strict_type: bool = False,
) -> Pile[TestElement]:
    """Create a test Pile with mock elements."""
    items = create_test_elements(count=count)
    return Pile(items=items, item_type=item_type, strict_type=strict_type)


def create_typed_pile(
    items: list[Element],
    *,
    item_type: type | set[type] | None = None,
    strict_type: bool = False,
) -> Pile:
    """Create a Pile with custom items and type constraints."""
    return Pile(items=items, item_type=item_type, strict_type=strict_type)


def create_test_progression(
    items: list[Element] | None = None,
    name: str = "test_progression",
) -> Progression:
    """Create a test Progression from items."""
    if items is None:
        items = create_test_elements(count=5)
    return Progression(order=[item.id for item in items], name=name)


def create_test_flow(
    item_count: int = 5,
    progression_count: int = 2,
) -> Flow[TestElement, Progression]:
    """Create a test Flow with elements and progressions."""
    items = create_test_elements(count=item_count)
    progressions = [Progression(name=f"prog_{i}", order=[]) for i in range(progression_count)]
    return Flow(items=items, progressions=progressions, item_type=TestElement)


def create_empty_graph() -> Graph:
    """Create an empty Graph for testing."""
    return Graph()


def create_simple_graph() -> tuple[Graph, list[Node]]:
    """Create a simple graph with 3 nodes in a chain: A -> B -> C."""
    graph = Graph()
    n1 = Node(content={"value": "A"})
    n2 = Node(content={"value": "B"})
    n3 = Node(content={"value": "C"})
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_edge(Edge(head=n1.id, tail=n2.id))
    graph.add_edge(Edge(head=n2.id, tail=n3.id))
    return graph, [n1, n2, n3]


def create_cyclic_graph() -> tuple[Graph, list[Node]]:
    """Create a graph with a cycle: A -> B -> C -> A."""
    graph = Graph()
    n1 = Node(content={"value": "A"})
    n2 = Node(content={"value": "B"})
    n3 = Node(content={"value": "C"})
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_edge(Edge(head=n1.id, tail=n2.id))
    graph.add_edge(Edge(head=n2.id, tail=n3.id))
    graph.add_edge(Edge(head=n3.id, tail=n1.id))
    return graph, [n1, n2, n3]


def create_dag_graph() -> tuple[Graph, list[Node]]:
    """Create a DAG: A -> B -> D, A -> C -> D."""
    graph = Graph()
    n1 = Node(content={"value": "A"})
    n2 = Node(content={"value": "B"})
    n3 = Node(content={"value": "C"})
    n4 = Node(content={"value": "D"})
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_node(n4)
    graph.add_edge(Edge(head=n1.id, tail=n2.id))
    graph.add_edge(Edge(head=n1.id, tail=n3.id))
    graph.add_edge(Edge(head=n2.id, tail=n4.id))
    graph.add_edge(Edge(head=n3.id, tail=n4.id))
    return graph, [n1, n2, n3, n4]


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def element_fixture() -> TestElement:
    """Create a single mock Element for testing."""
    return TestElement(value=0, name="test")


@pytest.fixture
def sample_element() -> Element:
    """Create a sample Element instance."""
    return Element(metadata={"test_key": "test_value"})


@pytest.fixture
def node_fixture() -> Node:
    """Create a single mock Node for testing."""
    return Node(content={"value": "test"})


@pytest.fixture
def sample_node() -> Node:
    """Create a sample Node instance."""
    return Node(content={"key": "value"}, metadata={"node_type": "test"})


@pytest.fixture
def sample_content() -> SampleContent:
    """Create a sample content instance."""
    return SampleContent(title="Test Title", count=42, tags=["a", "b"])


@pytest.fixture
def sample_uuid():
    """Generate a sample UUID."""
    return uuid4()


@pytest.fixture
def test_elements() -> list[TestElement]:
    """Create a list of 5 test Elements."""
    return create_test_elements(count=5)


@pytest.fixture
def multiple_elements() -> list[Element]:
    """Create multiple Element instances for collection tests."""
    return [Element(metadata={"index": i}) for i in range(5)]


@pytest.fixture
def test_nodes() -> list[Node]:
    """Create a list of 5 test Nodes."""
    return create_test_nodes(count=5)


@pytest.fixture
def test_pile() -> Pile[TestElement]:
    """Create a test Pile with 5 elements."""
    return create_test_pile(count=5)


@pytest.fixture
def test_progression(test_elements) -> Progression:
    """Create a test Progression from test_elements."""
    return create_test_progression(items=test_elements)


@pytest.fixture
def test_flow() -> Flow[TestElement, Progression]:
    """Create a test Flow with 5 items and 2 progressions."""
    return create_test_flow(item_count=5, progression_count=2)


@pytest.fixture
def empty_graph() -> Graph:
    """Create an empty Graph."""
    return create_empty_graph()


@pytest.fixture
def simple_graph() -> tuple[Graph, list[Node]]:
    """Create a simple chain graph: A -> B -> C."""
    return create_simple_graph()


@pytest.fixture
def cyclic_graph() -> tuple[Graph, list[Node]]:
    """Create a cyclic graph: A -> B -> C -> A."""
    return create_cyclic_graph()


@pytest.fixture
def dag_graph() -> tuple[Graph, list[Node]]:
    """Create a DAG graph."""
    return create_dag_graph()


@pytest.fixture
def simple_event() -> SimpleTestEvent:
    """Create a SimpleTestEvent with default value."""
    return SimpleTestEvent(return_value="test_result")


@pytest.fixture
def failing_event() -> FailingTestEvent:
    """Create a FailingTestEvent."""
    return FailingTestEvent(error_message="Test error")


@pytest.fixture
def slow_event() -> SlowTestEvent:
    """Create a SlowTestEvent with 0.1s delay."""
    return SlowTestEvent(delay=0.1)


@pytest.fixture
def streaming_event() -> StreamingTestEvent:
    """Create a StreamingTestEvent with 3 items."""
    return StreamingTestEvent(stream_count=3)
