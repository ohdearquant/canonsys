"""Event: Async executable with lifecycle tracking and execution state."""

from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass
from typing import Any, final

import orjson
from pydantic import Field, field_serializer, field_validator

from kron.errors import KronError, KronTimeoutError
from kron.protocols import Invocable, Serializable, implements
from kron.types import Enum, MaybeSentinel, MaybeUnset, Unset, is_sentinel, is_unset
from kron.utils import async_synchronized, concurrency, json_dumpb

from .element import LN_ELEMENT_FIELDS, Element

__all__ = (
    "Event",
    "EventStatus",
    "Execution",
)


class EventStatus(Enum):
    """Event execution status states.

    Values:
        PENDING: Not yet started
        PROCESSING: Currently executing
        COMPLETED: Finished successfully
        FAILED: Execution failed with error
        CANCELLED: Interrupted by timeout or cancellation
        SKIPPED: Bypassed due to condition
        ABORTED: Pre-validation rejected, never started
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    ABORTED = "aborted"


@implements(Serializable)
@dataclass(slots=True)
class Execution:
    """Execution state (status, duration, response, error, retryable).

    Attributes:
        status: Current execution status
        duration: Elapsed time in seconds (Unset until complete)
        response: Result (Unset if unavailable, None if legitimate null)
        error: Exception if failed (Unset/None/BaseException)
        retryable: Whether retry is safe (Unset/bool)
    """

    status: EventStatus = EventStatus.PENDING
    duration: MaybeUnset[float] = Unset
    response: MaybeSentinel[Any] = Unset
    error: MaybeUnset[BaseException] | None = Unset
    retryable: MaybeUnset[bool] = Unset

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize to dict. Sentinels become None; errors become dicts."""
        res_ = Unset
        if is_sentinel(self.response):
            res_ = None
        else:
            with contextlib.suppress(orjson.JSONDecodeError, TypeError):
                res_ = json_dumpb(self.response)
            if is_unset(res_):
                res_ = "<unserializable>"

        error_dict = None
        if not is_unset(self.error) and self.error is not None:
            if isinstance(self.error, Serializable):
                error_dict = self.error.to_dict()
            elif isinstance(self.error, ExceptionGroup):
                error_dict = self._serialize_exception_group(self.error)
            else:
                error_dict = {
                    "error": type(self.error).__name__,
                    "message": str(self.error),
                }

        duration_value = None if is_unset(self.duration) else self.duration
        retryable_value = None if is_unset(self.retryable) else self.retryable

        return {
            "status": self.status.value,
            "duration": duration_value,
            "response": res_,
            "error": error_dict,
            "retryable": retryable_value,
        }

    def _serialize_exception_group(
        self,
        eg: ExceptionGroup,
        depth: int = 0,
        _seen: set[int] | None = None,
    ) -> dict[str, Any]:
        """Recursively serialize ExceptionGroup with depth limit and cycle detection.

        Args:
            eg: ExceptionGroup to serialize.
            depth: Current recursion depth (internal).
            _seen: Object IDs already visited for cycle detection (internal).

        Returns:
            Dict with error type, message, and nested exceptions.
        """
        MAX_DEPTH = 100
        if depth > MAX_DEPTH:
            return {
                "error": "ExceptionGroup",
                "message": f"Max nesting depth ({MAX_DEPTH}) exceeded",
                "nested_count": len(eg.exceptions) if hasattr(eg, "exceptions") else 0,
            }

        if _seen is None:
            _seen = set()

        eg_id = id(eg)
        if eg_id in _seen:
            return {
                "error": "ExceptionGroup",
                "message": "Circular reference detected",
            }

        _seen.add(eg_id)

        try:
            exceptions = []
            for exc in eg.exceptions:
                if isinstance(exc, Serializable):
                    exceptions.append(exc.to_dict())
                elif isinstance(exc, ExceptionGroup):
                    exceptions.append(self._serialize_exception_group(exc, depth + 1, _seen))
                else:
                    exceptions.append(
                        {
                            "error": type(exc).__name__,
                            "message": str(exc),
                        }
                    )

            return {
                "error": type(eg).__name__,
                "message": str(eg),
                "exceptions": exceptions,
            }
        finally:
            _seen.discard(eg_id)

    def add_error(self, exc: BaseException) -> None:
        """Add error; creates ExceptionGroup if multiple errors accumulated."""
        if is_unset(self.error) or self.error is None:
            self.error = exc
        elif isinstance(self.error, ExceptionGroup):
            self.error = ExceptionGroup(  # type: ignore[type-var]
                "multiple errors",
                [*self.error.exceptions, exc],
            )
        else:
            self.error = ExceptionGroup(  # type: ignore[type-var]
                "multiple errors",
                [self.error, exc],
            )


