"""Schema migration - discovers Entity subclasses and manages DDL.

All Entity subclasses are auto-registered via __init_subclass__.
FK[Model] relationships determine dependency ordering for table creation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = (
    "apply_evidence_active_view",
    "apply_rls_policies",
    "apply_tenant_function",
    "apply_triggers",
    "create_table",
    "drop_all",
    "drop_table",
    "generate_all_migrations",
    "generate_all_rls_policies",
    "generate_ddl",
    "generate_evidence_active_view",
    "generate_full_ddl",
    "generate_immutability_triggers",
    "generate_index_ddl",
    "get_migration_order",
    "is_immutable_entity",
    "migrate",
    "migrate_with_rls",
    "migrate_with_rls_and_roles",
)

from kron.core import generate_ddl, get_fk_dependencies

from ..connection import TenantScope, transaction
from ..crud import execute_sql
from .rls import (
    generate_composite_fks,
    generate_rls_policy,
    generate_tenant_function,
    generate_tenant_index,
    generate_tenant_scoped_unique_constraints,
    generate_tenant_unique_constraint,
    is_tenant_scoped,
)
from .roles import RoleConfig, generate_database_roles, generate_table_ownership

if TYPE_CHECKING:
    from canon.entities import Entity


def _get_entity_registry() -> dict[str, type]:
    """Get persistable entity registry from kron."""
    from kron.core import PERSISTABLE_NODE_REGISTRY

    return PERSISTABLE_NODE_REGISTRY


def _get_table_name(cls: type) -> str:
    """Get table name from Entity class (handles both old and new interface)."""
    if hasattr(cls, "_table_name"):
        return cls._table_name
    return cls.node_config.table_name


def _get_schema(cls: type) -> str:
    """Get schema from Entity class (handles both old and new interface)."""
    if hasattr(cls, "_schema"):
        return cls._schema
    return cls.node_config.schema


def _topological_sort(entities: dict[str, type[Entity]]) -> list[type[Entity]]:
    """Sort entities by FK dependencies (dependencies first).

    Uses Kahn's algorithm for topological sorting.
    """
    # Build dependency graph
    in_degree: dict[str, int] = dict.fromkeys(entities, 0)
    dependents: dict[str, list[str]] = {name: [] for name in entities}

    for name, cls in entities.items():
        deps = get_fk_dependencies(cls)
        for dep in deps:
            # Skip self-references (table referencing itself)
            if dep == name:
                continue
            if dep in entities:
                in_degree[name] += 1
                dependents[dep].append(name)

    # Start with entities that have no dependencies
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result: list[type[Entity]] = []

    while queue:
        name = queue.pop(0)
        result.append(entities[name])

        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Check for cycles
    if len(result) != len(entities):
        remaining = set(entities.keys()) - {_get_table_name(cls) for cls in result}
        raise ValueError(f"Circular FK dependencies detected: {remaining}")

    return result


def get_migration_order() -> list[type[Entity]]:
    """Get Entity classes in dependency order for migration."""
    registry = _get_entity_registry()
    return _topological_sort(registry)


async def create_table(
    entity_cls: type[Entity],
    dsn: str | None = None,
) -> None:
    """Create a single table."""
    ddl = generate_ddl(entity_cls)
    await execute_sql(ddl, dsn=dsn)


async def drop_table(
    entity_cls: type[Entity],
    dsn: str | None = None,
    cascade: bool = False,
) -> None:
    """Drop a single table."""
    cascade_sql = " CASCADE" if cascade else ""
    schema = _get_schema(entity_cls)
    table = _get_table_name(entity_cls)
    await execute_sql(
        f'DROP TABLE IF EXISTS "{schema}"."{table}"{cascade_sql};',
        dsn=dsn,
    )


async def migrate(dsn: str | None = None) -> list[str]:
    """Create all registered Entity tables in dependency order.

    Returns list of table names created.
    """
    entities = get_migration_order()
    created: list[str] = []

    for entity_cls in entities:
        await create_table(entity_cls, dsn=dsn)
        created.append(_get_table_name(entity_cls))

    return created


async def drop_all(dsn: str | None = None, cascade: bool = True) -> list[str]:
    """Drop all registered Entity tables in reverse dependency order.

    Returns list of table names dropped.
    """
    entities = get_migration_order()
    dropped: list[str] = []

    # Drop in reverse order (dependents first)
    for entity_cls in reversed(entities):
        await drop_table(entity_cls, dsn=dsn, cascade=cascade)
        dropped.append(_get_table_name(entity_cls))

    return dropped


def is_immutable_entity(entity_cls: type[Entity]) -> bool:
    """Check if an Entity class is immutable (created with immutable=True)."""
    return getattr(entity_cls, "_immutable", False)


def get_allowed_update_fields(entity_cls: type[Entity]) -> set[str]:
    """Get allowed update fields for an ImmutableEntity."""
    return getattr(entity_cls, "_allowed_update_fields", set())


def generate_immutable_update_trigger(entity_cls: type[Entity]) -> str:
    """Generate UPDATE block trigger for an ImmutableEntity.

    The trigger blocks all updates except for fields in _allowed_update_fields.
    """
    table = _get_table_name(entity_cls)
    schema = _get_schema(entity_cls)
    allowed = get_allowed_update_fields(entity_cls)

    # Get all field names except id (always excluded)
    # metadata IS protected for ImmutableEntity to prevent content_hash tampering
    immutable_fields = [
        name for name in entity_cls.model_fields.keys() if name != "id" and name not in allowed
    ]

    fn_name = f"tr_{table}_update_immutable"
    trigger_name = fn_name

    # Build the immutable fields array literal
    fields_array = "ARRAY[" + ", ".join(f"'{f}'" for f in immutable_fields) + "]"

    # Build allowed update check if there are allowed fields
    if allowed:
        allowed_check = f"""
    -- Allowed update: only {", ".join(sorted(allowed))} changed
    IF array_length(changed_fields, 1) = 1 AND changed_fields[1] = ANY(ARRAY[{", ".join(f"'{f}'" for f in sorted(allowed))}]) THEN
        RETURN NEW;
    END IF;"""
    else:
        allowed_check = ""

    return f"""-- Auto-generated immutability trigger for {table}
