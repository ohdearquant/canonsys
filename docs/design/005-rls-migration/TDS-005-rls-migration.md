---
doc_type: TDS
title: "Technical Design Specification: Row-Level Security and Migration"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: []
charters: []
predecessors: ["TDS-001-tenant-isolation", "TDS-002-entity", "TDS-003-immutability", "TDS-004-entity-db-correspondence"]
---

# Technical Design Specification: Row-Level Security and Migration

## 1. Overview

### 1.1 Purpose

This specification defines the Row-Level Security (RLS) enforcement and schema migration system.
This is **infrastructure** that enables tenant isolation for all phrase execution.

### 1.2 Scope

**In Scope**: RLS policy generation, fail-closed tenant context, topological sort for FK ordering,
multi-phase atomic migration, role separation, composite FK constraints.

**Out of Scope**: Application-level authorization (TDS-015), break-glass access (TDS-016), schema
versioning and rollback.

### 1.3 Goals

1. **Fail-Closed Isolation**: RLS denies access by default
2. **Database-Level Enforcement**: Tenant boundaries at PostgreSQL level
3. **Atomic Migration**: All-or-nothing schema changes
4. **Role Separation**: Principle of least privilege

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Migration Orchestration                              │
│  migrate_with_rls_and_roles() - 10-phase atomic migration                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌─────────────┐ ┌────────────────────┐
         │  Topological Sort │ │  DDL Gen    │ │  RLS Policy Gen    │
         └──────────────────┘ └─────────────┘ └────────────────────┘
                                      ▼
                    ┌─────────────────────────────────────┐
                    │        PostgreSQL Database           │
                    │  - Tables with FORCE RLS             │
                    │  - app.tenant_id() function          │
                    │  - Composite FK constraints          │
                    └─────────────────────────────────────┘
```

## 3. Tenant Context Function

```sql
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
```

**Properties**: STABLE (same result within transaction), SECURITY DEFINER, fail-closed.

## 4. RLS Policy

```sql
ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."users" FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_users ON "public"."users"
    USING (tenant_id = app.tenant_id())
    WITH CHECK (tenant_id = app.tenant_id());
```

## 5. Topological Sort

```python
def _topological_sort(entities: dict[str, type[Entity]]) -> list[type[Entity]]:
    """Kahn's algorithm: process zero in-degree nodes first.

    Complexity: O(V + E) where V = entities, E = FK relationships
    Self-referential FKs excluded to avoid false cycles.
    """
```

## 6. 10-Phase Migration

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

**All phases in single transaction** - failure rolls back everything.

## 7. Role Attributes

| Role      | SUPERUSER | BYPASSRLS | Owns Tables | Privileges                  |
| --------- | --------- | --------- | ----------- | --------------------------- |
| owner     | NO        | NO        | YES         | DDL, owns all tables        |
| app       | NO        | NO        | NO          | SELECT/INSERT/UPDATE/DELETE |
| support   | NO        | NO        | NO          | Same as app + break-glass   |
| analytics | NO        | NO        | NO          | SELECT only                 |

## 8. Key Files

| File                                   | Purpose                  |
| -------------------------------------- | ------------------------ |
| `libs/canon/src/canon/db/migration/rls.py`       | RLS policy generation    |
| `libs/canon/src/canon/db/migration/migration.py` | Migration orchestration  |
| `libs/canon/src/canon/db/migration/roles.py`     | Database role generation |
| `libs/canon/src/canon/db/connection.py`          | TenantScope management   |

## 9. Infrastructure Role

This TDS provides **infrastructure for all control surfaces**:

| Capability             | How Used                                          |
| ---------------------- | ------------------------------------------------- |
| RLS Policies           | Database-level tenant isolation for every surface |
| Role Separation        | `canonsys_app` role with NOBYPASSRLS              |
| Composite FKs          | Cross-tenant reference prevention                 |
| `evidence_active` View | Filters superseded evidence records               |

## 10. Security Guarantees

- Application bugs cannot leak cross-tenant data
- Missing tenant context fails immediately (not silently)
- Direct SQL access blocked by RLS (defense in depth)
- Table owner bypass prevented by `FORCE ROW LEVEL SECURITY`

## 11. References

- **ADR**: ADR-005-rls-migration
- **Implementation**: `libs/canon/src/canon/db/migration/`
- **Related**: TDS-001-tenant-isolation, TDS-004-entity-db-correspondence
