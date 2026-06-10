---
doc_type: ADR
title: "ADR-031: Config-Driven Registry Allowlists for Anti-Gaming Patterns"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
decision_date: "2026-01-20"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-008-policy-gates"
  - "ADR-029-caching-mechanism"
successors:
  - "TDS-031-registry-allowlists"
supersedes: null
superseded_by: null

tags:
  - anti-gaming
  - registry
  - allowlists
  - authorization
  - deployment
related:
  - "TDS-031-registry-allowlists"
  - "ADR-008-policy-gates"
  - "ADR-015-jit-role"
  - "ADR-029-caching-mechanism"
pr: null

quality:
  confidence: 0.85
  sources: 4
  docs: full
---

# ADR-031: Config-Driven Registry Allowlists for Anti-Gaming Patterns

## Context

### Problem Statement

Many compliance surfaces require checking whether an entity (role, destination, tool, policy) is in
an approved list before proceeding. Without a centralized pattern:

- Each surface implements its own allowlist logic
- Inconsistent validation semantics across features
- No audit trail for registry changes
- Gaming vectors through unapproved roles/destinations/tools

**Why This Matters**: "Check if X is in the allowed list" repeated ad-hoc across 20+ surfaces
creates maintenance burden and compliance gaps. A user could bypass controls by finding an unguarded
path.

### Background

**Current State**: Role checks scattered across services, destination validation implemented
per-integration, tool allowlists hardcoded or in environment variables. No unified pattern for
registry-based authorization.

**Driving Forces**:

- **Anti-Gaming**: Prevent unauthorized entities from bypassing compliance checks
- **Audit Trail**: Track who added/removed entries and when
- **Tenant Isolation**: Allowlists are tenant-scoped by default
- **Consistency**: Single pattern for all "is X in approved list" checks

### Assumptions

1. Registries are tenant-scoped unless explicitly marked global
2. Registry entries are immutable (add/remove, not update)
3. Each registry has a defined scope (what it controls)
4. Registry changes require audit evidence

### Constraints

| Type         | Constraint                                | Impact                      |
| ------------ | ----------------------------------------- | --------------------------- |
| Isolation    | Tenant A cannot see Tenant B's registries | tenant_id in every query    |
| Immutability | Entries are append-only with soft deletes | Full history preserved      |
| Performance  | Allowlist checks are hot-path operations  | In-memory caching required  |
| Audit        | Every change must produce evidence        | Evidence hooks on mutations |

---

## Decision

### Summary

**We will** implement a centralized registry pattern with config-driven allowlists, providing a base
`Registry` class that all specific registries extend, with `verify_in_allowlist()` as the standard
gate operation.

### Rationale

**Key factors in the decision**:

1. **Single Abstract Pattern**: One `Registry` base class handles get/set/validate/audit operations.
   Specific registries (RoleRegistry, DestinationAllowlist) only define schema.

2. **Config-Driven Entries**: Allowlist entries are configuration, not code. Tenants can customize
   within bounds defined by the registry schema.

3. **Gate Integration**: `verify_in_allowlist(registry_type, entry_id, ctx)` is a vocabulary feature
   that gates check. This integrates with the existing gate system (ADR-008).

4. **Evidence on Mutation**: Adding/removing entries emits evidence, providing audit trail for "why
   was X in the allowlist?"

5. **Scoped Registries**: Some registries are global (system tools), others tenant-scoped (custom
   roles). The pattern handles both with explicit scope markers.

### Implementation Approach

The registry system has four components:

```
+-------------------------------------------------------------------------+
|                       Registry Architecture                              |
+-------------------------------------------------------------------------+
|  Component 1: Registry Base Class                                        |
|    - Abstract base with get/set/validate/remove operations               |
|    - Auto-registration via __init_subclass__ (like Gate pattern)         |
|    - Scope enum: GLOBAL | TENANT | ORGANIZATION                          |
|    - Entry schema defined per registry subclass                          |
+-------------------------------------------------------------------------+
|  Component 2: AllowlistEntry Entity                                      |
|    - entry_id: Unique identifier within registry                         |
|    - registry_type: Which registry this belongs to                       |
|    - scope: GLOBAL | TENANT | ORGANIZATION                               |
|    - tenant_id: Owning tenant (null for global)                          |
|    - status: ACTIVE | REMOVED                                            |
|    - metadata: Registry-specific attributes                              |
+-------------------------------------------------------------------------+
|  Component 3: verify_in_allowlist() Feature                              |
|    - Vocabulary feature for gate integration                             |
|    - Returns AllowlistResult with entry details or rejection reason      |
|    - Cacheable (integrates with ADR-029 caching)                         |
+-------------------------------------------------------------------------+
|  Component 4: Audit Trail                                                |
|    - Evidence emitted on entry_added, entry_removed events               |
|    - Links to actor who made the change                                  |
|    - Immutable history via standard evidence chain                       |
+-------------------------------------------------------------------------+
```