CREATE OR REPLACE FUNCTION {fn_name}()
RETURNS TRIGGER AS $$
DECLARE
    immutable_fields TEXT[] := {fields_array};
    changed_fields TEXT[] := '{{}}';
    field TEXT;
BEGIN
    FOREACH field IN ARRAY immutable_fields LOOP
        IF (row_to_json(OLD)->>field) IS DISTINCT FROM (row_to_json(NEW)->>field) THEN
            changed_fields := array_append(changed_fields, field);
        END IF;
    END LOOP;
{allowed_check}
    IF array_length(changed_fields, 1) > 0 THEN
        RAISE EXCEPTION '{table} is immutable. Attempted to modify fields: %', changed_fields
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS {trigger_name} ON "{schema}"."{table}";
CREATE TRIGGER {trigger_name}
    BEFORE UPDATE ON "{schema}"."{table}"
    FOR EACH ROW
    EXECUTE FUNCTION {fn_name}();
"""


def generate_immutable_delete_trigger(entity_cls: type[Entity]) -> str:
    """Generate DELETE block trigger for an ImmutableEntity."""
    table = _get_table_name(entity_cls)
    schema = _get_schema(entity_cls)
    fn_name = f"tr_{table}_delete_immutable"
    trigger_name = fn_name

    return f"""-- Auto-generated delete block trigger for {table}
