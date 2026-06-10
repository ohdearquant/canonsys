# 001 - Tenant Isolation - Code Mapping

## Primary Code Paths

| File                                                  | Lines    | Description                                               |
| ----------------------------------------------------- | -------- | --------------------------------------------------------- |
| `/libs/canon/src/canon/entities/shared/tenant.py`      | L98-102  | Tenant Entity definition with FK[Organization]            |
| `/libs/canon/src/canon/db/connection.py`    | L42-69   | DbContext, TenantScope                                    |
| `/libs/canon/src/canon/db/connection.py`    | L86-98   | with_context() - context manager for tenant scope         |
| `/libs/canon/src/canon/db/connection.py`    | L138-185 | connection() with tenant context injection                |
| `/libs/canon/src/canon/db/migration/rls.py` | L14-16   | is_tenant_scoped() check for tenant_id field              |
| `/libs/canon/src/canon/db/migration/rls.py` | L19-62   | generate_tenant_function() - app.tenant_id() SQL function |
| `/libs/canon/src/canon/db/migration/rls.py` | L150-180 | generate_rls_policy() - RLS policy DDL                    |
| `/libs/canon/src/canon/db/migration/rls.py` | L98-147  | generate_composite_fks() - tenant-scoped FK constraints   |

## Key Classes/Functions

| Name                         | Location                   | Purpose                                              |
| ---------------------------- | -------------------------- | ---------------------------------------------------- |
| `Tenant`                     | `core/shared.py:L98`       | Root tenant entity - isolated workspace/account      |
| `TenantContent`              | `core/shared.py:L84`       | Tenant content model with name, slug, settings       |
| `DbContext`                  | `db/connection.py:L42`     | Dataclass holding tenant_id, actor_id, request_id    |
| `TenantScope`                | `db/connection.py:L59`     | Enum: REQUIRED, OPTIONAL, DISABLED                   |
| `with_context()`             | `db/connection.py:L86`     | Context manager for tenant scope                     |
| `connection()`               | `db/connection.py:L138`    | Async CM that injects tenant context into pg session |
| `is_tenant_scoped()`         | `db/migration/rls.py:L14`  | Checks if entity has tenant_id field                 |
| `generate_tenant_function()` | `db/migration/rls.py:L19`  | Generates app.tenant_id() SQL function               |
| `generate_rls_policy()`      | `db/migration/rls.py:L150` | Generates RLS policy for tenant isolation            |
| `generate_composite_fks()`   | `db/migration/rls.py:L98`  | Generates FK(tenant_id, fk_id) constraints           |

## Architectural Patterns

### 1. ContextVar-Based Tenant Propagation

```python
_db_context: ContextVar[DbContext | None] = ContextVar("db_context", default=None)
```

- Async-safe, task-local tenant context
- Set once at request entry, propagates through all DB operations
- `with_context()` provides RAII-style scoping

### 2. Session Variable Injection

```python
await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(ctx.tenant_id))
```

- Tenant ID injected into PostgreSQL session at connection acquire
- RLS policies read from `app.tenant_id` session variable
- Also injects `app.actor_id` and `app.request_id` for audit tracing
- `SET LOCAL row_security = on` forces RLS even for superuser

### 3. Fail-Closed Tenant Function

```sql
CREATE FUNCTION app.tenant_id() RETURNS uuid AS $$
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'tenant context not set'
```

- Function fails if context not set (never returns NULL)
- RLS policy uses `tenant_id = app.tenant_id()` - fails closed

### 4. Composite FK Enforcement

```sql
FOREIGN KEY (tenant_id, fk_field) REFERENCES target(tenant_id, id)
```

- Database-level enforcement of tenant boundaries
- Prevents cross-tenant FK references even if RLS bypassed

### 5. Tenant-Scoped Content Model

```python
class TenantAwareContent(ContentModel):
    tenant_id: FK[Tenant]
```

- Base content model for tenant-scoped entities
- Ensures tenant_id field is consistently defined
- Used by Person, User, Session, and other tenant-scoped entities

## Dependencies

- **Depends on**: None (foundational layer)
- **Depended by**:
  - 002-entity (Entity uses FK[Tenant] via TenantAwareContent)
  - 004-entity-db-correspondence (CRUD uses TenantScope)
  - 005-rls-migration (RLS depends on tenant context)
  - 006-evidence-chain-cep (Evidence has tenant_id)

## Key Decisions (for ADR candidates)

1. **ContextVar over thread-local**: Chose ContextVar for async-safe tenant propagation. Works
   correctly with asyncio tasks, unlike thread-local.

2. **Session variable over connection parameter**: Tenant context set via `set_config()` rather than
   connection pool partitioning. Allows single pool with dynamic tenant switching.

3. **FORCE ROW LEVEL SECURITY**: Applied to all tenant-scoped tables. Removes table owner bypass but
   NOT superuser bypass.

4. **Composite FK for cross-tenant protection**: `FOREIGN KEY (tenant_id, id)` enforced at DB level,
   not just application. Belt-and-suspenders approach.

5. **Fail-closed tenant function**: `app.tenant_id()` raises exception if not set, never returns
   NULL. Prevents silent bypass.

## Open Questions

1. **Break-glass access pattern**: How should support/admin access work when tenant context is
   needed but user spans tenants? RoleConfig suggests break-glass but mechanism not fully
   documented.

2. **Tenant hierarchy**: `Tenant.organization_id` suggests multi-level hierarchy but Organization
   entity relationship not fully explored.

3. **Analytics role RLS bypass**: analytics role has NOBYPASSRLS but how does it query aggregate
   data across tenants?
