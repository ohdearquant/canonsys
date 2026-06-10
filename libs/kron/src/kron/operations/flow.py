"""Dependency-aware operation graph execution.

Execute DAGs of Operations with concurrency control and progress streaming.
Core functions: flow() for batch results, flow_stream() for incremental results.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from kron.core import EventStatus, Graph
from kron.types import Undefined, UndefinedType, is_sentinel
from kron.utils import concurrency
from kron.utils.concurrency import CapacityLimiter, CompletionStream

from .node import Operation

if TYPE_CHECKING:
    from kron.session import Branch, Session

logger = logging.getLogger(__name__)

__all__ = ("DependencyAwareExecutor", "OperationResult", "flow", "flow_stream")


@dataclass
class OperationResult:
    """Single operation result from streaming execution.

    Attributes:
        name: Operation name from metadata.
        result: Return value (None if failed).
        error: Exception instance if failed, else None.
        completed: Count of finished operations so far.
        total: Total operations in graph.
    """

    name: str
    result: Any
    error: Exception | None = None
    completed: int = 0
    total: int = 0

    @property
    def success(self) -> bool:
        """True if operation completed without error."""
        return self.error is None


class DependencyAwareExecutor:
    """Execute operation DAGs respecting dependencies and concurrency limits.

    Lifecycle:
        1. Pre-allocate branches for all operations
        2. Launch all tasks (each waits on predecessors internally)
        3. Acquire concurrency slot only when dependencies complete
        4. Execute and store result/error
        5. Signal completion to dependents

    Thread Safety:
        Uses asyncio Events for dependency coordination and CapacityLimiter
        for concurrency control. Results/errors stored in thread-safe dicts.

    Note:
        Does not inject context between operations. Use metadata["branch"]
        to assign specific branches, or set default_branch for all.
    """

    def __init__(
        self,
        session: Session,
        graph: Graph,
        max_concurrent: int | UndefinedType = Undefined,
        stop_on_error: bool = True,
        verbose: bool = False,
        default_branch: Branch | str | UndefinedType = Undefined,
    ):
        """Initialize executor.

        Args:
            session: Session with services and operation registry.
            graph: DAG of Operation nodes.
            max_concurrent: Max parallel operations (None=unlimited).
            stop_on_error: Raise on first failure vs continue.
            verbose: Log progress to debug logger.
            default_branch: Fallback branch for operations without metadata["branch"].
        """
        self.session = session
        self.graph = graph
        resolved_max_concurrent = None if is_sentinel(max_concurrent) else max_concurrent
        resolved_default_branch = None if is_sentinel(default_branch) else default_branch
        self.max_concurrent = resolved_max_concurrent
        self.stop_on_error = stop_on_error
        self.verbose = verbose
        self._default_branch = resolved_default_branch

        self.results: dict[UUID, Any] = {}
        self.errors: dict[UUID, Exception] = {}
        self.completion_events: dict[UUID, concurrency.Event] = {}
        self.operation_branches: dict[UUID, Branch | None] = {}

        self._limiter: CapacityLimiter | None = (
            CapacityLimiter(resolved_max_concurrent) if resolved_max_concurrent else None
        )

        for node in graph.nodes:
            if isinstance(node, Operation):
                self.completion_events[node.id] = concurrency.Event()

    async def execute(self) -> dict[str, Any]:
        """Execute graph and return results keyed by operation name.

        Returns:
            Dict mapping operation names to their results.

        Raises:
            ValueError: If graph has cycles or non-Operation nodes.
            Exception: First operation error if stop_on_error=True.
        """
        if not self.graph.is_acyclic():
            raise ValueError("Operation graph has cycles - must be a DAG")

        # Validate all nodes are Operations
        for node in self.graph.nodes:
            if not isinstance(node, Operation):
                raise ValueError(
                    f"Graph contains non-Operation node: {node} ({type(node).__name__})"
                )

        # Pre-allocate branches to avoid locking during execution
        await self._preallocate_branches()

        # Execute operations with dependency coordination
        operations = [node for node in self.graph.nodes if isinstance(node, Operation)]

        # Create operation tasks (they wait on dependencies internally)
        tasks = [self._execute_operation(op) for op in operations]

        # Use CompletionStream to process results as they arrive
        # Concurrency is handled by self._limiter AFTER dependency resolution
        # This ensures limiter slots are only held by tasks ready to execute
        async with CompletionStream(tasks, limit=None) as stream:
            async for idx, _ in stream:
                op = operations[idx]
                if self.verbose:
                    name = op.metadata.get("name", str(op.id)[:8])
                    if op.id in self.errors:
                        logger.debug("Operation '%s' failed", name)
                    elif op.id in self.results:
                        logger.debug("Operation '%s' completed", name)

        # Compile results keyed by operation name for user-friendly access
        results_by_name = {}
        for node in self.graph.nodes:
            if isinstance(node, Operation):
                name = node.metadata.get("name", str(node.id))
                if node.id in self.results:
                    results_by_name[name] = self.results[node.id]

        return results_by_name

    async def stream_execute(self) -> AsyncGenerator[OperationResult, None]:
        """Execute graph, yielding OperationResult as each operation completes.

        Yields:
            OperationResult with name, result/error, and progress counts.

        Raises:
            ValueError: If graph has cycles or non-Operation nodes.
        """
        if not self.graph.is_acyclic():
            raise ValueError("Operation graph has cycles - must be a DAG")

        # Validate all nodes are Operations
        for node in self.graph.nodes:
            if not isinstance(node, Operation):
                raise ValueError(
                    f"Graph contains non-Operation node: {node} ({type(node).__name__})"
                )

        # Pre-allocate branches
        await self._preallocate_branches()

        # Execute operations with dependency coordination
        operations = [node for node in self.graph.nodes if isinstance(node, Operation)]
        total = len(operations)

        # Create operation tasks
        tasks = [self._execute_operation(op) for op in operations]

        # Stream results as they complete
        # Concurrency is handled by self._limiter AFTER dependency resolution
        completed = 0
        async with CompletionStream(tasks, limit=None) as stream:
            async for idx, _ in stream:
                completed += 1
                op = operations[idx]
                name = op.metadata.get("name", str(op.id))

                # Build result
                if op.id in self.errors:
                    yield OperationResult(
                        name=name,
                        result=None,
                        error=self.errors[op.id],
                        completed=completed,
                        total=total,
                    )
                else:
                    yield OperationResult(
                        name=name,
                        result=self.results.get(op.id),
                        error=None,
                        completed=completed,
                        total=total,
                    )

    def _resolve_operation_branch(self, branch_spec: Any) -> Branch | None:
        """Resolve branch spec (Branch|UUID|str|None) to Branch or None."""
        if branch_spec is None:
            return None

        # Already a Branch
        if hasattr(branch_spec, "id") and hasattr(branch_spec, "order"):
            return branch_spec

        if isinstance(branch_spec, (UUID, str)):
            try:
                return self.session.get_branch(branch_spec)
            except Exception as e:
                logger.debug("Branch '%s' not found, using default: %s", branch_spec, e)
                return None

        return None

    async def _preallocate_branches(self) -> None:
        """Assign branches to all operations before execution."""
        default_branch = self._resolve_operation_branch(self._default_branch)
        if default_branch is None:
            default_branch = getattr(self.session, "default_branch", None)

        for node in self.graph.nodes:
            if isinstance(node, Operation):
                op_branch = node.metadata.get("branch")
                if op_branch is not None:
                    resolved = self._resolve_operation_branch(op_branch)
                    self.operation_branches[node.id] = (
                        resolved if resolved is not None else default_branch
                    )
                else:
                    self.operation_branches[node.id] = default_branch

        if self.verbose:
            logger.debug("Pre-allocated branches for %d operations", len(self.operation_branches))

    async def _execute_operation(self, operation: Operation) -> Operation:
        """Execute single operation: wait deps -> acquire slot -> invoke -> signal."""
        try:
            # Wait for all dependencies to complete (no limiter held yet)
            await self._wait_for_dependencies(operation)

            # Acquire limiter slot ONLY when ready to execute
            if self._limiter:
                await self._limiter.acquire()

            try:
                # Execute the operation (no context injection - use params as-is)
                await self._invoke_operation(operation)
            finally:
                if self._limiter:
                    self._limiter.release()

        except Exception as e:
            self.errors[operation.id] = e
            if self.verbose:
                logger.exception("Operation %s failed: %s", str(operation.id)[:8], e)

            if self.stop_on_error:
                self.completion_events[operation.id].set()
                raise

        finally:
            self.completion_events[operation.id].set()

        return operation

    async def _wait_for_dependencies(self, operation: Operation) -> None:
        """Block until all predecessor operations signal completion."""
        predecessors = self.graph.get_predecessors(operation)

        if self.verbose and predecessors:
            logger.debug(
                "Operation %s waiting for %d dependencies",
                str(operation.id)[:8],
                len(predecessors),
            )

        for pred in predecessors:
            if pred.id in self.completion_events:
                await self.completion_events[pred.id].wait()

    async def _invoke_operation(self, operation: Operation) -> None:
        """Bind, invoke, and store result or error."""
        if self.verbose:
            name = operation.metadata.get("name", str(operation.id)[:8])
            logger.debug("Executing operation: %s", name)

        branch = self.operation_branches.get(operation.id)
        if branch is None:
            raise ValueError(f"No branch allocated for operation {operation.id}")

        operation.bind(self.session, branch)
        await operation.invoke()

        if operation.execution.status == EventStatus.COMPLETED:
            self.results[operation.id] = operation.execution.response
            if self.verbose:
                name = operation.metadata.get("name", str(operation.id)[:8])
                logger.debug("Completed operation: %s", name)
        else:
            error_msg = f"Execution status: {operation.execution.status}"
            if hasattr(operation.execution, "error") and operation.execution.error:
                error_msg += f" - {operation.execution.error}"
            self.errors[operation.id] = RuntimeError(error_msg)
            if self.verbose:
                name = operation.metadata.get("name", str(operation.id)[:8])
                logger.warning("Operation %s failed: %s", name, error_msg)


async def flow(
    session: Session,
    graph: Graph,
    *,
    branch: Branch | str | None = None,
    max_concurrent: int | None = None,
    stop_on_error: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute operation graph with dependency-aware scheduling.

    Operations are executed with their given parameters - no context injection.
    For context passing between operations, use flow_report or manage context
    explicitly before adding operations to the graph.

    Args:
        session: Session for services and branches.
        graph: Operation graph (DAG) to execute.
        branch: Default branch (operations can override via metadata).
        max_concurrent: Max concurrent operations (None = unlimited).
        stop_on_error: Stop on first error.
        verbose: Print progress.

    Returns:
        Dictionary mapping operation names to their results.
    """
    executor = DependencyAwareExecutor(
        session=session,
        graph=graph,
        max_concurrent=max_concurrent,
        stop_on_error=stop_on_error,
        verbose=verbose,
        default_branch=branch,
    )

    return await executor.execute()


async def flow_stream(
    session: Session,
    graph: Graph,
    *,
    branch: Branch | str | None = None,
    max_concurrent: int | None = None,
    stop_on_error: bool = True,
) -> AsyncGenerator[OperationResult, None]:
    """Execute graph with streaming results. Same args as flow().

    Yields:
        OperationResult with progress tracking as each operation completes.
    """
    executor = DependencyAwareExecutor(
        session=session,
        graph=graph,
        max_concurrent=max_concurrent,
        stop_on_error=stop_on_error,
        verbose=False,
        default_branch=branch,
    )

    async for result in executor.stream_execute():
        yield result
