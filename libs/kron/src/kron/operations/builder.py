"""Fluent builder for operation DAGs.

Build graphs with chained .add() calls, automatic sequential linking,
and explicit dependency management. Alias: Builder = OperationGraphBuilder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from kron.core import Edge, Graph
from kron.types import Undefined, UndefinedType, is_sentinel, not_sentinel
from kron.utils import to_uuid

from .node import Operation

if TYPE_CHECKING:
    from kron.session import Branch

__all__ = ("Builder", "OperationGraphBuilder")


def _resolve_branch_ref(branch: Any) -> UUID | str:
    """Convert branch reference to UUID or trimmed name string.

    Raises:
        ValueError: If branch is not a valid UUID, Branch, or non-empty string.
    """
    try:
        return to_uuid(branch)
    except (ValueError, TypeError):
        pass

    if isinstance(branch, str) and branch.strip():
        return branch.strip()

    raise ValueError(f"Invalid branch reference: {branch}")


class OperationGraphBuilder:
    """Fluent builder for operation DAGs with automatic linking.

    Operations added sequentially auto-link unless depends_on is specified.
    Use depends_on=[] for independent operations, depends_on=["op1"] for explicit.

    Example:
        graph = (Builder()
            .add("fetch", "http_get", {"url": "..."})
            .add("parse", "json_parse")  # auto-links to fetch
            .add("validate", "schema_check", depends_on=["parse"])
            .build())

    Attributes:
        graph: Underlying Graph being built.
    """

    def __init__(self, graph: Graph | UndefinedType = Undefined):
        """Initialize builder, optionally with existing graph.

        Args:
            graph: Pre-existing Graph to extend, or Undefined for new.
        """
        self.graph = Graph() if is_sentinel(graph) else graph
        self._nodes: dict[str, Operation] = {}
        self._executed: set[UUID] = set()
        self._current_heads: list[str] = []

    def add(
        self,
        name: str,
        operation: str,
        parameters: dict[str, Any] | Any | UndefinedType = Undefined,
        depends_on: list[str] | UndefinedType = Undefined,
        branch: str | UUID | Branch | UndefinedType = Undefined,
        inherit_context: bool = False,
        metadata: dict[str, Any] | UndefinedType = Undefined,
    ) -> OperationGraphBuilder:
        """Add operation to graph.

        Args:
            name: Unique operation name for reference.
            operation: Operation type (registry key).
            parameters: Factory arguments (dict or model).
            depends_on: Explicit dependencies. Undefined=auto-link, []=independent.
            branch: Target branch (Branch|UUID|str). Undefined=default.
            inherit_context: Store primary_dependency for context inheritance.
            metadata: Additional metadata dict.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If name exists or dependency not found.
        """
        if name in self._nodes:
            raise ValueError(f"Operation with name '{name}' already exists")

        resolved_params = {} if is_sentinel(parameters) else parameters
        resolved_metadata = {} if is_sentinel(metadata) else metadata
        op = Operation(
            operation_type=operation,
            parameters=resolved_params,
            metadata=resolved_metadata,
            streaming=False,
        )
        op.metadata["name"] = name

        if not_sentinel(branch):
            op.metadata["branch"] = _resolve_branch_ref(branch)

        if inherit_context and not_sentinel(depends_on) and depends_on:
            op.metadata["inherit_context"] = True
            op.metadata["primary_dependency"] = self._nodes[depends_on[0]].id

        self.graph.add_node(op)
        self._nodes[name] = op

        if not_sentinel(depends_on):
            for dep_name in depends_on:
                if dep_name not in self._nodes:
                    raise ValueError(f"Dependency '{dep_name}' not found")
                dep_node = self._nodes[dep_name]
                edge = Edge(head=dep_node.id, tail=op.id, label=["depends_on"])
                self.graph.add_edge(edge)
        elif self._current_heads:
            for head_name in self._current_heads:
                if head_name in self._nodes:
                    head_node = self._nodes[head_name]
                    edge = Edge(head=head_node.id, tail=op.id, label=["sequential"])
                    self.graph.add_edge(edge)

        self._current_heads = [name]
        return self

    def depends_on(
        self,
        target: str,
        *dependencies: str,
        label: list[str] | UndefinedType = Undefined,
    ) -> OperationGraphBuilder:
        """Add explicit dependency edges: dependencies -> target.

        Args:
            target: Operation that depends on others.
            *dependencies: Operations that target depends on.
            label: Optional edge labels.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If target or any dependency not found.
        """
        if target not in self._nodes:
            raise ValueError(f"Target operation '{target}' not found")

        target_node = self._nodes[target]
        resolved_label = [] if is_sentinel(label, {"none", "empty"}) else label

        for dep_name in dependencies:
            if dep_name not in self._nodes:
                raise ValueError(f"Dependency operation '{dep_name}' not found")

            dep_node = self._nodes[dep_name]

            # Create edge: dependency -> target
            edge = Edge(
                head=dep_node.id,
                tail=target_node.id,
                label=resolved_label,
            )
            self.graph.add_edge(edge)

        return self

    def get(self, name: str) -> Operation:
        """Get operation by name. Raises ValueError if not found."""
        if name not in self._nodes:
            raise ValueError(f"Operation '{name}' not found")
        return self._nodes[name]

    def get_by_id(self, operation_id: UUID) -> Operation | None:
        """Get operation by UUID, or None if not in graph."""
        node = self.graph.nodes.get(operation_id, None)
        if isinstance(node, Operation):
            return node
        return None

    def mark_executed(self, *names: str) -> OperationGraphBuilder:
        """Mark operations as executed for incremental workflows. Returns self."""
        for name in names:
            if name in self._nodes:
                self._executed.add(self._nodes[name].id)
        return self

    def get_unexecuted_nodes(self) -> list[Operation]:
        """Return operations not marked as executed."""
        return [op for op in self._nodes.values() if op.id not in self._executed]

    def build(self) -> Graph:
        """Validate and return the graph. Raises ValueError if cyclic."""
        if not self.graph.is_acyclic():
            raise ValueError("Operation graph has cycles - must be a DAG")
        return self.graph

    def clear(self) -> OperationGraphBuilder:
        """Reset builder to empty state. Returns self."""
        self.graph = Graph()
        self._nodes = {}
        self._executed = set()
        self._current_heads = []
        return self

    def __repr__(self) -> str:
        return (
            f"OperationGraphBuilder("
            f"operations={len(self._nodes)}, "
            f"edges={len(self.graph.edges)}, "
            f"executed={len(self._executed)})"
        )


# Alias for convenience
Builder = OperationGraphBuilder
