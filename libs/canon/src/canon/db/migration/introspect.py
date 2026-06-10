"""Database schema introspection.

Queries pg_catalog to build SchemaSpec from live database state.
Enables state-based migration by comparing introspected schema against Entity-derived schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = (
    "introspect_check_constraints",
    "introspect_columns",
    "introspect_foreign_keys",
    "introspect_indexes",
    "introspect_primary_key",
    "introspect_schema",
    "introspect_table",
    "introspect_triggers",
    "introspect_unique_constraints",
)

from .schema import (
    CheckConstraintSpec,
    ColumnSpec,
    ForeignKeySpec,
    IndexMethod,
    IndexSpec,
    OnAction,
    SchemaSpec,
    TableSpec,
    TriggerSpec,
    UniqueConstraintSpec,
)

if TYPE_CHECKING:
    from asyncpg import Connection


async def introspect_columns(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[ColumnSpec, ...]:
    """Introspect column definitions from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of ColumnSpec objects.
    """
    query = """
    SELECT
        a.attname AS name,
        pg_catalog.format_type(a.atttypid, a.atttypmod) AS type,
        NOT a.attnotnull AS nullable,
        pg_get_expr(d.adbin, d.adrelid) AS default_expr,
        EXISTS (
            SELECT 1 FROM pg_constraint c
            WHERE c.conrelid = a.attrelid
            AND c.contype = 'p'
            AND a.attnum = ANY(c.conkey)
        ) AS is_primary_key,
        EXISTS (
            SELECT 1 FROM pg_constraint c
            WHERE c.conrelid = a.attrelid
            AND c.contype = 'u'
            AND array_length(c.conkey, 1) = 1
            AND a.attnum = c.conkey[1]
        ) AS is_unique
    FROM pg_attribute a
    JOIN pg_class t ON a.attrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
    WHERE n.nspname = $1
    AND t.relname = $2
    AND a.attnum > 0
    AND NOT a.attisdropped
    ORDER BY a.attnum;
    """
    rows = await conn.fetch(query, schema, table_name)

    columns = []
    for row in rows:
        # Normalize type names to uppercase
        col_type = _normalize_type(row["type"])

        col = ColumnSpec(
            name=row["name"],
            type=col_type,
            nullable=row["nullable"],
            default=row["default_expr"],
            is_primary_key=row["is_primary_key"],
            is_unique=row["is_unique"],
        )
        columns.append(col)

    return tuple(columns)


def _normalize_type(pg_type: str) -> str:
    """Normalize PostgreSQL type names to standard form.

    Args:
        pg_type: Type as returned by format_type().

    Returns:
        Normalized type name (e.g., "uuid" -> "UUID").
    """
    # Map common PostgreSQL type aliases to standard names
    type_map = {
        "uuid": "UUID",
        "text": "TEXT",
        "boolean": "BOOLEAN",
        "integer": "INTEGER",
        "bigint": "BIGINT",
        "smallint": "SMALLINT",
        "real": "REAL",
        "double precision": "DOUBLE PRECISION",
        "jsonb": "JSONB",
        "json": "JSON",
        "bytea": "BYTEA",
        "date": "DATE",
        "time without time zone": "TIME",
        "time with time zone": "TIMETZ",
        "timestamp without time zone": "TIMESTAMP",
        "timestamp with time zone": "TIMESTAMPTZ",
        "numeric": "NUMERIC",
    }

    lower_type = pg_type.lower()

    # Direct mapping
    if lower_type in type_map:
        return type_map[lower_type]

    # Character varying with length
    if lower_type.startswith("character varying"):
        return pg_type.upper().replace("CHARACTER VARYING", "VARCHAR")

    # Vector type (pgvector)
    if lower_type.startswith("vector"):
        return pg_type.upper()

    # Numeric with precision
    if lower_type.startswith("numeric("):
        return pg_type.upper()

    # Default: uppercase
    return pg_type.upper()


async def introspect_foreign_keys(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[ForeignKeySpec, ...]:
    """Introspect foreign key constraints from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of ForeignKeySpec objects.
    """
    query = """
    SELECT
        c.conname AS name,
        array_agg(a.attname ORDER BY k.n) AS columns,
        rn.nspname AS ref_schema,
        rt.relname AS ref_table,
        array_agg(ra.attname ORDER BY k.n) AS ref_columns,
        CASE c.confdeltype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
        END AS on_delete,
        CASE c.confupdtype
            WHEN 'a' THEN 'NO ACTION'
            WHEN 'r' THEN 'RESTRICT'
            WHEN 'c' THEN 'CASCADE'
            WHEN 'n' THEN 'SET NULL'
            WHEN 'd' THEN 'SET DEFAULT'
        END AS on_update,
        c.condeferrable AS deferrable,
        c.condeferred AS initially_deferred
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    JOIN pg_class rt ON c.confrelid = rt.oid
    JOIN pg_namespace rn ON rt.relnamespace = rn.oid
    CROSS JOIN LATERAL unnest(c.conkey, c.confkey) WITH ORDINALITY AS k(col_num, ref_num, n)
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.col_num
    JOIN pg_attribute ra ON ra.attrelid = c.confrelid AND ra.attnum = k.ref_num
    WHERE c.contype = 'f'
    AND n.nspname = $1
    AND t.relname = $2
    GROUP BY c.conname, rn.nspname, rt.relname, c.confdeltype, c.confupdtype,
             c.condeferrable, c.condeferred
    ORDER BY c.conname;
    """
    rows = await conn.fetch(query, schema, table_name)

    fks = []
    for row in rows:
        fk = ForeignKeySpec(
            name=row["name"],
            columns=tuple(row["columns"]),
            ref_table=row["ref_table"],
            ref_columns=tuple(row["ref_columns"]),
            on_delete=OnAction(row["on_delete"]),
            on_update=OnAction(row["on_update"]),
            deferrable=row["deferrable"],
            initially_deferred=row["initially_deferred"],
        )
        fks.append(fk)

    return tuple(fks)


async def introspect_indexes(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[IndexSpec, ...]:
    """Introspect indexes from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of IndexSpec objects (excluding primary key and unique constraint indexes).
    """
    query = """
    SELECT
        i.relname AS name,
        array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns,
        ix.indisunique AS is_unique,
        am.amname AS method,
        pg_get_expr(ix.indpred, ix.indrelid) AS where_clause
    FROM pg_index ix
    JOIN pg_class i ON i.oid = ix.indexrelid
    JOIN pg_class t ON t.oid = ix.indrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_am am ON am.oid = i.relam
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
    WHERE n.nspname = $1
    AND t.relname = $2
    AND NOT ix.indisprimary  -- Exclude primary key
    AND NOT EXISTS (  -- Exclude unique constraint indexes
        SELECT 1 FROM pg_constraint c
        WHERE c.conindid = ix.indexrelid AND c.contype = 'u'
    )
    GROUP BY i.relname, ix.indisunique, am.amname, ix.indpred, ix.indrelid
    ORDER BY i.relname;
    """
    rows = await conn.fetch(query, schema, table_name)

    indexes = []
    for row in rows:
        # Map method name to enum
        method_map = {
            "btree": IndexMethod.BTREE,
            "hash": IndexMethod.HASH,
            "gist": IndexMethod.GIST,
            "gin": IndexMethod.GIN,
            "spgist": IndexMethod.SPGIST,
            "brin": IndexMethod.BRIN,
            "ivfflat": IndexMethod.IVFFLAT,
            "hnsw": IndexMethod.HNSW,
        }
        method = method_map.get(row["method"], IndexMethod.BTREE)

        idx = IndexSpec(
            name=row["name"],
            columns=tuple(row["columns"]),
            unique=row["is_unique"],
            method=method,
            where=row["where_clause"],
        )
        indexes.append(idx)

    return tuple(indexes)


async def introspect_triggers(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[TriggerSpec, ...]:
    """Introspect triggers from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of TriggerSpec objects.
    """
    query = """
    SELECT
        t.tgname AS name,
        CASE
            WHEN t.tgtype::int & 2 = 2 THEN 'BEFORE'
            WHEN t.tgtype::int & 64 = 64 THEN 'INSTEAD OF'
            ELSE 'AFTER'
        END AS timing,
        array_remove(ARRAY[
            CASE WHEN t.tgtype::int & 4 = 4 THEN 'INSERT' END,
            CASE WHEN t.tgtype::int & 8 = 8 THEN 'DELETE' END,
            CASE WHEN t.tgtype::int & 16 = 16 THEN 'UPDATE' END
        ], NULL) AS events,
        p.proname AS function_name,
        pn.nspname AS function_schema,
        CASE
            WHEN t.tgtype::int & 1 = 1 THEN 'ROW'
            ELSE 'STATEMENT'
        END AS for_each,
        pg_get_triggerdef(t.oid) AS definition
    FROM pg_trigger t
    JOIN pg_class c ON t.tgrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    JOIN pg_proc p ON t.tgfoid = p.oid
    JOIN pg_namespace pn ON p.pronamespace = pn.oid
    WHERE n.nspname = $1
    AND c.relname = $2
    AND NOT t.tgisinternal  -- Exclude internal triggers
    ORDER BY t.tgname;
    """
    rows = await conn.fetch(query, schema, table_name)

    triggers = []
    for row in rows:
        # Extract WHEN clause from trigger definition if present
        when_clause = None
        definition = row["definition"]
        if "WHEN (" in definition:
            # Extract WHEN clause between "WHEN (" and ") EXECUTE"
            start = definition.find("WHEN (") + 6
            end = definition.find(") EXECUTE")
            if start > 5 and end > start:
                when_clause = definition[start:end]

        trigger = TriggerSpec(
            name=row["name"],
            timing=row["timing"],
            events=tuple(row["events"]),
            function=f"{row['function_schema']}.{row['function_name']}",
            for_each=row["for_each"],
            when=when_clause,
        )
        triggers.append(trigger)

    return tuple(triggers)


async def introspect_check_constraints(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[CheckConstraintSpec, ...]:
    """Introspect CHECK constraints from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of CheckConstraintSpec objects.
    """
    query = """
    SELECT
        c.conname AS name,
        pg_get_constraintdef(c.oid) AS definition
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE c.contype = 'c'
    AND n.nspname = $1
    AND t.relname = $2
    ORDER BY c.conname;
    """
    rows = await conn.fetch(query, schema, table_name)

    constraints = []
    for row in rows:
        # Extract expression from "CHECK (expression)"
        definition = row["definition"]
        if definition.startswith("CHECK (") and definition.endswith(")"):
            expression = definition[7:-1]
        else:
            expression = definition

        constraint = CheckConstraintSpec(
            name=row["name"],
            expression=expression,
        )
        constraints.append(constraint)

    return tuple(constraints)


async def introspect_unique_constraints(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[UniqueConstraintSpec, ...]:
    """Introspect UNIQUE constraints from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of UniqueConstraintSpec objects.
    """
    query = """
    SELECT
        c.conname AS name,
        array_agg(a.attname ORDER BY array_position(c.conkey, a.attnum)) AS columns
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
    WHERE c.contype = 'u'
    AND n.nspname = $1
    AND t.relname = $2
    GROUP BY c.conname
    ORDER BY c.conname;
    """
    rows = await conn.fetch(query, schema, table_name)

    constraints = []
    for row in rows:
        constraint = UniqueConstraintSpec(
            name=row["name"],
            columns=tuple(row["columns"]),
        )
        constraints.append(constraint)

    return tuple(constraints)


async def introspect_primary_key(
    conn: Connection, table_name: str, schema: str = "public"
) -> tuple[str, ...]:
    """Introspect primary key columns from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        Tuple of primary key column names.
    """
    query = """
    SELECT array_agg(a.attname ORDER BY array_position(c.conkey, a.attnum)) AS columns
    FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    JOIN pg_namespace n ON t.relnamespace = n.oid
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
    WHERE c.contype = 'p'
    AND n.nspname = $1
    AND t.relname = $2
    GROUP BY c.conname;
    """
    row = await conn.fetchrow(query, schema, table_name)

    if row and row["columns"]:
        return tuple(row["columns"])
    return ("id",)  # Default assumption


async def introspect_table(
    conn: Connection, table_name: str, schema: str = "public"
) -> TableSpec | None:
    """Introspect a complete table schema from pg_catalog.

    Args:
        conn: Database connection.
        table_name: Name of the table.
        schema: Schema name (default: public).

    Returns:
        TableSpec if table exists, None otherwise.
    """
    # Check if table exists
    exists_query = """
    SELECT EXISTS (
        SELECT 1 FROM pg_class t
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = $1 AND t.relname = $2 AND t.relkind = 'r'
    );
    """
    exists = await conn.fetchval(exists_query, schema, table_name)
    if not exists:
        return None

    # Introspect all components
    columns = await introspect_columns(conn, table_name, schema)
    primary_key = await introspect_primary_key(conn, table_name, schema)
    foreign_keys = await introspect_foreign_keys(conn, table_name, schema)
    indexes = await introspect_indexes(conn, table_name, schema)
    triggers = await introspect_triggers(conn, table_name, schema)
    check_constraints = await introspect_check_constraints(conn, table_name, schema)
    unique_constraints = await introspect_unique_constraints(conn, table_name, schema)

    return TableSpec(
        name=table_name,
        schema=schema,
        columns=columns,
        primary_key=primary_key,
        foreign_keys=foreign_keys,
        indexes=indexes,
        triggers=triggers,
        check_constraints=check_constraints,
        unique_constraints=unique_constraints,
    )


async def introspect_schema(conn: Connection, schema: str = "public") -> SchemaSpec:
    """Introspect all tables in a schema.

    Args:
        conn: Database connection.
        schema: Schema name (default: public).

    Returns:
        SchemaSpec with all tables in the schema.
    """
    # Get all table names
    query = """
    SELECT t.relname AS name
    FROM pg_class t
    JOIN pg_namespace n ON t.relnamespace = n.oid
    WHERE n.nspname = $1
    AND t.relkind = 'r'
    ORDER BY t.relname;
    """
    rows = await conn.fetch(query, schema)

    tables = []
    for row in rows:
        table_spec = await introspect_table(conn, row["name"], schema)
        if table_spec:
            tables.append(table_spec)

    # Compute version hash (same as SchemaSpec.from_registry)
    from kron.utils import compute_hash

    table_data = [
        {
            "name": t.name,
            "schema": t.schema,
            "columns": [
                {
                    "name": c.name,
                    "type": c.type,
                    "nullable": c.nullable,
                    "default": c.default,
                }
                for c in t.columns
            ],
            "foreign_keys": [
                {"name": fk.name, "columns": fk.columns, "ref_table": fk.ref_table}
                for fk in t.foreign_keys
            ],
            "indexes": [
                {"name": idx.name, "columns": idx.columns, "unique": idx.unique}
                for idx in t.indexes
            ],
        }
        for t in sorted(tables, key=lambda t: t.name)
    ]
    version = compute_hash(table_data)

    return SchemaSpec(tables=tuple(tables), version=version)
