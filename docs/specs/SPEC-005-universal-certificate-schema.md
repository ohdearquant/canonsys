# Technical Specification: Universal Certificate Schema (UCS-v1)

**Author**: Jason La Barbera **Captured**: 2026-01-13 **Status**: Ready for Implementation

---

## 1. Design Philosophy

This schema is designed for **High-Stakes Administrative Decisions**.

It is not a database row. It is a **self-contained, cryptographically verifiable artifact**.

### Core Rules

| Rule                      | Description                                                                    |
| ------------------------- | ------------------------------------------------------------------------------ |
| **Polymorphic Payload**   | The `decision_context` dictates required fields, but the envelope is universal |
| **Pointer-Only Evidence** | Never contains narrative data. Only pointers (hashes/IDs) to sanitized CEPs    |
| **Identity-as-Authority** | The `issuer` block captures the role claiming authority, not just the user ID  |

---

## 2. JSON Schema Structure

```json
{
  "meta": {
    "certificate_id": "UUID-v4",
    "schema_version": "1.0",
    "issued_at_utc": "ISO-8601",
    "environment": "production"
  },

  "context": {
    "workflow_type": "TERMINATION_DECISION",
    "subject_token": "SHA256(employee_id + salt)",
    "jurisdiction_code": "US-CA"
  },

  "authority": {
    "issuer_id": "user_12345",
    "issuer_role": "HRBP_DIRECTOR",
    "delegation_chain": null
  },

  "assertions": {
    "policy_basis": {
      "code": "POL-TERM-004",
      "exception_flag": false
    },
    "risk_acceptance": true,
    "parity_attested": true,
    "er_clearance": {
      "cleared": true,
      "timestamp": "ISO-8601",
      "system_ref": "ER_CASE_DB_CHECK_ID"
    }
  },

  "evidence_pointers": [
    {
      "cep_id": "CEP-8892-X",
      "type": "PERFORMANCE_DATA_PACKET",
      "hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    }
  ],

  "seal": {
    "previous_cert_hash": "sha256:...",
    "signature": "RSA-4096_SIGNATURE_OF_ABOVE_FIELDS"
  }
}
```

---

## 3. Field Definitions

### 3.1 Meta Block

| Field            | Type     | Description                              |
| ---------------- | -------- | ---------------------------------------- |
| `certificate_id` | UUID-v4  | Globally unique identifier               |
| `schema_version` | string   | Schema version for forward compatibility |
| `issued_at_utc`  | ISO-8601 | Immutable timestamp                      |
| `environment`    | enum     | `production` or `simulation`             |

### 3.2 Context Block

| Field               | Type   | Description                                                                       |
| ------------------- | ------ | --------------------------------------------------------------------------------- |
| `workflow_type`     | enum   | `TERMINATION_DECISION`, `INVESTIGATION_CLOSE`, `PIP_FAIL`, `EXCEPTIONAL_APPROVAL` |
| `subject_token`     | string | Privacy-preserving identifier: `SHA256(employee_id + salt)`                       |
| `jurisdiction_code` | string | Determines applicable policy logic (e.g., `US-CA`, `US-NYC`)                      |

### 3.3 Authority Block

| Field              | Type       | Description                               |
| ------------------ | ---------- | ----------------------------------------- |
| `issuer_id`        | string     | Who clicked the button                    |
| `issuer_role`      | enum       | The seat of authority (role > individual) |
| `delegation_chain` | array/null | If acting on behalf of someone else       |

### 3.4 Assertions Block

The control surface inputs. Varies by `workflow_type`.

**For TERMINATION_DECISION:**

| Field                         | Type     | Description                            |
| ----------------------------- | -------- | -------------------------------------- |
| `policy_basis.code`           | string   | Policy code reference, not text        |
| `policy_basis.exception_flag` | boolean  | Explicit exception invoked             |
| `risk_acceptance`             | boolean  | "I accept the legal exposure"          |
| `parity_attested`             | boolean  | "I confirm consistency with precedent" |
| `er_clearance.cleared`        | boolean  | ER system clearance                    |
| `er_clearance.timestamp`      | ISO-8601 | When clearance was obtained            |
| `er_clearance.system_ref`     | string   | ER system reference ID                 |

### 3.5 Evidence Pointers Block

| Field    | Type   | Description                                                    |
| -------- | ------ | -------------------------------------------------------------- |
| `cep_id` | string | Certified Evidence Packet ID                                   |
| `type`   | enum   | `PERFORMANCE_DATA_PACKET`, `INVESTIGATION_SUMMARY`, etc.       |
| `hash`   | string | SHA256 hash of CEP content. If CEP changes, certificate breaks |

**Critical: No content. Only ID and hash.**

### 3.6 Seal Block

| Field                | Type        | Description                            |
| -------------------- | ----------- | -------------------------------------- |
| `previous_cert_hash` | string/null | For certificate chaining (optional)    |
| `signature`          | string      | RSA-4096 signature of all above fields |

