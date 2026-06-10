---
doc_type: TDS
title: "Technical Design Specification: Service Context"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core"]
charters: []
---

# Technical Design Specification: Service Context

## 1. Overview

### 1.1 Purpose

The Service Context system provides **two-tier context management** for CanonSys services:

1. **ServiceContext** - Service-level configuration resolved at service initialization
2. **RequestContext** - Per-request state carrying identity, tracing, and policy state

This separation enables service instances bound to tenants and charters, with request-level tracking
and evidence as **active assertion**.

### 1.2 Design Principles

1. **Two-Tier Separation**: Service-level config vs. per-request state
2. **Active Assertion**: Evidence captures policy/gate state at execution time
3. **Fail-Closed**: Missing context fields prevent operations
4. **Immutable Flow**: Context transforms create new instances

## 2. Architecture

### 2.1 Context Flow

```
Service Initialization          Per-Request Flow
        |                              |
   ServiceContext                RequestContext
        |                              |
   +-- tenant_id              +-- tenant_id
   +-- charter                +-- actor_id, subject_id
   +-- service_name           +-- correlation_id, causation_id
        |                      +-- jurisdictions
        v                      +-- policy_version
   CanonService                +-- gate_results
        |                              |
        +--- request(payload, ctx) ----+
                    |
             to_evidence_data()
                    |
                Evidence
```

### 2.2 Module Structure

| Module                   | Purpose                                     |
| ------------------------ | ------------------------------------------- |
| `enforcement/types.py`   | ServiceContext, RequestContext dataclasses  |
| `enforcement/service.py` | CanonService with dispatch, gates, evidence |

## 3. ServiceContext

Service-level context resolved at service initialization:

```python
@dataclass
class ServiceContext:
    tenant_id: UUID
    charter: Charter | None = None
    jurisdiction: str | None = None
    service_name: str | None = None
```

**Purpose**: Determines which situational gates activate based on tenant charter.

## 4. RequestContext

Per-request context that flows through CanonSys:

```python
@dataclass
class RequestContext:
    # Identity (using typed IDs)
    tenant_id: ID[Tenant]
    actor_id: ID[User] | None = None
    subject_id: ID[Person] | None = None
    organization_id: ID[Organization] | None = None

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

    # Extension
    metadata: dict[str, Any] = field(default_factory=dict)

    # DB connection
    conn: Any | None = None
```

### 4.1 Context Methods

```python
def add_gate_result(self, result: dict[str, Any]) -> None:
    """Add a gate result to the context."""
    self.gate_results.append(result)

def with_causation(self, causation_id: UUID) -> RequestContext:
    """Create child context with causation link."""
    import copy
    new_ctx = copy.copy(self)
    new_ctx.causation_id = causation_id
    return new_ctx

def to_evidence_data(self) -> dict[str, Any]:
    """Serialize for evidence storage (active assertion)."""
    return {
        "tenant_id": str(self.tenant_id),
        "actor_id": str(self.actor_id) if self.actor_id else None,
        "correlation_id": str(self.correlation_id) if self.correlation_id else None,
        "policy_version": self.policy_version,
        "gate_results": self.gate_results,
        # ... full serialization
    }
```

## 5. Active Assertion Pattern

### 5.1 Concept

When evidence is created with `RequestContext.to_evidence_data()`, it becomes an **active
assertion**:

> "This data was recorded at this time, AND I attest that:
>
> - Gates X, Y, Z passed
> - Policy version 2026.01 was active
> - Jurisdiction US-NYC rules applied"

### 5.2 Evidence Data Structure

```python
evidence = Evidence(
    tenant_id=ctx.tenant_id,
    evidence_type="consent.grant",
    data={
        "action": "grant",
        "success": True,
        # Active assertion
        "context": ctx.to_evidence_data(),
    },
)
```

## 6. Phrase Execution Context

All vocabulary phrases receive RequestContext:

```python
@canon_phrase(...)
async def resolve_charter(
    options: dict,
    ctx: RequestContext,
) -> dict:
    # ctx provides tenant_id, conn, and policy state
    rows = await select(
        "charters",
        where={"tenant_id": ctx.tenant_id},
        conn=ctx.conn,
    )
```

See: `hub/foundation/packages/core/phrases/`

## 7. ServiceContext vs RequestContext

| Aspect       | ServiceContext       | RequestContext        |
| ------------ | -------------------- | --------------------- |
| Lifecycle    | Service init         | Per-request           |
| Tenant       | Bound at init        | Carried in request    |
| Charter      | Activates gates      | Active for request    |
| Gates        | Determines which run | Accumulates results   |
| Policy State | N/A                  | Version, library hash |
| Evidence     | N/A                  | `to_evidence_data()`  |

## 8. Integration Points

| Component            | Purpose               |
| -------------------- | --------------------- |
| `Charter`            | Policy activation     |
| `enforcement.gate`   | Gate evaluation       |
| `kron.services`      | ServiceBackend, hooks |
| `utils.opa.engine`   | OPA policy engine     |

## 9. References

- **Core phrases**: `hub/foundation/packages/core/phrases/`
- **Types**: `libs/canon/src/canon/enforcement/types.py`
- **Related**: ADR-012-single-enforcement
