---
doc_type: ADR
title: "ADR-005: Row-Level Security and Migration Strategy"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: []
charters: []
---

# ADR-005: Row-Level Security and Migration Strategy

## Status

Accepted

## Context

CanonSys requires tenant isolation that cannot be bypassed by application bugs. Traditional
application-level authorization is vulnerable to developer error, SQL injection, and code path
oversights. The compliance-as-substrate philosophy demands database-level enforcement.

### Decision Drivers

- Tenant data must be isolated at the database layer
- Migration must be atomic - no partially protected states
- Role separation must follow principle of least privilege
- Cross-tenant FK violations must be prevented at constraint level

## Decision

### D1: FORCE RLS on All Tables

```sql
ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."users" FORCE ROW LEVEL SECURITY;
```

**Rationale**: Even if owner credentials are used accidentally, RLS still applies. FORCE RLS does
NOT affect superusers (acceptable - superuser credentials vault-managed).

**Implementation**: See `libs/canon/src/canon/db/migration/rls.py`

### D2: Topological Sort for Migration Order

Kahn's algorithm automatically computes table creation order from FK dependency graph.

```python
def _topological_sort(entities: dict[str, type[Entity]]) -> list[type[Entity]]:
    # Process zero in-degree nodes first
    # Self-referential FKs excluded from dependency calculation
```

**Implementation**: See `libs/canon/src/canon/db/migration/migration.py`

### D3: Four-Role Separation

| Role      | Owns Tables | Privileges                              | BYPASSRLS |
| --------- | ----------- | --------------------------------------- | --------- |
| owner     | YES         | DDL, runs migrations                    | NO        |
| app       | NO          | SELECT/INSERT/UPDATE/DELETE on public.* | NO        |
| support   | NO          | Same as app + break-glass via session   | NO        |
| analytics | NO          | SELECT only                             | NO        |

**Implementation**: See `libs/canon/src/canon/db/migration/roles.py`

### D4: Single Transaction for Atomic Migration

All DDL in one transaction - tables never exist without RLS protection.

```python
async with transaction(dsn, tenant_scope=TenantScope.DISABLED) as conn:
    # Phase 1-10: roles, tables, ownership, triggers, indexes,
    # constraints, tenant_unique, composite_fks, rls, views
```

### D5: Composite FK Constraints

```sql
-- Ensure composite key exists on target
ALTER TABLE "public"."persons" ADD CONSTRAINT uq_persons_tenant_id
    UNIQUE (tenant_id, id);

-- Composite FK enforces same-tenant references
ALTER TABLE "public"."evidence"
ADD CONSTRAINT fk_evidence_subject_id_tenant
FOREIGN KEY (tenant_id, "subject_id")
REFERENCES "public"."persons"(tenant_id, id);
```

## Vocabulary Mapping

This ADR is **infrastructure** - RLS enables tenant isolation for all phrase execution.

| Concept                        | Implementation                      | Purpose                        |
| ------------------------------ | ----------------------------------- | ------------------------------ |
| `app.tenant_id()`              | `canon.db.migration.rls`       | Fail-closed tenant context     |
| `TenantScope`                  | `canon.db.connection`          | Transaction context management |
| `migrate_with_rls_and_roles()` | `canon.db.migration.migration` | 10-phase atomic migration      |

## Alternatives Considered

### Alternative 1: Application-Level Only

**Why Rejected**: Vulnerable to bugs, injection, code path oversights. Compliance requires
defense-in-depth.

### Alternative 2: Single Role

**Why Rejected**: No privilege separation. Owner always bypasses RLS.

### Alternative 3: Phased Migration

**Why Rejected**: Tables unprotected between phases. Single transaction ensures all-or-nothing.

## Consequences

### Positive

- Application bugs cannot leak cross-tenant data
- SQL injection attacks limited to current tenant
- Credential compromise (app role) limits blast radius
- Cross-tenant FK violations impossible at database level

### Negative

- Owner role requires tenant context for administrative queries
- Migrations must run with TenantScope.DISABLED (superuser context)
- Migration requires downtime window (no online schema changes yet)

## References

- **TDS**: `/docs-shared/canonsys/01_design/005-rls-migration/TDS-005-rls-migration.md`
- **Implementation**: `libs/canon/src/canon/db/migration/`
- **Related ADRs**: ADR-001-tenant-isolation, ADR-004-entity-db-correspondence
