---
doc_type: ADR
title: "ADR-013: Service Context and RequestContext"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["core"]
charters: []
---

# ADR-013: Service Context and RequestContext

## Status

Accepted

## Context

CanonSys services require consistent context propagation for:

1. **Identity**: Who is performing the action (tenant, actor, subject)
2. **Traceability**: Correlation and causation IDs for audit trails
3. **Policy State**: Which policy version and gates were active
4. **Evidence**: Capturing context as "active assertion" for compliance proof

Without a canonical context definition, services would define inconsistent context fields, lack
uniform traceability, and fail to capture policy state in evidence.

### Decision Drivers

- Canonical definition: one authoritative context structure
- Two-tier separation: service-level config vs per-request state
- Explicit propagation: context via function parameters, not global state
- Evidence serialization: context must serialize for evidence
- Immutable transforms: updates create new instances

## Decision

### D1: Two-Tier Context System

**ServiceContext** - Resolved at service initialization:

- Tenant binding
- Charter for situational gate activation
- Service metadata

**RequestContext** - Per-request state:

- Identity (tenant, actor, subject)
- Tracing (correlation, causation)
- Policy state (version, library hash)
- Accumulated gate results

### D2: Explicit Context Propagation

Context is passed explicitly via function parameters, not stored in global state:

```python
# CORRECT: Explicit parameter
async def verify_consent(subject_id: UUID, scope: ConsentScope, ctx: RequestContext):
    ...

# WRONG: Global/thread-local
async def verify_consent(subject_id: UUID, scope: ConsentScope):
    ctx = get_current_context()  # Anti-pattern
```

This ensures async safety, explicit dependencies, and testability.

### D3: Active Assertion Pattern

Evidence captures policy state at execution time via `to_evidence_data()`:

```python
def to_evidence_data(self) -> dict[str, Any]:
    return {
        "tenant_id": str(self.tenant_id),
        "actor_id": str(self.actor_id) if self.actor_id else None,
        "policy_version": self.policy_version,
        "gate_results": self.gate_results,
        # ... full serialization
    }
```

### D4: Immutable Transforms

Context updates create new instances:

```python
# CORRECT: Creates new context
child_ctx = ctx.with_causation(parent_operation_id)

# WRONG: Mutates original
ctx.causation_id = parent_operation_id
```

## Vocabulary Mapping

| Phrase                  | Package | Purpose                           |
| ----------------------- | ------- | --------------------------------- |
| `resolve_charter`       | `core`  | Resolve active charter for tenant |
| `verify_audit_complete` | `core`  | Verify audit trail is complete    |

**Note**: RequestContext is infrastructure, not a phrase. It is the carrier for phrase execution
context.

## RequestContext Structure

```python
@dataclass
class RequestContext:
    # Identity
    tenant_id: ID[Tenant]
    actor_id: ID[User] | None = None
    subject_id: ID[Person] | None = None

    # Tracing
    request_id: UUID | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None

    # Service & Action
    service_name: str | None = None
    action: str | None = None

    # Jurisdiction
    jurisdictions: tuple[str, ...] = ()

    # Policy State
    charter: Charter | None = None
    policy_version: str | None = None
    policy_library_hash: str | None = None

    # Accumulated Results
    gate_results: list[dict[str, Any]] = field(default_factory=list)

    # DB connection (request lifetime)
    conn: Any | None = None
```

## Consequences

### Positive

- Uniform traceability across all services
- Active assertion in evidence proves what was checked
- Async-safe: no global state or thread-locals
- Testable: easy to create test contexts
- Extensible: metadata dict for service-specific extensions

### Negative

- Boilerplate: every function needs `ctx: RequestContext` parameter
- Discipline required: developers must propagate context
- Large dataclass: 15+ fields

## References

- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Implementation**: `libs/canon/src/canon/enforcement/types.py`
- **Related ADRs**: ADR-012-single-enforcement