CREATE OR REPLACE FUNCTION {fn_name}()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '{table} is immutable and cannot be deleted (id=%)', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS {trigger_name} ON "{schema}"."{table}";
CREATE TRIGGER {trigger_name}
    BEFORE DELETE ON "{schema}"."{table}"
    FOR EACH ROW
    EXECUTE FUNCTION {fn_name}();
"""


def generate_immutability_triggers(entity_cls: type[Entity]) -> str:
    """Generate all immutability triggers for an ImmutableEntity."""
    if not is_immutable_entity(entity_cls):
        return ""

    return (
        generate_immutable_update_trigger(entity_cls)
        + "\n"
        + generate_immutable_delete_trigger(entity_cls)
    )


def generate_index_ddl(entity_cls: type[Entity], index_spec: dict) -> str:
    """Generate CREATE INDEX statement from index spec.

    Index spec format:
        {"columns": ["col1", "col2"], "unique": False, "where": "col1 IS NOT NULL"}
    """
    table = _get_table_name(entity_cls)
    schema = _get_schema(entity_cls)
    columns = index_spec.get("columns", [])
    unique = index_spec.get("unique", False)
    where = index_spec.get("where")
    name = index_spec.get("name") or f"ix_{table}_{'_'.join(columns)}"

    unique_kw = "UNIQUE " if unique else ""
    cols = ", ".join(f'"{c}"' for c in columns)
    where_clause = f" WHERE {where}" if where else ""

    return f'CREATE {unique_kw}INDEX IF NOT EXISTS {name} ON "{schema}"."{table}"({cols}){where_clause};'


def generate_full_ddl(entity_cls: type[Entity]) -> str:
    """Generate complete DDL for an Entity: table + triggers + indexes."""
    parts = [generate_ddl(entity_cls)]

    # Add immutability triggers if applicable
    if is_immutable_entity(entity_cls):
        parts.append(generate_immutability_triggers(entity_cls))

    # Add indexes if defined
    indexes = getattr(entity_cls, "_indexes", [])
    for idx in indexes:
        parts.append(generate_index_ddl(entity_cls, idx))

    return "\n\n".join(filter(None, parts))


async def apply_triggers(dsn: str | None = None) -> list[str]:
    """Apply immutability triggers for all ImmutableEntity subclasses.

    Returns list of table names with triggers applied.
    """
    entities = get_migration_order()
    applied: list[str] = []

    for entity_cls in entities:
        if is_immutable_entity(entity_cls):
            ddl = generate_immutability_triggers(entity_cls)
            await execute_sql(ddl, dsn=dsn)
            applied.append(_get_table_name(entity_cls))

    return applied


def generate_all_migrations() -> str:
    """Generate complete migration SQL for all entities.

    Returns a single SQL string with all tables, triggers, and indexes.
    """
    entities = get_migration_order()
    parts: list[str] = []

    parts.append("-- Auto-generated migration script")
    parts.append("-- Generated from Entity class definitions\n")

    for entity_cls in entities:
        parts.append(f"-- {entity_cls.__name__}")
        parts.append(generate_full_ddl(entity_cls))
        parts.append("")

    return "\n".join(parts)


def generate_all_rls_policies() -> str:
    """Generate RLS policies for all tenant-scoped entities."""
    entities = get_migration_order()
    parts: list[str] = []

    parts.append("-- Auto-generated RLS policies")
    parts.append("-- Enforces tenant isolation at database level\n")

    # First, the tenant function
    parts.append(generate_tenant_function())

    # Then policies for each tenant-scoped entity
    for entity_cls in entities:
        if is_tenant_scoped(entity_cls):
            parts.append(f"-- {entity_cls.__name__}")
            parts.append(generate_rls_policy(entity_cls))

    return "\n".join(parts)


async def apply_tenant_function(dsn: str | None = None) -> None:
    """Create the app.tenant_id() function in the database."""
    ddl = generate_tenant_function()
    await execute_sql(ddl, dsn=dsn)


async def apply_rls_policies(dsn: str | None = None) -> list[str]:
    """Apply RLS policies for all tenant-scoped entities.

    Returns list of table names with RLS applied.
    """
    entities = get_migration_order()
    applied: list[str] = []

    for entity_cls in entities:
        if is_tenant_scoped(entity_cls):
            ddl = generate_rls_policy(entity_cls)
            await execute_sql(ddl, dsn=dsn)
            applied.append(_get_table_name(entity_cls))

    return applied


async def migrate_with_rls(
    dsn: str | None = None,
    app_role: str | None = None,
) -> dict[str, list[str]]:
    """Full migration with RLS: tables → triggers → constraints → RLS.

    All operations run in a single transaction to prevent partial migrations
    from leaving tables unprotected.

    Phases:
    1. Create tables (in dependency order)
    2. Apply immutability triggers
    3. Create tenant_id indexes for RLS performance
    4. Create unique constraints for composite FK targets
    5. Create composite FKs to enforce tenant boundaries on writes
    6. Apply tenant function and RLS policies

    Args:
        dsn: Database connection string.
        app_role: Application role name for privilege hardening.
                  If provided, the app role will only have EXECUTE on
                  app.tenant_id(), preventing function tampering.

    Returns:
        Dict with keys: tables, triggers, indexes, constraints, composite_fks, rls
    """
    result: dict[str, list[str]] = {
        "tables": [],
        "triggers": [],
        "indexes": [],
        "constraints": [],
        "composite_fks": [],
        "rls": [],
    }

    entities = get_migration_order()

    # Run everything in a transaction to ensure atomicity
    async with transaction(dsn, tenant_scope=TenantScope.DISABLED) as conn:
        # Phase 1: Create tables
        for entity_cls in entities:
            ddl = generate_ddl(entity_cls)
            await conn.execute(ddl)
            result["tables"].append(_get_table_name(entity_cls))

        # Phase 2: Apply immutability triggers
        for entity_cls in entities:
            if is_immutable_entity(entity_cls):
                ddl = generate_immutability_triggers(entity_cls)
                await conn.execute(ddl)
                result["triggers"].append(_get_table_name(entity_cls))

        # Phase 3: Create tenant_id indexes
        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_tenant_index(entity_cls)
                await conn.execute(ddl)
                result["indexes"].append(_get_table_name(entity_cls))

        # Phase 4: Create unique constraints for composite FK targets
        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_tenant_unique_constraint(entity_cls)
                await conn.execute(ddl)
                result["constraints"].append(_get_table_name(entity_cls))

        # Phase 5: Create composite FKs
        for entity_cls in entities:
            ddl = generate_composite_fks(entity_cls)
            if ddl:
                await conn.execute(ddl)
                result["composite_fks"].append(_get_table_name(entity_cls))

        # Phase 6: Apply tenant function and RLS policies
        ddl = generate_tenant_function(app_role)
        await conn.execute(ddl)

        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_rls_policy(entity_cls)
                await conn.execute(ddl)
                result["rls"].append(_get_table_name(entity_cls))

    return result


async def migrate_with_rls_and_roles(
    dsn: str | None = None,
    role_config: RoleConfig | None = None,
) -> dict[str, list[str]]:
    """Full migration with RLS and role separation.

    Complete infrastructure setup:
    1. Create database roles
    2. Create tables (in dependency order)
    3. Set table ownership to owner role
    4. Apply immutability triggers
    5. Create tenant_id indexes for RLS performance
    6. Create unique constraints for composite FK targets
    7. Create tenant-scoped unique constraints
    8. Create composite FKs to enforce tenant boundaries
    9. Apply tenant function and RLS policies
    10. Create evidence_active view
    Args:
        dsn: Database connection string.
        role_config: Role configuration. Uses defaults if None.

    Returns:
        Dict with keys: roles, tables, ownership, triggers, indexes,
                        constraints, tenant_unique, composite_fks, rls, views
    """
    config = role_config or RoleConfig()

    result: dict[str, list[str]] = {
        "roles": [],
        "tables": [],
        "ownership": [],
        "triggers": [],
        "indexes": [],
        "constraints": [],
        "tenant_unique": [],
        "composite_fks": [],
        "rls": [],
        "views": [],
    }

    entities = get_migration_order()

    async with transaction(dsn, tenant_scope=TenantScope.DISABLED) as conn:
        # Phase 1: Create database roles
        ddl = generate_database_roles(config)
        await conn.execute(ddl)
        result["roles"] = [config.owner, config.app, config.support, config.analytics]

        # Phase 2: Create tables
        for entity_cls in entities:
            ddl = generate_ddl(entity_cls)
            await conn.execute(ddl)
            result["tables"].append(_get_table_name(entity_cls))

        # Phase 3: Set table ownership
        for entity_cls in entities:
            ddl = generate_table_ownership(entity_cls, config.owner)
            await conn.execute(ddl)
            result["ownership"].append(_get_table_name(entity_cls))

        # Phase 4: Apply immutability triggers
        for entity_cls in entities:
            if is_immutable_entity(entity_cls):
                ddl = generate_immutability_triggers(entity_cls)
                await conn.execute(ddl)
                result["triggers"].append(_get_table_name(entity_cls))

        # Phase 5: Create tenant_id indexes
        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_tenant_index(entity_cls)
                await conn.execute(ddl)
                result["indexes"].append(_get_table_name(entity_cls))

        # Phase 6: Create unique constraints for composite FK targets
        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_tenant_unique_constraint(entity_cls)
                await conn.execute(ddl)
                result["constraints"].append(_get_table_name(entity_cls))

        # Phase 7: Create tenant-scoped unique constraints
        for entity_cls in entities:
            ddl = generate_tenant_scoped_unique_constraints(entity_cls)
            if ddl:
                await conn.execute(ddl)
                result["tenant_unique"].append(_get_table_name(entity_cls))

        # Phase 8: Create composite FKs
        for entity_cls in entities:
            ddl = generate_composite_fks(entity_cls)
            if ddl:
                await conn.execute(ddl)
                result["composite_fks"].append(_get_table_name(entity_cls))

        # Phase 9: Apply tenant function and RLS policies
        ddl = generate_tenant_function(config.app)
        await conn.execute(ddl)

        for entity_cls in entities:
            if is_tenant_scoped(entity_cls):
                ddl = generate_rls_policy(entity_cls)
                await conn.execute(ddl)
                result["rls"].append(_get_table_name(entity_cls))

        # Phase 10: Create evidence_active view
        ddl = generate_evidence_active_view()
        await conn.execute(ddl)
        result["views"].append("evidence_active")

    return result


def generate_evidence_active_view(schema: str = "public") -> str:
    """Generate the evidence_active view.

    Active evidence = records that have not been superseded.
    Since forward pointer is derived, we use a LEFT JOIN
    to find records with no successor.

    Usage:
        SELECT * FROM evidence_active WHERE tenant_id = ...

    The view filters out superseded evidence, showing only current/active heads.
    This is the default view for most queries - use base table only when
    you need full supersession history.
    """
    return f"""-- Active evidence view (non-superseded records)
CREATE OR REPLACE VIEW "{schema}"."evidence_active" AS
SELECT e.*
FROM "{schema}"."evidences" e
LEFT JOIN "{schema}"."evidences" s ON s.supersedes_id = e.id
WHERE s.id IS NULL;

COMMENT ON VIEW "{schema}"."evidence_active" IS
    'Active (non-superseded) evidence records. Use this view for most queries.';
"""


async def apply_evidence_active_view(dsn: str | None = None, schema: str = "public") -> None:
    """Create the evidence_active view in the database."""
    ddl = generate_evidence_active_view(schema)
    await execute_sql(ddl, dsn=dsn)
