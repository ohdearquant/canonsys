"""Service utilities: rate limiting and resilience patterns.

Exports:
    Rate limiting:
        - RateLimitConfig: Token bucket configuration
        - TokenBucket: Rate limiter with continuous refill

    Resilience:
        - CircuitBreaker: Fail-fast with state machine (CLOSED/OPEN/HALF_OPEN)
        - CircuitBreakerOpenError: Raised when circuit is open
        - CircuitState: Circuit state enum
        - RetryConfig: Retry policy configuration
        - retry_with_backoff: Async retry with exponential backoff + jitter

    Headers:
        - HeaderFactory: HTTP header construction
        - AUTH_TYPES: Authentication type literal
"""

from .header_factory import AUTH_TYPES, HeaderFactory
from .rate_limiter import RateLimitConfig, TokenBucket
from .resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    RetryConfig,
    retry_with_backoff,
)

__all__ = (
    # Header
    "AUTH_TYPES",
    "HeaderFactory",
    # Rate limiting
    "RateLimitConfig",
    "TokenBucket",
    # Resilience
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "RetryConfig",
    "retry_with_backoff",
)
