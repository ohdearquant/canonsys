---
doc_type: ADR
title: "ADR-012: Single Enforcement Point via CanonService.request()"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core", "authorization"]
charters: []
---

# ADR-012: Single Enforcement Point via CanonService.request()

## Status

Accepted

## Context

CanonSys makes people decisions provable. Every business action must:

1. Pass compliance gates before execution
2. Emit evidence after execution
3. Handle errors uniformly (fail-closed)
4. Correlate to audit context (tenant, actor, subject, policy state)

Without a single enforcement point, these concerns would be scattered across services, creating risk
of bypassed compliance checks, missing evidence, and inconsistent error handling.

### Decision Drivers

- Uniform gate execution: all actions pass through compliance gates
- Automatic evidence emission: no developer code required
- Fail-closed error handling: any error blocks action
- Context propagation: RequestContext flows through entire lifecycle

## Decision

### D1: Single Entry Point via request()

All service operations flow through `CanonService.request()`. Direct handler calls are forbidden.

```
CanonService.request(payload, ctx)
    |
    +--- Phase 1: Normalize payload
    +--- Phase 2: Validate action
    +--- Phase 3: Sync context
    +--- Phase 4: Find handler
    +--- Phase 5: Coerce options
    +--- Phase 6: Execute gates (service + action level)
    +--- Phase 7: Execute handler + emit evidence
```

### D2: Declarative Gate Configuration

Gates declared via decorators, not imperative code:

```python
@gates(hard=["tenant.active", "user.authenticated"])
class ConsentService(CanonService):

    @action(hard_gates=["consent.data_processing"], evidence_type="consent.grant")
    async def grant(self, payload: dict, ctx: RequestContext) -> dict:
        # Gates already passed when we get here
        ...
```

**Implementation**: See vocabulary package `authorization`:

- `require_dual_approval` - Requires two distinct approvers
- `require_access_justification` - Requires documented justification
- `verify_approval_chain_complete` - Verifies approval chain

### D3: Fail-Closed Error Handling

All exceptions convert to `ResponseModel.fail()`:

- Gate blocked: action blocked with gate_id and results
- Gate not found (hard gates): action blocked
- Handler exception: logged and converted to error response

**Implementation**: See vocabulary package `core`:

- `invoke_break_glass` - Emergency override with audit trail

## Vocabulary Mapping

| Phrase                           | Package         | Purpose                                 |
| -------------------------------- | --------------- | --------------------------------------- |
| `invoke_break_glass`             | `core`          | Emergency override activation           |
| `require_dual_approval`          | `authorization` | Gate requiring two approvers            |
| `require_access_justification`   | `authorization` | Gate requiring documented reason        |
| `verify_approval_chain_complete` | `authorization` | Verify approval chain                   |
| `check_er_clearance`             | `authorization` | Check ER (Employee Relations) clearance |

## Alternatives Considered

### Alternative 1: Middleware Pattern

Use framework-level middleware for gate enforcement.

**Rejected**: Action-specific gates impossible, evidence correlation lost, framework coupling.

### Alternative 2: Decorator-Only Pattern

Each handler decorated with `@gate_check`, `@emit_evidence`, `@fail_closed`.

**Rejected**: Easy to forget decorators, ordering issues, evidence correlation problems.

## Consequences

### Positive

- Cannot bypass compliance: all paths go through `request()`
- Evidence by default: auto-emitted unless explicitly skipped
- Uniform error handling: all services return ResponseModel
- Complete audit trail: every action has evidence with gate results

### Negative

- CanonService inheritance required
- 7-phase flow has learning curve
- Sequential gate execution may add latency

## References

- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Vocabulary Package**: `hub/foundation/packages/authorization/`
- **Related ADRs**: ADR-008-policy-gates, ADR-013-service-context
