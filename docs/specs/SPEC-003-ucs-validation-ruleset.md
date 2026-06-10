# UCS-v1 Validation & Enforcement Ruleset

**Author**: Jason La Barbera **Captured**: 2026-01-13 **Status**: Ready for Implementation

_Fail-Closed, Discovery-Resilient_

---

## 0. Prime Directive (Non-Negotiable)

**No certificate may be issued unless it is valid, authorized, complete, and sealed.**

There is no "warn and proceed." Invalid certificates do not exist.

---

## 1. Validation Phases (Order Matters)

UCS validation happens in six strict phases. Failure in any phase = hard stop.

```
STRUCTURE → CONTEXT → AUTHORITY → ASSERTIONS → EVIDENCE → SEAL
```

---

## 2. Phase I — Structural Validation (Syntax & Shape)

### Required

- `meta`, `context`, `authority`, `assertions`, `evidence_pointers`, `seal`
- `schema_version` must equal `1.0`
- All enums must match known values
- No unknown fields allowed (schema strictness)

### Hard-Fail Conditions

- Missing block
- Extra / unrecognized field
- Null where value required

**Rationale**: Unknown fields = hidden narrative = discovery risk.

---

## 3. Phase II — Context Validation (What Game Are We Playing?)

### Required

- `workflow_type` ∈ allowed enum
- `jurisdiction_code` present
- `subject_token` present and hashed

### Workflow-Specific Rules

| workflow_type         | Required Assertions                 |
| --------------------- | ----------------------------------- |
| `TERMINATION`         | `parity_attested`, `er_clearance`   |
| `INVESTIGATION_CLOSE` | `finding_classification`            |
| `PIP_FAIL`            | `observation_window_complete`       |
| `EXEC_OVERRIDE`       | `override_scope`, `risk_acceptance` |

### Hard-Fail Conditions

- Missing required assertion for workflow
- Assertion present that does not belong to workflow

**Rationale**: Prevents schema drift and "helpful" feature creep.

---

## 4. Phase III — Authority Validation (Who Is Allowed to Bind the Org?)

### Required

- `issuer_role` present
- Role must be authorized for `workflow_type`
- Delegation chain (if present) must resolve to authorized role

### Example Rule

```
TERMINATION requires issuer_role ∈ {HRBP_DIRECTOR, ER_LEAD, LEGAL_COUNSEL}
```

### Hard-Fail Conditions

- Role mismatch
- Delegation without authority basis
- Person authorized but role not

**Key Principle**: Authority is role-based, not identity-based.

This is how you survive turnover and deposition.

---

## 5. Phase IV — Assertion Validation (Control Surface Enforcement)

### Global Assertion Rules

- No assertion may be null
- Boolean assertions must be explicit (`true`/`false`)
- No free-text fields anywhere

### Termination-Specific Assertions

- `risk_acceptance` = `true`
- `parity_attested` = `true`
- `er_clearance.cleared`:
  - `false` → proceed
  - `true` or `unknown` → escalation required → block issuance

### Hard-Fail Conditions

- Missing attestation
- Implicit parity ("not applicable")
- ER clearance unresolved

**Rationale**: Judgment must be owned, not implied.

---

## 6. Phase V — Evidence Pointer Validation (The Moat)

### Required

Each `evidence_pointer` must include:

- `cep_id`
- `hash`
- `type`

### Enforcement Rules

- CEP hash must resolve and match stored CEP hash
- CEP must be sealed
- CEP `schema_version` must be compatible
- CEP must not be revoked or superseded

### Absolute Prohibitions

- URLs
- Filenames
- Attachments
- Raw system references

### Hard-Fail Conditions

- Hash mismatch
- CEP unsealed
- CEP superseded
- Evidence pointer missing

**This is the airlock. Nothing upstream can leak through it.**

---

## 7. Phase VI — Seal & Immutability Validation

### Required

- Signature must verify against all prior fields
- `previous_cert_hash` (if present) must exist and verify
- Certificate content must match signed payload byte-for-byte

### Hard-Fail Conditions

- Signature invalid
- Any field mutated post-sign
- Hash chain broken

**If this fails, the certificate renders: INVALID / TAMPERED.**

---

## 8. Enforcement Outcomes (System Judgment)

Every validation attempt results in one of three states:

### 1. APPROVED

- Certificate issued
- Seal applied
- Immutable

### 2. BLOCKED

- Certificate not issued
- No artifact exists
- Reason code logged (internal only)

### 3. ESCALATION_REQUIRED

- Triggered by:
  - ER clearance = `true`/`unknown`
  - Delegation ambiguity
- Must resolve before re-attempt

**Blocked ≠ logged. Blocked = nonexistent.**

---

## 9. What the Validator Must NEVER Do

The validator must never:

- Auto-correct inputs
- Suggest alternative wording
- Infer intent
- Relax constraints
- Provide "safe defaults"

**Silence is safer than help.**

---

## 10. Invariants (Pin These to the Wall)

These are system laws:

1. No certificate without authority
2. No evidence without CEP
3. No parity without attestation
4. No clearance = no action
5. No edits after seal
6. No raw data ever

**Break any one → system collapses under cross-examination.**

---

## 11. Why This Validator Is the Real Product

Most systems:

- Log actions
- Explain processes
- Store data

This validator:

- Denies reality until it is safe
- Constrains judgment
- Produces admissible artifacts

**That's why this is not "AI governance." It's administrative law enforcement at runtime.**

---

## 12. Calibration Questions

**If Engineering asks:**

> "Can we make this more flexible?"

**The answer is:**

> "Flexibility is what gets subpoenaed."

**If Legal asks:**

> "Can we stand behind this?"

**The answer is:**

> "Yes — and nothing behind it."

---

## 13. Implementation Notes

### Maps to Existing CanonSys Patterns

| Ruleset Phase         | CanonSys Component                          |
| --------------------- | -------------------------------------------- |
| Phase I (Structure)   | Pydantic model validation                    |
| Phase II (Context)    | `workflow_type` enum + jurisdiction resolver |
| Phase III (Authority) | `RoleAuthorizationGate` (needs completion)   |
| Phase IV (Assertions) | Gate assertions in `RequestContext`          |
| Phase V (Evidence)    | Evidence hash verification                   |
| Phase VI (Seal)       | RSA-4096 signing (to implement)              |

### Enforcement Outcomes Map

| Ruleset Outcome     | CanonSys Pattern                      |
| ------------------- | -------------------------------------- |
| APPROVED            | `PhraseResult(status=PASSED)`            |
| BLOCKED             | `GateBlocked` exception                  |
| ESCALATION_REQUIRED | `PhraseResult(status=ESCALATE)` (to add) |
