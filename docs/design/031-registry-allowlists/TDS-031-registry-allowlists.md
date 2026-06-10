---
doc_type: TDS
title: "Technical Design Specification: Config-Driven Registry Allowlists"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: tds
phase: design
scope: L3

predecessors:
  - "ADR-031-registry-allowlists"
successors: []
supersedes: null
superseded_by: null

tags:
  - anti-gaming
  - registry
  - allowlists
  - authorization
  - deployment
related:
  - "ADR-031-registry-allowlists"
  - "ADR-008-policy-gates"
  - "TDS-029-caching-mechanism"
pr: null

quality:
  confidence: 0.85
  sources: 4
  docs: full
---

# Technical Design Specification: Config-Driven Registry Allowlists

## 1. Overview

### 1.1 Purpose

This TDS specifies the registry allowlist pattern that enables CanonSys to validate entities (roles,
destinations, tools, policies) against approved lists before permitting operations. The pattern
provides a unified abstraction for all "is X in the approved list?" checks.

### 1.2 Scope

**In Scope**:

- Registry base class with CRUD operations
- AllowlistEntry entity with tenant isolation
- verify_in_allowlist() vocabulary feature
- Gate integration for enforcement
- Cache integration for performance
- Audit trail via evidence emission

**Out of Scope**:

- Specific registry implementations (covered per-feature)
- Policy engine integration (see ADR-009)
- Complex rule evaluation (simple membership check only)

### 1.3 Background

**Research References**:

- ADR-031: Architecture decision for registry pattern
- ADR-008: Gate system integration
- ADR-029: Cache integration

### 1.4 Design Goals

| Priority | Goal                      | Rationale                   |
| -------- | ------------------------- | --------------------------- |
| P0       | Unified allowlist pattern | Consistency across surfaces |
| P0       | Anti-gaming defense       | Prevent unauthorized bypass |
| P1       | Complete audit trail      | Every mutation traceable    |
| P1       | Cache integration         | Hot-path performance        |
| P2       | Tenant isolation          | Multi-tenant security       |

### 1.5 Key Constraints

**Technical Constraints**:

- Must extend Entity base class patterns
- Cache invalidation required on mutations
- Evidence emission mandatory on add/remove

**Business Constraints**:

- Registry entries are immutable (add/remove, not update)
- Tenant isolation by default

**Security Constraints**:

- No bypass path for allowlist checks
- Audit trail for all mutations

---

## 2. Architecture

### 2.1 Component Diagram

```
                 +--------------------------+
                 |      CanonService        |
                 |  (gates decorator)       |
                 +-----------+--------------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
+-----------------+  +-----------------+  +-----------------+
| AllowlistGate   |  | Registry        |  | AllowlistEntry  |
|                 |  |                 |  |                 |
| - registry_type |  | - get()         |  | - id            |
| - check()       |  | - add()         |  | - entry_id      |
|                 |  | - remove()      |  | - registry_type |
+-----------------+  | - validate()    |  | - scope         |
                     +-----------------+  | - status        |
                             |            | - metadata      |
                             v            +-----------------+
                     +-----------------+
                     | DecisionCache   |
                     | (from ADR-029)  |
                     +-----------------+
```

### 2.2 Dependencies

**Internal Dependencies**:

| Component     | Purpose          | Location                 |
| ------------- | ---------------- | ------------------------ |
| Entity        | Base class       | `canon.core`        |
| Gate          | Gate abstraction | `canon.enforcement` |
| DecisionCache | Caching          | `canon.utils`       |
| Evidence      | Audit trail      | `canon.evidence`    |

**External Dependencies**:

| Library  | Purpose           | Version  |
| -------- | ----------------- | -------- |
| asyncpg  | PostgreSQL driver | >=0.28.0 |
| pydantic | Validation        | >=2.0.0  |

---

## 3. Interface Definitions

### 3.1 RegistryType and AllowlistEntry

```python
class RegistryType(StrEnum):
    """Registry type identifiers."""
    ROLE = "role"
    DESTINATION = "destination"
    TOOL = "tool"
    POLICY = "policy"
    VENDOR = "vendor"
    JURISDICTION = "jurisdiction"


class RegistryScope(StrEnum):
    """Visibility scope for registry entries."""
    GLOBAL = "global"
    TENANT = "tenant"
    ORGANIZATION = "organization"


class EntryStatus(StrEnum):
    """Entry lifecycle status."""
    ACTIVE = "active"
    REMOVED = "removed"


@dataclass(frozen=True)
class AllowlistEntry:
    """An entry in a registry allowlist."""
    id: UUID
    registry_type: RegistryType
    entry_id: str
    scope: RegistryScope
    tenant_id: UUID | None
    organization_id: UUID | None
    status: EntryStatus
    metadata: dict[str, Any]
    created_at: datetime
    created_by: UUID
    removed_at: datetime | None
    removed_by: UUID | None

    @property
    def is_active(self) -> bool:
        return self.status == EntryStatus.ACTIVE
```

