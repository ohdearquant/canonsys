"""Compiled charter registry - caches compiled charters for runtime lookup.

Charters are compiled once and cached. The registry provides:
1. Fast lookup by charter_id (UUID)
2. Automatic compilation from Charter entities
3. Thread-safe caching with TTL support

Design decisions:
- Charters don't change at runtime (once published)
- Cache is invalidated when charter is updated/superseded
- Compilation is lazy (on first access)
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from canon.dsl import CompiledCharter, compile_charter

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)


class CharterNotFoundError(Exception):
    """Raised when a charter is not found in registry or database."""

    def __init__(self, charter_id: UUID) -> None:
        self.charter_id = charter_id
        super().__init__(f"Charter not found: {charter_id}")


class _CacheEntry:
    """Cache entry with metadata for TTL and versioning."""

    __slots__ = ("cached_at", "compiled", "content_hash")

    def __init__(self, compiled: CompiledCharter, content_hash: str | None) -> None:
        self.compiled = compiled
        self.content_hash = content_hash
        self.cached_at = datetime.now(UTC)


class CharterRegistry:
    """Thread-safe registry for compiled charters.

    Provides in-memory caching of compiled charters with:
    - Lazy compilation on first access
    - Hash-based invalidation (detects charter updates)
    - Explicit registration for pre-compiled charters

    Usage:
        registry = CharterRegistry()

        # Register pre-compiled charter
        registry.register(charter_id, compiled_charter)

        # Get compiled charter (from cache or compile on-demand)
        compiled = await registry.get(charter_id, conn)

        # Invalidate on charter update
        registry.invalidate(charter_id)
    """

    def __init__(self) -> None:
        self._cache: dict[UUID, _CacheEntry] = {}
        self._lock = threading.RLock()

    def register(
        self,
        charter_id: UUID,
        compiled: CompiledCharter,
        content_hash: str | None = None,
    ) -> None:
        """Register a pre-compiled charter in the cache.

        Args:
            charter_id: Charter UUID.
            compiled: Pre-compiled CompiledCharter.
            content_hash: Optional content hash for cache validation.
        """
        with self._lock:
            self._cache[charter_id] = _CacheEntry(compiled, content_hash)
            logger.debug("Registered charter %s in registry", charter_id)

    def invalidate(self, charter_id: UUID) -> bool:
        """Invalidate a cached charter, forcing recompilation on next access.

        Args:
            charter_id: Charter UUID to invalidate.

        Returns:
            True if charter was in cache and removed, False otherwise.
        """
        with self._lock:
            if charter_id in self._cache:
                del self._cache[charter_id]
                logger.debug("Invalidated charter %s from registry", charter_id)
                return True
            return False

    def clear(self) -> None:
        """Clear all cached charters."""
        with self._lock:
            self._cache.clear()
            logger.debug("Cleared charter registry")

    def get_cached(self, charter_id: UUID) -> CompiledCharter | None:
        """Get a compiled charter from cache only (no DB lookup).

        Args:
            charter_id: Charter UUID.

        Returns:
            CompiledCharter if cached, None otherwise.
        """
        with self._lock:
            entry = self._cache.get(charter_id)
            return entry.compiled if entry else None

    async def get(
        self,
        charter_id: UUID,
        conn: asyncpg.Connection,
    ) -> CompiledCharter:
        """Get a compiled charter, loading from DB and compiling if needed.

        This method:
        1. Checks cache for compiled charter
        2. If cached, validates content_hash hasn't changed
        3. If not cached or stale, loads from DB and compiles
        4. Caches the result

        Args:
            charter_id: Charter UUID.
            conn: Database connection for loading charter.

        Returns:
            CompiledCharter ready for execution.

        Raises:
            CharterNotFoundError: If charter doesn't exist.
        """
        # Check cache first
        with self._lock:
            entry = self._cache.get(charter_id)

        if entry:
            # Validate cache is still fresh (check content_hash)
            row = await conn.fetchrow(
                'SELECT content_hash FROM "public"."charters" WHERE id = $1',
                charter_id,
            )
            if row and row["content_hash"] == entry.content_hash:
                logger.debug("Cache hit for charter %s", charter_id)
                return entry.compiled
            # Hash changed, need to recompile
            logger.debug("Cache stale for charter %s (hash changed)", charter_id)

        # Load from database
        row = await conn.fetchrow(
            """
            SELECT id, source, content_hash, status
            FROM "public"."charters"
            WHERE id = $1
            """,
            charter_id,
        )

        if not row:
            raise CharterNotFoundError(charter_id)

        # Compile the charter
        source = row["source"]
        content_hash = row["content_hash"]

        try:
            compiled = compile_charter(source)
        except Exception as e:
            logger.error("Failed to compile charter %s: %s", charter_id, e)
            raise

        # Cache the result
        with self._lock:
            self._cache[charter_id] = _CacheEntry(compiled, content_hash)

        logger.debug("Compiled and cached charter %s", charter_id)
        return compiled

    @property
    def size(self) -> int:
        """Number of charters currently cached."""
        with self._lock:
            return len(self._cache)


# Global registry instance
_registry: CharterRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> CharterRegistry:
    """Get the global charter registry instance.

    Thread-safe singleton pattern.
    """
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CharterRegistry()
    return _registry


def register_charter(
    charter_id: UUID,
    compiled: CompiledCharter,
    content_hash: str | None = None,
) -> None:
    """Register a pre-compiled charter in the global registry.

    Convenience wrapper around get_registry().register().
    """
    get_registry().register(charter_id, compiled, content_hash)


async def get_compiled_charter(
    charter_id: UUID,
    conn: asyncpg.Connection,
) -> CompiledCharter:
    """Get a compiled charter from the global registry.

    Loads from database and compiles if not cached.

    Args:
        charter_id: Charter UUID.
        conn: Database connection.

    Returns:
        CompiledCharter ready for execution.

    Raises:
        CharterNotFoundError: If charter doesn't exist.
    """
    return await get_registry().get(charter_id, conn)
