# 016-Break-Glass - Vocabulary Mapping

## Vocabulary Packages

| Package         | Path                                                   | Purpose                                 |
| --------------- | ------------------------------------------------------ | --------------------------------------- |
| `core`          | `hub/foundation/packages/core/`          | Break-glass and override phrases        |
| `authorization` | `hub/foundation/packages/authorization/` | Access justification and approval gates |

## Phrase Mapping

### Core Package

| Phrase                      | File                                   | ADR Section |
| --------------------------- | -------------------------------------- | ----------- |
| `invoke_break_glass`        | `phrases/invoke_break_glass.py`        | D1          |
| `invoke_executive_override` | `phrases/invoke_executive_override.py` | D5          |

### Authorization Package

| Phrase                         | File                                      | ADR Section |
| ------------------------------ | ----------------------------------------- | ----------- |
| `require_access_justification` | `phrases/require_access_justification.py` | D2          |
| `require_dual_approval`        | `phrases/require_dual_approval.py`        | D1          |
| `require_distinct_identities`  | `phrases/require_distinct_identities.py`  | D3          |

## Control Surfaces

| Surface                | Charter             | Primary Phrases                                                              |
| ---------------------- | ------------------- | ---------------------------------------------------------------------------- |
| Break Glass Activation | `break_glass.canon` | `invoke_break_glass`, `require_dual_approval`, `require_distinct_identities` |

## Charters

### Break Glass Activation

**Path**: `hub/charters/surfaces/identity/break_glass.canon`

**Packages Used**:

- identity
- authorization
- certification
- core
- incident
- pattern
- lifecycle
- policy

**Key Phrases in Charter**:

- `require_incident_declared()` - Emergency declaration
- `verify_request_source_authenticated()` - Source authentication
- `verify_strong_auth_posture()` - Activator MFA check
- `require_dual_approval()` - Cluster/datacenter scope
- `require_distinct_identities()` - Witness verification
- `invoke_break_glass()` - Access grant
- `emit_certificate()` - Closure certification

### Executive Override Charter

**Path**: `hub/charters/executive_override.canon`

**Key Phrases in Charter**:

- `require_executive_authority()` - Authority assertion
- `require_risk_acknowledgement()` - Risk acceptance
- `require_legal_review_complete()` - Legal review
- `build_certificate_summary()` - Summary construction
- `certify_executive_override()` - Override certification

## Design-to-Code Traceability

| Decision                   | Implementation                                   |
| -------------------------- | ------------------------------------------------ |
| D1: DEGRADED defensibility | `defensibility_state: "DEGRADED"` in certificate |
| D2: Typed attestation      | Min 50 char validation in `invoke_break_glass`   |
| D3: Auto-notification      | `notified_parties: tuple` (immutable)            |
| D4: Non-exportable         | `exportable: bool = False` default               |
| D5: Executive override     | Parallel `ExecutiveOverride` dataclass           |

## Key Patterns

### Break-Glass != Bypass

Both paths produce certificates. Break-glass produces `BREAK_GLASS` type with `DEGRADED`
defensibility, not a bypass that skips compliance.

### Typed Attestation

Free-text justification (min 50 characters) creates stronger audit trail than checkbox selection.

### Auto-Notification

`notified_parties` is a tuple (not list) to prevent modification. Legal, ER, and Audit are always
notified immediately.

### Dual Approval Escalation

High-risk scopes (CLUSTER, DATACENTER, ALL_CRITICAL, IDENTITY_SYSTEMS) require
`require_dual_approval` phrase.
