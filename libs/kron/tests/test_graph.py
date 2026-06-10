"""Tests for canon.kron.core.graph - Directed graph with pathfinding."""

import pytest

from kron.core import Edge, Graph, Node
from kron.errors import ExistsError, NotFoundError


class TestGraphCreation:
    """Test Graph instantiation."""

    def test_empty_graph(self, empty_graph):
        """Empty Graph should have no nodes or edges."""
        assert len(empty_graph.nodes) == 0
        assert len(empty_graph.edges) == 0

    def test_graph_add_node(self, empty_graph):
        """Graph.add_node() should add node."""
        node = Node(content={"value": "test"})
        empty_graph.add_node(node)

        assert node in empty_graph.nodes
        assert len(empty_graph) == 1

    def test_graph_add_duplicate_node_raises(self, empty_graph):
        """Graph.add_node() should raise ExistsError for duplicate."""
        node = Node(content={"value": "test"})
        empty_graph.add_node(node)

        with pytest.raises(ExistsError):
            empty_graph.add_node(node)

    def test_graph_add_edge(self, simple_graph):
        """Graph.add_edge() should connect nodes."""
        graph, nodes = simple_graph
        # Simple graph already has edges A -> B -> C
        assert len(graph.edges) == 2

    def test_graph_add_edge_invalid_head_raises(self, empty_graph):
        """Graph.add_edge() should raise NotFoundError if head not in graph."""
        from uuid import uuid4

        node = Node(content={"value": "tail"})
        empty_graph.add_node(node)

        edge = Edge(head=uuid4(), tail=node.id)
        with pytest.raises(NotFoundError):
            empty_graph.add_edge(edge)

    def test_graph_add_edge_invalid_tail_raises(self, empty_graph):
        """Graph.add_edge() should raise NotFoundError if tail not in graph."""
        from uuid import uuid4

        node = Node(content={"value": "head"})
        empty_graph.add_node(node)

        edge = Edge(head=node.id, tail=uuid4())
        with pytest.raises(NotFoundError):
            empty_graph.add_edge(edge)


class TestGraphNodeOperations:
    """Test Graph node operations."""

    def test_remove_node(self, simple_graph):
        """Graph.remove_node() should remove node and connected edges."""
        graph, nodes = simple_graph
        middle_node = nodes[1]  # B in A -> B -> C
        initial_edge_count = len(graph.edges)

        removed = graph.remove_node(middle_node.id)

        assert removed.id == middle_node.id
        assert middle_node not in graph.nodes
        # Both edges connected to B should be removed
        assert len(graph.edges) < initial_edge_count

    def test_remove_node_not_found_raises(self, empty_graph):
        """Graph.remove_node() should raise NotFoundError."""
        from uuid import uuid4

        with pytest.raises(NotFoundError):
            empty_graph.remove_node(uuid4())


class TestGraphEdgeOperations:
    """Test Graph edge operations."""

    def test_remove_edge(self, simple_graph):
        """Graph.remove_edge() should remove edge."""
        graph, nodes = simple_graph
        edges = list(graph.edges)
        first_edge = edges[0]
        initial_count = len(graph.edges)

        removed = graph.remove_edge(first_edge.id)

        assert removed.id == first_edge.id
        assert len(graph.edges) == initial_count - 1

    def test_remove_edge_not_found_raises(self, empty_graph):
        """Graph.remove_edge() should raise NotFoundError."""
        from uuid import uuid4

        with pytest.raises(NotFoundError):
            empty_graph.remove_edge(uuid4())


class TestGraphTraversal:
    """Test Graph traversal operations."""

    def test_get_predecessors(self, simple_graph):
        """Graph should return predecessor nodes."""
        graph, nodes = simple_graph
        # A -> B -> C, so B's predecessor is A
        predecessors = graph.get_predecessors(nodes[1].id)

        assert len(predecessors) == 1
        assert predecessors[0].id == nodes[0].id

    def test_get_successors(self, simple_graph):
        """Graph should return successor nodes."""
        graph, nodes = simple_graph
        # A -> B -> C, so B's successor is C
        successors = graph.get_successors(nodes[1].id)

        assert len(successors) == 1
        assert successors[0].id == nodes[2].id

    def test_get_heads(self, simple_graph):
        """Graph.get_heads() should return source nodes."""
        graph, nodes = simple_graph
        # A has no incoming edges
        heads = graph.get_heads()

        assert len(heads) == 1
        assert heads[0].id == nodes[0].id

    def test_get_tails(self, simple_graph):
        """Graph.get_tails() should return sink nodes."""
        graph, nodes = simple_graph
        # C has no outgoing edges
        tails = graph.get_tails()

        assert len(tails) == 1
        assert tails[0].id == nodes[2].id

    def test_get_node_edges_in(self, simple_graph):
        """Graph.get_node_edges(direction='in') should return incoming edges."""
        graph, nodes = simple_graph
        in_edges = graph.get_node_edges(nodes[1].id, direction="in")

        assert len(in_edges) == 1
        assert in_edges[0].tail == nodes[1].id

    def test_get_node_edges_out(self, simple_graph):
        """Graph.get_node_edges(direction='out') should return outgoing edges."""
        graph, nodes = simple_graph
        out_edges = graph.get_node_edges(nodes[1].id, direction="out")

        assert len(out_edges) == 1
        assert out_edges[0].head == nodes[1].id

    def test_get_node_edges_both(self, simple_graph):
        """Graph.get_node_edges(direction='both') should return all edges."""
        graph, nodes = simple_graph
        all_edges = graph.get_node_edges(nodes[1].id, direction="both")

        assert len(all_edges) == 2  # One in, one out

    def test_topological_order(self, dag_graph):
        """Graph.topological_order() should return valid order."""
        graph, nodes = dag_graph
        # DAG: A -> B -> D, A -> C -> D
        order = graph.topological_sort()

        # A should come before B, C; B, C should come before D
        a_idx = next(i for i, n in enumerate(order) if n.content["value"] == "A")
        b_idx = next(i for i, n in enumerate(order) if n.content["value"] == "B")
        c_idx = next(i for i, n in enumerate(order) if n.content["value"] == "C")
        d_idx = next(i for i, n in enumerate(order) if n.content["value"] == "D")

        assert a_idx < b_idx
        assert a_idx < c_idx
        assert b_idx < d_idx
        assert c_idx < d_idx