**Registry Types**:

| Registry              | Scope  | Purpose                             | Example Entries             |
| --------------------- | ------ | ----------------------------------- | --------------------------- |
| role_registry         | TENANT | Approved roles for JIT assignment   | hiring_manager, hr_admin    |
| destination_allowlist | TENANT | Approved alert/webhook destinations | slack://..., email://...    |
| tool_registry         | GLOBAL | Approved AEDT/AI tools              | checkr_v3.2, hirelogic_2024 |
| policy_registry       | TENANT | Approved policy bundles             | fcra_2024, nyc_ll144_v2     |
| vendor_registry       | GLOBAL | Approved third-party vendors        | checkr, sterling, hireright |

### Alternatives Considered

#### Alternative 1: Per-Feature Allowlists (Status Quo)

**Description**: Each feature implements its own allowlist logic.

| Criterion       | Score (1-5) | Notes                               |
| --------------- | ----------- | ----------------------------------- |
| Consistency     | 1           | Each implementation differs         |
| Maintainability | 2           | Changes require updating many files |
| Audit           | 2           | No unified audit pattern            |
| Performance     | 3           | Can optimize per-feature            |

**Why Not Chosen**: Creates maintenance burden and audit gaps.

#### Alternative 2: OPA Policy for Allowlists

**Description**: Use OPA policies to define allowlists.

| Criterion       | Score (1-5) | Notes                        |
| --------------- | ----------- | ---------------------------- |
| Consistency     | 4           | OPA provides unified pattern |
| Maintainability | 3           | Policy bundles need updates  |
| Audit           | 3           | OPA logs decisions           |
| Performance     | 2           | OPA evaluation overhead      |

**Why Not Chosen**: OPA is for complex policy logic. Allowlists are simple membership checks that
don't need Rego expressiveness.

#### Alternative 3: Database Table per Allowlist

**Description**: Create separate tables for each allowlist type.

| Criterion       | Score (1-5) | Notes                    |
| --------------- | ----------- | ------------------------ |
| Consistency     | 2           | Schema differs per table |
| Maintainability | 2           | Many tables to manage    |
| Audit           | 3           | DB triggers for history  |
| Performance     | 4           | Indexed lookups          |

**Why Not Chosen**: Schema proliferation. Unified registry table with type discriminator is simpler.

### Decision Matrix

| Criterion          | Weight | Per-Feature | OPA      | Separate Tables | Registry Pattern |
| ------------------ | ------ | ----------- | -------- | --------------- | ---------------- |
| Consistency        | 30%    | 1           | 4        | 2               | 5                |
| Maintainability    | 25%    | 2           | 3        | 2               | 5                |
| Audit              | 25%    | 2           | 3        | 3               | 5                |
| Performance        | 20%    | 3           | 2        | 4               | 4                |
| **Weighted Total** | 100%   | **1.90**    | **3.15** | **2.55**        | **4.80**         |

---

## Consequences

### Positive Consequences

1. **Unified Pattern**: All allowlist checks use the same abstraction. New registries require only
   type definition, not new code.

2. **Anti-Gaming Defense**: Centralized validation prevents bypass. If it's not in the registry,
   it's not allowed.

3. **Complete Audit Trail**: Every registry mutation emits evidence. "Who approved this role?" is
   always answerable.

4. **Cacheable**: Registry lookups integrate with decision-scope caching (ADR-029) for hot-path
   performance.

5. **Tenant Isolation**: Registry entries are tenant-scoped by default, preventing cross-tenant
   leakage.

### Negative Consequences

1. **Indirection Layer**: Adding an entry requires understanding the registry abstraction, not just
   inserting a row. Mitigation: Clear documentation and service wrappers.

2. **Migration Effort**: Existing hardcoded allowlists must be migrated to registry entries.
   Mitigation: Incremental migration with compatibility layer.

3. **Cache Invalidation**: Registry changes must invalidate cached entries to prevent stale
   approvals. Mitigation: Short TTL and explicit invalidation on mutations.

### Neutral Consequences

1. **Vocabulary Growth**: Adds `verify_in_allowlist()` to vocabulary layer (consistent with
   pattern).

### Risks

