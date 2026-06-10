---
doc_type: ADR
title: "ADR-015: Defense-in-Depth with Permit + JIT Roles"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["authorization", "identity"]
charters: ["privileged_escalation", "service_account_privilege", "break_glass"]
---

# ADR-015: Defense-in-Depth with Permit + JIT Roles

## Status

Accepted

## Context

CanonSys authorizes sensitive people operations (terminations, promotions, compensation changes).
These actions require:

1. **Provable authorization**: Every action traceable to an approved decision
2. **Replay prevention**: An authorization cannot be reused
3. **Limited exposure**: Minimize window of execution capability
4. **No standing power**: Humans should not have persistent ability to execute sensitive actions

### Decision Drivers

- Defense in depth: multiple authorization layers
- Transaction binding: one certificate = one execution
- Capability control: user cannot see/execute without active grant
- Audit correlation: grant links to certificate + permit

## Decision

### D1: Defense-in-Depth with Permit + JIT Layers

Two-layer authorization: Permit (transaction-level) + JIT (capability-level).

```
Layer 1 (Primary): Permit Token
  - Single-use, consumed on first redemption
  - Binds certificate to specific execution
  - DENY on reuse

Layer 2 (Hardening): JIT Role
  - Time-bound HRIS security group membership
  - Removes standing execution capability
  - Revoked after permit consumption
```

**Implementation**: See vocabulary packages:

- `require_access_justification` - justification before access grant
- `check_er_clearance` - ER clearance verification
- `require_dual_approval` - dual approval for high-risk actions
- `verify_strong_auth_posture` - authentication posture validation

### D2: Permit is Primary, JIT is Hardening

The permit token is the **primary** authorization mechanism. It binds a certificate to a single
execution and cannot be reused.

JIT role is **defense hardening**. It removes standing execution capability from the user.

**Implementation**: `PermitToken` entity with `TokenStatus` (ACTIVE, USED, REVOKED).

### D3: JIT Role Naming Convention

JIT roles follow strict naming: `{Action}_Executor_JIT`

```python
# Examples:
# TERMINATE -> Terminate_Executor_JIT
# PROMOTE -> Promote_Executor_JIT
```

### D4: Scheduled Revocation (5-Minute Delay)

JIT revocation is scheduled 5 minutes after permit redemption, not immediate.

Rationale:

- Edge case handling: Network failure during BP execution
- Race condition prevention: Immediate revoke could race with HRIS processing
- Legitimate completion: User should finish valid operation

### D5: Immutable State Transitions

JITRoleGrant is a frozen dataclass. State changes create new instances via `with_status()`.

## Vocabulary Mapping

| Phrase                         | Package         | Purpose                         |
| ------------------------------ | --------------- | ------------------------------- |
| `require_access_justification` | `authorization` | Justification gate before grant |
| `check_er_clearance`           | `authorization` | ER clearance verification       |
| `require_dual_approval`        | `authorization` | Dual approval for high-risk     |
| `verify_strong_auth_posture`   | `identity`      | MFA and auth posture check      |
| `require_distinct_identities`  | `authorization` | Prevent self-approval           |
| `require_time_bounded_access`  | `authorization` | Enforce temporal bounds         |

## Control Surface Integration

| Surface                       | Charter                                  | Key Phrases Used                                       |
| ----------------------------- | ---------------------------------------- | ------------------------------------------------------ |
| Privileged Escalation         | `privileged_escalation.canon`            | `require_dual_approval`, `verify_strong_auth_posture`  |
| Service Account Privilege     | `service_account_privilege.canon`        | `require_access_justification`, `check_er_clearance`   |
| Break Glass Activation        | `break_glass.canon`                      | `require_dual_approval`, `require_distinct_identities` |

## Alternatives Considered

### Alternative 1: Permit Token Only

Single-use permit tokens. Rejected: no UI protection, no capability removal.

### Alternative 2: JIT Role Only

Time-bound HRIS security group. Rejected: no transaction binding, replay within window.

## Consequences

### Positive

- Defense in Depth: Both permit AND JIT must be valid
- No Standing Power: Users cannot execute without time-bound grant
- UI Reflects Authorization: HRIS shows only authorized actions
- Complete Audit Trail: Grant links to certificate, permit, HRIS request

### Negative

- HRIS Integration Required: Depends on Workday API
- Latency: Grant adds HRIS API call (~100-500ms)
- Scheduler Dependency: Revocation requires background tasks

## References

- **Vocabulary Package**: `hub/foundation/packages/authorization/`
- **Vocabulary Package**: `hub/foundation/packages/identity/`
- **Charters**: `hub/charters/surfaces/identity/`
- **Related ADRs**: ADR-007-decision-certificate, ADR-016-break-glass
