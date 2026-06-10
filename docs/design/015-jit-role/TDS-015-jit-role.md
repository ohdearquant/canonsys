---
doc_type: TDS
title: "Technical Design Specification: JIT Execution Roles"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["authorization", "identity"]
charters: ["privileged_escalation", "service_account_privilege", "break_glass"]
---

# Technical Design Specification: JIT Execution Roles

## 1. Overview

### 1.1 Purpose

JIT (Just-in-Time) Execution Roles provide defense-in-depth for sensitive people operations. They
are the **secondary** authorization layer, removing standing execution power from humans.

### 1.2 Platform Invariants

1. **Permit Primary**: JIT role is defense hardening, not primary authorization
2. **No Standing Power**: Humans have no persistent execution capability
3. **Grant + Revoke**: JIT implemented via API calls, not native TTL
4. **Immutable Transitions**: State changes create new frozen instances
5. **Audit Correlation**: All grants correlate to certificate_id and permit_jti

## 2. Vocabulary Integration

### 2.1 Authorization Package Phrases

| Phrase                           | Purpose                                 |
| -------------------------------- | --------------------------------------- |
| `require_access_justification`   | Gate requiring documented justification |
| `check_er_clearance`             | Verify ER clearance status              |
| `require_dual_approval`          | Enforce two-party approval              |
| `require_distinct_identities`    | Prevent self-approval                   |
| `require_time_bounded_access`    | Enforce temporal bounds on access       |
| `require_segregation_analysis`   | Segregation of duties check             |
| `verify_approval_chain_complete` | Validate approval chain                 |

### 2.2 Identity Package Phrases

| Phrase                                | Purpose                           |
| ------------------------------------- | --------------------------------- |
| `verify_strong_auth_posture`          | MFA and device posture validation |
| `get_ca_level`                        | Get credential assurance level    |
| `verify_request_source_authenticated` | Validate request authentication   |

## 3. Defense-in-Depth Model

```
Certificate + Permit issued
    ↓
JIT role granted via HRIS API [LAYER 2]
    ↓
User executes action with Permit
    ↓
Permit consumed (single-use) [LAYER 1]
    ↓
JIT role revoked via scheduled API call [LAYER 2]
```

**Layer 1 (Primary)**: PermitToken consumed on first redemption. Cannot be reused.

**Layer 2 (Hardening)**: JITRoleGrant removes standing execution power. Scheduled revocation.

## 4. Token Lifecycle

```
PENDING → ACTIVE → REVOKE_SCHEDULED → REVOKED
    ↘                                    ↗
        -----→ FAILED (terminal) ------→
```

| Status           | Description                                 |
| ---------------- | ------------------------------------------- |
| PENDING          | Grant requested, awaiting HRIS confirmation |
| ACTIVE           | Role active in HRIS, user can execute       |
| REVOKE_SCHEDULED | Permit consumed, revocation queued          |
| REVOKED          | Role removed from HRIS                      |
| FAILED           | Grant or revoke failed (terminal)           |

## 5. Control Surface Integration

### Privileged Role Escalation

Uses JIT pattern for time-bound elevated access:

- `verify_strong_auth_posture` for auth validation
- `require_dual_approval` for ADMIN/SUPERUSER roles
- Scheduled auto-revoke after escalation window

### Service Account Privilege

Uses authorization phrases for service account grants:

- `require_access_justification` for privilege requests
- Rotation configuration validation
- Recertification scheduling

### Break Glass Activation

Emergency access with witness attestation:

- `require_distinct_identities` for witness verification
- `require_dual_approval` for cluster/datacenter scope
- Automatic revert scheduling

## 6. HRIS Integration Points

| Operation   | API Call                               | Description            |
| ----------- | -------------------------------------- | ---------------------- |
| Grant Role  | `Put_Worker_Security_Group_Assignment` | Add user to JIT group  |
| Revoke Role | `Put_Worker_Security_Group_Assignment` | Remove user from group |
| Verify      | `Get_Worker_Security_Groups`           | Confirm assignments    |

## 7. Security Considerations

### Why JIT When Permit Exists?

| Threat           | Permit Defense    | JIT Defense                       |
| ---------------- | ----------------- | --------------------------------- |
| UI exploration   | N/A               | User cannot see execution options |
| Replay attack    | Permit consumed   | Role revoked                      |
| Window extension | Permit short TTL  | Role expires                      |
| Insider threat   | Transaction-bound | Capability-bound                  |

**Combined**: Attacker must have both unconsumed permit AND active JIT role.

### Timing Parameters

| Parameter    | Value      | Rationale                                  |
| ------------ | ---------- | ------------------------------------------ |
| Revoke delay | 5 minutes  | Handle network failures, prevent races     |
| Max duration | 30 minutes | Generous for legitimate use, still bounded |
| Retry limit  | 3 attempts | Escalate to ops after repeated failures    |

## 8. Testing Requirements

| Test Category                 | Coverage Target |
| ----------------------------- | --------------- |
| Lifecycle state transitions   | 100%            |
| Immutable pattern enforcement | 100%            |
| Grant/revoke correlation      | 100%            |
| Retry logic                   | 100%            |
| Expiration handling           | 100%            |
| HRIS integration (mocked)     | 100%            |

## 9. References

- **Authorization Package**: `hub/foundation/packages/authorization/`
- **Identity Package**: `hub/foundation/packages/identity/`
- **Privileged Escalation Charter**:
  `hub/charters/surfaces/identity/privileged_escalation.canon`
- **Service Account Privilege Charter**:
  `hub/charters/surfaces/identity/service_account_privilege.canon`
- **Break Glass Activation Charter**:
  `hub/charters/surfaces/identity/break_glass.canon`
- **Related**: TDS-007-decision-certificate, TDS-016-break-glass
