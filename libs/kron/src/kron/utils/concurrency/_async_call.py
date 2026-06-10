"""Async batch processing with retry, timeout, and concurrency control.

Primary exports:
    alcall: Apply function to list elements concurrently with full control.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from ._cancel import move_on_after
from ._errors import get_cancelled_exc_class, non_cancel_subgroup
from ._primitives import Semaphore
from ._task import create_task_group
from ._utils import is_coro_func, run_sync, sleep

T = TypeVar("T")

__all__ = ("alcall",)


async def _call_with_timeout(
    func: Callable,
    item: Any,
    is_coro: bool,
    timeout: float | None,
    **kwargs,
) -> Any:
    """Invoke function with optional timeout, handling both sync and async."""
    if is_coro:
        if timeout is not None:
            with move_on_after(timeout) as cancel_scope:
                result = await func(item, **kwargs)
            if cancel_scope.cancelled_caught:
                raise TimeoutError(f"Function call timed out after {timeout}s")
            return result
        return await func(item, **kwargs)
    else:
        if timeout is not None:
            with move_on_after(timeout) as cancel_scope:
                result = await run_sync(func, item, **kwargs)
            if cancel_scope.cancelled_caught:
                raise TimeoutError(f"Function call timed out after {timeout}s")
            return result
        return await run_sync(func, item, **kwargs)


async def _execute_with_retry(
    func: Callable,
    item: Any,
    index: int,
    *,
    is_coro: bool,
    timeout: float | None,
    initial_delay: float,
    backoff: float,
    max_attempts: int,
    default: Any,
    has_default: bool,
    **kwargs,
) -> tuple[int, Any]:
    """Execute function with exponential backoff retry.

    Returns (index, result) tuple to preserve ordering in concurrent execution.
    Cancellation exceptions are never retried (respects structured concurrency).
    """
    attempts = 0
    current_delay = initial_delay

    while True:
        try:
            result = await _call_with_timeout(func, item, is_coro, timeout, **kwargs)
            return index, result

        except get_cancelled_exc_class():
            raise

        except Exception:
            attempts += 1
            if attempts <= max_attempts:
                if current_delay:
                    await sleep(current_delay)
                    current_delay *= backoff
            else:
                if has_default:
                    return index, default
                raise


async def alcall(
    input_: list[Any],
    func: Callable[..., T],
    /,
    *,
    retry_initial_delay: float = 0,
    retry_backoff: float = 1,
    retry_default: Any = None,
    retry_timeout: float | None = None,
    retry_attempts: int = 0,
    max_concurrent: int | None = None,
    throttle_period: float | None = None,
    return_exceptions: bool = False,
    **kwargs: Any,
) -> list[T | BaseException]:
    """Apply function to each list element asynchronously with retry and concurrency control.

    Args:
        input_: List of items to process
        func: Callable to apply (sync or async)
        retry_initial_delay: Initial retry delay (seconds)
        retry_backoff: Backoff multiplier for retry delays
        retry_default: Default value on retry exhaustion (None = raise)
        retry_timeout: Timeout per function call (seconds)
        retry_attempts: Maximum retry attempts (0 = no retry)
        max_concurrent: Max concurrent executions (None = unlimited)
        throttle_period: Delay between starting tasks (seconds)
        return_exceptions: Return exceptions instead of raising
        **kwargs: Additional arguments passed to func

    Returns:
        List of results (preserves input order, may include exceptions if return_exceptions=True)

    Raises:
        ValueError: If func is not callable
        TimeoutError: If retry_timeout exceeded
        ExceptionGroup: If return_exceptions=False and tasks raise
    """
    if not callable(func):
        raise ValueError("func must be callable")

    if not isinstance(input_, list):
        input_ = list(input_)

    if not input_:
        return []

    semaphore = Semaphore(max_concurrent) if max_concurrent else None
    throttle_delay = throttle_period or 0
    is_coro = is_coro_func(func)
    n_items = len(input_)
    out: list[Any] = [None] * n_items

    # Check if retry_default was explicitly provided
    has_default = retry_default is not None or "retry_default" in kwargs

    async def task_wrapper(item: Any, idx: int) -> None:
        try:
            if semaphore:
                async with semaphore:
                    _, result = await _execute_with_retry(
                        func,
                        item,
                        idx,
                        is_coro=is_coro,
                        timeout=retry_timeout,
                        initial_delay=retry_initial_delay,
                        backoff=retry_backoff,
                        max_attempts=retry_attempts,
                        default=retry_default,
                        has_default=has_default,
                        **kwargs,
                    )
            else:
                _, result = await _execute_with_retry(
                    func,
                    item,
                    idx,
                    is_coro=is_coro,
                    timeout=retry_timeout,
                    initial_delay=retry_initial_delay,
                    backoff=retry_backoff,
                    max_attempts=retry_attempts,
                    default=retry_default,
                    has_default=has_default,
                    **kwargs,
                )
            out[idx] = result
        except BaseException as exc:
            out[idx] = exc
            if not return_exceptions:
                raise

    try:
        async with create_task_group() as tg:
            for idx, item in enumerate(input_):
                tg.start_soon(task_wrapper, item, idx)
                if throttle_delay and idx < n_items - 1:
                    await sleep(throttle_delay)
    except ExceptionGroup as eg:
        if not return_exceptions:
            rest = non_cancel_subgroup(eg)
            if rest is not None:
                raise rest
            raise

    return out
