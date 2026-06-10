"""Row-Level Security (RLS) for tenant isolation.

Generates PostgreSQL RLS policies that enforce tenant boundaries at the database level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from canon.entities import Entity

__all__ = (
    "generate_composite_fks",
    "generate_rls_policy",
    "generate_tenant_function",
    "generate_tenant_index",
    "generate_tenant_scoped_unique_constraints",
    "generate_tenant_unique_constraint",
    "get_tenant_unique_fields",
    "is_tenant_scoped",
)


def is_tenant_scoped(entity_cls: type[Entity]) -> bool:
    """Check if an Entity class has tenant_id field (requires RLS)."""
    return "tenant_id" in entity_cls.model_fields


def generate_tenant_function(app_role: str | None = None) -> str:
    """Generate the app.tenant_id() SQL function.

    This function retrieves the current tenant context from the session variable.
    It fails closed: if tenant context is not set, it raises an exception.

    The function is STABLE (same result within a transaction) and used by RLS
    policies to filter rows by tenant.

    Args:
        app_role: If provided, grants EXECUTE to this role and revokes
                  modification privileges (privilege hardening).
    """
    sql = """-- Tenant context function (fail-closed)
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.tenant_id()
RETURNS uuid
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $fn$
DECLARE
    v text;
BEGIN
    v := current_setting('app.tenant_id', true);
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'tenant context not set (app.tenant_id)'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN v::uuid;
END;
$fn$;
"""
    # Add privilege hardening if app_role specified
    if app_role:
        sql += f"""
-- Privilege hardening: app role can only EXECUTE, not modify
REVOKE ALL ON SCHEMA app FROM {app_role};
GRANT USAGE ON SCHEMA app TO {app_role};
REVOKE ALL ON FUNCTION app.tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.tenant_id() TO {app_role};
"""
    return sql


def generate_tenant_index(entity_cls: type[Entity]) -> str:
    """Generate index on tenant_id for RLS query performance.

    RLS policies filter by tenant_id on every query. Without an index,
    this causes sequential scans on large tables.
    """
    if not is_tenant_scoped(entity_cls):
        return ""

    table = entity_cls._table_name
    schema = entity_cls._schema
    index_name = f"ix_{table}_tenant_id"

    return f'CREATE INDEX IF NOT EXISTS {index_name} ON "{schema}"."{table}"(tenant_id);'


def generate_tenant_unique_constraint(entity_cls: type[Entity]) -> str:
    """Generate unique constraint on (tenant_id, id) for composite FK targets.

    Required for composite FKs to reference (tenant_id, id) pairs.
    """
    if not is_tenant_scoped(entity_cls):
        return ""

    table = entity_cls._table_name
    schema = entity_cls._schema
    constraint_name = f"uq_{table}_tenant_id"

    return (
        f'ALTER TABLE "{schema}"."{table}" ADD CONSTRAINT {constraint_name} UNIQUE (tenant_id, id);'
    )


def generate_composite_fks(entity_cls: type[Entity]) -> str:
    """Generate composite FK constraints for tenant-scoped cross-references.

    For each FK field pointing to another tenant-scoped entity, creates:
    FOREIGN KEY (tenant_id, fk_field) REFERENCES target(tenant_id, id)

    This enforces at the database level that FKs cannot cross tenant boundaries.
    """
    from kron.core import PERSISTABLE_NODE_REGISTRY
    from kron.types import FKMeta, extract_kron_db_meta

    if not is_tenant_scoped(entity_cls):
        return ""

    table = entity_cls._table_name
    schema = entity_cls._schema
    registry = PERSISTABLE_NODE_REGISTRY

    parts: list[str] = []

    for field_name, field_info in entity_cls.model_fields.items():
        # Skip tenant_id itself
        if field_name == "tenant_id":
            continue

        fk_info = extract_kron_db_meta(field_info, metas="FK")
        if not isinstance(fk_info, FKMeta):
            continue

        # Find the target entity
        target_cls = registry.get(fk_info.table_name)
        if not target_cls:
            continue

        # Only create composite FK if target is also tenant-scoped
        if not is_tenant_scoped(target_cls):
            continue

        constraint_name = f"fk_{table}_{field_name}_tenant"
        target_table = target_cls._table_name
        target_schema = target_cls._schema

        parts.append(
            f'ALTER TABLE "{schema}"."{table}" '
            f"ADD CONSTRAINT {constraint_name} "
            f'FOREIGN KEY (tenant_id, "{field_name}") '
            f'REFERENCES "{target_schema}"."{target_table}"(tenant_id, id);'
        )

    return "\n".join(parts)


def generate_rls_policy(entity_cls: type[Entity]) -> str:
    """Generate RLS policy for a tenant-scoped entity.

    Creates:
    1. ALTER TABLE ... ENABLE ROW LEVEL SECURITY
    2. ALTER TABLE ... FORCE ROW LEVEL SECURITY (removes table owner bypass)
    3. Policy for SELECT/INSERT/UPDATE/DELETE based on tenant_id = app.tenant_id()

    SECURITY NOTE: FORCE ROW LEVEL SECURITY only removes the bypass for the
    table owner role. Superusers and roles with BYPASSRLS attribute ALWAYS
    bypass RLS regardless of FORCE. Ensure the application role:
    - Is NOT a superuser
    - Does NOT have BYPASSRLS attribute
    - Does NOT own the tables (use separate admin role for DDL)
    """
    if not is_tenant_scoped(entity_cls):
        return ""

    table = entity_cls._table_name
    schema = entity_cls._schema
    policy_name = f"tenant_isolation_{table}"

    return f"""-- RLS policy for {table}
ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS {policy_name} ON "{schema}"."{table}";
CREATE POLICY {policy_name} ON "{schema}"."{table}"
    USING (tenant_id = app.tenant_id())
    WITH CHECK (tenant_id = app.tenant_id());
"""


def get_tenant_unique_fields(entity_cls: type[Entity]) -> set[str]:
    """Get fields that should be unique within tenant scope.

    Reads from _unique_within_tenant class variable.
    Fields listed here get UNIQUE(tenant_id, field) constraints.
    """
    return getattr(entity_cls, "_unique_within_tenant", set())


def generate_tenant_scoped_unique_constraints(entity_cls: type[Entity]) -> str:
    """Generate UNIQUE constraints for tenant-scoped fields.

    For each field in _unique_within_tenant, creates:
    UNIQUE (tenant_id, field)

    This prevents cross-tenant uniqueness leakage (e.g., email
    existence in one tenant shouldn't affect another).

    Example:
        class User(Entity):
            _unique_within_tenant = {"email"}
            email: str
            tenant_id: FK[Tenant]

        Generates: UNIQUE (tenant_id, email)
    """
    if not is_tenant_scoped(entity_cls):
        return ""

    unique_fields = get_tenant_unique_fields(entity_cls)
    if not unique_fields:
        return ""

    table = entity_cls._table_name
    schema = entity_cls._schema
    parts: list[str] = []

    for field in sorted(unique_fields):
        # Verify field exists
        if field not in entity_cls.model_fields:
            raise ValueError(
                f"{entity_cls.__name__}._unique_within_tenant references "
                f"non-existent field: {field}"
            )

        constraint_name = f"uq_{table}_tenant_{field}"
        parts.append(
            f'ALTER TABLE "{schema}"."{table}" '
            f"ADD CONSTRAINT {constraint_name} "
            f'UNIQUE (tenant_id, "{field}");'
        )

    return "\n".join(parts)
