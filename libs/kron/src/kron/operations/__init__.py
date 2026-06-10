"""Operations: executable graph nodes with dependency-aware execution.

Core types:
    Operation: Node + Event hybrid for graph-based execution.
    OperationRegistry: Per-session factory mapping.
    OperationGraphBuilder (Builder): Fluent DAG construction.

Execution:
    flow(): Execute DAG, return results dict.
    flow_stream(): Execute DAG, yield results incrementally.
"""

from __future__ import annotations

from .builder import Builder, OperationGraphBuilder
from .flow import DependencyAwareExecutor, OperationResult, flow, flow_stream
from .node import Operation, create_operation
from .registry import OperationFactory, OperationRegistry

__all__ = (
    "Builder",
    "DependencyAwareExecutor",
    "Operation",
    "OperationFactory",
    "OperationGraphBuilder",
    "OperationRegistry",
    "OperationResult",
    "create_operation",
    "flow",
    "flow_stream",
)
