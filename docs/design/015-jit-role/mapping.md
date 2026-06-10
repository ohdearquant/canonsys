# 015-JIT-Role - Vocabulary Mapping

## Vocabulary Packages

| Package         | Path                                                   | Purpose                                 |
| --------------- | ------------------------------------------------------ | --------------------------------------- |
| `authorization` | `hub/foundation/packages/authorization/` | Access justification and approval gates |
| `identity`      | `hub/foundation/packages/identity/`      | Authentication posture validation       |

## Phrase Mapping

### Authorization Package

| Phrase                           | File                                        | ADR Section |
| -------------------------------- | ------------------------------------------- | ----------- |
| `require_access_justification`   | `phrases/require_access_justification.py`   | D1          |
| `check_er_clearance`             | `phrases/check_er_clearance.py`             | D1          |
| `require_dual_approval`          | `phrases/require_dual_approval.py`          | D1          |
| `require_distinct_identities`    | `phrases/require_distinct_identities.py`    | D1          |
| `require_time_bounded_access`    | `phrases/require_time_bounded_access.py`    | D4          |
| `require_segregation_analysis`   | `phrases/require_segregation_analysis.py`   | D1          |
| `verify_approval_chain_complete` | `phrases/verify_approval_chain_complete.py` | D1          |

### Identity Package

| Phrase                                | File                                             | ADR Section |
| ------------------------------------- | ------------------------------------------------ | ----------- |
| `verify_strong_auth_posture`          | `phrases/verify_strong_auth_posture.py`          | D1          |
| `get_ca_level`                        | `phrases/get_ca_level.py`                        | D1          |
| `verify_request_source_authenticated` | `phrases/verify_request_source_authenticated.py` | D1          |

## Control Surfaces

| Surface                       | Charter                           | Primary Phrases                                        |
| ----------------------------- | --------------------------------- | ------------------------------------------------------ |
| Privileged Escalation         | `privileged_escalation.canon`     | `require_dual_approval`, `verify_strong_auth_posture`  |
| Service Account Privilege     | `service_account_privilege.canon` | `require_access_justification`                         |
| Break Glass Activation        | `break_glass.canon`               | `require_distinct_identities`, `require_dual_approval` |

## Design-to-Code Traceability

| Decision                  | Implementation                        |
| ------------------------- | ------------------------------------- |
| D1: Defense-in-depth      | Permit + JIT two-layer check          |
| D2: Permit primary        | `PermitToken` with `TokenStatus`      |
| D3: JIT naming            | `{Action}_Executor_JIT` convention    |
| D4: Scheduled revoke      | 5-minute delay via `RevokeSchedule`   |
| D5: Immutable transitions | Frozen dataclass with `with_status()` |

## Charter Package Dependencies

All three control surfaces declare shared package dependencies:

```
packages:
    - identity
    - authorization
    - certification
    - core
    - lifecycle
    - pattern
    - policy
```

## Key Patterns

### Defense-in-Depth

JIT role is Layer 2 hardening. Permit token is Layer 1 primary authorization. Both layers must be
valid for action execution.

### Dual Approval Escalation

High-risk scopes (ADMIN, SUPERUSER, CLUSTER, DATACENTER) require `require_dual_approval` phrase to
enforce two-party approval.

### Strong Authentication Posture

All JIT grants require `verify_strong_auth_posture` to validate MFA and device posture before
granting elevated access.
