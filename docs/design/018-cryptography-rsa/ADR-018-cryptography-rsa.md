---
# Core Fields (REQUIRED)
doc_type: ADR
title: "ADR-018: Cryptography - RSA-4096, SHA-256, and PKCS1v15"
version: "2.0.0"
status: active
created: "2026-01-15"
updated: "2026-01-29"
decision_date: "2026-01-15"
by: "architect"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

# Chain Fields
predecessors: ["ADR-003-immutability", "ADR-006-evidence-chain-cep"]
successors: ["ADR-020-timestamp-tsa"]
supersedes: null
superseded_by: null

# Context Fields
tags:
  - cryptography
  - security
  - certification
related: ["TDS-018-cryptography-rsa"]
pr: null

# Quality Metrics
quality:
  confidence: 0.95
  sources: 5
  docs: full
---

# ADR-018: Cryptography - RSA-4096, SHA-256, and PKCS1v15

## Context

### Problem Statement

CanonSys requires cryptographic primitives for content integrity verification, evidence chain
linking, digital signatures on certificates, and timestamp attestation. The system must select
algorithms that remain secure for 10+ years while maintaining operational compatibility.

**Why This Matters**: Incorrect algorithm choices could render evidence legally inadmissible,
compromise audit trails, or require costly migrations when algorithms are deprecated.

### Background

**Current State**: CanonSys uses cryptography for four core purposes:

1. **Content integrity**: `content_hash` on every Entity proves data hasn't been tampered with
2. **Evidence chains**: `chain_hash` links evidence records in tamper-evident sequences
3. **Digital signatures**: Decision certificates are signed for non-repudiation
4. **Timestamp attestation**: RFC 3161 tokens prove when content existed

**Driving Forces**:

- **Longevity**: Evidence may be verified in legal proceedings decades later
- **Regulatory acceptance**: Must satisfy NIST, SOC2, GDPR, and PCI DSS auditors
- **HSM/KMS compatibility**: Must work with AWS KMS, Azure Key Vault, GCP Cloud KMS, HashiCorp Vault

### Assumptions

1. Evidence retention period is 7-10 years minimum
2. HSM/KMS integration is required for production deployments
3. Quantum computing threats are 10+ years away for RSA-4096

### Constraints

| Type       | Constraint                   | Impact                                     |
| ---------- | ---------------------------- | ------------------------------------------ |
| Technical  | HSM/KMS compatibility        | Limits algorithm choices to universal ones |
| Regulatory | NIST SP 800-131A compliance  | Minimum RSA-3072 post-2030                 |
| Timeline   | 10+ year evidence retention  | Algorithms must remain secure long-term    |
| Business   | Audit defensibility required | Must use recognized standards              |

---

## Decision

### Summary

**We will** use RSA-4096 with PKCS#1 v1.5 padding and SHA-256 for all cryptographic operations, with
fail-closed verification semantics.

### Rationale

**Key factors in the decision**:

1. **NIST Compliance**: RSA-4096 exceeds NIST SP 800-131A requirements (3072-bit minimum post-2030)
2. **Universal Compatibility**: PKCS#1 v1.5 is supported by all major HSMs and KMS providers
3. **Simplicity**: Single hash algorithm (SHA-256) reduces complexity and error surface

### Implementation Approach

Cryptographic primitives are exposed through the `certification` vocabulary package:

```python
# hub/foundation/packages/certification/phrases/sign_certificate.py
@canon_phrase(
    Operable.from_structure(SignCertificateSpecs),
    inputs={"certificate_id"},
    outputs={"certificate_id", "signing_key_id", "signature", "signed_at"},
)
async def sign_certificate(options, ctx):
    """Sign with RSA-4096 + PKCS1v15 + SHA-256."""
```

Core utilities in `libs/canon/src/canon/utils/`:

- `hashing.py`: `compute_hash()`, `compute_chain_hash()`
- `security/signer.py`: `sign_payload()`, `verify_signature()`

### Alternatives Considered

#### Alternative 1: RSA-2048

**Description**: Standard key size in many legacy systems.

| Criterion       | Score (1-5) | Notes                           |
| --------------- | ----------- | ------------------------------- |
| Security margin | 2           | NIST recommends 3072+ post-2030 |
| Performance     | 5           | 4x faster than 4096             |
| Compatibility   | 5           | Universal support               |

**Why Not Chosen**: Insufficient security margin for 10+ year evidence retention.

#### Alternative 2: ECDSA P-384

**Description**: Elliptic curve signatures with smaller keys.

| Criterion       | Score (1-5) | Notes                       |
| --------------- | ----------- | --------------------------- |
| Security margin | 5           | Equivalent to RSA-7680      |
| Performance     | 5           | Faster signing/verification |
| Compatibility   | 3           | HSM support less universal  |

**Why Not Chosen**: Variable HSM/KMS support creates operational complexity.

#### Alternative 3: PSS Padding

**Description**: Probabilistic Signature Scheme, theoretically superior to PKCS#1 v1.5.

