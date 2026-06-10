"""iModel - Unified service interface for canon.

Provides a high-level interface wrapping ServiceBackend with optional:
- Rate limiting via TokenBucket
- Hook registry for lifecycle callbacks

This is a simplified version for canon's needs, without the full
executor/processor machinery from krons.
"""

from __future__ import annotations

import logging
from typing import Any

from .backend import Calling, NormalizedResponse, ServiceBackend
from .endpoint import Endpoint
from .hook import HookPhase, HookRegistry
from .utilities.rate_limiter import RateLimitConfig, TokenBucket

__all__ = ("iModel",)

logger = logging.getLogger(__name__)


class iModel:
    """Unified service interface wrapping ServiceBackend with rate limiting and hooks.

    Combines ServiceBackend (API abstraction) with optional:
    - Rate limiting: TokenBucket for simple blocking rate limits
    - Hook registry: Lifecycle callbacks at PreInvocation/PostInvocation/ErrorHandling

    Attributes:
        backend: ServiceBackend instance (e.g., Endpoint for HTTP APIs).
        rate_limiter: Optional TokenBucket for simple blocking rate limits.
        hook_registry: Optional HookRegistry for invocation lifecycle callbacks.
        provider_metadata: Provider-specific state (e.g., session_id for context).

    Example:
        >>> endpoint = Endpoint(config=config)
        >>> model = iModel(backend=endpoint, limit_requests=100)
        >>> calling = await model.invoke(model="gpt-4", messages=[...])
        >>> print(calling.response)
    """

    def __init__(
        self,
        backend: ServiceBackend,
        rate_limiter: TokenBucket | None = None,
        hook_registry: HookRegistry | None = None,
        capacity_refresh_time: float = 60.0,
        limit_requests: int | None = None,
    ):
        """Initialize iModel with ServiceBackend.

        Args:
            backend: ServiceBackend instance (required).
            rate_limiter: TokenBucket for simple blocking rate limits.
            hook_registry: HookRegistry for lifecycle callbacks.
            capacity_refresh_time: Seconds for rate limit bucket refill.
            limit_requests: If set without rate_limiter, auto-constructs TokenBucket.
        """
        if rate_limiter is None and limit_requests:
            rate_limiter = TokenBucket(
                RateLimitConfig(
                    capacity=limit_requests,
                    refill_rate=limit_requests / capacity_refresh_time,
                )
            )

        self.backend = backend
        self.rate_limiter = rate_limiter
        self.hook_registry = hook_registry
        self.provider_metadata: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Service name from backend."""
        return self.backend.name

    @property
    def version(self) -> str:
        """Service version from backend."""
        return self.backend.version or ""

    @property
    def tags(self) -> set[str]:
        """Service tags from backend."""
        return self.backend.tags

    async def create_calling(
        self,
        timeout: float | None = None,
        streaming: bool = False,
        **arguments: Any,
    ) -> Calling:
        """Create Calling instance via backend.

        Calls create_payload on backend to get validated payload.
        Attaches hook_registry to Calling if configured.

        Args:
            timeout: Event timeout in seconds.
            streaming: Whether this is a streaming request.
            **arguments: Request arguments passed to backend.

        Returns:
            Configured Calling instance.
        """
        # Pre-event-create hook
        if self.hook_registry and self.hook_registry.can_handle(HookPhase.PreEventCreate):
            calling_type = self.backend.event_type
            result, should_exit, status = await self.hook_registry.pre_event_create(calling_type)
            if should_exit or status == "cancelled":
                if isinstance(result, Exception):
                    raise result
                raise RuntimeError("PreEventCreate hook requested exit")

        payload = self.backend.create_payload(request=arguments)
        calling_type = self.backend.event_type

        calling = calling_type(
            backend=self.backend,
            payload=payload,
            timeout=timeout,
            streaming=streaming,
        )

        if self.hook_registry:
            calling.attach_hook_registry(self.hook_registry)

        return calling

    async def invoke(
        self,
        calling: Calling | None = None,
        timeout: float = 30.0,
        **arguments: Any,
    ) -> Calling:
        """Invoke calling with optional rate limiting.

        Args:
            calling: Pre-created Calling instance. If provided, **arguments are IGNORED.
            timeout: Max wait time for rate limit (seconds).
            **arguments: Request arguments passed to create_calling. IGNORED if calling provided.

        Returns:
            Calling instance with execution results populated.

        Raises:
            TimeoutError: If rate limit acquisition times out.
        """
        if calling is None:
            calling = await self.create_calling(**arguments)

        if self.rate_limiter:
            acquired = await self.rate_limiter.acquire(timeout=timeout)
            if not acquired:
                raise TimeoutError(f"Rate limit acquisition timeout ({timeout}s)")

        await calling.invoke()
        self._store_provider_metadata(calling)
        return calling

    def _store_provider_metadata(self, calling: Calling) -> None:
        """Extract and store provider-specific metadata for context continuation."""
        from kron.types import is_sentinel

        if (
            isinstance(self.backend, Endpoint)
            and self.backend.config.provider == "claude_code"
            and not is_sentinel(calling.response)
        ):
            response = calling.response
            if isinstance(response, NormalizedResponse) and response.metadata:
                session_id = response.metadata.get("session_id")
                if session_id:
                    self.provider_metadata["session_id"] = session_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize iModel configuration."""
        return {
            "backend": {
                "provider": self.backend.provider,
                "name": self.backend.name,
                "version": self.backend.version,
            },
            "rate_limiter": self.rate_limiter.to_dict() if self.rate_limiter else None,
            "provider_metadata": self.provider_metadata,
        }

    def __repr__(self) -> str:
        """String representation."""
        return f"iModel(backend={self.backend.name}, version={self.backend.version})"

    async def __aenter__(self) -> iModel:
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> bool:
        """Exit async context.

        Returns:
            False to propagate any exceptions (never suppresses).
        """
        return False