| Risk                                   | Likelihood | Impact | Mitigation                            |
| -------------------------------------- | ---------- | ------ | ------------------------------------- |
| Orphaned entries after tenant deletion | L          | M      | Cascade delete on tenant removal      |
| Cache stale after registry update      | M          | H      | Invalidate on mutation, short TTL     |
| Registry type explosion                | L          | L      | Review process for new registry types |
| Performance regression on uncached     | M          | M      | Warm cache on service startup         |

### Dependencies Introduced

| Dependency | Type | Version | Stability | Notes                                      |
| ---------- | ---- | ------- | --------- | ------------------------------------------ |
| (none)     | -    | -       | -         | Built on existing Entity/Evidence patterns |

### Migration Impact

**Backwards Compatibility**: Additive. Existing checks continue working while registry pattern is
adopted incrementally.

**Migration Steps**:

1. Implement Registry base class and AllowlistEntry entity
2. Create registry types for highest-priority surfaces (Deployment Approval, Backup Verification)
3. Migrate existing hardcoded allowlists to registry entries
4. Update gates to use `verify_in_allowlist()` feature
5. Deprecate and remove old allowlist implementations

**Rollback Plan**:

1. Feature flag `CANON_REGISTRY_ENABLED=false`
2. Fall back to legacy allowlist checks
3. No data loss (registry entries preserved)

---

## Verification

### Success Criteria

- [ ] Registry base class with get/set/validate/remove operations
- [ ] AllowlistEntry entity with tenant isolation
- [ ] verify_in_allowlist() vocabulary feature
- [ ] Evidence emission on entry_added, entry_removed
- [ ] Cache integration for hot-path performance
- [ ] At least 3 registry types implemented (role, destination, tool)

### Metrics to Track

| Metric                          | Baseline | Target | Review Date |
| ------------------------------- | -------- | ------ | ----------- |
| Registry lookup latency p99     | N/A      | < 5ms  | 2026-02-20  |
| Cache hit rate                  | N/A      | > 80%  | 2026-02-20  |
| Surfaces using registry pattern | 0        | 10+    | 2026-03-20  |
| Audit evidence completeness     | N/A      | 100%   | 2026-02-20  |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Platform Team

---

## Vocabulary Mapping

### Package: `deployment`

**Location**: `hub/domains/corporate/packages/deployment/`

| Phrase                           | Purpose                       | Surfaces                  |
| -------------------------------- | ----------------------------- | ------------------------- |
| `require_deployment_approval`    | Verify deployment is approved | Deployment Approval       |
| `verify_backup_complete`         | Verify backup completed       | Backup Verification       |
| `require_backup_verified`        | Ensure backup verification    | Backup Verification       |
| `require_production_environment` | Verify production context     | Deployment Approval       |
| `verify_rollback_plan_present`   | Ensure rollback plan exists   | Deployment Approval       |

### Package: `infra`

**Location**: `hub/domains/corporate/packages/infra/`

| Phrase                   | Purpose                           | Surfaces            |
| ------------------------ | --------------------------------- | ------------------- |
| `verify_traffic_drained` | Verify traffic drained before ops | Backup Verification |

### Control Surface Coverage

| Surface             | Description         | Registry Type       | Gate Integration       |
| ------------------- | ------------------- | ------------------- | ---------------------- |
| Deployment Approval | Deployment approval | deployment_registry | DeploymentApprovalGate |
| Backup Verification | Backup verification | backup_registry     | BackupVerificationGate |

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate system that registry checks integrate with
- `ADR-015-jit-role`: Role registry enables JIT role assignment validation
- `ADR-029-caching-mechanism`: Registry lookups use decision-scope caching

### Impacts

- `TDS-031-registry-allowlists`: Technical specification implementing this decision
- Infrastructure attack surface coverage (Deployment Approval, Backup Verification)

---

## References

- TDS: `docs-shared/canonsys/01_design/031-registry-allowlists/TDS-031-registry-allowlists.md`
- Gate system: `docs-shared/canonsys/01_design/008-policy-gates/ADR-008-policy-gates.md`
- Deployment package: `hub/domains/corporate/packages/deployment/`
- SOC 2 CC7.1-8.1: Deployment and change management controls

---

## Validation Checklist

### Nygard Format Compliance

- [x] Context explains forces at play
- [x] Decision is clearly stated
- [x] Consequences cover positive, negative, and neutral outcomes

### Completeness

- [x] Problem clearly stated
- [x] Background and constraints documented
- [x] At least 2 alternatives considered
- [x] Decision matrix completed
- [x] Risks identified with mitigations

### Quality

- [x] Rationale is convincing
- [x] Trade-offs are honest
- [x] Success criteria are measurable
- [x] Review schedule defined

### Traceability

- [x] Related artifacts linked
- [x] Vocabulary mapping provided
- [x] References provided
