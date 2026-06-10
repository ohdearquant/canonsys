"""Services module: iModel, ServiceBackend, hooks, and utilities.

Core exports:
- iModel: Unified service interface with rate limiting and hooks
- ServiceBackend/Endpoint: Backend abstractions for API calls
- HookRegistry/HookPhase: Lifecycle hook system
- Utilities: CircuitBreaker, RetryConfig, TokenBucket

Uses lazy loading for fast import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Lazy import mapping
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Backend
    "Calling": ("kron.services.backend", "Calling"),
    "NormalizedResponse": ("kron.services.backend", "NormalizedResponse"),
    "ServiceBackend": ("kron.services.backend", "ServiceBackend"),
    "ServiceConfig": ("kron.services.backend", "ServiceConfig"),
    # Endpoint
    "Endpoint": ("kron.services.endpoint", "Endpoint"),
    "EndpointConfig": ("kron.services.endpoint", "EndpointConfig"),
    "APICalling": ("kron.services.endpoint", "APICalling"),
    # Hook
    "HookRegistry": ("kron.services.hook", "HookRegistry"),
    "HookPhase": ("kron.services.hook", "HookPhase"),
    # Model
    "iModel": ("kron.services.model", "iModel"),
    # Registry
    "ServiceRegistry": ("kron.services.registry", "ServiceRegistry"),
    # Utilities - resilience
    "CircuitBreaker": ("kron.services.utilities.resilience", "CircuitBreaker"),
    "CircuitBreakerOpenError": (
        "kron.services.utilities.resilience",
        "CircuitBreakerOpenError",
    ),
    "CircuitState": ("kron.services.utilities.resilience", "CircuitState"),
    "RetryConfig": ("kron.services.utilities.resilience", "RetryConfig"),
    "retry_with_backoff": (
        "kron.services.utilities.resilience",
        "retry_with_backoff",
    ),
    # Utilities - rate limiter
    "RateLimitConfig": (
        "kron.services.utilities.rate_limiter",
        "RateLimitConfig",
    ),
    "TokenBucket": ("kron.services.utilities.rate_limiter", "TokenBucket"),
    # Utilities - header factory
    "HeaderFactory": ("kron.services.utilities.header_factory", "HeaderFactory"),
    "AUTH_TYPES": ("kron.services.utilities.header_factory", "AUTH_TYPES"),
}

_LOADED: dict[str, object] = {}


def __getattr__(name: str) -> object:
    """Lazy import attributes on first access."""
    if name in _LOADED:
        return _LOADED[name]

    if name in _LAZY_IMPORTS:
        from importlib import import_module

        module_name, attr_name = _LAZY_IMPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attr_name)
        _LOADED[name] = value
        return value

    raise AttributeError(f"module 'kron.services' has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return all available attributes for autocomplete."""
    return list(__all__)


# TYPE_CHECKING block for static analysis
if TYPE_CHECKING:
    from .backend import Calling, NormalizedResponse, ServiceBackend, ServiceConfig
    from .endpoint import APICalling, Endpoint, EndpointConfig
    from .hook import HookPhase, HookRegistry
    from .model import iModel
    from .registry import ServiceRegistry
    from .utilities.header_factory import AUTH_TYPES, HeaderFactory
    from .utilities.rate_limiter import RateLimitConfig, TokenBucket
    from .utilities.resilience import (
        CircuitBreaker,
        CircuitBreakerOpenError,
        CircuitState,
        RetryConfig,
        retry_with_backoff,
    )

__all__ = (
    # Backend
    "APICalling",
    "Calling",
    "Endpoint",
    "EndpointConfig",
    "NormalizedResponse",
    "ServiceBackend",
    "ServiceConfig",
    # Hook
    "HookPhase",
    "HookRegistry",
    # Model
    "iModel",
    # Registry
    "ServiceRegistry",
    # Utilities
    "AUTH_TYPES",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "HeaderFactory",
    "RateLimitConfig",
    "RetryConfig",
    "TokenBucket",
    "retry_with_backoff",
)
