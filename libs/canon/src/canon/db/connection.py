"""Database connection pool and tenant context for RLS.

Provides:
- Connection pool (asyncpg)
- Tenant context injection for Row-Level Security
- Transaction helpers
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from canon.exceptions import TenantError

if TYPE_CHECKING:
    import asyncpg

__all__ = (
    "DbContext",
    "TenantContextRequired",
    "TenantScope",
    "close_pool",
    "connection",
    "get_db_context",
    "get_pool",
    "set_db_context",
    "transaction",
    "with_context",
)

# Pool singleton
_pool: asyncpg.Pool | None = None


# =============================================================================
# Tenant Context
# =============================================================================


@dataclass(frozen=True, slots=True)
class DbContext:
    """Database context for tenant isolation.

    Set before database operations to scope queries via RLS.

    Attributes:
        tenant_id: Required. Scopes all queries to this tenant.
        actor_id: Optional. User performing the operation (audit).
        request_id: Optional. Request correlation ID (tracing).
    """

    tenant_id: UUID
    actor_id: UUID | None = None
    request_id: str | None = None


class TenantScope(Enum):
    """Tenant context enforcement mode.

    REQUIRED: Fail if no tenant context (default for app queries)
    OPTIONAL: Use context if available, proceed without if not
    DISABLED: Skip context entirely (migrations, admin)
    """

    REQUIRED = "required"
    OPTIONAL = "optional"
    DISABLED = "disabled"


# Task-local context
_db_context: ContextVar[DbContext | None] = ContextVar("db_context", default=None)


def get_db_context() -> DbContext | None:
    """Get current database context."""
    return _db_context.get()


def set_db_context(ctx: DbContext | None) -> Token[DbContext | None]:
    """Set database context. Returns token for reset."""
    return _db_context.set(ctx)


@asynccontextmanager
async def with_context(ctx: DbContext) -> AsyncIterator[None]:
    """Context manager to set tenant context for a scope.

    Usage:
        async with with_context(DbContext(tenant_id=tid)):
            await do_stuff()  # RLS-filtered
    """
    token = _db_context.set(ctx)
    try:
        yield
    finally:
        _db_context.reset(token)


# =============================================================================
# Connection Pool
# =============================================================================


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Initialize connection with JSON codecs for JSONB columns.

    Uses orjson for encoding which natively handles UUID, datetime,
    and other types that stdlib json.dumps cannot serialize.
    """
    import orjson

    def _encode(obj: object) -> str:
        return orjson.dumps(obj).decode("utf-8")

    await conn.set_type_codec(
        "jsonb",
        encoder=_encode,
        decoder=orjson.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=_encode,
        decoder=orjson.loads,
        schema="pg_catalog",
    )


async def get_pool(dsn: str | None = None) -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool

    if _pool is None:
        import os

        import asyncpg

        ssl_mode = os.environ.get("DATABASE_SSL", "prefer")
        ssl_ctx = ssl_mode if ssl_mode != "disable" else False

        _pool = await asyncpg.create_pool(
            dsn or os.environ.get("DATABASE_URL", ""),
            min_size=2,
            max_size=int(os.environ.get("DATABASE_POOL_SIZE", "10")),
            command_timeout=int(os.environ.get("DATABASE_COMMAND_TIMEOUT", "60")),
            init=_init_connection,
            ssl=ssl_ctx,
        )

    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


class TenantContextRequired(TenantError):
    """Raised when tenant context is required but not set."""

    def __init__(self) -> None:
        super().__init__(reason="tenant context required but not set")


@asynccontextmanager
async def connection(
    dsn: str | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> AsyncIterator[asyncpg.Connection]:
    """Get a connection with tenant context injection.

    Injects tenant_id into Postgres session for RLS enforcement.

    Args:
        dsn: Database URL. Uses DATABASE_URL env if None.
        tenant_scope: How to handle tenant context.

    Raises:
        TenantContextRequired: If REQUIRED and no context set.

    Yields:
        Connection with tenant context configured.
    """
    ctx = get_db_context()

    if tenant_scope == TenantScope.REQUIRED and ctx is None:
        raise TenantContextRequired(
            "Tenant context required. Use `async with with_context(DbContext(...)):` first."
        )

    pool = await get_pool(dsn)
    async with pool.acquire() as conn:
        # Inject tenant context for RLS
        if ctx is not None and tenant_scope != TenantScope.DISABLED:
            await conn.execute(
                """
                SELECT
                    set_config('app.tenant_id', $1, true),
                    set_config('app.actor_id', COALESCE($2, ''), true),
                    set_config('app.request_id', COALESCE($3, ''), true)
                """,
                str(ctx.tenant_id),
                str(ctx.actor_id) if ctx.actor_id else None,
                ctx.request_id,
            )
            await conn.execute("SET LOCAL row_security = on")

        yield conn


@asynccontextmanager
async def transaction(
    dsn: str | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> AsyncIterator[asyncpg.Connection]:
    """Get a connection with transaction and tenant context.

    Same as connection() but wrapped in transaction block.
    """
    async with connection(dsn, tenant_scope) as conn, conn.transaction():
        yield conn
