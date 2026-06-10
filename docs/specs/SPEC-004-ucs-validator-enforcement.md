# UCS-v1 Validator Enforcement Specification

**Author**: Jason La Barbera **Captured**: 2026-01-13 **Status**: Ready for Implementation

_Mode: Fail-Closed | Scope: All certificate issuance, verification, and reads_

---

## 1. Validator Role (What This Component Is)

The UCS Validator is the sole authority that determines whether a certificate:

- May be issued
- Exists
- Is valid
- Can be relied upon

If the validator says "no," the system must behave as if nothing happened.

**Invalid certificates do not exist.**

---

## 2. Validator Operating Principles (Non-Negotiable)

1. **Deterministic** – Same input, same result. Always.
2. **Silent** – No suggestions, no corrections, no "help."
3. **Fail-Closed** – Ambiguity = denial.
4. **Strict** – Schema violations are fatal.
5. **Non-Creative** – Never infers intent or meaning.

This is not UX. This is enforcement.

---

## 3. Validation Pipeline (Exact Order)

Validation MUST occur in this order. Short-circuit on first failure.

```
PHASE 1 → Schema
PHASE 2 → Context
PHASE 3 → Authority
PHASE 4 → Assertions
PHASE 5 → Evidence
PHASE 6 → Cryptographic Seal
```

**No reordering. No skipping.**

---

## 4. Phase 1 — Schema Validation (Shape of Reality)

### Requirements

- Schema version == `1.0`
- All required top-level blocks present
- No unknown fields anywhere
- All field types match schema exactly
- All enums match known values

### Hard Fail If

- Extra field detected (even unused)
- Missing required field
- Null where value required
- Wrong type (string vs bool, etc.)

**Reason**: Unknown fields = narrative smuggling.

---

## 5. Phase 2 — Context Validation (What Decision Is This?)

### Required Checks

- `workflow_type` ∈ allowed enum
- `subject_token` present + valid hash format
- `jurisdiction_code` present

### Workflow Contract Enforcement

| workflow_type         | Required Assertions                                  |
| --------------------- | ---------------------------------------------------- |
| `TERMINATION`         | `parity_attested`, `er_clearance`, `risk_acceptance` |
| `INVESTIGATION_CLOSE` | `finding_classification`                             |
| `PIP_FAIL`            | `observation_window_complete`                        |
| `EXEC_OVERRIDE`       | `override_scope`, `risk_acceptance`                  |

### Hard Fail If

- Required assertion missing
- Assertion present that does not belong to workflow

**Reason**: Prevents cross-workflow contamination.

---

## 6. Phase 3 — Authority Validation (Who Can Bind the Org)

### Required Checks

- `issuer_role` present
- Role is authorized for `workflow_type`
- Delegation chain (if present) resolves to authorized role

### Example Rule (Termination)

```
TERMINATION requires issuer_role ∈ {
  HRBP_DIRECTOR,
  ER_LEAD,
  LEGAL_COUNSEL
}
```

### Hard Fail If

- Role not authorized
- Delegation without authority basis
- User is senior but role is wrong

**Authority is attached to the seat, not the person.**

---

## 7. Phase 4 — Assertion Validation (Control Surface)

### Global Rules

- No assertion may be omitted
- Booleans must be explicit
- No "unknown" except where explicitly allowed
- No free-text fields exist

### Termination-Specific Enforcement

- `risk_acceptance` == `true`
- `parity_attested` == `true`
- `er_clearance.cleared` == `false`

If:

- `true` → `ESCALATION_REQUIRED`
- `unknown` → `ESCALATION_REQUIRED`

**Escalation blocks issuance.**

### Hard Fail If

- Any assertion false where true required
- Any required assertion missing
- Any assertion ambiguous

---

## 8. Phase 5 — Evidence Pointer Validation (Airlock)

### For Each Evidence Pointer

- `cep_id` exists
- CEP hash matches stored hash
- CEP is sealed
- CEP is not superseded or revoked
- CEP schema version compatible

### Absolute Prohibitions

- URLs
- Filenames
- Attachments
- Raw system identifiers

### Hard Fail If

- Hash mismatch
- CEP unsealed
- CEP superseded
- Evidence pointer malformed

**This is the discovery kill switch.**

---

## 9. Phase 6 — Cryptographic Seal Validation

### Required Checks

- Signature verifies over exact payload
- Signing key ID valid and not revoked
- Key version recorded
- Previous certificate hash (if present) resolves

### Hard Fail If

- Signature invalid
- Any byte mismatch
- Chain broken

**If seal fails → certificate renders `INVALID / TAMPERED`.**

---

## 10. Validator Outcomes (Only Three States)

### 1. APPROVED

- Certificate sealed
- Immutable
- Persisted

### 2. BLOCKED

- No artifact created
- No partial save
- No shadow record

### 3. ESCALATION_REQUIRED

- Issuance halted
- External clearance required
- Must re-submit from Phase 1

**Blocked ≠ logged.** **Blocked = non-existent.**

---

## 11. What the Validator Must NEVER Do

The validator must never:

- Auto-correct fields
- Suggest alternatives
- Normalize input
- Default missing values
- Explain failures beyond a code

**Human interpretation is outside the system.**

---

## 12. Invariants (Burn These In)

1. No certificate without authority
2. No evidence without CEP
3. No parity without attestation
4. No clearance = no action
5. No edits after seal
6. No raw data ever

**Break any one → legal collapse.**

---

## 13. Engineering Reality Check

This validator:

- Is stateless
- Is deterministic
- Is easy to test
- Is impossible to "half-pass"

**That's why it scales legally.**

---

## 14. Definition of Done (Step 2)

You are done when:

- Validator rejects unknown fields
- Validator blocks silently
- Validator produces zero artifacts on failure
- Engineering cannot "work around" it

If someone asks:

> "Can we make this more forgiving?"

The answer is:

> "Forgiveness is discoverable."

---

## 15. Implementation Mapping

| Validator Phase      | CanonSys Component     | Status                  |
| -------------------- | ----------------------- | ----------------------- |
| Phase 1 (Schema)     | Pydantic strict mode    | ✅ Aligned              |
| Phase 2 (Context)    | `workflow_type` enum    | ✅ Aligned              |
| Phase 3 (Authority)  | `RoleAuthorizationGate` | 🔴 Needs completion     |
| Phase 4 (Assertions) | Gate assertions         | ✅ Aligned              |
| Phase 5 (Evidence)   | CEP hash verification   | 🔴 Needs implementation |
| Phase 6 (Seal)       | RSA-4096 signing        | 🔴 Needs implementation |

---

## 16. Related Documents

- [PRD: Termination Decision Certification](./PRD-termination-decision-certification.md)
- [SPEC: Universal Certificate Schema](./SPEC-universal-certificate-schema.md)
- [SPEC: UCS Validation Ruleset](./SPEC-ucs-validation-ruleset.md)
- [PRD: Certified Evidence Packet](./PRD-certified-evidence-packet.md)
