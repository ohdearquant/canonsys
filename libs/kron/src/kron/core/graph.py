"""Graph: directed graph with adjacency-based operations."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, PrivateAttr, field_validator, model_validator
from typing_extensions import override

from kron.errors import NotFoundError
from kron.protocols import Containable, Deserializable, Serializable, implements
from kron.types import Unset, UnsetType, is_unset
from kron.utils import synchronized

from .element import Element
from .node import Node
from .pile import Pile

__all__ = ("Edge", "EdgeCondition", "Graph")


class EdgeCondition:
    """Runtime predicate for edge traversal.

    Subclass and override apply() for custom traversal logic.
    Default implementation always returns True (unconditional traversal).

    Example:
        class WeightThreshold(EdgeCondition):
            async def apply(self, context) -> bool:
                return context.get("weight", 0) > self.threshold
    """

    def __init__(self, **kwargs: Any):
        """Initialize with arbitrary state attributes."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    async def apply(self, *args: Any, **kwargs: Any) -> bool:
        """Evaluate condition. Override for custom logic."""
        return True

    async def __call__(self, *args: Any, **kwargs: Any) -> bool:
        """Async callable interface delegating to apply()."""
        return await self.apply(*args, **kwargs)


class Edge(Element):
    """Directed edge connecting two nodes with optional labels, conditions, and properties.

    Edges are directional: head -> tail. Conditions are runtime-only (not serialized).
    """

    head: UUID = Field(description="Source node ID")
    tail: UUID = Field(description="Target node ID")
    label: list[str] = Field(default_factory=list, description="Edge labels/tags")
    condition: EdgeCondition | None = Field(
        default=None, exclude=True, description="Runtime traversal predicate"
    )
    properties: dict[str, Any] = Field(default_factory=dict, description="Custom edge attributes")

    @field_validator("head", "tail", mode="before")
    @classmethod
    def _validate_uuid(cls, value: Any) -> UUID:
        """Coerce head/tail to UUID."""
        return cls._coerce_id(value)

    async def check_condition(self, *args: Any, **kwargs: Any) -> bool:
        """Check traversability. Returns True if no condition set or condition passes."""
        if self.condition is None:
            return True
        return await self.condition.apply(*args, **kwargs)


