---
doc_type: TDS
title: "Technical Design Specification: Single Enforcement Point"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core", "authorization"]
charters: []
---

# Technical Design Specification: Single Enforcement Point

## 1. Overview

### 1.1 Purpose

`CanonService` with kron's invoke pattern is the **single enforcement point** for all service
operations in CanonSys. Every business action flows through the kron `iModel.invoke()` method,
ensuring uniform compliance gate execution, evidence emission, and fail-closed error handling via hooks.

### 1.2 Design Principles

1. **Single Entry Point**: All service operations go through `request()`
2. **Fail-Closed**: Any error blocks action (no silent failures)
3. **Evidence by Default**: Every action emits evidence unless explicitly skipped
4. **Gate Before Execute**: Gates always run before handler dispatch
5. **Uniform Interface**: All services share the same request/response contract

## 2. Architecture

### 2.1 Component Hierarchy

```
CanonService
    |
    +-- config: CanonServiceConfig (provider="canon", name="{service}")
    |
    +-- request(payload, ctx) -> ResponseModel
            |
            +-- Phase 1-5: Preparation
            +-- Phase 6: Gate execution
            +-- Phase 7: Handler dispatch + evidence
```

### 2.2 Module Structure

| Module                   | Purpose                                        |
| ------------------------ | ---------------------------------------------- |
| `enforcement/service.py` | CanonService class, @gates, @action decorators |
| `enforcement/types.py`   | RequestContext, ServiceContext                 |
| `enforcement/gate.py`    | Gate base class, create_gate, run_gates        |
| `enforcement/hooks.py`   | Kron hooks integration                         |

## 3. Seven-Phase Request Flow

### Phase 1: Normalize Payload

Accept dict or typed RequestModel. Coerce dict to model.

### Phase 2: Validate Action

Ensure action is specified before handler lookup.

### Phase 3: Sync Context

Ensure RequestContext has action and service_name for evidence correlation.

### Phase 4: Find Handler

Dynamic dispatch to `_handle_{action}` method.

### Phase 5: Coerce Options

Type-safe options coercion based on `@action(request_options=...)` decorator.

### Phase 6: Gate Execution

Execute compliance gates before handler. Block if any gate fails.

- **Service-level**: `@gates(hard=[...], situational=[...])` on class
- **Action-level**: `@action(hard_gates=[...], situational_gates=[...])` on handler

### Phase 7: Execute Handler + Evidence

Execute handler, emit evidence, handle errors uniformly.

## 4. Gate Integration

### 4.1 Gate Types

**Hard gates**: Always run, fail-closed if not found **Situational gates**: Resolved via Charter,
only run if active for tenant

### 4.2 Key Authorization Phrases

| Phrase                           | Purpose                                       |
| -------------------------------- | --------------------------------------------- |
| `require_dual_approval`          | Gate requiring two distinct approvers         |
| `require_access_justification`   | Gate requiring documented justification       |
| `require_segregation_analysis`   | Gate requiring segregation of duties analysis |
| `verify_approval_chain_complete` | Verify all required approvals obtained        |
| `check_er_clearance`             | Check Employee Relations clearance            |

See: `hub/foundation/packages/authorization/phrases/`

### 4.3 Break-Glass Override

For emergency situations, break-glass provides override with full audit trail:

```python
result = await invoke_break_glass(
    {"reason": "Production outage", "incident_id": incident_id},
    ctx
)
```

See: `hub/foundation/packages/core/phrases/invoke_break_glass.py`

## 5. Evidence Emission

### 5.1 Auto-Evidence Pattern

Every action automatically emits evidence unless `@action(skip_evidence=True)`:

```python
evidence = Evidence(
    tenant_id=ctx.tenant_id,
    evidence_type=f"{service_name}.{action}",
    data={
        "action": action,
        "success": response.success,
        "context": ctx.to_evidence_data(),  # Active assertion
    },
)
```

### 5.2 Active Assertion Pattern

Evidence includes `ctx.to_evidence_data()` which captures:

- Gate results: which gates passed
- Policy version: which version was active
- Jurisdictions: which rules applied

## 6. Error Handling

### 6.1 Fail-Closed Principle

```
Any error -> action blocked -> ResponseModel.fail()

- Invalid payload -> fail
- Unknown action -> fail
- Gate blocked -> fail
- Gate not found -> fail (hard gates)
- Handler exception -> fail
```

### 6.2 Error Response Data

Gate blocks include full gate_results for audit:

```python
ResponseModel.fail(
    f"Blocked by gate {e.gate_id}",
    data={"gate_id": e.gate_id, "gate_results": ctx.gate_results},
)
```

## 7. Integration Points

| Component        | Purpose                               |
| ---------------- | ------------------------------------- |
| `RequestContext` | Identity + policy state (see ADR-013) |
| `ResponseModel`  | Uniform response envelope             |
| `Gate`           | Compliance checkpoints                |
| `Evidence`       | Proof artifact storage                |

## 8. References

- **Core phrases**: `hub/foundation/packages/core/phrases/`
- **Authorization phrases**: `hub/foundation/packages/authorization/phrases/`
- **Related**: ADR-008-policy-gates, ADR-013-service-context
