"""Task group wrapper for structured concurrency.

Thin wrapper around anyio.TaskGroup to provide a consistent internal API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

import anyio
import anyio.abc

T = TypeVar("T")
R = TypeVar("R")

__all__ = (
    "TaskGroup",
    "create_task_group",
)


class TaskGroup:
    """Wrapper around anyio.TaskGroup for structured concurrency.

    All spawned tasks complete (or are cancelled) before the group exits.
    Exceptions propagate and cancel sibling tasks.
    """

    __slots__ = ("_tg",)

    def __init__(self, tg: anyio.abc.TaskGroup) -> None:
        """Initialize with underlying anyio task group.

        Args:
            tg: The anyio TaskGroup to wrap.
        """
        self._tg = tg

    @property
    def cancel_scope(self) -> anyio.CancelScope:
        """Cancel scope controlling the task group lifetime."""
        return self._tg.cancel_scope

    def start_soon(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        name: str | None = None,
    ) -> None:
        """Spawn task immediately without waiting for it to initialize.

        Args:
            func: Async callable to run.
            *args: Positional arguments for func.
            name: Optional task name for debugging.
        """
        self._tg.start_soon(func, *args, name=name)

    async def start(
        self,
        func: Callable[..., Awaitable[R]],
        *args: Any,
        name: str | None = None,
    ) -> R:
        """Spawn task and wait for it to signal readiness via task_status.started().

        Args:
            func: Async callable that calls task_status.started(value).
            *args: Positional arguments for func.
            name: Optional task name for debugging.

        Returns:
            Value passed to task_status.started().
        """
        return await self._tg.start(func, *args, name=name)


@asynccontextmanager
async def create_task_group() -> AsyncIterator[TaskGroup]:
    """Create a task group context for structured concurrency.

    Usage:
        async with create_task_group() as tg:
            tg.start_soon(some_async_func)

    Yields:
        TaskGroup instance.
    """
    async with anyio.create_task_group() as tg:
        yield TaskGroup(tg)
