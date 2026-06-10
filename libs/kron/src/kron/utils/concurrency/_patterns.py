"""High-level async concurrency patterns.

Provides structured concurrency primitives for common async workflows:
    gather: Run awaitables concurrently, collect all results.
    race: Return first completion, cancel the rest.
    bounded_map: Apply async function with concurrency limit.
    retry: Exponential backoff with deadline awareness.
    CompletionStream: Iterate results as they complete.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import TypeVar

import anyio
import anyio.abc

from ._cancel import effective_deadline, move_on_at
from ._errors import non_cancel_subgroup
from ._primitives import CapacityLimiter
from ._task import create_task_group
from ._utils import current_time

T = TypeVar("T")
R = TypeVar("R")


__all__ = (
    "CompletionStream",
    "bounded_map",
    "gather",
    "race",
    "retry",
)


async def gather(*aws: Awaitable[T], return_exceptions: bool = False) -> list[T | BaseException]:
    """Run awaitables concurrently and collect results in input order.

    Args:
        *aws: Awaitables to execute concurrently.
        return_exceptions: If True, exceptions are returned in results list.
            If False (default), first exception propagates after cancelling others.

    Returns:
        List of results in the same order as input awaitables.
        May contain exceptions if return_exceptions=True.

    Raises:
        BaseExceptionGroup: If return_exceptions=False and any awaitable raises.

    Example:
        >>> results = await gather(fetch_a(), fetch_b(), fetch_c())
        >>> # With error handling:
        >>> results = await gather(*tasks, return_exceptions=True)
        >>> errors = [r for r in results if isinstance(r, Exception)]
    """
    if not aws:
        return []

    results: list[T | BaseException | None] = [None] * len(aws)

    async def _runner(idx: int, aw: Awaitable[T]) -> None:
        try:
            results[idx] = await aw
        except BaseException as exc:
            results[idx] = exc
            if not return_exceptions:
                raise

    try:
        async with create_task_group() as tg:
            for i, aw in enumerate(aws):
                tg.start_soon(_runner, i, aw)
    except BaseExceptionGroup as eg:
        if not return_exceptions:
            rest = non_cancel_subgroup(eg)
            if rest is not None:
                raise rest from eg
            raise  # pragma: no cover

    return results  # type: ignore


async def race(*aws: Awaitable[T]) -> T:
    """Return the result of the first awaitable to complete.

    Cancels all remaining awaitables once a winner is determined.
    If the first to complete raises, that exception is re-raised.

    Args:
        *aws: Awaitables to race. Must provide at least one.

    Returns:
        Result of the first awaitable to complete successfully.

    Raises:
        ValueError: If no awaitables provided.
        BaseException: If the winning awaitable raises.

    Example:
        >>> result = await race(slow_api(), fast_cache(), timeout_fallback())
    """
    if not aws:
        raise ValueError("race() requires at least one awaitable")

    send, recv = anyio.create_memory_object_stream(1)

    async def _runner(aw: Awaitable[T]) -> None:
        try:
            res = await aw
            await send.send((True, res))
        except BaseException as exc:
            await send.send((False, exc))

    async with send, recv, create_task_group() as tg:
        for aw in aws:
            tg.start_soon(_runner, aw)
        ok, payload = await recv.receive()
        tg.cancel_scope.cancel()

    if ok:
        return payload  # type: ignore[return-value]
    raise payload  # type: ignore[misc]


async def bounded_map(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]:
    """Apply async function to items with bounded concurrency.

    Maintains input order in results while limiting concurrent executions.

    Args:
        func: Async function to apply to each item.
        items: Iterable of items to process.
        limit: Maximum concurrent executions (must be >= 1).
        return_exceptions: If True, exceptions are returned in results.
            If False, first exception propagates.

    Returns:
        List of results in input order.

    Raises:
        ValueError: If limit < 1.
        BaseExceptionGroup: If return_exceptions=False and any call raises.

    Example:
        >>> async def fetch(url): ...
        >>> results = await bounded_map(fetch, urls, limit=10)
    """
    if limit <= 0:
        raise ValueError("limit must be >= 1")

    seq = list(items)
    if not seq:
        return []

    out: list[R | BaseException | None] = [None] * len(seq)
    limiter = CapacityLimiter(limit)

    async def _runner(i: int, x: T) -> None:
        async with limiter:
            try:
                out[i] = await func(x)
            except BaseException as exc:
                out[i] = exc
                if not return_exceptions:
                    raise

    try:
        async with create_task_group() as tg:
            for i, x in enumerate(seq):
                tg.start_soon(_runner, i, x)
    except BaseExceptionGroup as eg:
        if not return_exceptions:
            rest = non_cancel_subgroup(eg)
            if rest is not None:
                raise rest from eg
            raise  # pragma: no cover

    return out  # type: ignore


class CompletionStream:
    """Iterate async results as they complete (first-finished order).

    Provides structured concurrency with optional concurrency limiting.
    Must be used as an async context manager.

    Args:
        aws: Sequence of awaitables to execute.
        limit: Max concurrent executions (None = unlimited).
        return_exceptions: If True, exceptions are yielded as results.
            If False (default), exceptions propagate and terminate iteration.

    Example:
        >>> async with CompletionStream(tasks, limit=5) as stream:
        ...     async for idx, result in stream:
        ...         print(f"Task {idx} completed: {result}")

    Note:
        Results are yielded as (index, result) tuples where index is the
        original position in the input sequence.
    """

    def __init__(
        self,
        aws: Sequence[Awaitable[T]],
        *,
        limit: int | None = None,
        return_exceptions: bool = False,
    ):
        self.aws = aws
        self.limit = limit
        self.return_exceptions = return_exceptions
        self._task_group: anyio.abc.TaskGroup | None = None
        self._send: anyio.abc.ObjectSendStream[tuple[int, T]] | None = None
        self._recv: anyio.abc.ObjectReceiveStream[tuple[int, T]] | None = None
        self._completed_count = 0
        self._total_count = len(aws)

    async def __aenter__(self):
        n = len(self.aws)
        self._send, self._recv = anyio.create_memory_object_stream(n)
        self._task_group = anyio.create_task_group()
        await self._task_group.__aenter__()

        limiter = CapacityLimiter(self.limit) if self.limit else None

        async def _runner(i: int, aw: Awaitable[T]) -> None:
            if limiter:
                await limiter.acquire()
            try:
                try:
                    res = await aw
                except BaseException as exc:
                    if self.return_exceptions:
                        res = exc  # type: ignore[assignment]
                    else:
                        raise
                try:
                    assert self._send is not None
                    await self._send.send((i, res))  # type: ignore[arg-type]
                except anyio.ClosedResourceError:  # pragma: no cover
                    pass
            finally:
                if limiter:
                    limiter.release()

        for i, aw in enumerate(self.aws):
            self._task_group.start_soon(_runner, i, aw)

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._task_group:
                await self._task_group.__aexit__(exc_type, exc_val, exc_tb)
        finally:
            if self._send:
                await self._send.aclose()
            if self._recv:
                await self._recv.aclose()
        return False

    def __aiter__(self):
        if not self._recv:
            raise RuntimeError("CompletionStream must be used as async context manager")
        return self

    async def __anext__(self):
        if self._completed_count >= self._total_count:
            raise StopAsyncIteration

        try:
            result = await self._recv.receive()
            self._completed_count += 1
            return result
        except anyio.EndOfStream:  # pragma: no cover
            raise StopAsyncIteration


async def retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    jitter: float = 0.1,
) -> T:
    """Retry async function with exponential backoff and deadline awareness.

    Respects structured concurrency: cancellation is never retried.
    Automatically caps delays to any ambient deadline from parent scope.

    Args:
        fn: Zero-argument async callable to retry.
        attempts: Maximum attempts (>= 1).
        base_delay: Initial delay in seconds (> 0).
        max_delay: Maximum delay cap in seconds (>= 0).
        retry_on: Exception types to retry on (must not include CancelledError).
        jitter: Random jitter factor (0.1 = up to 10% extra delay).

    Returns:
        Result of successful fn() call.

    Raises:
        ValueError: If parameters are invalid or retry_on includes cancellation.
        BaseException: Last exception after exhausting attempts.

    Example:
        >>> async def flaky_api():
        ...     return await http_client.get(url)
        >>> result = await retry(flaky_api, attempts=3, base_delay=0.5)
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if base_delay <= 0:
        raise ValueError("base_delay must be > 0")
    if max_delay < 0:
        raise ValueError("max_delay must be >= 0")
    if jitter < 0:
        raise ValueError("jitter must be >= 0")

    cancelled_exc = anyio.get_cancelled_exc_class()
    if any(issubclass(cancelled_exc, t) for t in retry_on):
        raise ValueError("retry_on must not include the cancellation exception type")

    attempt = 0
    deadline = effective_deadline()
    while True:
        try:
            return await fn()
        except retry_on:
            attempt += 1
            if attempt >= attempts:
                raise

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            if jitter:
                delay *= 1 + random.random() * jitter

            if deadline is not None:
                remaining = deadline - current_time()
                if remaining <= 0:  # pragma: no cover
                    raise
                with move_on_at(deadline):
                    await anyio.sleep(delay)
                if current_time() >= deadline:  # pragma: no cover
                    raise
            else:
                await anyio.sleep(delay)
