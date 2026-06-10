# 005 - RLS and Migration - Code Mapping

**Updated**: 2026-01-29 | **Status**: Infrastructure (no vocabulary)

## Summary

RLS and Migration is **infrastructure** that enables tenant isolation for all phrase execution. It
does not define vocabulary packages itself.

## Implementation Files

| File                                   | Purpose                                       |
| -------------------------------------- | --------------------------------------------- |
| `libs/canon/src/canon/db/migration/rls.py`       | generate_tenant_function, generate_rls_policy |
| `libs/canon/src/canon/db/migration/migration.py` | _topological_sort, migrate_with_rls_and_roles |
| `libs/canon/src/canon/db/migration/roles.py`     | RoleConfig, generate_database_roles           |
| `libs/canon/src/canon/db/connection.py`          | TenantScope, transaction context              |

## Key Functions

| Function                          | Location       | Purpose                              |
| --------------------------------- | -------------- | ------------------------------------ |
| `generate_tenant_function()`      | `rls.py`       | app.tenant_id() fail-closed function |
| `generate_rls_policy()`           | `rls.py`       | ENABLE/FORCE RLS per table           |
| `generate_composite_fks()`        | `rls.py`       | Cross-tenant FK enforcement          |
| `_topological_sort()`             | `migration.py` | Kahn's algorithm for FK ordering     |
| `migrate_with_rls_and_roles()`    | `migration.py` | 10-phase atomic migration            |
| `generate_database_roles()`       | `roles.py`     | 4-role privilege separation          |
| `generate_evidence_active_view()` | `migration.py` | Non-superseded evidence view         |

## 10-Phase Migration

1. Create roles (owner/app/support/analytics)
2. Create tables (dependency order)
3. Set table ownership
4. Apply immutability triggers
5. Create tenant_id indexes
6. Create unique constraints for composite FK targets
7. Create tenant-scoped unique constraints
8. Create composite FKs
9. Apply tenant function and RLS policies
10. Create evidence_active view

## Security Guarantees

- Application bugs cannot leak cross-tenant data
- Missing tenant context fails immediately
- Direct SQL access blocked by RLS
- Table owner bypass prevented by FORCE RLS

## Downstream Dependencies

All vocabulary packages execute within RLS-protected context:

| Package  | Usage                                         |
| -------- | --------------------------------------------- |
| All 50+  | TenantScope.REQUIRED for phrase execution     |
| evidence | evidence_active view for supersession queries |

## Design Documents

- **ADR**: ADR-005-rls-migration.md
- **TDS**: TDS-005-rls-migration.md
