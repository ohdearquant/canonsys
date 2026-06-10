"""Decision-scope caching for governance scalability.

P1 Fix: Scalability - Decision caching

Caches governance decisions by scope to avoid O(n) evaluation per request.
Cache keys incorporate: gate_id/policy_id + tenant_id + decision_scope + relevant context.

TTL-based invalidation ensures fresh evaluations for time-sensitive policies
while amortizing cost for stable decisions.

Reference: CONSTRAINTS-001-enterprise-ilities.md §5 Scalability
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DecisionCacheConfig:
    """Configuration for decision cache.

    Attributes:
        max_size: Maximum number of cached entries
        default_ttl: Default TTL in seconds
        gate_ttl: TTL for gate results (shorter for time-sensitive)
        policy_ttl: TTL for policy results
        enabled: Whether caching is enabled
    """

    max_size: int = 10000
    default_ttl: float = 300.0  # 5 minutes
    gate_ttl: float = 60.0  # 1 minute for gates (more dynamic)
    policy_ttl: float = 300.0  # 5 minutes for policies
    enabled: bool = True

    @classmethod
    def from_env(cls) -> DecisionCacheConfig:
        """Create config from environment variables.

        P2 Configuration: Externalize cache settings.

        Environment variables:
            CANON_CACHE_MAX_SIZE: Max cache entries (default 10000)
            CANON_CACHE_DEFAULT_TTL: Default TTL seconds (default 300.0)
            CANON_CACHE_GATE_TTL: Gate TTL seconds (default 60.0)
            CANON_CACHE_POLICY_TTL: Policy TTL seconds (default 300.0)
            CANON_CACHE_ENABLED: Enable caching (default true)

        Returns:
            DecisionCacheConfig from environment
        """
        import os

        return cls(
            max_size=int(os.environ.get("CANON_CACHE_MAX_SIZE", "10000")),
            default_ttl=float(os.environ.get("CANON_CACHE_DEFAULT_TTL", "300.0")),
            gate_ttl=float(os.environ.get("CANON_CACHE_GATE_TTL", "60.0")),
            policy_ttl=float(os.environ.get("CANON_CACHE_POLICY_TTL", "300.0")),
            enabled=os.environ.get("CANON_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"),
        )


@dataclass(frozen=True)
class CacheKey:
    """Cache key for governance decisions.

    Components:
        - kind: "gate" or "policy"
        - id: gate_id or policy_id
        - tenant_id: Tenant identifier
        - scope: Decision scope (e.g., "adverse_action")
        - context_hash: Hash of relevant context fields
    """

    kind: str
    id: str
    tenant_id: str
    scope: str
    context_hash: str

    @classmethod
    def for_gate(
        cls,
        gate_id: str,
        tenant_id: str,
        scope: str,
        context: dict[str, Any] | None = None,
    ) -> CacheKey:
        """Create cache key for gate result."""
        context_hash = cls._hash_context(context) if context else "none"
        return cls(
            kind="gate",
            id=gate_id,
            tenant_id=tenant_id,
            scope=scope,
            context_hash=context_hash,
        )

    @classmethod
    def for_policy(
        cls,
        policy_id: str,
        tenant_id: str,
        scope: str,
        input_data: dict[str, Any] | None = None,
    ) -> CacheKey:
        """Create cache key for policy result."""
        context_hash = cls._hash_context(input_data) if input_data else "none"
        return cls(
            kind="policy",
            id=policy_id,
            tenant_id=tenant_id,
            scope=scope,
            context_hash=context_hash,
        )

    @staticmethod
    def _hash_context(context: dict[str, Any]) -> str:
        """Hash context dict for cache key.

        Only hashes stable fields - excludes timestamps, request_ids, etc.
        """
        import json

        # Sort keys for deterministic hashing
        # Exclude volatile fields
        volatile_keys = {
            "timestamp",
            "request_id",
            "correlation_id",
            "created_at",
            "updated_at",
        }
        stable_context = {
            k: v for k, v in sorted(context.items()) if k not in volatile_keys and v is not None
        }

        serialized = json.dumps(stable_context, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def __str__(self) -> str:
        return f"{self.kind}:{self.id}:{self.tenant_id}:{self.scope}:{self.context_hash}"


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value and metadata."""

    value: T
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def expired(self) -> bool:
        """Check if entry has expired."""
        return time.monotonic() - self.created_at > self.ttl

    @property
    def age(self) -> float:
        """Age of entry in seconds."""
        return time.monotonic() - self.created_at


