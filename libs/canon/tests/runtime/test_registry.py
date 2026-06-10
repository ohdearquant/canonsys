"""Tests for canon.runtime.registry module."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from canon.dsl.compiler import CompiledCharter
from canon.runtime.registry import (
    CharterNotFoundError,
    CharterRegistry,
    get_compiled_charter,
    get_registry,
    register_charter,
)

from .conftest import CHARTER_ID

CHARTER_ID_2 = UUID("00000000-0000-0000-0000-000000000020")
CHARTER_ID_3 = UUID("00000000-0000-0000-0000-000000000030")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_compiled(name: str = "Test Charter") -> MagicMock:
    """Create a lightweight mock CompiledCharter for cache tests."""
    mock = MagicMock(spec=CompiledCharter)
    mock.name = name
    return mock


# ---------------------------------------------------------------------------
# TestCharterRegistry - synchronous cache operations
# ---------------------------------------------------------------------------


class TestRegisterAndGetCached:
    """Test register + get_cached round-trip."""

    def test_register_then_get_cached(self):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()

        registry.register(CHARTER_ID, compiled, content_hash="abc123")

        result = registry.get_cached(CHARTER_ID)
        assert result is compiled

    def test_register_without_content_hash(self):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()

        registry.register(CHARTER_ID, compiled)

        result = registry.get_cached(CHARTER_ID)
        assert result is compiled

    def test_register_overwrites_existing(self):
        registry = CharterRegistry()
        first = _make_mock_compiled("First")
        second = _make_mock_compiled("Second")

        registry.register(CHARTER_ID, first)
        registry.register(CHARTER_ID, second)

        result = registry.get_cached(CHARTER_ID)
        assert result is second

    def test_get_cached_returns_none_for_unknown(self):
        registry = CharterRegistry()

        result = registry.get_cached(CHARTER_ID)

        assert result is None

    def test_get_cached_returns_none_for_wrong_id(self):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()
        registry.register(CHARTER_ID, compiled)

        result = registry.get_cached(CHARTER_ID_2)

        assert result is None


class TestInvalidate:
    """Test invalidate removes cached entries."""

    def test_invalidate_removes_entry(self):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()
        registry.register(CHARTER_ID, compiled)

        removed = registry.invalidate(CHARTER_ID)

        assert removed is True
        assert registry.get_cached(CHARTER_ID) is None

    def test_invalidate_returns_false_for_unknown(self):
        registry = CharterRegistry()

        removed = registry.invalidate(CHARTER_ID)

        assert removed is False

    def test_invalidate_only_removes_targeted_entry(self):
        registry = CharterRegistry()
        compiled_1 = _make_mock_compiled("One")
        compiled_2 = _make_mock_compiled("Two")
        registry.register(CHARTER_ID, compiled_1)
        registry.register(CHARTER_ID_2, compiled_2)

        registry.invalidate(CHARTER_ID)

        assert registry.get_cached(CHARTER_ID) is None
        assert registry.get_cached(CHARTER_ID_2) is compiled_2


class TestClear:
    """Test clear removes all entries."""

    def test_clear_empties_registry(self):
        registry = CharterRegistry()
        registry.register(CHARTER_ID, _make_mock_compiled())
        registry.register(CHARTER_ID_2, _make_mock_compiled())

        registry.clear()

        assert registry.size == 0
        assert registry.get_cached(CHARTER_ID) is None
        assert registry.get_cached(CHARTER_ID_2) is None

    def test_clear_on_empty_registry(self):
        registry = CharterRegistry()

        registry.clear()

        assert registry.size == 0


class TestSizeProperty:
    """Test the size property."""

    def test_size_empty(self):
        registry = CharterRegistry()
        assert registry.size == 0

    def test_size_after_register(self):
        registry = CharterRegistry()
        registry.register(CHARTER_ID, _make_mock_compiled())
        assert registry.size == 1

    def test_size_after_multiple_registers(self):
        registry = CharterRegistry()
        registry.register(CHARTER_ID, _make_mock_compiled())
        registry.register(CHARTER_ID_2, _make_mock_compiled())
        registry.register(CHARTER_ID_3, _make_mock_compiled())
        assert registry.size == 3

    def test_size_after_invalidate(self):
        registry = CharterRegistry()
        registry.register(CHARTER_ID, _make_mock_compiled())
        registry.register(CHARTER_ID_2, _make_mock_compiled())

        registry.invalidate(CHARTER_ID)

        assert registry.size == 1

    def test_size_overwrite_does_not_increase(self):
        registry = CharterRegistry()
        registry.register(CHARTER_ID, _make_mock_compiled("First"))
        registry.register(CHARTER_ID, _make_mock_compiled("Second"))
        assert registry.size == 1


# ---------------------------------------------------------------------------
# TestCharterRegistryAsyncGet - async get() method
# ---------------------------------------------------------------------------


class TestAsyncGetCacheHit:
    """Test async get() when charter is already cached and fresh."""

    @pytest.mark.anyio
    async def test_cache_hit_returns_cached_compiled(self, mock_conn):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()
        registry.register(CHARTER_ID, compiled, content_hash="hash_abc")

        # DB confirms hash is unchanged
        mock_conn.fetchrow.return_value = {"content_hash": "hash_abc"}

        result = await registry.get(CHARTER_ID, mock_conn)

        assert result is compiled

    @pytest.mark.anyio
    async def test_cache_hit_checks_content_hash(self, mock_conn):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()
        registry.register(CHARTER_ID, compiled, content_hash="hash_abc")

        mock_conn.fetchrow.return_value = {"content_hash": "hash_abc"}

        await registry.get(CHARTER_ID, mock_conn)

        # First call should be the hash-check query
        first_call = mock_conn.fetchrow.call_args_list[0]
        assert "content_hash" in first_call[0][0]
        assert first_call[0][1] == CHARTER_ID


class TestAsyncGetCacheMiss:
    """Test async get() when charter is not in cache."""

    @pytest.mark.anyio
    async def test_cache_miss_loads_and_compiles(self, mock_conn):
        registry = CharterRegistry()
        compiled = _make_mock_compiled("From DB")

        # DB returns charter row
        mock_conn.fetchrow.return_value = {
            "id": CHARTER_ID,
            "source": 'charter "Test" v1.0\nschemas: canon.hr@2026.01',
            "content_hash": "hash_xyz",
            "status": "active",
        }

        with patch("canon.runtime.registry.compile_charter", return_value=compiled) as mock_compile:
            result = await registry.get(CHARTER_ID, mock_conn)

        assert result is compiled
        mock_compile.assert_called_once_with('charter "Test" v1.0\nschemas: canon.hr@2026.01')

    @pytest.mark.anyio
    async def test_cache_miss_caches_result(self, mock_conn):
        registry = CharterRegistry()
        compiled = _make_mock_compiled()

        mock_conn.fetchrow.return_value = {
            "id": CHARTER_ID,
            "source": "charter source",
            "content_hash": "hash_xyz",
            "status": "active",
        }

        with patch("canon.runtime.registry.compile_charter", return_value=compiled):
            await registry.get(CHARTER_ID, mock_conn)

        # Should now be cached
        assert registry.get_cached(CHARTER_ID) is compiled
        assert registry.size == 1


class TestAsyncGetCharterNotFound:
    """Test async get() raises CharterNotFoundError when charter not in DB."""

    @pytest.mark.anyio
    async def test_raises_charter_not_found(self, mock_conn):
        registry = CharterRegistry()

        # DB returns nothing
        mock_conn.fetchrow.return_value = None

        with pytest.raises(CharterNotFoundError) as exc_info:
            await registry.get(CHARTER_ID, mock_conn)

        assert exc_info.value.charter_id == CHARTER_ID
        assert str(CHARTER_ID) in str(exc_info.value)

    @pytest.mark.anyio
    async def test_charter_not_found_is_exception(self):
        exc = CharterNotFoundError(CHARTER_ID)
        assert isinstance(exc, Exception)


class TestAsyncGetStaleCache:
    """Test async get() recompiles when content_hash changes (stale cache)."""

    @pytest.mark.anyio
    async def test_stale_cache_recompiles(self, mock_conn):
        registry = CharterRegistry()
        old_compiled = _make_mock_compiled("Old")
        new_compiled = _make_mock_compiled("New")

        # Register with old hash
        registry.register(CHARTER_ID, old_compiled, content_hash="old_hash")

        # First fetchrow call: hash check returns different hash (stale)
        # Second fetchrow call: full charter load
        mock_conn.fetchrow.side_effect = [
            {"content_hash": "new_hash"},  # hash check - mismatch
            {
                "id": CHARTER_ID,
                "source": "updated source",
                "content_hash": "new_hash",
                "status": "active",
            },  # full load
        ]

        with patch(
            "canon.runtime.registry.compile_charter", return_value=new_compiled
        ) as mock_compile:
            result = await registry.get(CHARTER_ID, mock_conn)

        assert result is new_compiled
        mock_compile.assert_called_once_with("updated source")

    @pytest.mark.anyio
    async def test_stale_cache_updates_cached_entry(self, mock_conn):
        registry = CharterRegistry()
        old_compiled = _make_mock_compiled("Old")
        new_compiled = _make_mock_compiled("New")

        registry.register(CHARTER_ID, old_compiled, content_hash="old_hash")

        mock_conn.fetchrow.side_effect = [
            {"content_hash": "new_hash"},
            {
                "id": CHARTER_ID,
                "source": "updated source",
                "content_hash": "new_hash",
                "status": "active",
            },
        ]

        with patch("canon.runtime.registry.compile_charter", return_value=new_compiled):
            await registry.get(CHARTER_ID, mock_conn)

        # Cache should hold new compiled charter
        assert registry.get_cached(CHARTER_ID) is new_compiled

    @pytest.mark.anyio
    async def test_stale_cache_not_found_in_db_raises(self, mock_conn):
        """Edge case: cached but charter was deleted from DB."""
        registry = CharterRegistry()
        old_compiled = _make_mock_compiled("Old")
        registry.register(CHARTER_ID, old_compiled, content_hash="old_hash")

        # Hash check returns different hash, full load returns None (deleted)
        mock_conn.fetchrow.side_effect = [
            {"content_hash": "new_hash"},  # hash mismatch
            None,  # charter deleted from DB
        ]

        with pytest.raises(CharterNotFoundError):
            await registry.get(CHARTER_ID, mock_conn)


class TestAsyncGetCompileError:
    """Test async get() propagates compilation errors."""

    @pytest.mark.anyio
    async def test_compile_error_propagates(self, mock_conn):
        registry = CharterRegistry()

        mock_conn.fetchrow.return_value = {
            "id": CHARTER_ID,
            "source": "invalid charter source",
            "content_hash": "hash_bad",
            "status": "active",
        }

        with (
            patch(
                "canon.runtime.registry.compile_charter",
                side_effect=ValueError("bad syntax"),
            ),
            pytest.raises(ValueError, match="bad syntax"),
        ):
            await registry.get(CHARTER_ID, mock_conn)

    @pytest.mark.anyio
    async def test_compile_error_does_not_cache(self, mock_conn):
        registry = CharterRegistry()

        mock_conn.fetchrow.return_value = {
            "id": CHARTER_ID,
            "source": "invalid source",
            "content_hash": "hash_bad",
            "status": "active",
        }

        with (
            patch(
                "canon.runtime.registry.compile_charter",
                side_effect=ValueError("bad"),
            ),
            pytest.raises(ValueError),
        ):
            await registry.get(CHARTER_ID, mock_conn)

        assert registry.get_cached(CHARTER_ID) is None
        assert registry.size == 0


# ---------------------------------------------------------------------------
# TestThreadSafety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Test concurrent register/invalidate operations."""

    def test_concurrent_register_and_invalidate(self):
        registry = CharterRegistry()
        errors: list[Exception] = []
        ids = [uuid4() for _ in range(50)]

        def register_batch(start: int) -> None:
            try:
                for i in range(start, start + 25):
                    charter_id = ids[i % len(ids)]
                    registry.register(charter_id, _make_mock_compiled(f"c-{i}"))
            except Exception as e:
                errors.append(e)

        def invalidate_batch(start: int) -> None:
            try:
                for i in range(start, start + 25):
                    charter_id = ids[i % len(ids)]
                    registry.invalidate(charter_id)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for i in range(4):
                futures.append(pool.submit(register_batch, i * 10))
                futures.append(pool.submit(invalidate_batch, i * 10))
            for f in as_completed(futures):
                f.result()  # re-raise if exception

        assert errors == [], f"Thread safety errors: {errors}"

    def test_concurrent_register_preserves_all_entries(self):
        registry = CharterRegistry()
        ids = [uuid4() for _ in range(100)]
        compiled_map = {cid: _make_mock_compiled(f"c-{i}") for i, cid in enumerate(ids)}
        barrier = threading.Barrier(4)

        def register_slice(start: int, end: int) -> None:
            barrier.wait()
            for i in range(start, end):
                registry.register(ids[i], compiled_map[ids[i]])

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(register_slice, 0, 25),
                pool.submit(register_slice, 25, 50),
                pool.submit(register_slice, 50, 75),
                pool.submit(register_slice, 75, 100),
            ]
            for f in as_completed(futures):
                f.result()

        assert registry.size == 100
        for cid in ids:
            assert registry.get_cached(cid) is compiled_map[cid]