| Criterion     | Score (1-5) | Notes                           |
| ------------- | ----------- | ------------------------------- |
| Security      | 5           | Provably secure in ROM          |
| Compatibility | 3           | Some HSMs require configuration |
| Simplicity    | 3           | More complex padding scheme     |

**Why Not Chosen**: No practical security benefit for our scale; compatibility issues.

### Decision Matrix

| Criterion          | Weight | RSA-2048 | ECDSA P-384 | RSA-4096+PKCS1v15 |
| ------------------ | ------ | -------- | ----------- | ----------------- |
| Security margin    | 35%    | 2        | 5           | 4                 |
| HSM/KMS compat     | 30%    | 5        | 3           | 5                 |
| Performance        | 15%    | 5        | 5           | 3                 |
| Simplicity         | 20%    | 4        | 3           | 5                 |
| **Weighted Total** | 100%   | **3.55** | **4.00**    | **4.35**          |

---

## Consequences

### Positive Consequences

1. **15-20 year security margin**: RSA-4096 exceeds NIST requirements through 2030+
2. **Universal HSM/KMS support**: PKCS#1 v1.5 works with all major providers
3. **Regulatory compliance**: All algorithms are NIST SP 800-131A approved
4. **Fail-closed verification**: No information leakage; consistent behavior on error

### Negative Consequences

1. **Performance overhead**: RSA-4096 signing is ~4x slower than RSA-2048 (acceptable for audit use)
2. **Key storage size**: 4096-bit keys are larger (minimal impact with modern storage)
3. **No algorithm agility**: Hardcoded algorithms require code changes to migrate

### Neutral Consequences

1. **Single hash algorithm**: SHA-256 for everything simplifies code but removes flexibility

### Risks

| Risk                        | Likelihood | Impact | Mitigation                                         |
| --------------------------- | ---------- | ------ | -------------------------------------------------- |
| SHA-256 cryptographic break | L          | H      | Monitor NIST advisories; plan SHA-3 migration path |
| HSM key rotation failure    | M          | M      | Implement prospective revocation pattern           |
| Quantum computing threat    | L          | H      | RSA-4096 provides 10+ year buffer                  |

### Dependencies Introduced

| Dependency     | Type    | Version | Stability | Notes                           |
| -------------- | ------- | ------- | --------- | ------------------------------- |
| `cryptography` | Library | 41.0+   | Stable    | Python cryptography hazmat APIs |
| OpenSSL        | System  | 1.1.1+  | Stable    | For ts -verify in TSA           |

### Migration Impact

**Backwards Compatibility**: Compatible - new signing does not break existing hashes.

**Migration Steps**:

1. Deploy new signing key via KMS
2. Update KeyRegistry with new key version
3. Signatures continue with prospective revocation semantics

---

## Verification

### Success Criteria

- [x] RSA-4096 key generation works with all target HSMs (AWS, Azure, GCP)
- [x] Signature verification returns False on any error (fail-closed)
- [x] Chain hash computation is deterministic (same input = same hash)
- [x] Content hash limit (10 MB) prevents DoS attacks

### Metrics to Track

| Metric                | Baseline | Target   | Review Date |
| --------------------- | -------- | -------- | ----------- |
| Signing latency (p99) | N/A      | < 100ms  | 2026-03-01  |
| Verification failures | N/A      | < 0.001% | 2026-03-01  |
| Key rotation success  | N/A      | 100%     | 2026-03-01  |

### Review Schedule

- **Initial Review**: 2026-04-01 (3 months after deployment)
- **Ongoing Reviews**: Annually
- **Review Owner**: Security Team

---

## Vocabulary Mapping

| Phrase                          | Package         | Purpose                                 |
| ------------------------------- | --------------- | --------------------------------------- |
| `sign_certificate`              | `certification` | Sign decision certificate with RSA-4096 |
| `request_timestamp_attestation` | `certification` | Request RFC 3161 timestamp              |
| `record_attestation`            | `certification` | Record typed attestation                |
| `emit_certificate`              | `certification` | Emit signed decision certificate        |

**Package Path**: `hub/foundation/packages/certification/`

---

## Related Artifacts

### Builds On

- `ADR-003-immutability`: Immutability via supersession requires hash verification
- `ADR-006-evidence-chain-cep`: Evidence chains use `compute_chain_hash()`

### Impacts

- `TDS-018-cryptography-rsa`: Technical implementation details
- `ADR-020-timestamp-tsa`: RFC 3161 uses these crypto primitives

---

## References

- **NIST SP 800-131A**: Transitioning to Use of Cryptographic Algorithms
- **RFC 3447**: PKCS #1: RSA Cryptography Specifications
- **SOC2 CC7.1**: System Operations - Change Management
- **Vocabulary Package**: `hub/foundation/packages/certification/`
- **Core Utils**: `libs/canon/src/canon/utils/hashing.py`, `libs/canon/src/canon/utils/security/`
