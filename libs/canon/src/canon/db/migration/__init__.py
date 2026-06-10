"""Schema migration for Entity classes.

Core migration:
    migrate, migrate_with_rls - Apply migrations with optional RLS
    drop_all, drop_table - Remove tables

DDL generation:
    generate_ddl, generate_full_ddl - Generate CREATE TABLE
    generate_all_migrations - Generate full migration script

RLS (Row-Level Security):
    generate_rls_policy, generate_tenant_function - Tenant isolation
    apply_rls_policies, apply_tenant_function - Apply RLS to database

Roles:
    RoleConfig - Database role configuration
    generate_database_roles - Create role hierarchy

Schema inspection:
    SchemaSpec, TableSpec - Schema specifications
    introspect_schema, introspect_table - Read schema from database
    diff_schemas - Compare schemas for migration planning
"""

from .diff import (
    MigrationOp,
    MigrationPlan,
    OperationRisk,
    OperationType,
    diff_schemas,
    diff_tables,
)
from .introspect import introspect_schema, introspect_table
from .migration import (
    apply_evidence_active_view,
    apply_rls_policies,
    apply_tenant_function,
    apply_triggers,
    create_table,
    drop_all,
    drop_table,
    generate_all_migrations,
    generate_all_rls_policies,
    generate_evidence_active_view,
    generate_full_ddl,
    generate_immutability_triggers,
    generate_index_ddl,
    get_migration_order,
    is_immutable_entity,
    migrate,
    migrate_with_rls,
    migrate_with_rls_and_roles,
)
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

__all__ = (
    # Diff
    "MigrationOp",
    "MigrationPlan",
    "OperationRisk",
    "OperationType",
    "diff_schemas",
    "diff_tables",
    # Introspect
    "introspect_schema",
    "introspect_table",
    # Migration
    "apply_evidence_active_view",
    "apply_rls_policies",
    "apply_tenant_function",
    "apply_triggers",
    "create_table",
    "drop_all",
    "drop_table",
    "generate_all_migrations",
    "generate_all_rls_policies",
    "generate_evidence_active_view",
    "generate_full_ddl",
    "generate_immutability_triggers",
    "generate_index_ddl",
    "get_migration_order",
    "is_immutable_entity",
    "migrate",
    "migrate_with_rls",
    "migrate_with_rls_and_roles",
    # RLS
    "generate_composite_fks",
    "generate_rls_policy",
    "generate_tenant_function",
    "generate_tenant_index",
    "generate_tenant_scoped_unique_constraints",
    "generate_tenant_unique_constraint",
    "is_tenant_scoped",
    # Roles
    "RoleConfig",
    "generate_database_roles",
    "generate_table_ownership",
    # Schema specs
    "CheckConstraintSpec",
    "ColumnSpec",
    "ForeignKeySpec",
    "IndexMethod",
    "IndexSpec",
    "OnAction",
    "SchemaSpec",
    "TableSpec",
    "TriggerSpec",
    "UniqueConstraintSpec",
)
