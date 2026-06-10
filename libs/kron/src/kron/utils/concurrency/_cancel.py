"""Cancellation scope utilities wrapping anyio with None-safe timeouts.

Provides context managers for timeout-based cancellation:
- `fail_after`/`fail_at`: Raise TimeoutError on expiry
- `move_on_after`/`move_on_at`: Silent cancellation on expiry

All accept None to disable timeout while preserving outer scope cancellability.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import anyio

from ._utils import current_time

CancelScope = anyio.CancelScope


__all__ = (
    "CancelScope",
    "effective_deadline",
    "fail_after",
    "fail_at",
    "move_on_after",
    "move_on_at",
)


@contextmanager
def fail_after(seconds: float | None) -> Iterator[CancelScope]:
    """Context manager that raises TimeoutError after elapsed seconds.

    Args:
        seconds: Timeout duration, or None to disable timeout.

    Yields:
        CancelScope that can be checked via `scope.cancelled_caught`.
    """
    if seconds is None:
        with CancelScope() as scope:
            yield scope
        return
    with anyio.fail_after(seconds) as scope:
        yield scope


@contextmanager
def move_on_after(seconds: float | None) -> Iterator[CancelScope]:
    """Context manager that silently cancels after elapsed seconds.

    Args:
        seconds: Timeout duration, or None to disable timeout.

    Yields:
        CancelScope; check `scope.cancelled_caught` to detect timeout.
    """
    if seconds is None:
        with CancelScope() as scope:
            yield scope
        return
    with anyio.move_on_after(seconds) as scope:
        yield scope


@contextmanager
def fail_at(deadline: float | None) -> Iterator[CancelScope]:
    """Context manager that raises TimeoutError at absolute deadline.

    Args:
        deadline: Absolute time (from `current_time()`), or None to disable.

    Yields:
        CancelScope that can be checked via `scope.cancelled_caught`.
    """
    if deadline is None:
        with CancelScope() as scope:
            yield scope
        return
    now = current_time()
    seconds = max(0.0, deadline - now)
    with fail_after(seconds) as scope:
        yield scope


@contextmanager
def move_on_at(deadline: float | None) -> Iterator[CancelScope]:
    """Context manager that silently cancels at absolute deadline.

    Args:
        deadline: Absolute time (from `current_time()`), or None to disable.

    Yields:
        CancelScope; check `scope.cancelled_caught` to detect timeout.
    """
    if deadline is None:
        with CancelScope() as scope:
            yield scope
        return
    now = current_time()
    seconds = max(0.0, deadline - now)
    with anyio.move_on_after(seconds) as scope:
        yield scope


def effective_deadline() -> float | None:
    """Return current effective deadline from enclosing cancel scopes.

    Returns:
        Absolute deadline time, -inf if already cancelled, or None if unlimited.

    Note:
        AnyIO uses +inf for "no deadline" and -inf for "already cancelled".
        This function returns None for +inf but preserves -inf for detection.
    """
    d = anyio.current_effective_deadline()
    return None if d == float("inf") else d