# ---------------------------------------------------------------------------
# TestModuleLevelFunctions
# ---------------------------------------------------------------------------


class TestGetRegistry:
    """Test get_registry() singleton behavior."""

    def test_returns_charter_registry_instance(self):
        registry = get_registry()
        assert isinstance(registry, CharterRegistry)

    def test_returns_same_instance(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_singleton_reset_creates_new_instance(self):
        """Verify that resetting _registry produces a fresh instance."""
        with patch("canon.runtime.registry._registry", None):
            r1 = get_registry()
            assert isinstance(r1, CharterRegistry)


class TestRegisterCharterConvenience:
    """Test register_charter() module-level convenience function."""

    def test_register_charter_adds_to_global_registry(self):
        compiled = _make_mock_compiled("Convenience")
        unique_id = uuid4()

        register_charter(unique_id, compiled, content_hash="conv_hash")

        result = get_registry().get_cached(unique_id)
        assert result is compiled

        # Cleanup
        get_registry().invalidate(unique_id)


class TestGetCompiledCharterConvenience:
    """Test get_compiled_charter() module-level convenience function."""

    @pytest.mark.anyio
    async def test_delegates_to_global_registry(self, mock_conn):
        compiled = _make_mock_compiled("Global")
        unique_id = uuid4()

        # Pre-register so we get a cache hit
        get_registry().register(unique_id, compiled, content_hash="g_hash")
        mock_conn.fetchrow.return_value = {"content_hash": "g_hash"}

        result = await get_compiled_charter(unique_id, mock_conn)

        assert result is compiled

        # Cleanup
        get_registry().invalidate(unique_id)

    @pytest.mark.anyio
    async def test_raises_not_found(self, mock_conn):
        mock_conn.fetchrow.return_value = None
        unknown_id = uuid4()

        with pytest.raises(CharterNotFoundError):
            await get_compiled_charter(unknown_id, mock_conn)
