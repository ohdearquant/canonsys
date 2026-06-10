---
doc_type: TDS
title: "Technical Design Specification: UCS Verification"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["evidence", "certification"]
charters: []
---

# Technical Design Specification: UCS Verification

## 1. Overview

### 1.1 Purpose

The UCS (Unified Compliance Subject) Verification system validates certificates against compliance
rules using OPA/Rego delegation. Core components:

1. **UCSValidator** - Python wrapper for ucs_validator.rego policy
2. **UCSDataProvider** - Supplies CEP and signing key context to OPA
3. **UCS Transform** - Converts certificate data to UCS-v1 JSON format
4. **Fail-Closed Semantics** - Any error results in BLOCKED status

### 1.2 Design Principles

1. **Fail-Closed**: Any error = BLOCKED (never fail-open)
2. **Type-Safe**: Python enums map to Rego decisions
3. **Time-Aware**: Signing key windows and CEP expiration enforced
4. **Privacy-First**: Subject IDs tokenized via SHA256

## 2. Vocabulary Integration

Verification logic is expressed through vocabulary phrases in `evidence` and `certification`
packages.

### 2.1 Evidence Package Phrases

| Phrase                             | Purpose                                                    |
| ---------------------------------- | ---------------------------------------------------------- |
| `verify_chain_of_custody_complete` | Validates complete evidence chain from creation to sealing |
| `verify_cep_sealed`                | Confirms CEP is sealed and cannot be modified              |
| `verify_cep_not_expired`           | Checks CEP temporal validity                               |
| `require_cep_hash_match`           | Validates hash integrity between certificate and CEP       |
| `verify_evidence_integrity`        | Detects evidence tampering                                 |
| `verify_chain`                     | Validates hash chain linkage                               |

### 2.2 Certification Package Phrases

| Phrase                          | Purpose                              |
| ------------------------------- | ------------------------------------ |
| `check_certificate_exists`      | Confirms certificate has been issued |
| `sign_certificate`              | Cryptographic signature creation     |
| `request_timestamp_attestation` | RFC 3161 timestamp attestation       |

## 3. UCS-v1 Schema

```json
{
  "meta": {
    "certificate_id": "cert-001",
    "schema_version": "1.0",
    "issued_at_utc": "2026-01-15T10:30:00Z"
  },
  "context": {
    "workflow_type": "TERMINATION_DECISION",
    "subject_token": "7f83b1657ff1fc53...",
    "jurisdiction_code": "US-NYC"
  },
  "authority": {
    "issuer_id": "user_456",
    "issuer_role": "HRBP_DIRECTOR"
  },
  "assertions": {
    "risk_acceptance": true,
    "parity_attested": true
  },
  "evidence_pointers": [
    { "cep_id": "CEP-001", "type": "CEP_CONDUCT_RECORD", "hash": "sha256:abc" }
  ],
  "seal": {
    "payload_hash": "sha256:xyz",
    "signature": "RSA-4096 sig...",
    "signing_key_id": "key-456"
  }
}
```

## 4. Validation Flow

```
UCS Certificate
    ↓
schema_ok? → No → BLOCKED: Schema invalid
    ↓ Yes
workflow_ok? → No → BLOCKED: Workflow invariants
    ↓ Yes
authority_ok? → No → BLOCKED: Role not authorized
    ↓ Yes
evidence_ok? → No → BLOCKED: Evidence invalid
    ↓ Yes
signing_ok? → No → BLOCKED: Signing invalid
    ↓ Yes
APPROVED
```

## 5. Fail-Closed Semantics

```python
# Default deny in Rego
default allow = false
default decision = {"status": "BLOCKED", "reason": "DEFAULT_DENY"}

# Python error handling
try:
    result = await self._engine.evaluate_single(...)
except Exception as e:
    # ANY error = BLOCKED
    return ValidationResult(
        status=ValidationStatus.BLOCKED,
        reason=f"Validation error: {e}",
    )
```

| Condition                     | Result  |
| ----------------------------- | ------- |
| OPA evaluation error          | BLOCKED |
| Missing CEP in data.ceps      | BLOCKED |
| Expired CEP                   | BLOCKED |
| Signing key not found         | BLOCKED |
| Key validity window violation | BLOCKED |
| Unauthorized role             | BLOCKED |

## 6. Integration Points

### Dependencies

| Component               | Purpose                        |
| ----------------------- | ------------------------------ |
| `evidence` package      | CEP validation phrases         |
| `certification` package | Certificate validation phrases |
| PolicyEngine            | Rego evaluation                |
| EnginePool              | Engine pooling                 |

### Dependents

| Component                      | Purpose                    |
| ------------------------------ | -------------------------- |
| Decision Certificate (ADR-007) | Certificate validation     |
| Evidence Chain CEP (ADR-006)   | CEP integrity verification |

## 7. Testing Requirements

| Test Category          | Coverage Target        |
| ---------------------- | ---------------------- |
| Schema validation      | 100%                   |
| Workflow invariants    | 100% per workflow type |
| Role authorization     | 100%                   |
| CEP pointer validation | 100%                   |
| Signing key windows    | 100%                   |
| Fail-closed paths      | 100%                   |

## 8. References

- **Evidence Package**: `hub/foundation/packages/evidence/`
- **Certification Package**: `hub/foundation/packages/certification/`
- **Related**: TDS-007-decision-certificate, TDS-006-evidence-chain-cep
