---
doc_type: TDS
title: "Technical Design Specification: Decision Certificate"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["certification"]
charters: ["layoff_rif", "wire_transfer", "settlement_authority"]
---

# Technical Design Specification: Decision Certificate

## 1. Overview

### 1.1 Purpose

The Decision Certificate is the **primary product artifact** of CanonSys - a verifiable record that
proves process was followed, not that the outcome was correct.

### 1.2 Vocabulary Package

All certificate operations are implemented in the `certification` vocabulary package:

```
hub/foundation/packages/certification/
├── phrases/
│   ├── emit_certificate.py      # Create provisional certificate
│   ├── mint_certificate.py      # Finalize (temporal cliff)
│   ├── sign_certificate.py      # RSA-4096 signing
│   ├── supersede_certificate.py # Replace with audit trail
│   ├── record_attestation.py    # Human sign-off
│   └── build_certificate_summary.py
├── certificate.py               # Entity definition
└── types/                       # Supporting types
```

### 1.3 Platform Invariants

1. **Supersession Doctrine**: Certificates are never revoked, only superseded
2. **Zero-Warnings Rule**: No certificate minted unless all gates pass
3. **Temporal Cliff**: MINTED marks irreversible immutability

## 2. Certificate Lifecycle

```
PROVISIONAL -> GATED -> MINTED -> SUPERSEDED
```

| State       | Mutability | Transition                                |
| ----------- | ---------- | ----------------------------------------- |
| PROVISIONAL | Editable   | `emit_certificate()` creates              |
| GATED       | Frozen     | All gates passed                          |
| MINTED      | Immutable  | `mint_certificate()` finalizes            |
| SUPERSEDED  | Immutable  | `supersede_certificate()` links successor |

## 3. Key Phrases

### 3.1 emit_certificate

Creates certificate in PROVISIONAL status with evidence binding.

**Inputs**: `action_type`, `subject_id`, `case_id`, `jurisdiction`, `evidence_ids`, `gates_passed`

**Outputs**: `id`, `tenant_id`, `status`, `created_at`, `content_hash`

See: `certification/phrases/emit_certificate.py`

### 3.2 mint_certificate

Transitions GATED -> MINTED. This is the **temporal cliff** - after minting, the certificate is
cryptographically sealed.

**Inputs**: `certificate_id`, `attestations`, `outcome`, `outcome_rationale`

**Outputs**: `id`, `status`, `minted_at`, `validation_hash`

See: `certification/phrases/emit_certificate.py` (mint_certificate function)

### 3.3 sign_certificate

Signs certificate with RSA-4096 + SHA-256 + PKCS1v15.

See: `certification/phrases/sign_certificate.py`

### 3.4 supersede_certificate

Creates new certificate with `supersedes_id` linking to predecessor. Original remains immutable.

See: `certification/phrases/supersede_certificate.py`

### 3.5 record_attestation

Records human sign-off with non-repudiation context (signer_id, role, method, IP, user agent).

See: `certification/phrases/record_attestation.py`

## 4. Control Surface Integration

The certification phrases are used in charter workflows:

| Surface              | Usage                                                                   |
| -------------------- | ----------------------------------------------------------------------- |
| RIF Layoff           | `emit_certificate()` in certification phase after dual approval         |
| Wire Transfer        | `emit_certificate()`, `record_attestation()` in certification phase     |
| Settlement Authority | `emit_certificate()`, `record_attestation()`, `verify_case_integrity()` |

Example from the RIF Layoff surface:

```
phase certification:
    require executive_attestation.passed
    await dual_signer_approval_completed
    require require_dual_approval()
    action emit_certificate()
    certify immutable
    evidence rif_inclusion_certificate
```

## 5. Entity Definition

See `certification/certificate.py` for the complete `DecisionCertificate` entity with embedded
models:

- `ModelIdentity` - AI model provenance
- `InputFingerprint` - Hash of inputs consumed
- `GateEvaluation` - Record of gate checks
- `ReviewBehavior` - Anti-rubber stamp metrics
- `AttestationRecord` - Human sign-off

## 6. Anti-Patterns

- **Do NOT** revoke certificates (use supersession)
- **Do NOT** mint without UCS validation
- **Do NOT** delete immutable records
- **Do NOT** skip gate evaluations

## 7. References

- **ADR**: ADR-007-decision-certificate
- **Package**: `hub/foundation/packages/certification/`
- **Charters**: `hub/charters/surfaces/`