@implements(Invocable)
class Event(Element):
    """Base event with lifecycle tracking and execution state.

    Subclasses implement _invoke(). invoke() manages transitions, timing, errors.

    Attributes:
        execution: Execution state
        timeout: Optional timeout in seconds (None = no timeout)
    """

    execution: Execution = Field(default_factory=Execution)
    timeout: MaybeUnset[float] = Field(Unset, exclude=True)
    streaming: bool = Field(False, exclude=True)

    def model_post_init(self, __context) -> None:
        """Initialize async lock for thread-safe invoke()."""
        super().model_post_init(__context)
        self._async_lock = concurrency.Lock()

    @field_validator("timeout")
    @classmethod
    def _validate_timeout(cls, v: Any) -> MaybeUnset[float]:
        """Validate timeout is positive and finite (raises ValueError if not)."""
        if is_sentinel(v, {"none", "empty"}):
            return Unset
        if not math.isfinite(v):
            raise ValueError(f"timeout must be finite, got {v}")
        if v <= 0:
            raise ValueError(f"timeout must be positive, got {v}")
        return v

    @field_serializer("execution")
    def _serialize_execution(self, val: Execution) -> dict:
        """Serialize Execution to dict."""
        return val.to_dict()

    @property
    def request(self) -> dict:
        """Request parameters for this event. Override in subclasses."""
        return {}

    async def _invoke(self) -> Any:
        """Execute event logic. Subclasses must override."""
        raise NotImplementedError("Subclasses must implement _invoke()")

    @final
    @async_synchronized
    async def invoke(self) -> None:
        """Execute with lifecycle management: status tracking, timing, error capture.

        Idempotent: no-op if status is not PENDING. Thread-safe via async lock.
        Sets execution.status, duration, response/error, and retryable flag.
        """
        if self.execution.status != EventStatus.PENDING:
            return

        start = concurrency.current_time()

        try:
            self.execution.status = EventStatus.PROCESSING

            if not is_unset(self.timeout):
                with concurrency.fail_after(self.timeout):
                    result = await self._invoke()
            else:
                result = await self._invoke()

            self.execution.response = result
            self.execution.error = None
            self.execution.status = EventStatus.COMPLETED
            self.execution.retryable = False

        except TimeoutError:
            lion_timeout = KronTimeoutError(
                f"Operation timed out after {self.timeout}s",
                retryable=True,
            )

            self.execution.response = Unset
            self.execution.error = lion_timeout
            self.execution.status = EventStatus.CANCELLED
            self.execution.retryable = lion_timeout.retryable

        except Exception as e:
            if isinstance(e, ExceptionGroup):
                retryable = all(
                    not isinstance(exc, KronError) or exc.retryable for exc in e.exceptions
                )
                self.execution.retryable = retryable
            else:
                self.execution.retryable = e.retryable if isinstance(e, KronError) else True

            self.execution.response = Unset
            self.execution.error = e
            self.execution.status = EventStatus.FAILED

        except BaseException as e:
            if isinstance(e, concurrency.get_cancelled_exc_class()):
                self.execution.response = Unset
                self.execution.error = e
                self.execution.status = EventStatus.CANCELLED
                self.execution.retryable = True

            raise

        finally:
            self.execution.duration = concurrency.current_time() - start

    async def stream(self) -> Any:
        """Stream execution results. Override if streaming=True."""
        raise NotImplementedError("Subclasses must implement stream() if streaming=True")

    def as_fresh_event(self, copy_meta: bool = False) -> Event:
        """Clone with reset execution state (new ID, PENDING status).

        Args:
            copy_meta: If True, copy original metadata to clone.

        Returns:
            Fresh Event with original ID/created_at stored in metadata["original"].
        """
        d_ = self.to_dict()
        for key in ["execution", *LN_ELEMENT_FIELDS]:
            d_.pop(key, None)

        fresh = self.__class__(**d_)

        if not is_sentinel(self.timeout):
            fresh.timeout = self.timeout

        if copy_meta:
            fresh.metadata = self.metadata.copy()

        fresh.metadata["original"] = {
            "id": str(self.id),
            "created_at": self.created_at,
        }
        return fresh
