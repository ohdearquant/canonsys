---
doc_type: TDS
title: "Technical Design Specification: Break-Glass Protocol"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core", "authorization"]
charters: ["break_glass"]
---

# Technical Design Specification: Break-Glass Protocol

## 1. Overview

### 1.1 Purpose

The Break-Glass Protocol provides an emergency path when normal compliance gates cannot pass. It
does **NOT bypass compliance** - it produces a different certificate class (`BREAK_GLASS`) with
explicitly degraded defensibility.

**Core Principle**: "The system screams, not whispers."

### 1.2 Platform Invariants

1. **Break-Glass != Bypass**: Different certificate class, not skipped compliance
2. **Degraded Defensibility**: Explicitly acknowledged, harder to defend in litigation
3. **Typed Attestation**: Free-text justification required, not checkbox selection
4. **Auto-Notification**: Legal, ER, and Audit notified immediately
5. **Non-Exportable**: Cannot leave organization without Legal sign-off

## 2. Vocabulary Integration

### 2.1 Core Package Phrases

| Phrase                      | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `invoke_break_glass`        | Create BREAK_GLASS certificate with notification |
| `invoke_executive_override` | Executive policy deviation record                |

### 2.2 Authorization Package Phrases

| Phrase                         | Purpose                                    |
| ------------------------------ | ------------------------------------------ |
| `require_access_justification` | Justification gate before emergency access |
| `require_dual_approval`        | Dual approval for cluster/datacenter scope |
| `require_distinct_identities`  | Witness verification                       |

## 3. Break-Glass vs Normal Path

| Aspect           | Normal Path  | Break-Glass Path   |
| ---------------- | ------------ | ------------------ |
| Certificate Type | CERTIFIED    | BREAK_GLASS        |
| Defensibility    | FULL         | DEGRADED           |
| Notification     | None         | Legal/ER/Audit     |
| Exportable       | Yes          | No (without Legal) |
| Legal Review     | Not required | Mandatory          |
| Audit Trail      | Standard     | Enhanced           |

**Both paths produce certificates**. The difference is in legal defensibility and oversight.

## 4. Control Surface: Break Glass Activation

The Break Glass Activation charter implements the break-glass workflow:

### Workflow Phases

1. **Emergency Declaration**: Incident declared, source authenticated
2. **Activator Verification**: Strong auth posture, prior bypass check
3. **Witness Attestation**: Distinct identity verification
4. **Access Grant**: Policy pass, break-glass invocation
5. **Monitoring**: Action tracking, recertification trigger
6. **Closure**: Auto or manual, case integrity verification

### Situational Gates

| Condition                            | Required Phrase                |
| ------------------------------------ | ------------------------------ |
| `access_scope == "CLUSTER"`          | `require_dual_approval`        |
| `access_scope == "DATACENTER"`       | `require_dual_approval`        |
| `systems_affected == "ALL_CRITICAL"` | `require_dual_approval`        |
| `frequent_usage_detected == true`    | `require_access_justification` |

### Role Definitions

| Role               | Actions                                             | MFA | Break Glass |
| ------------------ | --------------------------------------------------- | --- | ----------- |
| activator          | `save_evidence`, `invoke_break_glass`               | Yes | No          |
| witness            | `record_attestation`                                | Yes | No          |
| security_analyst   | `check_prior_bypasses`, `derive_prior_action_count` | Yes | No          |
| security_lead      | `schedule_auto_revert`, `emit_certificate`          | Yes | No          |
| incident_commander | `notify_incident_commander`, `emit_certificate`     | No  | Yes         |
| ciso               | `emit_certificate`                                  | No  | Yes         |

## 5. BreakGlassCertificate Fields

| Field                 | Type             | Description                        |
| --------------------- | ---------------- | ---------------------------------- |
| `certificate_id`      | UUID             | Unique identifier                  |
| `certificate_type`    | str              | Always "BREAK_GLASS"               |
| `action`              | str              | What action was taken              |
| `subject_id`          | UUID             | Who the action targets             |
| `actor_id`            | UUID             | Who invoked break-glass            |
| `reason_code`         | BreakGlassReason | Categorized reason                 |
| `attestation`         | str              | Typed justification (min 50 chars) |
| `defensibility_state` | str              | "DEGRADED" (always)                |
| `exportable`          | bool             | False (always)                     |
| `notified_parties`    | tuple            | ("Legal", "ER", "Audit")           |

## 6. BreakGlassReason Enum

| Value           | Description                                       |
| --------------- | ------------------------------------------------- |
| `SAFETY_THREAT` | Immediate safety concern (violence, harassment)   |
| `SYSTEM_OUTAGE` | CanonSys system unavailable                       |
| `TIME_CRITICAL` | Deadline cannot be met through normal process     |
| `LEGAL_MANDATE` | Legal/regulatory requirement for immediate action |
| `OTHER`         | Other reason (requires detailed attestation)      |

## 7. Executive Override Charter

The `executive_override.canon` charter handles policy deviations:

### Workflow Phases

1. **Scope Declaration**: Override scope, policy deviation documented
2. **Supporting Certificates**: TDC existence, CEP integrity verified
3. **Authority Assertion**: Executive role, delegation chain verified
4. **Risk Acceptance**: Litigation/regulatory exposure documented
5. **Legal Review**: Legal review freshness check
6. **Override Certification**: Certificate summary, executive override certified

### Executive Roles

| Role            | Actions                                                   | MFA | Break Glass |
| --------------- | --------------------------------------------------------- | --- | ----------- |
| chro            | `declare_override_scope`, `certify_executive_override`    | Yes | Yes         |
| general_counsel | `document_litigation_exposure`, `verify_delegation_chain` | Yes | Yes         |
| ceo             | `certify_executive_override`, `document_policy_deviation` | Yes | Yes         |

## 8. Security Considerations

### Threat Model

| Threat                 | Mitigation                              |
| ---------------------- | --------------------------------------- |
| Frivolous invocation   | Typed attestation + Legal review        |
| Evidence suppression   | Non-exportable default                  |
| Audit trail gaps       | Immutable notification list             |
| Post-hoc justification | Issued_at timestamp + auto-notification |

### Degraded Defensibility Implications

1. **Litigation Risk**: Harder to defend in court/EEOC
2. **Burden of Proof**: May shift to employer
3. **Scrutiny**: Will receive extra examination
4. **Documentation**: Must show genuine emergency

## 9. Testing Requirements

| Test Category            | Coverage Target |
| ------------------------ | --------------- |
| Certificate creation     | 100%            |
| Attestation validation   | 100%            |
| Notification dispatch    | 100%            |
| Token lifecycle          | 100%            |
| Serialization round-trip | 100%            |

## 10. References

- **Core Package**: `hub/foundation/packages/core/`
- **Authorization Package**: `hub/foundation/packages/authorization/`
- **Break Glass Activation Charter**:
  `hub/charters/surfaces/identity/break_glass.canon`
- **Executive Override Charter**: `hub/charters/executive_override.canon`
- **Related**: TDS-007-decision-certificate, TDS-008-policy-gates
