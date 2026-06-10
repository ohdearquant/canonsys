---
doc_type: ADR
title: "ADR-010: Action Declaration Pattern"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["core"]
charters: []
---

# ADR-010: Action Declaration Pattern

## Status

Accepted

## Context

CanonService handlers need consistent metadata declaration for evidence type binding, emission
control, request options schema, and action-specific gates. Without a declarative pattern, these
concerns would be scattered in handler bodies, inconsistent across services, and invisible to
introspection.

### Decision Drivers

- Metadata declared at decoration time, not runtime
- Frozen after decoration (immutable configuration)
- Accessible via introspection for CanonService request flow
- Co-located with handler code (not in separate config files)

## Decision

### D1: Use @action Decorator for Handler Metadata

```python
@action(
    evidence_type="consent.grant",
    request_options=GrantOptions,
    hard_gates=["consent.valid_scope"],
    situational_gates=["consent.gdpr_basis"],
)
async def grant(self, payload: dict, ctx: RequestContext) -> dict:
    ...
```

**Implementation**: See `libs/canon/src/canon/enforcement/service.py` - specifically:

- `ActionMeta` - Frozen dataclass storing decorator metadata
- `get_action_meta()` - Accessor for handler metadata

### D2: Frozen Dataclass for Immutability

```python
@dataclass(frozen=True, slots=True)
class ActionMeta:
    evidence_type: str | None = None
    skip_evidence: bool = False
    request_options: type[BaseModel] | None = None
    hard_gates: tuple[str, ...] = ()
    situational_gates: tuple[str, ...] = ()
```

No runtime modification allowed.

### D3: Evidence Type Defaults

If `evidence_type` is None, CanonService uses `{service_name}.{action}`:

```python
# ConsentService.grant -> evidence_type = "consent.grant"
```

### D4: Skip Evidence for Hot Paths

```python
@action(skip_evidence=True)
async def verify(self, payload, ctx): ...
```

Verify and health endpoints should not emit evidence.

### D5: Gate Resolution Order

Gates execute in specific order:

1. Class hard gates (`@gates(hard=[...])`)
2. Class situational gates
3. Action hard gates (`@action(hard_gates=[...])`)
4. Action situational gates

**Charter Integration**: Situational gates only run if active in tenant's `charter.policy_ids`.

## Vocabulary Mapping

The @action decorator is infrastructure that vocabulary phrases use. Core package phrases implement
actions via this pattern:

| Phrase                      | Package | Purpose                          |
| --------------------------- | ------- | -------------------------------- |
| `invoke_break_glass`        | `core`  | Emergency access override action |
| `invoke_executive_override` | `core`  | Executive override action        |
| `activate_charter`          | `core`  | Activate charter action          |
| `ratify_charter`            | `core`  | Ratify charter action            |
| `resolve_charter`           | `core`  | Resolve active charter           |
| `verify_audit_complete`     | `core`  | Verify audit completion          |

## Control Surface Integration

Every control surface's Service Actions section maps to CanonService methods with `@action`
decorators:

| Surface Action       | Decorator Pattern                           | Phase         |
| -------------------- | ------------------------------------------- | ------------- |
| `CHECK_ELIGIBILITY`  | `@action(hard_gates=["eligibility.*"])`     | Phase 0       |
| `SUBMIT_FACTS`       | `@action(evidence_type="facts.submit")`     | Phase 1       |
| `BIND_EVIDENCE`      | `@action(hard_gates=["evidence.complete"])` | Phase 2       |
| `EVALUATE_POLICY`    | `@action(situational_gates=["policy.*"])`   | Phase 3       |
| `CERTIFY_DECISION`   | `@action(evidence_type="decision.certify")` | Phase 4       |
| `VERIFY_CERTIFICATE` | `@action(skip_evidence=True)`               | Post-decision |

## Alternatives Considered

### Alternative 1: Configuration Dictionary

Define action metadata in class-level dict:

```python
class ConsentService(CanonService):
    action_config = {
        "grant": {"evidence_type": "consent.grant"},
    }
```

Rejected: Disconnected from handler, no type safety, easy to desync.

### Alternative 2: Handler Docstring Parsing

Extract metadata from structured docstrings.

Rejected: Fragile format, no IDE support, string parsing overhead.

## Consequences

### Positive

- **Consistency**: All actions declare metadata the same way
- **Discoverability**: `get_action_meta(handler)` enables tooling
- **Audit by Default**: Evidence emission automatic unless skipped
- **Type Safety**: Pydantic coercion catches invalid payloads
- **Separation of Concerns**: Metadata separate from business logic

### Negative

- **Learning Curve**: Developers must understand decorator parameters
- **Inheritance Unclear**: How ActionMeta interacts with subclasses undefined
- **Static Configuration**: Cannot change action metadata at runtime

## References

- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Implementation**: `libs/canon/src/canon/enforcement/service.py`
- **Related ADRs**: ADR-012-single-enforcement (CanonService.request() flow)