@dataclass
class DecisionCache(Generic[T]):
    """Thread-safe TTL cache for governance decisions.

    Usage:
        cache = DecisionCache(config=DecisionCacheConfig(max_size=5000))

        # Check cache
        key = CacheKey.for_gate(gate_id, tenant_id, scope)
        if cached := cache.get(key):
            return cached.with_cached(True)

        # Evaluate and cache
        result = await evaluate(gate, context)
        if gate.cacheable:
            cache.set(key, result, ttl=60.0)
        return result
    """

    config: DecisionCacheConfig = field(default_factory=DecisionCacheConfig)

    # Internal storage
    _cache: dict[str, CacheEntry[T]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    # Metrics
    _hits: int = field(default=0, init=False)
    _misses: int = field(default=0, init=False)
    _evictions: int = field(default=0, init=False)

    @property
    def metrics(self) -> dict[str, Any]:
        """Cache metrics snapshot."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "size": len(self._cache),
                "max_size": self.config.max_size,
                "hit_rate": hit_rate,
            }

    def get(self, key: CacheKey) -> T | None:
        """Get cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if not self.config.enabled:
            return None

        str_key = str(key)

        with self._lock:
            entry = self._cache.get(str_key)
            if entry is None:
                self._misses += 1
                return None

            if entry.expired:
                del self._cache[str_key]
                self._misses += 1
                return None

            entry.hits += 1
            self._hits += 1
            return entry.value

    def set(
        self,
        key: CacheKey,
        value: T,
        ttl: float | None = None,
    ) -> None:
        """Cache a value.

        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if not specified)
        """
        if not self.config.enabled:
            return

        # Determine TTL based on key kind
        if ttl is None:
            if key.kind == "gate":
                ttl = self.config.gate_ttl
            elif key.kind == "policy":
                ttl = self.config.policy_ttl
            else:
                ttl = self.config.default_ttl

        str_key = str(key)

        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.config.max_size:
                self._evict_oldest()

            self._cache[str_key] = CacheEntry(
                value=value,
                created_at=time.monotonic(),
                ttl=ttl,
            )

    def invalidate(self, key: CacheKey) -> bool:
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and removed
        """
        str_key = str(key)

        with self._lock:
            if str_key in self._cache:
                del self._cache[str_key]
                return True
            return False

    def invalidate_by_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix.

        Args:
            prefix: Key prefix to match (e.g., "gate:consent")

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def invalidate_by_tenant(self, tenant_id: str) -> int:
        """Invalidate all entries for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if f":{tenant_id}:" in k]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def _evict_oldest(self) -> None:
        """Evict oldest entry (must hold lock)."""
        if not self._cache:
            return

        # Find oldest entry
        oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        self._evictions += 1

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.expired]
            for k in expired:
                del self._cache[k]
            return len(expired)


# Global cache instance
_decision_cache: DecisionCache | None = None


def get_decision_cache() -> DecisionCache:
    """Get singleton decision cache."""
    global _decision_cache
    if _decision_cache is None:
        _decision_cache = DecisionCache()
    return _decision_cache


def configure_decision_cache(config: DecisionCacheConfig) -> DecisionCache:
    """Configure global decision cache.

    Args:
        config: Cache configuration

    Returns:
        Configured DecisionCache instance
    """
    global _decision_cache
    _decision_cache = DecisionCache(config=config)
    return _decision_cache
