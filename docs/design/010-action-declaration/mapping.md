# 010 Action Declaration - Code Mapping

## Overview

The action declaration system uses decorators to declare **action metadata** and **gate
requirements**. This is infrastructure that vocabulary phrases use for execution.

## Vocabulary Package

**Package**: `hub/foundation/packages/core/`

Phrases that implement actions via this pattern:

| Phrase                      | File                                   | Evidence Type             |
| --------------------------- | -------------------------------------- | ------------------------- |
| `invoke_break_glass`        | `phrases/invoke_break_glass.py`        | `core.break_glass`        |
| `invoke_executive_override` | `phrases/invoke_executive_override.py` | `core.executive_override` |
| `activate_charter`          | `phrases/activate_charter.py`          | `core.charter_activate`   |
| `ratify_charter`            | `phrases/ratify_charter.py`            | `core.charter_ratify`     |
| `resolve_charter`           | `phrases/resolve_charter.py`           | (skip_evidence)           |
| `verify_audit_complete`     | `phrases/verify_audit_complete.py`     | (skip_evidence)           |
| `verify_audit_current`      | `phrases/verify_audit_current.py`      | (skip_evidence)           |
| `verify_evidence_freshness` | `phrases/verify_evidence_freshness.py` | (skip_evidence)           |

## Infrastructure Code

| Module                              | Purpose                                  |
| ----------------------------------- | ---------------------------------------- |
| `libs/canon/src/canon/enforcement/service.py` | CanonService, @gates, @action decorators |
| `libs/canon/src/canon/enforcement/types.py`   | ServiceContext, RequestContext           |
| `libs/canon/src/canon/enforcement/gate.py`    | Gate base class, run_gates               |
| `libs/canon/src/canon/enforcement/hooks.py`   | Compliance hooks for kron                |

## Key Classes

### Decorators (service.py)

**Class-Level**:

- `@gates(hard=[], situational=[])` - Service-level gates
- `ServiceGates` - Gate configuration dataclass

**Method-Level**:

- `@action(evidence_type, skip_evidence, request_options, hard_gates, situational_gates)`
- `ActionMeta` - Action metadata dataclass

**Accessors**:

- `get_action_meta(handler)` - Get ActionMeta from handler
- `get_service_gates(cls)` - Get ServiceGates from class

## Architectural Patterns

### 1. Two-Level Gate Declaration

```python
@gates(hard=["tenant.active"], situational=["jurisdiction_allowed"])
class ConsentService(CanonService):

    @action(hard_gates=["consent.valid_scope"])
    async def grant(self, payload, ctx):
        ...
```

### 2. Gate Resolution Order

1. Class hard gates
2. Class situational gates
3. Action hard gates
4. Action situational gates

### 3. Charter-Driven Activation

Situational gates only run if in `charter.policy_ids`:

```python
if gate_id in active_policy_ids:
    gate = create_gate(gate_id)
    gates_to_run.append(gate)
```

### 4. Evidence Auto-Emission

Unless `skip_evidence=True`, every action emits evidence.

### 5. Options Coercion

```python
if action_meta.request_options:
    req.options = action_meta.request_options.model_validate(req.options)
```

## Control Surface Mapping

| Kill Chain Phase | Decorator Pattern                           |
| ---------------- | ------------------------------------------- |
| Phase 0          | `@action(hard_gates=["eligibility.*"])`     |
| Phase 1          | `@action(evidence_type="facts.submit")`     |
| Phase 2          | `@action(hard_gates=["evidence.complete"])` |
| Phase 3          | `@action(situational_gates=["policy.*"])`   |
| Phase 4          | `@action(evidence_type="decision.certify")` |

## How Phrases Use @action

```python
# In a phrase implementation
@action(
    evidence_type="core.break_glass",
    hard_gates=["break_glass.authorized"],
)
async def invoke_break_glass(reason: str, ctx: Ctx) -> BreakGlassResult:
    # ... implementation
```

## Dependencies

**Depends on**:

- `pydantic.BaseModel` - Options model
- `kron.services` - ServiceBackend

**Depended by**:

- All vocabulary phrases implementing actions
- All control surface service implementations