### 3.2 Vocabulary Features

```python
async def verify_in_allowlist(
    registry_type: RegistryType | str,
    entry_id: str,
    ctx: RequestContext,
    *,
    require_active: bool = True,
    conn: Any | None = None,
) -> AllowlistResult:
    """Verify an entry exists in the specified registry.

    Returns:
        AllowlistResult with is_allowed status and entry details
    """


async def add_to_registry(
    registry_type: RegistryType | str,
    entry_id: str,
    ctx: RequestContext,
    *,
    metadata: dict[str, Any] | None = None,
    scope: RegistryScope = RegistryScope.TENANT,
    conn: Any | None = None,
) -> AllowlistEntry:
    """Add a new entry to a registry.

    Emits 'registry.entry_added' evidence.
    """


async def remove_from_registry(
    registry_type: RegistryType | str,
    entry_id: str,
    ctx: RequestContext,
    *,
    reason: str | None = None,
    conn: Any | None = None,
) -> AllowlistEntry:
    """Remove an entry from a registry (soft delete).

    Emits 'registry.entry_removed' evidence.
    """
```

---

## 4. Data Models

### 4.1 Database Schema

```sql
CREATE TABLE allowlist_entry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    registry_type VARCHAR(50) NOT NULL,
    entry_id VARCHAR(255) NOT NULL,
    scope VARCHAR(20) NOT NULL DEFAULT 'tenant',
    tenant_id UUID REFERENCES tenant(id),
    organization_id UUID REFERENCES organization(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID NOT NULL REFERENCES "user"(id),
    removed_at TIMESTAMPTZ,
    removed_by UUID REFERENCES "user"(id),

    CONSTRAINT chk_scope_tenant CHECK (
        (scope = 'global' AND tenant_id IS NULL) OR
        (scope = 'tenant' AND tenant_id IS NOT NULL) OR
        (scope = 'organization' AND tenant_id IS NOT NULL AND organization_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX ix_allowlist_entry_unique_active
ON allowlist_entry (registry_type, entry_id, tenant_id)
WHERE status = 'active';
```

---

## 5. Behavior

### 5.1 Validation Flow

```
Request -> verify_in_allowlist() -> Cache Hit? --Yes--> Return Cached Result
                    |
                    +--No--> Query Registry -> Cache Result -> Return
```

### 5.2 Cache Integration

- **Cache Key**: `registry:{type}:{entry_id}:{tenant_id}`
- **TTL**: 300s (configurable)
- **Invalidation**: On add/remove operations

---

## 6. Vocabulary Mapping

### Package: `deployment`

**Location**: `hub/domains/corporate/packages/deployment/`

| Phrase                           | File                                        | Purpose                    |
| -------------------------------- | ------------------------------------------- | -------------------------- |
| `require_deployment_approval`    | `phrases/require_deployment_approval.py`    | Verify deployment approved |
| `verify_backup_complete`         | `phrases/verify_backup_complete.py`         | Verify backup done         |
| `require_backup_verified`        | `phrases/require_backup_verified.py`        | Ensure backup verified     |
| `require_production_environment` | `phrases/require_production_environment.py` | Verify production env      |
| `verify_rollback_plan_present`   | `phrases/verify_rollback_plan_present.py`   | Ensure rollback plan       |

### Control Surface Coverage

| Surface             | Phrases Used                                                  | Status      |
| ------------------- | ------------------------------------------------------------- | ----------- |
| Deployment Approval | `require_deployment_approval`, `verify_rollback_plan_present` | Implemented |
| Backup Verification | `verify_backup_complete`, `require_backup_verified`           | Implemented |

---

## 7. Testing Strategy

### 7.1 Test Coverage Requirements

| Component           | Coverage Target | Test File                                 |
| ------------------- | --------------- | ----------------------------------------- |
| Registry base       | 95%+            | tests/features/registry/test_base.py      |
| verify_in_allowlist | 100%            | tests/features/registry/test_verify.py    |
| AllowlistGate       | 100%            | tests/features/registry/test_gates.py     |
| Cache integration   | 90%+            | tests/features/registry/test_cache.py     |
| Tenant isolation    | 100%            | tests/features/registry/test_isolation.py |

---

## 8. Open Questions

| # | Question                       | Impact            | Proposed Resolution   | Status   |
| - | ------------------------------ | ----------------- | --------------------- | -------- |
| 1 | Pattern matching support       | Entry flexibility | Phase 2 enhancement   | Open     |
| 2 | Registry entry versioning      | History tracking  | Supersession pattern  | Resolved |
| 3 | Organization scope inheritance | Multi-org tenants | Additive, no override | Resolved |

---

## 9. References

- ADR: `docs-shared/canonsys/01_design/031-registry-allowlists/ADR-031-registry-allowlists.md`
- Gate system: ADR-008
- Cache integration: ADR-029
- Deployment package: `hub/domains/corporate/packages/deployment/`
