"""Async synchronization primitives wrapping anyio.

All primitives support async context manager protocol for safe acquire/release:

    async with Lock() as lock:
        # critical section

    async with Semaphore(3) as sem:
        # limited concurrency section
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Self, TypeVar

import anyio
import anyio.abc

T = TypeVar("T")


__all__ = (
    "CapacityLimiter",
    "Condition",
    "Event",
    "Lock",
    "Queue",
    "Semaphore",
)


class Lock:
    """Async mutex lock for exclusive access to shared resources.

    Usage:
        lock = Lock()
        async with lock:
            # exclusive access
    """

    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = anyio.Lock()

    async def acquire(self) -> None:
        """Acquire lock, blocking until available."""
        await self._lock.acquire()

    def release(self) -> None:
        """Release lock. Must hold lock before calling."""
        self._lock.release()

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


class Semaphore:
    """Async counting semaphore for limiting concurrent access.

    Args:
        initial_value: Maximum concurrent acquisitions allowed.

    Raises:
        ValueError: If initial_value < 0.

    Usage:
        sem = Semaphore(3)  # max 3 concurrent
        async with sem:
            # limited concurrency section
    """

    __slots__ = ("_sem",)

    def __init__(self, initial_value: int) -> None:
        if initial_value < 0:
            raise ValueError("initial_value must be >= 0")
        self._sem = anyio.Semaphore(initial_value)

    async def acquire(self) -> None:
        """Acquire semaphore slot, blocking if none available."""
        await self._sem.acquire()

    def release(self) -> None:
        """Release semaphore slot, waking one waiting task."""
        self._sem.release()

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


class CapacityLimiter:
    """Async capacity limiter for resource pool management.

    Unlike Semaphore, supports fractional tokens and borrower tracking.

    Args:
        total_tokens: Total capacity (must be > 0).

    Raises:
        ValueError: If total_tokens <= 0.

    Usage:
        limiter = CapacityLimiter(10.0)
        async with limiter:
            # uses 1 token
    """

    __slots__ = ("_lim",)

    def __init__(self, total_tokens: float) -> None:
        if total_tokens <= 0:
            raise ValueError("total_tokens must be > 0")
        self._lim = anyio.CapacityLimiter(total_tokens)

    async def acquire(self) -> None:
        """Acquire one token, blocking until available."""
        await self._lim.acquire()

    def release(self) -> None:
        """Release one token back to the pool."""
        self._lim.release()

    @property
    def remaining_tokens(self) -> float:
        """Alias for available_tokens. Use available_tokens instead."""
        return self._lim.available_tokens

    @property
    def total_tokens(self) -> float:
        """Total capacity configured for this limiter."""
        return self._lim.total_tokens

    @total_tokens.setter
    def total_tokens(self, value: float) -> None:
        if value <= 0:
            raise ValueError("total_tokens must be > 0")
        self._lim.total_tokens = value

    @property
    def borrowed_tokens(self) -> float:
        """Currently borrowed (in-use) tokens."""
        return self._lim.borrowed_tokens

    @property
    def available_tokens(self) -> float:
        """Tokens available for acquisition."""
        return self._lim.available_tokens

    async def acquire_on_behalf_of(self, borrower: object) -> None:
        """Acquire token tracked to specific borrower for debugging."""
        await self._lim.acquire_on_behalf_of(borrower)

    def release_on_behalf_of(self, borrower: object) -> None:
        """Release token previously acquired by specific borrower."""
        self._lim.release_on_behalf_of(borrower)

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()


@dataclass(slots=True)
class Queue(Generic[T]):
    """Async bounded FIFO queue backed by memory object streams.

    Use factory method `with_maxsize()` to create instances.

    Usage:
        queue: Queue[int] = Queue.with_maxsize(100)
        await queue.put(42)
        item = await queue.get()
    """

    _send: anyio.abc.ObjectSendStream[T]
    _recv: anyio.abc.ObjectReceiveStream[T]

    @classmethod
    def with_maxsize(cls, maxsize: int) -> Queue[T]:
        """Create bounded queue.

        Args:
            maxsize: Maximum items before put() blocks.

        Returns:
            New Queue instance.
        """
        send, recv = anyio.create_memory_object_stream(maxsize)
        return cls(send, recv)

    async def put(self, item: T) -> None:
        """Add item, blocking if queue is full."""
        await self._send.send(item)

    def put_nowait(self, item: T) -> None:
        """Add item without blocking. Raises WouldBlock if full."""
        self._send.send_nowait(item)  # type: ignore[attr-defined]

    async def get(self) -> T:
        """Remove and return item, blocking if empty."""
        return await self._recv.receive()

    def get_nowait(self) -> T:
        """Remove and return item. Raises WouldBlock if empty."""
        return self._recv.receive_nowait()  # type: ignore[attr-defined]

    async def close(self) -> None:
        """Close both send and receive streams."""
        await self._send.aclose()
        await self._recv.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    @property
    def sender(self) -> anyio.abc.ObjectSendStream[T]:
        """Underlying send stream for advanced usage."""
        return self._send

    @property
    def receiver(self) -> anyio.abc.ObjectReceiveStream[T]:
        """Underlying receive stream for advanced usage."""
        return self._recv


class Event:
    """One-shot async event for task coordination.

    Once set, remains set forever (no reset). All waiters wake simultaneously.

    Usage:
        event = Event()
        # Task A:
        await event.wait()  # blocks until set
        # Task B:
        event.set()  # wakes all waiters
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = anyio.Event()

    def set(self) -> None:
        """Set event flag, waking all waiters. Idempotent."""
        self._event.set()

    def is_set(self) -> bool:
        """Return True if event has been set."""
        return self._event.is_set()

    async def wait(self) -> None:
        """Block until event is set. Returns immediately if already set."""
        await self._event.wait()

    def statistics(self) -> anyio.EventStatistics:
        """Return statistics about waiting tasks."""
        return self._event.statistics()


class Condition:
    """Async condition variable for complex synchronization patterns.

    Args:
        lock: Optional Lock to use. Creates internal lock if None.

    Usage:
        cond = Condition()
        async with cond:
            while not ready:
                await cond.wait()
            # condition met, proceed
    """

    __slots__ = ("_condition",)

    def __init__(self, lock: Lock | None = None) -> None:
        _lock = lock._lock if lock else None
        self._condition = anyio.Condition(_lock)

    async def acquire(self) -> None:
        """Acquire the underlying lock."""
        await self._condition.acquire()

    def release(self) -> None:
        """Release the underlying lock."""
        self._condition.release()

    async def __aenter__(self) -> Self:
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.release()

    async def wait(self) -> None:
        """Release lock, wait for notify, re-acquire lock. Must hold lock."""
        await self._condition.wait()

    def notify(self, n: int = 1) -> None:
        """Wake up to n waiting tasks. Must hold lock."""
        self._condition.notify(n)

    def notify_all(self) -> None:
        """Wake all waiting tasks. Must hold lock."""
        self._condition.notify_all()

    def statistics(self) -> anyio.ConditionStatistics:
        """Return statistics about lock and waiting tasks."""
        return self._condition.statistics()
