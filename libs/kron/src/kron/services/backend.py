"""Service backend abstractions for canon.

Provides:
    - ServiceConfig: Base configuration for service backends
    - NormalizedResponse: Standardized response wrapper
    - ServiceBackend: Abstract base for service implementations
    - Calling: Base calling event for backend invocation
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, model_validator

from kron.types import HashableModel, Unset, UnsetType, is_sentinel

if TYPE_CHECKING:
    from .hook import HookRegistry

logger = logging.getLogger(__name__)

__all__ = (
    "Calling",
    "NormalizedResponse",
    "ServiceBackend",
    "ServiceConfig",
)


# Module-level cache for schema field keys (keyed by class)
_SCHEMA_FIELD_KEYS_CACHE: dict[type[BaseModel], set[str]] = {}


def _get_schema_field_keys(cls: type[BaseModel]) -> set[str]:
    """Get field names for a Pydantic model (cached).

    Uses model_fields instead of model_json_schema to include fields
    that may be excluded from JSON schema (e.g., SkipJsonSchema fields).
    """
    if cls not in _SCHEMA_FIELD_KEYS_CACHE:
        _SCHEMA_FIELD_KEYS_CACHE[cls] = set(cls.model_fields.keys())
    return _SCHEMA_FIELD_KEYS_CACHE[cls]


class ServiceConfig(HashableModel):
    """Base configuration for service backends.

    Attributes:
        provider: Service provider name (min 4 chars).
        name: Service name (min 4 chars).
        request_options: Optional Pydantic model type for request validation.
        timeout: Request timeout in seconds (default 300, max 3600).
        max_retries: Maximum retry attempts (default 3, max 10).
        version: Optional version string.
        tags: Service tags for categorization.
        kwargs: Extra configuration kwargs.
    """

    provider: str = Field(..., min_length=4, max_length=50)
    name: str = Field(..., min_length=4, max_length=100)
    request_options: type[BaseModel] | None = Field(default=None, exclude=True)
    timeout: int = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)
    version: str | None = None
    tags: list[str] = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _validate_kwargs(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Move unknown fields into kwargs."""
        if not isinstance(data, dict):
            return data
        kwargs = data.pop("kwargs", {})
        field_keys = _get_schema_field_keys(cls)
        for k in list(data.keys()):
            if k not in field_keys:
                kwargs[k] = data.pop(k)
        data["kwargs"] = kwargs
        return data

    def validate_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate payload against request_options schema if defined."""
        if not self.request_options:
            return data
        try:
            self.request_options.model_validate(data)
            return data
        except Exception as e:
            raise ValueError("Invalid payload") from e


class NormalizedResponse(HashableModel):
    """Generic normalized response for all service backends.

    Works for any backend type: HTTP endpoints, tools, LLM APIs, etc.
    Provides consistent interface regardless of underlying service.

    Attributes:
        status: Response status ('success' or 'error').
        data: Response payload (any type).
        error: Error message if status='error'.
        raw_response: Original unmodified response.
        metadata: Provider-specific metadata.
    """

    status: str = Field(..., description="Response status: 'success' or 'error'")
    data: Any = None
    error: str | None = Field(default=None, description="Error message if status='error'")
    raw_response: dict[str, Any] = Field(..., description="Original unmodified response")
    metadata: dict[str, Any] | None = Field(default=None, description="Provider-specific metadata")

    def _to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Convert to dict, excluding None values."""
        return self.model_dump(exclude_none=True, **kwargs)


