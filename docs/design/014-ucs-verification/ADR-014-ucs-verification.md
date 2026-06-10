---
doc_type: ADR
title: "ADR-014: UCS Verification Protocol"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["evidence", "certification"]
charters: []
---

# ADR-014: UCS Verification Protocol

## Status

Accepted

## Context

CanonSys requires a uniform standard for verifying certificates before high-risk employment actions
execute. Without standardization:

1. Inconsistent verification across different code paths
2. Missing evidence binding - certificates reference CEPs without hash verification
3. Authority gaps - role authorization checked ad-hoc
4. Temporal vulnerabilities - signing key validity windows not enforced
5. Privacy leakage - subject identifiers exposed in verification payloads

### Decision Drivers

- Compliance substrate: verification at the gate, not in the action
- Fail-closed by design: errors block action rather than allow it
- Audit completeness: every verification produces evidence
- Uniform semantics: all high-risk actions verified the same way

## Decision

### D1: UCS Verification as Pre-Condition for High-Risk Actions

Uniform verification before all high-risk actions (termination, investigation close, PIP failure,
executive override, adverse action).

**Implementation**: See vocabulary packages `evidence` and `certification`:

- `verify_chain_of_custody_complete` - validates CEP evidence chain integrity
- `check_certificate_exists` - confirms certificate has been issued
- `verify_cep_sealed` - ensures CEP is sealed and immutable
- `verify_evidence_integrity` - validates hash integrity of evidence

### D2: Three-State Validation Result with Fail-Closed Default

```python
class ValidationStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
```

Every path that does not explicitly reach `allow = true` results in BLOCKED. Any exception during
validation returns BLOCKED status.

### D3: Evidence Binding via CEP Hash Matching

Certificates include CEP content hash for integrity verification. Evidence pointers validated via:

- Hash match: CEP content unchanged since certificate created
- Type match: prevent CEP type-swap attacks
- Status = ACTIVE: CEP not revoked or expired
- Temporal validity: CEP within validity window

**Implementation**: See `require_cep_hash_match` and `verify_cep_reference` phrases.

### D4: UCS Gate Integration with Policy Gates

UCS verification happens before policy gates in layered defense:

```
UCS Verification (Certificate) -> Policy Gates (Runtime) -> Action Execution
```

### D5: Subject Tokenization for Privacy

Subject IDs are SHA256-hashed with tenant-specific salt before entering OPA evaluation. No PII in
verification payloads or OPA logs.

## Vocabulary Mapping

| Phrase                             | Package         | Purpose                           |
| ---------------------------------- | --------------- | --------------------------------- |
| `verify_chain_of_custody_complete` | `evidence`      | Validates complete evidence chain |
| `check_certificate_exists`         | `certification` | Confirms certificate existence    |
| `verify_cep_sealed`                | `evidence`      | Ensures CEP immutability          |
| `verify_cep_not_expired`           | `evidence`      | Temporal validity check           |
| `require_cep_hash_match`           | `evidence`      | Hash integrity verification       |
| `verify_evidence_integrity`        | `evidence`      | Evidence tampering detection      |
| `verify_cep_reference`             | `evidence`      | CEP pointer validation            |

## Alternatives Considered

### Alternative 1: Ad-hoc Verification

Each action verifies what it needs. Rejected: inconsistent, error-prone.

### Alternative 2: Post-action Verification

Verify after action, rollback if invalid. Rejected: rollback complexity.

### Alternative 3: Binary (pass/fail) Validation

No escalation path. Rejected: no handling for edge cases requiring human review.

## Consequences

### Positive

- Consistent verification across all high-risk paths
- Clear pre-condition semantics (verify before execute)
- Evidence produced even on blocked actions
- Tamper-evident via CEP hash matching

### Negative

- Additional latency on high-risk action path (~10-50ms)
- Requires certificate transformation before verification
- OPA engine must be available (dependency)

## References

- **Vocabulary Package**: `hub/foundation/packages/evidence/`
- **Vocabulary Package**: `hub/foundation/packages/certification/`
- **Related ADRs**: ADR-006-evidence-chain-cep, ADR-007-decision-certificate, ADR-008-policy-gates
