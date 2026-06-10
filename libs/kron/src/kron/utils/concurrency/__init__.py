"""Async concurrency utilities.

Core Patterns:
    alcall: Apply async function to list with retry, timeout, concurrency control.
    gather: Run awaitables concurrently, collect results in order.
    race: Return first completion, cancel the rest.
    bounded_map: Apply async function with concurrency limit.
    retry: Exponential backoff with deadline awareness.
    CompletionStream: Iterate results as they complete.

Primitives (anyio wrappers):
    Lock, Semaphore, Event, Condition, Queue, CapacityLimiter
    TaskGroup, create_task_group

Cancellation:
    CancelScope, move_on_after, move_on_at, fail_after, fail_at
    effective_deadline, get_cancelled_exc_class, is_cancelled

Utilities:
    run_sync: Run sync function in thread pool.
    sleep, current_time, is_coro_func
"""

from ._async_call import alcall
from ._cancel import (
    CancelScope,
    effective_deadline,
    fail_after,
    fail_at,
    move_on_after,
    move_on_at,
)
from ._errors import (
    get_cancelled_exc_class,
    is_cancelled,
    non_cancel_subgroup,
    shield,
    split_cancellation,
)
from ._patterns import CompletionStream, bounded_map, gather, race, retry
from ._primitives import CapacityLimiter, Condition, Event, Lock, Queue, Semaphore
from ._task import TaskGroup, create_task_group
from ._utils import current_time, is_coro_func, run_sync, sleep

__all__ = (
    # Async call
    "alcall",
    # Cancel
    "CancelScope",
    "effective_deadline",
    "fail_after",
    "fail_at",
    "move_on_after",
    "move_on_at",
    # Errors
    "get_cancelled_exc_class",
    "is_cancelled",
    "non_cancel_subgroup",
    "shield",
    "split_cancellation",
    # Patterns
    "CompletionStream",
    "bounded_map",
    "gather",
    "race",
    "retry",
    # Primitives
    "CapacityLimiter",
    "Condition",
    "Event",
    "Lock",
    "Queue",
    "Semaphore",
    # Task
    "TaskGroup",
    "create_task_group",
    # Utils
    "current_time",
    "is_coro_func",
    "run_sync",
    "sleep",
)