class Calling:
    """Base calling abstraction for service backend invocation.

    Wraps a payload for backend.call() with optional hook support.
    Subclasses (APICalling, etc.) add backend-specific behavior.

    Attributes:
        backend: ServiceBackend instance.
        payload: Request payload dict.
        timeout: Optional timeout in seconds.
        streaming: Whether streaming mode is enabled.
        response: NormalizedResponse after invocation.
    """

    def __init__(
        self,
        backend: ServiceBackend,
        payload: dict[str, Any],
        timeout: float | None = None,
        streaming: bool = False,
    ):
        """Initialize calling with backend and payload.

        Args:
            backend: ServiceBackend to invoke.
            payload: Request payload.
            timeout: Optional timeout in seconds.
            streaming: Enable streaming mode.
        """
        self.backend = backend
        self.payload = payload
        self.timeout = timeout
        self.streaming = streaming
        self._response: NormalizedResponse | UnsetType = Unset
        self._hook_registry: HookRegistry | None = None
        self._error: BaseException | None = None
        self._status: str = "pending"

    @property
    def response(self) -> NormalizedResponse | UnsetType:
        """Get response (Unset if not yet invoked)."""
        return self._response

    @property
    def error(self) -> BaseException | None:
        """Get error if invocation failed."""
        return self._error

    @property
    def status(self) -> str:
        """Get current status (pending, processing, completed, failed)."""
        return self._status

    @property
    def call_args(self) -> dict:
        """Get arguments for backend.call(**self.call_args).

        Returns:
            Dict of keyword arguments for backend.call()
        """
        return {
            "request": self.payload,
            "skip_payload_creation": True,
        }

    def attach_hook_registry(self, registry: HookRegistry) -> None:
        """Attach hook registry for lifecycle callbacks."""
        self._hook_registry = registry

    async def invoke(self) -> NormalizedResponse:
        """Execute backend call with optional hooks.

        Returns:
            NormalizedResponse from backend.

        Raises:
            Exception: Any exception from backend.call().
        """
        from .hook import HookPhase

        if self._status != "pending":
            if not is_sentinel(self._response):
                return self._response  # type: ignore
            raise RuntimeError("Cannot invoke: already processed")

        self._status = "processing"

        try:
            # Pre-invocation hook
            if self._hook_registry and self._hook_registry.can_handle(HookPhase.PreInvocation):
                result, should_exit, status = await self._hook_registry.pre_invocation(self)
                if should_exit or status == "cancelled":
                    if isinstance(result, Exception):
                        raise result
                    raise RuntimeError("Pre-invocation hook cancelled")

            # Actual backend call
            response = await self.backend.call(**self.call_args)
            self._response = response
            self._status = "completed"

            # Post-invocation hook
            if self._hook_registry and self._hook_registry.can_handle(HookPhase.PostInvocation):
                await self._hook_registry.post_invocation(self)

            return response

        except Exception as e:
            self._error = e
            self._status = "failed"

            # Error handling hook
            if self._hook_registry and self._hook_registry.can_handle(HookPhase.ErrorHandling):
                await self._hook_registry.error_handling(self, e)

            raise


class ServiceBackend:
    """Base class for all service backends (Endpoint, Tool, etc.).

    Provides common interface for service invocation.
    Subclasses must implement call() and event_type property.

    Attributes:
        config: ServiceConfig instance.
    """

    def __init__(self, config: ServiceConfig | dict[str, Any]):
        """Initialize backend with config.

        Args:
            config: ServiceConfig instance or dict.
        """
        if isinstance(config, dict):
            config = ServiceConfig(**config)
        self.config = config

    @property
    def provider(self) -> str:
        """Provider name from config."""
        return self.config.provider

    @property
    def name(self) -> str:
        """Service name from config."""
        return self.config.name

    @property
    def version(self) -> str | None:
        """Service version from config."""
        return self.config.version

    @property
    def tags(self) -> set[str]:
        """Service tags from config."""
        return set(self.config.tags) if self.config.tags else set()

    @property
    def request_options(self) -> type[BaseModel] | None:
        """Request options schema (Pydantic model type) from config."""
        return self.config.request_options

    @property
    @abstractmethod
    def event_type(self) -> type[Calling]:
        """Return Calling type for this backend (e.g., APICalling)."""
        ...

    def create_payload(
        self,
        request: dict | BaseModel,
        **kwargs,
    ) -> dict:
        """Build validated payload from request and config defaults.

        Args:
            request: Request parameters (dict or Pydantic model).
            **kwargs: Additional parameters merged last.

        Returns:
            Validated payload dict.
        """
        request_dict = (
            request if isinstance(request, dict) else request.model_dump(exclude_none=True)
        )

        payload = self.config.kwargs.copy()
        payload.update(request_dict)
        if kwargs:
            payload.update(kwargs)

        if self.config.request_options is not None:
            valid_fields = set(self.config.request_options.model_fields.keys())
            payload = {k: v for k, v in payload.items() if k in valid_fields}
            return self.config.validate_payload(payload)

        return payload

    def normalize_response(self, raw_response: Any) -> NormalizedResponse:
        """Normalize raw response into NormalizedResponse.

        Default implementation wraps response as-is. Subclasses can override
        to extract specific fields or add metadata.

        Args:
            raw_response: Raw response from service call

        Returns:
            NormalizedResponse with status, data, raw_response
        """
        return NormalizedResponse(
            status="success",
            data=raw_response,
            raw_response=(
                raw_response if isinstance(raw_response, dict) else {"data": raw_response}
            ),
        )

    @abstractmethod
    async def call(self, *args, **kw) -> NormalizedResponse:
        """Execute service call and return normalized response."""
        ...

    async def stream(self, *args, **kw):
        """Stream responses (not supported by default)."""
        raise NotImplementedError("This backend does not support streaming calls.")
