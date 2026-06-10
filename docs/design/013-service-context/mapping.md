# 013-Service-Context - Code Mapping

## Overview

The Service Context system provides **two-tier context management** for all CanonSys services.
RequestContext is the carrier for phrase execution - all vocabulary phrases receive it.

## Vocabulary Packages

| Package | Path                                          | Purpose                                  |
| ------- | --------------------------------------------- | ---------------------------------------- |
| `core`  | `hub/foundation/packages/core/` | Core infrastructure and audit primitives |

## Infrastructure Components

### ServiceContext

```python
@dataclass
class ServiceContext:
    tenant_id: UUID
    charter: Charter | None = None
    jurisdiction: str | None = None
    service_name: str | None = None
```

Location: `libs/canon/src/canon/enforcement/types.py`

### RequestContext

```python
@dataclass
class RequestContext:
    # Identity
    tenant_id: ID[Tenant]
    actor_id: ID[User] | None = None
    subject_id: ID[Person] | None = None

    # Tracing
    correlation_id: UUID | None = None
    causation_id: UUID | None = None

    # Policy State
    charter: Charter | None = None
    policy_version: str | None = None

    # Results
    gate_results: list[dict[str, Any]]

    # DB
    conn: Any | None = None
```

Location: `libs/canon/src/canon/enforcement/types.py`

## Key Methods

| Method                    | Purpose                                   |
| ------------------------- | ----------------------------------------- |
| `add_gate_result(result)` | Accumulate gate evaluations               |
| `with_causation(id)`      | Create child context with causation link  |
| `to_evidence_data()`      | Serialize for evidence (active assertion) |

## Phrase Integration

All vocabulary phrases receive RequestContext:

```python
@canon_phrase(...)
async def some_phrase(
    options: dict,
    ctx: RequestContext,  # Always provided
) -> dict:
    # Access tenant, conn, policy state
    ...
```

## Architectural Patterns

### 1. Two-Context Pattern

- **ServiceContext** (service init) - determines which situational gates activate
- **RequestContext** (per request) - carries actor/subject/action state

### 2. Active Assertion Pattern

`RequestContext.to_evidence_data()` captures policy/gate state at execution time. Evidence includes
which gates passed, which charter version was active, which jurisdiction rules applied.

### 3. Immutable Transforms

Context updates create copies, not mutations:

```python
child_ctx = ctx.with_causation(parent_id)  # Returns new context
```

### 4. Jurisdiction Tuple Ordering

`jurisdictions: tuple[str, ...]` ordered NYC -> NY -> FEDERAL. Order matters for policy evaluation -
most specific first.

## Dependencies

**Depends on:**

- `canon.entities.charter.Charter` - For situational gate activation
- `kron.enforcement` - RequestContext base patterns
- `kron.services` - ServiceBackend integration

**Depended by:**

- All vocabulary phrases (receive RequestContext)
- `ADR-012-single-enforcement` - CanonService request flow
- `ADR-008-policy-gates` - Gate evaluation

## Key Decisions

### D1: Separation of ServiceContext and RequestContext

ServiceContext resolved once at service init (tenant/charter). RequestContext created per request
(identity/tracing). Allows caching tenant config while maintaining request isolation.

### D2: Gate results accumulated on RequestContext

Full audit trail of all gates evaluated for evidence. Even passed gates are recorded.

### D3: Charter replaces Constitution

Charter provides richer policy activation with `policy_ids` for situational gates and `version` for
audit trails.