class TestGraphCycleDetection:
    """Test Graph cycle detection."""

    def test_is_acyclic_dag(self, dag_graph):
        """DAG should report is_acyclic=True."""
        graph, _ = dag_graph
        assert graph.is_acyclic() is True

    def test_is_acyclic_cycle(self, cyclic_graph):
        """Cyclic graph should report is_acyclic=False."""
        graph, _ = cyclic_graph
        assert graph.is_acyclic() is False

    def test_topological_sort_cyclic_raises(self, cyclic_graph):
        """Graph.topological_sort() on cyclic graph should raise ValueError."""
        graph, _ = cyclic_graph
        with pytest.raises(ValueError):
            graph.topological_sort()


class TestGraphPathfinding:
    """Test Graph pathfinding operations."""

    @pytest.mark.anyio
    async def test_find_path_exists(self, simple_graph):
        """Graph.find_path() should find path when it exists."""
        graph, nodes = simple_graph
        # A -> B -> C
        path = await graph.find_path(nodes[0].id, nodes[2].id)

        assert path is not None
        assert len(path) == 2  # Two edges: A->B, B->C

    @pytest.mark.anyio
    async def test_find_path_not_exists(self, simple_graph):
        """Graph.find_path() should return None when no path."""
        graph, nodes = simple_graph
        # C -> A has no path (only A -> B -> C exists)
        path = await graph.find_path(nodes[2].id, nodes[0].id)

        assert path is None

    @pytest.mark.anyio
    async def test_find_path_same_node(self, simple_graph):
        """Graph.find_path() with same start and end should return empty path."""
        graph, nodes = simple_graph
        path = await graph.find_path(nodes[0].id, nodes[0].id)

        assert path is not None
        assert len(path) == 0


class TestGraphContains:
    """Test Graph membership operations."""

    def test_contains_node(self, simple_graph):
        """Node in graph should return True."""
        graph, nodes = simple_graph
        assert nodes[0] in graph

    def test_contains_edge(self, simple_graph):
        """Edge in graph should return True."""
        graph, _ = simple_graph
        edge = list(graph.edges)[0]
        assert edge in graph

    def test_contains_uuid(self, simple_graph):
        """UUID in graph should check nodes and edges."""
        graph, nodes = simple_graph
        assert nodes[0].id in graph


class TestGraphSerialization:
    """Test Graph serialization."""

    def test_to_dict(self, simple_graph):
        """Graph.to_dict() should serialize nodes and edges."""
        graph, _ = simple_graph
        data = graph.to_dict()

        assert "nodes" in data
        assert "edges" in data

    def test_roundtrip(self, simple_graph):
        """Serialization roundtrip should preserve graph structure."""
        graph, nodes = simple_graph
        data = graph.to_dict(mode="json")
        restored = Graph.from_dict(data)

        assert len(restored.nodes) == len(graph.nodes)
        assert len(restored.edges) == len(graph.edges)

        # Check that edges still connect correct nodes
        for edge in restored.edges:
            assert edge.head in restored.nodes
            assert edge.tail in restored.nodes


class TestEdge:
    """Test Edge creation and properties."""

    def test_edge_with_label(self):
        """Edge should accept labels."""
        from uuid import uuid4

        edge = Edge(head=uuid4(), tail=uuid4(), label=["depends_on", "requires"])
        assert "depends_on" in edge.label
        assert "requires" in edge.label

    def test_edge_with_properties(self):
        """Edge should accept custom properties."""
        from uuid import uuid4

        edge = Edge(head=uuid4(), tail=uuid4(), properties={"weight": 1.5})
        assert edge.properties["weight"] == 1.5

    @pytest.mark.anyio
    async def test_edge_check_condition_default(self):
        """Edge.check_condition() should return True by default."""
        from uuid import uuid4

        edge = Edge(head=uuid4(), tail=uuid4())
        result = await edge.check_condition()
        assert result is True