---

## 4. The "Kill Shot" Mechanics

### 4.1 Evidence Pointers — Discovery Severance

**Scenario:**

> Plaintiff Attorney: "We demand the TDC." Company: "Here is the TDC." Plaintiff Attorney: "It just
> lists CEP-8892-X. What does that say?" Company: "That references a Certified Evidence Packet. The
> TDC proves we relied on certified evidence. If you want the evidence, you must request the
> specific CEP, which is a separate, sanitized legal document."

**Result:** Discovery is severed. They cannot get raw Slack messages by subpoenaing the termination
record.

### 4.2 Authority Block — Role Enforcement

We separate `issuer_id` (who clicked) from `issuer_role` (who has power).

**Scenario:**

- Junior Manager clicks "Terminate"
- `issuer_role` = `MANAGER_L1`
- `workflow_type` = `TERMINATION`
- Validator: "MANAGER_L1 is not authorized to sign TERMINATION certificates"
- **Result: BLOCK**

### 4.3 Seal — Tamper Detection

Once the signature is generated, the JSON is effectively "printed to PDF."

**If IT tries to update `policy_basis` later:**

- Signature verification fails against content
- Certificate renders as `INVALID / TAMPERED`

---

## 5. Workflow Type Variations

The schema is polymorphic. Same envelope, different assertions.

| Workflow Type          | Required Assertions                                  |
| ---------------------- | ---------------------------------------------------- |
| `TERMINATION_DECISION` | `parity_attested`, `risk_acceptance`, `er_clearance` |
| `INVESTIGATION_CLOSE`  | `finding_classification`, `interview_chain_complete` |
| `PIP_FAIL`             | `observation_period_complete`, `feedback_documented` |
| `EXCEPTIONAL_APPROVAL` | `override_reason`, `risk_acknowledged`               |

**Infrastructure (storage, signing, verification, UI) remains identical.**

---

## 6. Validation Rules

```python
def validate_certificate(cert: dict) -> Result:
    # 1. Schema version check
    if cert["meta"]["schema_version"] not in SUPPORTED_VERSIONS:
        return Fail("Unsupported schema version")

    # 2. Authority check
    if not is_authorized(cert["authority"]["issuer_role"], cert["context"]["workflow_type"]):
        return Fail("Issuer role not authorized for workflow type")

    # 3. Evidence integrity check
    for pointer in cert["evidence_pointers"]:
        cep = fetch_cep(pointer["cep_id"])
        if hash(cep) != pointer["hash"]:
            return Fail("CEP hash mismatch - evidence tampered")

    # 4. Signature verification
    if not verify_signature(cert["seal"]["signature"], cert):
        return Fail("Invalid signature - certificate tampered")

    # 5. Workflow-specific assertions
    if not validate_assertions(cert["context"]["workflow_type"], cert["assertions"]):
        return Fail("Missing required assertions for workflow type")

    return Success()
```

---

## 7. Storage Requirements

| Requirement  | Implementation                                     |
| ------------ | -------------------------------------------------- |
| Immutability | Write-once storage, no UPDATE path                 |
| Integrity    | Hash chain via `previous_cert_hash`                |
| Auditability | All access logged                                  |
| Availability | Replicated across regions                          |
| Retention    | Per jurisdiction requirements (typically 7+ years) |

---

## 8. API Surface

### Create Certificate

```
POST /api/v1/certificates
Authorization: Bearer <token>
Content-Type: application/json

{
  "workflow_type": "TERMINATION_DECISION",
  "subject_token": "...",
  "assertions": { ... },
  "evidence_pointers": [ ... ]
}

Response: 201 Created
{
  "certificate_id": "...",
  "seal": { ... }
}
```

### Verify Certificate

```
GET /api/v1/certificates/{id}/verify

Response: 200 OK
{
  "valid": true,
  "checks": {
    "signature": "pass",
    "evidence_integrity": "pass",
    "authority": "pass"
  }
}
```

### Retrieve Certificate

```
GET /api/v1/certificates/{id}

Response: 200 OK
{ full certificate JSON }
```

---

## 9. Related Documents

- [PRD: Termination Decision Certification](./PRD-termination-decision-certification.md)
- CEP: Certified Evidence Packet (specification pending)
- Integration Guide (pending)

---

## 10. Architecture Alignment

This schema directly implements CanonSys's formal capability model:

| UCS-v1 Concept           | Formal Model Equivalent       |
| ------------------------ | ----------------------------- |
| `evidence_pointers.hash` | Immutable hash chain          |
| `authority.issuer_role`  | Capability-based authority    |
| `seal.signature`         | Cryptographic verification    |
| `previous_cert_hash`     | Backward-pointer supersession |

The Lean4 formal proofs enforce these properties at the type level.
