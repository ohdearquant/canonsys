---
# Core Fields (REQUIRED)
doc_type: ADR
title: "ADR-020: RFC 3161 Timestamp Attestation"
version: "2.0.0"
status: active
created: "2026-01-17"
updated: "2026-01-29"
decision_date: "2026-01-17"
by: "architect"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

# Chain Fields
predecessors: ["ADR-018-cryptography-rsa", "ADR-006-evidence-chain-cep"]
successors: []
supersedes: null
superseded_by: null

# Context Fields
tags:
  - timestamp
  - attestation
  - certification
  - evidence
related: ["TDS-020-timestamp-tsa"]
pr: null

# Quality Metrics
quality:
  confidence: 0.95
  sources: 5
  docs: full
---

# ADR-020: RFC 3161 Timestamp Attestation

## Context

### Problem Statement

CanonSys requires cryptographic proof that evidence existed at a specific point in time, independent
of internal clocks. RFC 3161 timestamp tokens contain CMS SignedData structures that require
verification for legal defensibility. The system needs a verification strategy that is both
cryptographically sound and operationally simple.

**Why This Matters**: Without proper timestamp verification, evidence timestamps could be challenged
in legal proceedings as potentially backdated or manipulated, undermining the entire audit trail.

### Background

**Current State**: RFC 3161 timestamps are needed for:

- **FCRA compliance**: Prove adverse action notices sent within required timeframes
- **Audit defense**: Demonstrate evidence was not backdated
- **Legal proceedings**: Tamper-evident timestamps from neutral third parties
- **FRE 902(13)**: Self-authentication of electronic records

**Driving Forces**:

- **Legal defensibility**: Actual cryptographic verification required
- **Simplicity**: CMS/PKCS#7 verification is complex and error-prone
- **Battle-tested tools**: OpenSSL provides decades of hardened verification
- **Honesty**: System must report actual verification status, not assumptions

### Assumptions

1. OpenSSL binary is available in production PATH
2. Evidence immutability allows separate timestamp acquisition workflow
3. Retry workflow acceptable for TSA network failures

### Constraints

| Type        | Constraint               | Impact                                 |
| ----------- | ------------------------ | -------------------------------------- |
| Technical   | No hand-rolled CMS code  | Must use established libraries/tools   |
| Legal       | FRE 902(13) compliance   | Requires actual signature verification |
| Operational | TSA network availability | Need retry and fallback mechanisms     |
| Security    | Anti-replay protection   | Nonce required in timestamp requests   |

---

## Decision

### Summary

**We will** use OpenSSL's battle-tested `ts -verify` command for RFC 3161 timestamp verification,
with honest reporting of what was actually verified.

### Rationale

**Key factors in the decision**:

1. **Battle-tested**: OpenSSL's timestamp verification hardened over decades
2. **Compliance**: Recognized by auditors and legal standards
3. **Simplicity**: ~130 lines vs 300+ lines of hand-rolled CMS verification
4. **Honesty**: `signature_valid` reflects reality, not assumptions

### Implementation Approach

Timestamp attestation is implemented in the `certification` vocabulary package:

```python
# hub/foundation/packages/certification/phrases/request_timestamp_attestation.py
@canon_phrase(
    Operable.from_structure(RequestTimestampAttestationSpecs),
    inputs={"content_hash", "target_type", "target_id", "tsa_name"},
    outputs={"id", "token_hash", "gen_time", "requested_at", ...},
)
async def request_timestamp_attestation(options, ctx):
    """Request RFC 3161 timestamp attestation.

    1. Creates timestamp request for content_hash
    2. Calls TSA service
    3. Persists attestation record
    """
```

Two distinct verification modes ensure honesty:

1. **Hash-only verification** (fast): `signature_valid=False`
2. **Full OpenSSL verification** (legally defensible): `signature_valid=True`

### Alternatives Considered

#### Alternative 1: Hand-Rolled CMS Verification

**Description**: 300+ lines of CMS/PKCS#7 parsing and signature verification.

| Criterion       | Score (1-5) | Notes                             |
| --------------- | ----------- | --------------------------------- |
| Correctness     | 2           | Complex, error-prone              |
| Audit-friendly  | 2           | Auditors prefer established tools |
| Maintainability | 2           | Requires crypto expertise         |

**Why Not Chosen**: Violates "no hand-rolled crypto" principle; complex, error-prone, not
auditor-friendly.

#### Alternative 2: Python cryptography Library Only

**Description**: Use `cryptography` library's CMS support exclusively.

| Criterion    | Score (1-5) | Notes                                  |
| ------------ | ----------- | -------------------------------------- |
| Completeness | 2           | No high-level timestamp verification   |
| Complexity   | 3           | Still requires significant custom code |
| Portability  | 5           | Pure Python, no subprocess             |

