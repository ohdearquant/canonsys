---
doc_type: ADR
title: "ADR-016: Break-Glass Protocol with DEGRADED Defensibility"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["core", "authorization"]
charters: ["break_glass"]
---

# ADR-016: Break-Glass Protocol with DEGRADED Defensibility

## Status

Accepted

## Context

Emergency situations arise where normal compliance gates cannot pass, but business operations must
proceed:

- Immediate safety threats requiring instant termination
- System outages preventing normal workflow completion
- Legal mandates with tight deadlines
- Time-critical actions where delay causes harm

Traditional approaches present two problematic options:

1. **Full bypass**: Skipping compliance entirely, creating liability exposure
2. **Blocking regardless**: Forcing normal process even during emergencies

Neither is acceptable. We need an emergency path that preserves auditability while acknowledging
reduced legal defensibility.

### Decision Drivers

- Litigation defensibility: Actions must be defensible in court/EEOC
- Audit completeness: Every action must produce evidence
- Accountability: Someone must own the emergency decision
- Deterrence: Emergency path must not become the easy path
- Legal notification: Counsel must know immediately

## Decision

### D1: DEGRADED Defensibility (Not Bypass)

Break-glass produces a `BREAK_GLASS` certificate with `defensibility_state: "DEGRADED"`, not a
bypass that skips compliance.

```
Normal Path:    Gates pass -> Certificate (CERTIFIED, defensibility: FULL)
Break-Glass:    Gates fail -> Emergency path -> Certificate (BREAK_GLASS, defensibility: DEGRADED)
```

**Implementation**: See vocabulary package `core`:

- `invoke_break_glass` - creates BREAK_GLASS certificate with auto-notification

### D2: Typed Attestation (Not Checkboxes)

The `attestation` field requires free-text justification:

```python
attestation: str  # Required, minimum 50 characters
reason_code: BreakGlassReason  # SAFETY_THREAT, SYSTEM_OUTAGE, etc.
```

**Implementation**: Attestation validated for minimum substantive content.

### D3: Auto-Notification (Immutable Parties)

Legal, Employee Relations, and Audit are notified immediately on break-glass invocation:

```python
notified_parties: tuple[str, ...] = ("Legal", "ER", "Audit")  # Immutable tuple
```

### D4: Non-Exportable Default

Break-glass certificates cannot be exported without Legal sign-off:

```python
exportable: bool = False  # System-enforced default
```

### D5: Executive Override Pattern

`ExecutiveOverride` provides parallel pattern for policy deviations authorized by executives (CHRO,
GC, CEO, CFO).

**Implementation**: See `invoke_executive_override` phrase.

## Vocabulary Mapping

| Phrase                         | Package         | Purpose                        |
| ------------------------------ | --------------- | ------------------------------ |
| `invoke_break_glass`           | `core`          | Create BREAK_GLASS certificate |
| `invoke_executive_override`    | `core`          | Executive policy deviation     |
| `require_access_justification` | `authorization` | Justification gate             |
| `record_attestation`           | `certification` | Record typed attestation       |

## Control Surface Integration

| Surface                | Charter              | Key Phrases Used                                                             |
| ---------------------- | -------------------- | ---------------------------------------------------------------------------- |
| Break Glass Activation | `break_glass.canon`  | `invoke_break_glass`, `require_dual_approval`, `require_distinct_identities` |

## Alternatives Considered

### Alternative 1: Simple Audit Flag

Add `emergency: bool` flag to normal certificates. Rejected: no defensibility acknowledgment, easy
to ignore.

### Alternative 2: Full Bypass with Post-Hoc Logging

Skip compliance, log after. Rejected: compliance gaps, no evidence at decision time.

### Alternative 3: Checkbox-Based Justification

Predefined reasons user selects. Rejected: insufficient accountability, weak evidence.

## Consequences

### Positive

- Complete audit trail: Every emergency action produces evidence
- Legal defensibility: DEGRADED status sets appropriate expectations
- Accountability: Typed attestation creates ownership
- Oversight: Auto-notification ensures review
- Deterrence: Process friction discourages misuse

### Negative

- Process overhead: Emergency path still requires form completion
- Potential delay: Attestation takes time in genuine emergencies
- Training requirement: Users must understand appropriate use

### Compliance Implications

| Regulation    | Impact                                                      |
| ------------- | ----------------------------------------------------------- |
| **FCRA**      | Break-glass adverse actions may face enhanced scrutiny      |
| **GDPR**      | Emergency data processing must still be documented          |
| **SOC2**      | Break-glass events must appear in security incident reports |
| **EU AI Act** | Human override of AI decision requires documentation        |

## References

- **Vocabulary Package**: `hub/foundation/packages/core/`
- **Vocabulary Package**: `hub/foundation/packages/authorization/`
- **Charter**: `hub/charters/surfaces/identity/break_glass.canon`
- **Executive Override Charter**: `hub/charters/executive_override.canon`
- **Related ADRs**: ADR-007-decision-certificate, ADR-008-policy-gates, ADR-015-jit-role
