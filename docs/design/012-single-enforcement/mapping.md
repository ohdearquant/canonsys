# 012 Single Enforcement Point - Code Mapping

## Overview

The Single Enforcement Point pattern ensures all actions flow through **one control point**
(CanonService.request) where gates are checked, evidence is emitted, and compliance is enforced.

## Vocabulary Packages

| Package         | Path                                                   | Purpose                                |
| --------------- | ------------------------------------------------------ | -------------------------------------- |
| `core`          | `hub/foundation/packages/core/`          | Break-glass override, audit primitives |
| `authorization` | `hub/foundation/packages/authorization/` | Authorization gates and approvals      |

## Key Phrases

### Core Package

| Phrase                      | File                                   | Purpose                       |
| --------------------------- | -------------------------------------- | ----------------------------- |
| `invoke_break_glass`        | `phrases/invoke_break_glass.py`        | Emergency override activation |
| `invoke_executive_override` | `phrases/invoke_executive_override.py` | Executive-level override      |
| `verify_audit_complete`     | `phrases/verify_audit_complete.py`     | Verify audit is complete      |

### Authorization Package

| Phrase                           | File                                        | Purpose                      |
| -------------------------------- | ------------------------------------------- | ---------------------------- |
| `require_dual_approval`          | `phrases/require_dual_approval.py`          | Gate: two distinct approvers |
| `require_access_justification`   | `phrases/require_access_justification.py`   | Gate: documented reason      |
| `require_segregation_analysis`   | `phrases/require_segregation_analysis.py`   | Gate: SoD analysis           |
| `require_distinct_identities`    | `phrases/require_distinct_identities.py`    | Gate: different actors       |
| `verify_approval_chain_complete` | `phrases/verify_approval_chain_complete.py` | Verify approvals             |
| `check_er_clearance`             | `phrases/check_er_clearance.py`             | Check ER clearance           |
| `verify_role_approval`           | `phrases/verify_role_approval.py`           | Verify role has approval     |

## Architectural Patterns

### 1. Single Enforcement Point

ALL actions flow through `CanonService.request()`. No direct handler calls. This ensures:

- Gates always run
- Evidence always emitted
- Errors consistently handled

### 2. Fail-Closed Gate Resolution

```python
# Hard gate not found = GateNotFoundError (blocks action)
raise GateNotFoundError(gate_id)

# Situational gate not found = warning (less severe)
logger.warning("Situational gate '%s' not found", gate_id)
```

### 3. Charter-Driven Situational Gates

Situational gates only activate if present in `charter.policy_ids`. This allows per-tenant
compliance configuration.

### 4. Handler Convention

Actions map to `_handle_{action}` methods:

```python
handler_name = f"_handle_{action_value}"
handler = getattr(self, handler_name, None)
```

### 5. Evidence as Active Assertion

Evidence captures `ctx.to_evidence_data()`:

- Policy/gate state at execution time
- Correlation IDs for tracing
- Jurisdiction context

## Dependencies

**Depends on:**

- `ADR-008-policy-gates` - Gate creation and execution
- `ADR-013-service-context` - RequestContext propagation
- `kron.services` - ServiceBackend, HookRegistry

**Depended by:**

- All service implementations (ConsentService, etc.)
- Workflow orchestration

## Key Decisions

1. **Single Entry Point**: All service access through `request()`. Prevents compliance bypass.

2. **Layered Gate Execution**: Service gates first, then action gates. Clear precedence.

3. **Auto-Evidence Emission**: Every action emits evidence unless `skip_evidence=True`.

4. **Context Immutability**: `ctx.model_copy(update=...)` creates new context, not mutation.
