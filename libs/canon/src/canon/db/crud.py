"""CRUD database operations.

Simple insert/update/delete/select with tenant context.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from .connection import TenantScope, connection
from .validation import sanitize_order_by, validate_identifier

if TYPE_CHECKING:
    import asyncpg


def _serialize_value(value: Any) -> Any:
    """Serialize values for database insert/update.

    - dict/list: Passed directly (asyncpg JSON codec handles encoding)
    - ISO datetime string → datetime object (from model_dump mode="json")
    """
    # Parse ISO datetime strings back to datetime objects
    # This handles datetimes serialized via model_dump(mode="json")
    if isinstance(value, str):
        # Check for ISO format datetime strings (with Z or +00:00 suffix)
        if len(value) >= 19 and value[4] == "-" and value[7] == "-" and "T" in value:
            try:
                # Handle 'Z' suffix (Zulu/UTC)
                if value.endswith("Z"):
                    return datetime.fromisoformat(value[:-1] + "+00:00")
                return datetime.fromisoformat(value)
            except (ValueError, TypeError):
                pass
    return value


__all__ = (
    "count",
    "delete",
    "execute",
    "execute_sql",
    "fetch",
    "fetchval",
    "insert",
    "select",
    "select_one",
    "update",
    "upsert",
)


async def insert(
    table: str,
    data: dict[str, Any],
    *,
    schema: str = "public",
    returning: bool = True,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> dict[str, Any] | None:
    """Insert a row."""
    columns = list(data.keys())
    values = [_serialize_value(v) for v in data.values()]

    for col in columns:
        validate_identifier(col, "column")

    col_names = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(values)))

    sql = f'INSERT INTO "{schema}"."{table}" ({col_names}) VALUES ({placeholders})'
    if returning:
        sql += " RETURNING *"

    if conn is not None:
        if returning:
            row = await conn.fetchrow(sql, *values)
            return dict(row) if row else None
        await conn.execute(sql, *values)
        return None

    async with connection(dsn, tenant_scope) as c:
        if returning:
            row = await c.fetchrow(sql, *values)
            return dict(row) if row else None
        await c.execute(sql, *values)
        return None


async def upsert(
    table: str,
    data: dict[str, Any],
    *,
    conflict_column: str = "id",
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> dict[str, Any] | None:
    """Insert or update on conflict."""
    columns = list(data.keys())
    values = [_serialize_value(v) for v in data.values()]

    for col in columns:
        validate_identifier(col, "column")
    validate_identifier(conflict_column, "conflict column")

    col_names = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(values)))
    update_cols = [c for c in columns if c != conflict_column]
    update_clause = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in update_cols)

    sql = f"""
        INSERT INTO "{schema}"."{table}" ({col_names})
        VALUES ({placeholders})
        ON CONFLICT ("{conflict_column}") DO UPDATE SET {update_clause}
        RETURNING *
    """

    if conn is not None:
        row = await conn.fetchrow(sql, *values)
        return dict(row) if row else None

    async with connection(dsn, tenant_scope) as c:
        row = await c.fetchrow(sql, *values)
        return dict(row) if row else None


async def update(
    table: str,
    data: dict[str, Any],
    where: dict[str, Any],
    *,
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> dict[str, Any] | None:
    """Update a row by conditions."""
    columns = list(data.keys())
    values = [_serialize_value(v) for v in data.values()]

    for col in columns:
        validate_identifier(col, "column")

    set_clause = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(columns))

    where_parts = []
    for i, (col, val) in enumerate(where.items(), len(values) + 1):
        validate_identifier(col, "column")
        where_parts.append(f'"{col}" = ${i}')
        values.append(val)

    sql = f"""
        UPDATE "{schema}"."{table}"
        SET {set_clause}
        WHERE {" AND ".join(where_parts)}
        RETURNING *
    """

    if conn is not None:
        row = await conn.fetchrow(sql, *values)
        return dict(row) if row else None

    async with connection(dsn, tenant_scope) as c:
        row = await c.fetchrow(sql, *values)
        return dict(row) if row else None


async def delete(
    table: str,
    where: dict[str, Any],
    *,
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> int:
    """Delete rows. Returns count deleted."""
    values: list[Any] = []
    where_parts = []

    for i, (col, val) in enumerate(where.items(), 1):
        validate_identifier(col, "column")
        where_parts.append(f'"{col}" = ${i}')
        values.append(val)

    sql = f'DELETE FROM "{schema}"."{table}" WHERE {" AND ".join(where_parts)}'

    if conn is not None:
        result = await conn.execute(sql, *values)
        return int(result.split()[-1]) if result else 0

    async with connection(dsn, tenant_scope) as c:
        result = await c.execute(sql, *values)
        return int(result.split()[-1]) if result else 0


async def select(
    table: str,
    *,
    where: dict[str, Any] | None = None,
    order_by: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> list[dict[str, Any]]:
    """Select rows with optional filters."""
    sql_parts = [f'SELECT * FROM "{schema}"."{table}"']
    values: list[Any] = []
    idx = 1

    if where:
        conditions = []
        for col, val in where.items():
            validate_identifier(col, "column")
            conditions.append(f'"{col}" = ${idx}')
            values.append(val)
            idx += 1
        sql_parts.append("WHERE " + " AND ".join(conditions))

    if order_by:
        sql_parts.append(f"ORDER BY {sanitize_order_by(order_by)}")

    if limit is not None:
        sql_parts.append(f"LIMIT ${idx}")
        values.append(int(limit))
        idx += 1

    if offset is not None:
        sql_parts.append(f"OFFSET ${idx}")
        values.append(int(offset))

    sql = " ".join(sql_parts)

    if conn is not None:
        rows = await conn.fetch(sql, *values)
        return [dict(row) for row in rows]

    async with connection(dsn, tenant_scope) as c:
        rows = await c.fetch(sql, *values)
        return [dict(row) for row in rows]


async def select_one(
    table: str,
    where: dict[str, Any],
    *,
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> dict[str, Any] | None:
    """Select a single row."""
    rows = await select(
        table,
        where=where,
        limit=1,
        schema=schema,
        dsn=dsn,
        conn=conn,
        tenant_scope=tenant_scope,
    )
    return rows[0] if rows else None


async def count(
    table: str,
    *,
    where: dict[str, Any] | None = None,
    schema: str = "public",
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> int:
    """Count rows."""
    sql_parts = [f'SELECT COUNT(*) FROM "{schema}"."{table}"']
    values: list[Any] = []

    if where:
        conditions = []
        for i, (col, val) in enumerate(where.items(), 1):
            validate_identifier(col, "column")
            conditions.append(f'"{col}" = ${i}')
            values.append(val)
        sql_parts.append("WHERE " + " AND ".join(conditions))

    sql = " ".join(sql_parts)

    if conn is not None:
        return await conn.fetchval(sql, *values) or 0

    async with connection(dsn, tenant_scope) as c:
        return await c.fetchval(sql, *values) or 0


async def execute(
    sql: str,
    *args: Any,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> str:
    """Execute raw SQL."""
    if conn is not None:
        return await conn.execute(sql, *args)

    async with connection(dsn, tenant_scope) as c:
        return await c.execute(sql, *args)


async def fetch(
    sql: str,
    *args: Any,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> list[dict[str, Any]]:
    """Execute raw SQL and return rows."""
    if conn is not None:
        rows = await conn.fetch(sql, *args)
        return [dict(row) for row in rows]

    async with connection(dsn, tenant_scope) as c:
        rows = await c.fetch(sql, *args)
        return [dict(row) for row in rows]


async def fetchval(
    sql: str,
    *args: Any,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> Any:
    """Execute raw SQL and return single value."""
    if conn is not None:
        return await conn.fetchval(sql, *args)

    async with connection(dsn, tenant_scope) as c:
        return await c.fetchval(sql, *args)


async def execute_sql(
    sql: str,
    *args: Any,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
) -> str:
    """Execute raw SQL without tenant context (for migrations, DDL).

    Unlike execute(), this uses TenantScope.DISABLED by default,
    making it suitable for schema migrations and administrative tasks.
    """
    return await execute(sql, *args, dsn=dsn, conn=conn, tenant_scope=TenantScope.DISABLED)
