"""Hook system for service lifecycle callbacks.

Provides:
    - HookPhase: Enum for lifecycle phases (PreInvocation, PostInvocation, ErrorHandling)
    - HookRegistry: Registry for phase-based hook callbacks
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from kron.types import Enum
from kron.utils import concurrency

__all__ = (
    "HookPhase",
    "HookRegistry",
    "get_handler",
    "validate_hooks",
)

K = TypeVar("K")


class HookPhase(Enum):
    """Event lifecycle phases for hook registration.

    Hooks execute at specific points in Event lifecycle:
    - PreEventCreate: Before Event instantiation (receives event type)
    - PreInvocation: After Event created, before invoke() (receives event instance)
    - PostInvocation: After invoke() completes (receives event with result)
    - ErrorHandling: On exception during invocation
    """

    PreEventCreate = "pre_event_create"
    PreInvocation = "pre_invocation"
    PostInvocation = "post_invocation"
    ErrorHandling = "error_handling"


def get_handler(
    d_: dict[K, Any], k: K, get: bool = False, /
) -> Callable[..., Awaitable[Any]] | None:
    """Retrieve async handler from dict, wrapping sync functions if needed.

    Args:
        d_: Handler dictionary (HookPhase->handler or chunk_type->handler).
        k: Key to look up.
        get: If True, return default passthrough handler when key missing.

    Returns:
        Async handler function, or None if key missing and get=False.
    """
    handler = d_.get(k)
    if handler is None and not get:
        return None

    if handler is not None:
        if not concurrency.is_coro_func(handler):

            async def _wrapper(*args: Any, **kwargs: Any) -> Any:
                await concurrency.sleep(0)
                return handler(*args, **kwargs)

            return _wrapper
        return handler

    async def _default_handler(*args: Any, **_kwargs: Any) -> Any:
        await concurrency.sleep(0)
        return args[0] if args else None

    return _default_handler


def validate_hooks(kw: dict[Any, Any]) -> None:
    """Validate hook dict: keys must be HookPhase, values must be callable.

    Raises:
        ValueError: If dict structure or types are invalid.
    """
    if not isinstance(kw, dict):
        raise ValueError("Hooks must be a dictionary of callable functions")

    for k, v in kw.items():
        if not isinstance(k, HookPhase) or k not in HookPhase.allowed():
            raise ValueError(f"Hook key must be one of {HookPhase.allowed()}, got {k}")
        if not callable(v):
            raise ValueError(f"Hook for {k} must be callable, got {type(v)}")


def validate_stream_handlers(kw: dict[Any, Any]) -> None:
    """Validate stream handler dict: keys must be str|type, values callable.

    Raises:
        ValueError: If dict structure or types are invalid.
    """
    if not isinstance(kw, dict):
        raise ValueError("Stream handlers must be a dictionary of callable functions")

    for k, v in kw.items():
        if not isinstance(k, str | type):
            raise ValueError(f"Stream handler key must be a string or type, got {type(k)}")

        if not callable(v):
            raise ValueError(f"Stream handler for {k} must be callable, got {type(v)}")


class HookRegistry:
    """Registry for hook callbacks at Event lifecycle phases.

    Manages two handler types:
    - Phase hooks: Execute at PreEventCreate/PreInvocation/PostInvocation/ErrorHandling
    - Stream handlers: Process chunks during streaming (keyed by type name or class)

    Handler semantics:
    - Return value: Passed through to caller
    - Raise exception: Cancels/aborts operation (status depends on phase)
    - Exit flag: Determines whether exception should halt further processing

    Example:
        >>> async def pre_hook(event, **kw):
        ...     print(f"Pre-invoke: {event}")
        ...     return event
        >>> registry = HookRegistry(hooks={HookPhase.PreInvocation: pre_hook})
        >>> result = await registry.pre_invocation(event)
    """

    _hooks: dict[HookPhase, Callable[..., Any]]
    _stream_handlers: dict[str | type, Callable[..., Any]]

    def __init__(
        self,
        hooks: dict[HookPhase, Callable[..., Any]] | None = None,
        stream_handlers: dict[str | type, Callable[..., Any]] | None = None,
    ):
        """Initialize registry with optional hooks and stream handlers.

        Args:
            hooks: Mapping of HookPhase to handler callables.
            stream_handlers: Mapping of chunk type (str|type) to handler callables.
        """
        _hooks: dict[HookPhase, Callable[..., Any]] = {}
        _stream_handlers: dict[str | type, Callable[..., Any]] = {}

        if hooks is not None:
            validate_hooks(hooks)
            _hooks.update(hooks)

        if stream_handlers is not None:
            validate_stream_handlers(stream_handlers)
            _stream_handlers.update(stream_handlers)

        self._hooks = _hooks
        self._stream_handlers = _stream_handlers

    def can_handle(self, phase: HookPhase) -> bool:
        """Check if the registry has a handler for the given phase."""
        return phase in self._hooks

    async def _call_hook(
        self,
        phase: HookPhase,
        event_like: Any,
        **kw: Any,
    ) -> Any:
        """Internal dispatch to hook handler."""
        if phase not in self._hooks:
            return event_like

        handler = get_handler(self._hooks, phase, True)
        if handler is not None:
            return await handler(event_like, **kw)
        return event_like

    async def pre_event_create(
        self, event_type: type, /, exit: bool = False, **kw: Any
    ) -> tuple[Any, bool, str]:
        """Execute PreEventCreate hook before Event instantiation.

        Args:
            event_type: Event class being created.
            exit: If True and hook raises, signal caller to halt.
            **kw: Passed to hook handler.

        Returns:
            Tuple of (result|exception, should_exit, status).
        """
        try:
            res = await self._call_hook(HookPhase.PreEventCreate, event_type, exit=exit, **kw)
            return (res, False, "completed")
        except concurrency.get_cancelled_exc_class() as e:
            return (e, True, "cancelled")
        except Exception as e:
            return (e, exit, "cancelled")

    async def pre_invocation(
        self, event: Any, /, exit: bool = False, **kw: Any
    ) -> tuple[Any, bool, str]:
        """Execute PreInvocation hook before Event.invoke().

        Args:
            event: Event instance about to be invoked.
            exit: If True and hook raises, signal caller to halt.
            **kw: Passed to hook handler.

        Returns:
            Tuple of (result|exception, should_exit, status).
        """
        try:
            res = await self._call_hook(HookPhase.PreInvocation, event, exit=exit, **kw)
            return (res, False, "completed")
        except concurrency.get_cancelled_exc_class() as e:
            return (e, True, "cancelled")
        except Exception as e:
            return (e, exit, "cancelled")

    async def post_invocation(
        self, event: Any, /, exit: bool = False, **kw: Any
    ) -> tuple[Any, bool, str]:
        """Execute PostInvocation hook after Event.invoke() completes.

        Args:
            event: Event instance with execution results populated.
            exit: If True and hook raises, signal caller to halt.
            **kw: Passed to hook handler.

        Returns:
            Tuple of (result|exception, should_exit, status). Status is aborted on error.
        """
        try:
            res = await self._call_hook(HookPhase.PostInvocation, event, exit=exit, **kw)
            return (res, False, "completed")
        except concurrency.get_cancelled_exc_class() as e:
            return (e, True, "cancelled")
        except Exception as e:
            return (e, exit, "aborted")

    async def error_handling(
        self, event: Any, error: BaseException, /, exit: bool = False, **kw: Any
    ) -> tuple[Any, bool, str]:
        """Execute ErrorHandling hook on exception.

        Args:
            event: Event instance that failed.
            error: The exception that occurred.
            exit: If True and hook raises, signal caller to halt.
            **kw: Passed to hook handler.

        Returns:
            Tuple of (result|exception, should_exit, status).
        """
        try:
            res = await self._call_hook(
                HookPhase.ErrorHandling, event, error=error, exit=exit, **kw
            )
            return (res, False, "completed")
        except concurrency.get_cancelled_exc_class() as e:
            return (e, True, "cancelled")
        except Exception as e:
            return (e, exit, "aborted")

    async def handle_streaming_chunk(
        self,
        chunk_type: str | type | None,
        chunk: Any,
        /,
        exit: bool = False,
        **kw: Any,
    ) -> tuple[Any, bool, str | None]:
        """Process a streaming chunk via registered handler.

        Args:
            chunk_type: Type identifier for handler lookup (str name or class).
            chunk: The chunk data to process.
            exit: If True and handler raises, signal caller to halt.
            **kw: Passed to handler.

        Returns:
            Tuple of (result|exception, should_exit, status|None).

        Raises:
            ValueError: If chunk_type is None.
        """
        if chunk_type is None:
            raise ValueError("chunk_type cannot be None for streaming chunks")

        if chunk_type not in self._stream_handlers:
            return (chunk, False, None)

        try:
            handler = get_handler(self._stream_handlers, chunk_type, True)
            if handler is not None:
                res = await handler(chunk, **kw)
                return (res, False, None)
            return (chunk, False, None)
        except concurrency.get_cancelled_exc_class() as e:
            return (e, True, "cancelled")
        except Exception as e:
            return (e, exit, "aborted")

    async def call(
        self,
        event_like: Any,
        /,
        *,
        hook_phase: HookPhase | None = None,
        chunk_type: str | type | None = None,
        chunk: Any = None,
        exit: bool = False,
        **kw: Any,
    ) -> tuple[Any, bool, str | None]:
        """Call a hook or stream handler.

        If hook_phase is provided, it will call the corresponding hook.
        If chunk_type is provided, it will call the corresponding stream handler.
        If both are provided, hook_phase will be used.
        """
        if hook_phase is None and chunk_type is None:
            raise ValueError("Either hook_phase or chunk_type must be provided")

        if hook_phase:
            match hook_phase:
                case HookPhase.PreEventCreate | HookPhase.PreEventCreate.value:
                    return await self.pre_event_create(event_like, exit=exit, **kw)
                case HookPhase.PreInvocation | HookPhase.PreInvocation.value:
                    return await self.pre_invocation(event_like, exit=exit, **kw)
                case HookPhase.PostInvocation | HookPhase.PostInvocation.value:
                    return await self.post_invocation(event_like, exit=exit, **kw)
                case HookPhase.ErrorHandling | HookPhase.ErrorHandling.value:
                    error = kw.pop("error", None)
                    return await self.error_handling(event_like, error, exit=exit, **kw)

        return await self.handle_streaming_chunk(chunk_type, chunk, exit=exit, **kw)