**Why Not Chosen**: Library doesn't expose high-level timestamp verification; would still require
significant custom code for certificate chain building.

### Decision Matrix

| Criterion          | Weight | Hand-Rolled | Python Only | OpenSSL ts |
| ------------------ | ------ | ----------- | ----------- | ---------- |
| Correctness        | 35%    | 2           | 3           | 5          |
| Audit compliance   | 30%    | 2           | 3           | 5          |
| Simplicity         | 20%    | 2           | 3           | 5          |
| Portability        | 15%    | 4           | 5           | 3          |
| **Weighted Total** | 100%   | **2.30**    | **3.30**    | **4.70**   |

---

## Consequences

### Positive Consequences

1. **Legal defensibility**: Actual cryptographic verification via OpenSSL
2. **Honesty**: `signature_valid` reflects reality, not assumptions
3. **Simplicity**: Deleted 728 lines of orphaned certificate validator code
4. **Security**: Nonce enabled by default, circuit breakers separated

### Negative Consequences

1. **OpenSSL dependency**: Requires OpenSSL binary in PATH
2. **Subprocess overhead**: `verify_with_openssl()` spawns process (~50ms)

### Neutral Consequences

1. **Two verification modes**: Callers must choose appropriate mode for their use case

### Risks

| Risk                     | Likelihood | Impact | Mitigation                        |
| ------------------------ | ---------- | ------ | --------------------------------- |
| OpenSSL not in PATH      | L          | H      | Container image includes OpenSSL  |
| TSA service unavailable  | M          | M      | Retry workflow, backup TSA        |
| Subprocess spawn failure | L          | M      | Graceful degradation to hash-only |

### Dependencies Introduced

| Dependency | Type   | Version | Stability | Notes                     |
| ---------- | ------ | ------- | --------- | ------------------------- |
| OpenSSL    | Binary | 1.1.1+  | Stable    | Required for `ts -verify` |

### Migration Impact

**Backwards Compatibility**: Compatible - existing timestamps can be verified.

**Migration Steps**:

1. Ensure OpenSSL binary available in deployment
2. Update verification calls to use appropriate mode
3. Add CA bundle path for chain validation

---

## Verification

### Success Criteria

- [x] Hash-only verification returns `signature_valid=False` (honest)
- [x] OpenSSL verification returns `signature_valid=True` when valid
- [x] Nonce enabled by default for anti-replay
- [x] Circuit breakers separate for primary/backup TSA

### Metrics to Track

| Metric                   | Baseline | Target  | Review Date |
| ------------------------ | -------- | ------- | ----------- |
| TSA request success rate | N/A      | > 99.9% | 2026-03-01  |
| Verification latency p99 | N/A      | < 100ms | 2026-03-01  |
| Retry success rate       | N/A      | > 99%   | 2026-03-01  |

### Review Schedule

- **Initial Review**: 2026-04-01 (3 months after deployment)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Security Team

---

## Vocabulary Mapping

| Phrase                             | Package         | Purpose                                                              |
| ---------------------------------- | --------------- | -------------------------------------------------------------------- |
| `request_timestamp_attestation`    | `certification` | Create RFC 3161 timestamp request for content hash                   |
| `record_attestation`               | `certification` | Record typed attestation (process, ER clearance, executive override) |
| `verify_chain_of_custody_complete` | `evidence`      | Verify evidence chain integrity before timestamping                  |
| `seal_cep`                         | `evidence`      | Seal certified evidence packet for timestamping                      |

**Package Path**: `hub/foundation/packages/certification/`

---

## Control Surface Integration

Timestamp attestation is used across multiple control surfaces for certification phases:

| Surface                    | Charter                                          | Key Phrases                              |
| -------------------------- | ------------------------------------------------ | ---------------------------------------- |
| Tax Jurisdiction Change    | `surfaces/finance/tax_jurisdiction_change.canon` | `record_attestation`, `emit_certificate` |
| Cross-Border Data Transfer | `surfaces/data/cross_border_transfer.canon`      | `seal_cep`, `verify_cep_sealed`          |

---

## Related Artifacts

### Builds On

- `ADR-018-cryptography-rsa`: RSA-4096 and SHA-256 used for timestamps
- `ADR-006-evidence-chain-cep`: Evidence chains use timestamp attestation
- `ADR-003-immutability`: Separate attestation entity preserves Evidence immutability

### Impacts

- `TDS-020-timestamp-tsa`: Technical implementation details

---

## References

- **RFC 3161**: Time-Stamp Protocol (TSP)
- **FRE 902(13)**: Self-authentication of electronic records
- **eIDAS Article 41**: Qualified electronic time stamps
- **Vocabulary Package**: `hub/foundation/packages/certification/`
- **TSA Infrastructure**: `libs/canon/src/canon/utils/tsa/`