@implements(
    Serializable,
    Deserializable,
    Containable,
)
class Graph(Element):
    """Directed graph with Pile-backed storage and O(1) adjacency operations.

    Features:
        - O(1) node/edge lookup via adjacency lists
        - Cycle detection, topological sort, pathfinding
        - Thread-safe mutations (RLock synchronized)
        - Conditional edge traversal

    Example:
        graph = Graph()
        graph.add_node(Node())
        graph.add_edge(Edge(head=n1.id, tail=n2.id))
        path = await graph.find_path(n1, n2)
    """

    nodes: Pile[Node] = Field(
        default_factory=lambda: Pile(item_type=Node), description="Node storage"
    )
    edges: Pile[Edge] = Field(
        default_factory=lambda: Pile(item_type=Edge), description="Edge storage"
    )
    _out_edges: dict[UUID, set[UUID]] = PrivateAttr(default_factory=dict)
    _in_edges: dict[UUID, set[UUID]] = PrivateAttr(default_factory=dict)
    _lock: threading.RLock = PrivateAttr(default_factory=threading.RLock)

    @field_validator("nodes", "edges", mode="wrap")
    @classmethod
    def _deserialize_nodes_edges(cls, v: Any, handler) -> Pile:
        """Deserialize nodes/edges from dict if needed."""
        if isinstance(v, Pile):
            return v
        if isinstance(v, dict):
            return Pile.from_dict(v)
        return handler(v)  # pragma: no cover

    @model_validator(mode="after")
    def _rebuild_adjacency_after_init(self) -> Graph:
        """Rebuild adjacency lists after model initialization."""
        self._rebuild_adjacency()
        return self

    def _rebuild_adjacency(self) -> None:
        """Rebuild _out_edges and _in_edges from current nodes/edges."""
        self._out_edges = {node_id: set() for node_id in self.nodes.keys()}
        self._in_edges = {node_id: set() for node_id in self.nodes.keys()}

        for edge_id in self.edges.keys():
            edge = self.edges[edge_id]
            if edge.head in self._out_edges:
                self._out_edges[edge.head].add(edge_id)
            if edge.tail in self._in_edges:
                self._in_edges[edge.tail].add(edge_id)

    def _check_node_exists(self, node_id: UUID) -> Node:
        """Verify node exists. Raises NotFoundError with graph context."""
        try:
            return self.nodes[node_id]
        except NotFoundError as e:
            raise NotFoundError(
                f"Node {node_id} not found in graph",
                details=e.details,
                retryable=e.retryable,
                cause=e,
            )

    def _check_edge_exists(self, edge_id: UUID) -> Edge:
        """Verify edge exists. Raises NotFoundError with graph context."""
        try:
            return self.edges[edge_id]
        except NotFoundError as e:
            raise NotFoundError(
                f"Edge {edge_id} not found in graph",
                details=e.details,
                retryable=e.retryable,
                cause=e,
            )

    # ==================== Node Operations ====================

    @synchronized
    def add_node(self, node: Node) -> None:
        """Add node to graph. Raises ExistsError if duplicate."""
        self.nodes.add(node)
        self._out_edges[node.id] = set()
        self._in_edges[node.id] = set()

    @synchronized
    def remove_node(self, node_id: UUID | Node) -> Node:
        """Remove node and all connected edges. Raises NotFoundError if missing."""
        nid = self._coerce_id(node_id)
        self._check_node_exists(nid)

        for edge_id in list(self._in_edges[nid]):
            self.remove_edge(edge_id)
        for edge_id in list(self._out_edges[nid]):
            self.remove_edge(edge_id)

        del self._in_edges[nid]
        del self._out_edges[nid]
        return self.nodes.remove(nid)

    # ==================== Edge Operations ====================

    @synchronized
    def add_edge(self, edge: Edge) -> None:
        """Add edge to graph. Raises NotFoundError if head/tail missing."""
        if edge.head not in self.nodes:
            raise NotFoundError(f"Head node {edge.head} not in graph")
        if edge.tail not in self.nodes:
            raise NotFoundError(f"Tail node {edge.tail} not in graph")

        self.edges.add(edge)
        self._out_edges[edge.head].add(edge.id)
        self._in_edges[edge.tail].add(edge.id)

    @synchronized
    def remove_edge(self, edge_id: UUID | Edge) -> Edge:
        """Remove edge from graph. Raises NotFoundError if missing."""
        eid = self._coerce_id(edge_id)
        edge = self._check_edge_exists(eid)

        self._out_edges[edge.head].discard(eid)
        self._in_edges[edge.tail].discard(eid)
        return self.edges.remove(eid)

    # ==================== Graph Queries ====================

    def get_predecessors(self, node_id: UUID | Node) -> list[Node]:
        """Get nodes with edges pointing to this node (in-neighbors)."""
        nid = self._coerce_id(node_id)
        return [self.nodes[self.edges[eid].head] for eid in self._in_edges.get(nid, set())]

    def get_successors(self, node_id: UUID | Node) -> list[Node]:
        """Get nodes this node points to (out-neighbors)."""
        nid = self._coerce_id(node_id)
        return [self.nodes[self.edges[eid].tail] for eid in self._out_edges.get(nid, set())]

    def get_node_edges(
        self,
        node_id: UUID | Node,
        direction: Literal["in", "out", "both"] = "both",
    ) -> list[Edge]:
        """Get edges connected to node by direction (in/out/both)."""
        if direction not in {"in", "out", "both"}:
            raise ValueError(f"Invalid direction: {direction}")

        nid = self._coerce_id(node_id)
        result = []

        if direction in {"in", "both"}:
            result.extend(self.edges[eid] for eid in self._in_edges.get(nid, set()))
        if direction in {"out", "both"}:
            result.extend(self.edges[eid] for eid in self._out_edges.get(nid, set()))

        return result

    def get_heads(self) -> list[Node]:
        """Get source nodes (no incoming edges)."""
        return [self.nodes[nid] for nid, in_edges in self._in_edges.items() if not in_edges]

    def get_tails(self) -> list[Node]:
        """Get sink nodes (no outgoing edges)."""
        return [self.nodes[nid] for nid, out_edges in self._out_edges.items() if not out_edges]

    # ==================== Graph Algorithms ====================

    def is_acyclic(self) -> bool:
        """Check if graph is acyclic using three-color DFS. O(V+E)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        colors = dict.fromkeys(self.nodes.keys(), WHITE)

        def dfs(node_id: UUID) -> bool:
            colors[node_id] = GRAY
            for edge_id in self._out_edges[node_id]:
                neighbor_id = self.edges[edge_id].tail
                if colors[neighbor_id] == GRAY:
                    return False
                if colors[neighbor_id] == WHITE and not dfs(neighbor_id):
                    return False
            colors[node_id] = BLACK
            return True

        return all(
            not (colors[node_id] == WHITE and not dfs(node_id)) for node_id in self.nodes.keys()
        )

    def topological_sort(self) -> list[Node]:
        """Topological sort via Kahn's algorithm. Raises ValueError if cyclic."""
        if not self.is_acyclic():
            raise ValueError("Cannot topologically sort graph with cycles")

        in_degree = {nid: len(edges) for nid, edges in self._in_edges.items()}
        queue: deque[UUID] = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result: list[Node] = []

        while queue:
            node_id = queue.popleft()
            result.append(self.nodes[node_id])

            for edge_id in self._out_edges[node_id]:
                neighbor_id = self.edges[edge_id].tail
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(neighbor_id)

        return result

    async def find_path(
        self,
        start: UUID | Node,
        end: UUID | Node,
        check_conditions: bool = False,
    ) -> list[Edge] | None:
        """Find path via BFS. Returns edge list or None if no path exists.

        Args:
            start: Source node
            end: Target node
            check_conditions: If True, respect edge conditions during traversal

        Raises:
            NotFoundError: If start or end node not in graph
        """
        start_id = self._coerce_id(start)
        end_id = self._coerce_id(end)

        if start_id not in self.nodes or end_id not in self.nodes:
            raise NotFoundError("Start or end node not in graph")

        queue: deque[UUID] = deque([start_id])
        parent: dict[UUID, tuple[UUID, UUID]] = {}
        visited = {start_id}

        while queue:
            current_id = queue.popleft()

            if current_id == end_id:
                path = []
                node_id = end_id
                while node_id in parent:
                    parent_id, edge_id = parent[node_id]
                    path.append(self.edges[edge_id])
                    node_id = parent_id
                return list(reversed(path))

            for edge_id in self._out_edges[current_id]:
                edge: Edge = self.edges[edge_id]
                neighbor_id = edge.tail

                if neighbor_id not in visited:
                    if check_conditions and not await edge.check_condition():
                        continue
                    visited.add(neighbor_id)
                    parent[neighbor_id] = (current_id, edge_id)
                    queue.append(neighbor_id)

        return None

    def __contains__(self, item: object) -> bool:
        """Check if node, edge, or UUID is in graph."""
        if isinstance(item, Node):
            return item in self.nodes
        if isinstance(item, Edge):
            return item in self.edges
        if isinstance(item, UUID):
            return item in self.nodes or item in self.edges
        return False

    def __len__(self) -> int:
        """Return node count."""
        return len(self.nodes)

    # ==================== Serialization ====================

    @override
    def to_dict(
        self,
        mode: Literal["python", "json", "db"] = "python",
        created_at_format: (Literal["datetime", "isoformat", "timestamp"] | UnsetType) = Unset,
        meta_key: str | UnsetType = Unset,
        item_meta_key: str | UnsetType = Unset,
        item_created_at_format: (Literal["datetime", "isoformat", "timestamp"] | UnsetType) = Unset,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Serialize graph with nodes and edges as nested Pile dicts.

        Args:
            mode: Serialization mode (python/json/db)
            created_at_format: Timestamp format for Graph
            meta_key: Rename Graph metadata field
            item_meta_key: Metadata key for nodes/edges
            item_created_at_format: Timestamp format for nodes/edges
            **kwargs: Passed to model_dump()
        """
        exclude = kwargs.pop("exclude", set())
        exclude = (exclude if isinstance(exclude, set) else set(exclude)) | {
            "nodes",
            "edges",
        }

        data = super().to_dict(
            mode=mode,
            created_at_format=created_at_format,
            meta_key=meta_key,
            exclude=exclude,
            **kwargs,
        )

        data["nodes"] = self.nodes.to_dict(
            mode=mode,
            item_meta_key=item_meta_key,
            item_created_at_format=item_created_at_format,
        )
        data["edges"] = self.edges.to_dict(
            mode=mode,
            item_meta_key=item_meta_key,
            item_created_at_format=item_created_at_format,
        )

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        meta_key: str | UnsetType = Unset,
        item_meta_key: str | UnsetType = Unset,
        **kwargs: Any,
    ) -> Graph:
        """Deserialize Graph from dict. Adjacency lists rebuilt automatically.

        Args:
            data: Serialized graph data
            meta_key: Restore Graph metadata from this key
            item_meta_key: Metadata key for node/edge deserialization
            **kwargs: Additional model_validate arguments
        """
        from .pile import Pile

        data = data.copy()

        if not is_unset(meta_key) and meta_key in data:
            data["metadata"] = data.pop(meta_key)

        nodes_data = data.pop("nodes", None)
        edges_data = data.pop("edges", None)

        if nodes_data:
            data["nodes"] = Pile.from_dict(
                nodes_data, meta_key=item_meta_key, item_meta_key=item_meta_key
            )
        if edges_data:
            data["edges"] = Pile.from_dict(
                edges_data, meta_key=item_meta_key, item_meta_key=item_meta_key
            )

        return cls.model_validate(data, **kwargs)
