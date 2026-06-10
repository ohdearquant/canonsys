---
doc_type: TDS
title: "Technical Design Specification: Action Declaration"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core"]
charters: []
---

# Technical Design Specification: Action Declaration

## 1. Overview

### 1.1 Purpose

The action declaration system provides **declarative compliance enforcement** through decorators.
Gates and metadata are declared at class and method level, then automatically enforced by
CanonService.

### 1.2 Scope

- `@gates` decorator for service-level gate declaration
- `@action` decorator for action-specific metadata
- `ServiceGates` and `ActionMeta` dataclasses
- Gate resolution order and charter-driven activation
- Evidence auto-emission control

### 1.3 Design Principles

1. **Declarative**: Gates declared, not imperatively called
2. **Co-Located**: Compliance requirements live with handler code
3. **Fail-Closed**: Missing hard gates raise `GateNotFoundError`
4. **Charter-Driven**: Situational gates activated by policy
5. **Immutable Config**: Decorator metadata frozen after decoration

## 2. Architecture

### 2.1 Module Structure

| Module                   | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| `enforcement/service.py` | CanonService, @gates, @action, ServiceGates, ActionMeta |
| `enforcement/types.py`   | ServiceContext, RequestContext                          |
| `enforcement/gate.py`    | Gate base class, create_gate, run_gates                 |
| `enforcement/hooks.py`   | Compliance hooks for kron integration                   |

### 2.2 Component Diagram

```
@gates ──> ServiceGates ──> CanonService
@action ──> ActionMeta ──> CanonService
                               │
                               ├──> run_gates()
                               ├──> Evidence auto-emit
                               └──> Options coercion
```

## 3. @gates Decorator - Service-Level Gates

### 3.1 Syntax

```python
@gates(hard=["tenant.active"], situational=["consent.jurisdiction_allowed"])
class ConsentService(CanonService):
    ...
```

### 3.2 ServiceGates Dataclass

```python
@dataclass(frozen=True, slots=True)
class ServiceGates:
    hard: tuple[str, ...] = ()        # Always run, fail-closed if not found
    situational: tuple[str, ...] = () # Run if in charter.policy_ids
```

## 4. @action Decorator - Action Metadata

### 4.1 Syntax

```python
@action(
    evidence_type="consent.grant",
    request_options=GrantOptions,
    hard_gates=["consent.valid_scope"],
    situational_gates=["consent.video"],
)
async def grant(self, payload, ctx):
    ...

@action(skip_evidence=True)
async def verify(self, payload, ctx):
    ...
```

### 4.2 ActionMeta Dataclass

```python
@dataclass(frozen=True, slots=True)
class ActionMeta:
    evidence_type: str | None = None       # Custom type (default: {service}.{action})
    skip_evidence: bool = False            # Skip auto-emission
    request_options: type[BaseModel] | None = None
    hard_gates: tuple[str, ...] = ()
    situational_gates: tuple[str, ...] = ()
```

## 5. Gate Resolution Order

Gates execute in this order:

| Order | Gate Type          | Source                             | Behavior                |
| ----- | ------------------ | ---------------------------------- | ----------------------- |
| 1     | Class Hard         | `@gates(hard=[...])`               | Always run, fail-closed |
| 2     | Class Situational  | `@gates(situational=[...])`        | Run if in charter       |
| 3     | Action Hard        | `@action(hard_gates=[...])`        | Always run, fail-closed |
| 4     | Action Situational | `@action(situational_gates=[...])` | Run if in charter       |

### 5.1 Charter-Driven Activation

```python
if action_meta.situational_gates and self._service_context:
    charter = self._service_context.charter
    if charter:
        active_policy_ids = set(charter.policy_ids)
        for gate_id in action_meta.situational_gates:
            if gate_id in active_policy_ids:
                gate = create_gate(gate_id)
                gates_to_run.append(gate)
```

## 6. Evidence Auto-Emission

### 6.1 Default Behavior

Every action emits evidence unless `skip_evidence=True`:

```python
async def _emit_action_evidence(self, handler, action, ...):
    action_meta = get_action_meta(handler)
    if action_meta and action_meta.skip_evidence:
        return

    evidence_type = action_meta.evidence_type or f"{self._service_name}.{action}"
    # ... emit evidence
```

### 6.2 Evidence Type Customization

```python
# Default: consent.grant
@action()
async def grant(self, ...): ...

# Custom: consent.explicit_grant
@action(evidence_type="consent.explicit_grant")
async def grant(self, ...): ...
```

## 7. Options Coercion

```python
if action_meta and action_meta.request_options and isinstance(req.options, dict):
    req.options = action_meta.request_options.model_validate(req.options)
```

## 8. Vocabulary Integration

The @action decorator is infrastructure that enables phrase execution. Core package phrases
implement actions via this pattern:

| Phrase                  | Evidence Type           | Gates                          |
| ----------------------- | ----------------------- | ------------------------------ |
| `invoke_break_glass`    | `core.break_glass`      | Hard: `break_glass.authorized` |
| `activate_charter`      | `core.charter_activate` | Hard: `charter.valid`          |
| `ratify_charter`        | `core.charter_ratify`   | Hard: `charter.quorum`         |
| `verify_audit_complete` | (skip_evidence)         | None                           |

## 9. Control Surface Mapping

Every control surface Service Action maps to an @action decorated method:

| Kill Chain Phase     | Decorator Pattern                           |
| -------------------- | ------------------------------------------- |
| Phase 0: Eligibility | `@action(hard_gates=["eligibility.*"])`     |
| Phase 1: Facts       | `@action(evidence_type="facts.submit")`     |
| Phase 2: Evidence    | `@action(hard_gates=["evidence.complete"])` |
| Phase 3: Policy      | `@action(situational_gates=["policy.*"])`   |
| Phase 4: Certificate | `@action(evidence_type="decision.certify")` |

## 10. Integration Points

### 10.1 Dependencies

| Component                     | Purpose                      |
| ----------------------------- | ---------------------------- |
| `pydantic.BaseModel`          | Options model type hint      |
| `canon.enforcement.vocabulary` | Vocabulary phrases, create_gate |
| `kron.services`               | ServiceBackend, HookRegistry |
| `canon.entities.evidence`    | Evidence for auto-emission   |

### 10.2 Dependents

| Component                | Purpose                     |
| ------------------------ | --------------------------- |
| Service implementations  | Apply decorators            |
| `025-charter`            | Activates situational gates |
| Control surface charters | Define service actions      |

## 11. Testing Requirements

| Test Category                 | Coverage Target |
| ----------------------------- | --------------- |
| @gates decorator application  | 100%            |
| @action decorator application | 100%            |
| Gate resolution order         | 100%            |
| Hard gate fail-closed         | 100%            |
| Situational gate activation   | 100%            |
| Options coercion              | 100%            |
| Evidence emission             | 100%            |
| skip_evidence behavior        | 100%            |

## 12. References

- **Implementation**: `libs/canon/src/canon/enforcement/service.py`
- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Related**: TDS-008-policy-gates, TDS-012-single-enforcement, TDS-025-charter
