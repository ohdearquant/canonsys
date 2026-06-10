---
doc_type: ADR
title: "ADR-007: Decision Certificate Architecture"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: ["certification"]
charters: ["layoff_rif", "wire_transfer", "settlement_authority"]
---

# ADR-007: Decision Certificate Architecture

## Status

Accepted

## Context

CanonSys exists to make people operations decisions **provable**. Every significant decision -
terminations, adverse actions, PIP initiations, rejections - requires an immutable, verifiable
record that proves process was followed correctly.

The certificate is the **primary product artifact** - it proves process adherence, not outcome
correctness.

### Decision Drivers

- **Audit-grade proof**: Must satisfy SOC2, FCRA, EU AI Act evidence requirements
- **Cryptographic integrity**: Signatures must remain verifiable for 10+ years
- **Immutability**: Once minted, certificate content cannot change
- **Kill Chain enforcement**: No decision reaches production without validation approval
- **Evidence binding**: Certificates reference but don't contain evidence

## Decision

### D1: Certificate Lifecycle State Machine

Certificates progress through four states with irreversible transitions:

```
PROVISIONAL -> GATED -> MINTED -> SUPERSEDED
```

**Implementation**: See vocabulary package `certification` - specifically:

- `emit_certificate` - Creates certificate in PROVISIONAL status
- `mint_certificate` - Transitions GATED -> MINTED (temporal cliff)

### D2: Supersession Doctrine (Never Revoke)

Certificates are **never revoked**, only superseded. This preserves complete audit history.

**Implementation**: See vocabulary package `certification`:

- `supersede_certificate` - Creates successor, marks predecessor as SUPERSEDED

### D3: RSA-4096 Signing with Content Hash Chain

Certificates use RSA-4096 signatures with SHA-256 hashes for tamper evidence.

**Implementation**: See vocabulary package `certification`:

- `sign_certificate` - Signs with RSA-4096 + SHA-256 + PKCS1v15

### D4: Attestation Records for Human Sign-Off

Non-repudiation records prove specific humans approved specific decisions.

**Implementation**: See vocabulary package `certification`:

- `record_attestation` - Links human identity to decision approval
- `build_certificate_summary` - Aggregates certificate data for display

**Charter Integration**: Control surfaces using this pattern:

- the RIF Layoff surface - RIF layoff inclusion (executive attestation, dual approval, certification phase)
- the Wire Transfer surface - Large wire transfer (CFO approval, certification phase)
- the Settlement Authority surface - Settlement authority (board approval chain, certification phase)

## Vocabulary Mapping

| Phrase                      | Package         | Purpose                                              |
| --------------------------- | --------------- | ---------------------------------------------------- |
| `emit_certificate`          | `certification` | Create provisional certificate with evidence binding |
| `mint_certificate`          | `certification` | Finalize certificate (temporal cliff transition)     |
| `sign_certificate`          | `certification` | Cryptographically sign with RSA-4096                 |
| `supersede_certificate`     | `certification` | Replace certificate preserving audit history         |
| `record_attestation`        | `certification` | Record human sign-off with non-repudiation           |
| `build_certificate_summary` | `certification` | Aggregate certificate data for display               |

## Control Surface Integration

| Surface              | Charter                       | Key Phrases Used                                                  |
| -------------------- | ----------------------------- | ----------------------------------------------------------------- |
| RIF Layoff           | `layoff_rif.canon`            | `emit_certificate`, `record_attestation`, `verify_case_integrity` |
| Wire Transfer        | `wire_transfer.canon`         | `emit_certificate`, `record_attestation`, `get_case_history`      |
| Settlement Authority | `settlement_authority.canon`  | `emit_certificate`, `record_attestation`, `verify_case_integrity` |

## Alternatives Considered

### Alternative 1: Embed Evidence in Certificate

Store full evidence objects inside certificate rather than references.

**Rejected**: Evidence can be arbitrarily large; violates separation of concerns.

### Alternative 2: Allow Certificate Revocation

Add `revoked_at` and `revocation_reason` fields.

**Rejected**: Revocation creates audit ambiguity; supersession provides cleaner correction path.

### Alternative 3: Separate Signing Service

External microservice handles all cryptographic operations.

**Rejected**: Network latency on critical path; complexity without proportional benefit.

## Consequences

### Positive

- Cryptographic signatures remain verifiable indefinitely
- Supersession preserves complete correction trail
- Kill Chain enforced in code, not policy
- Review behavior metrics satisfy GDPR/EU AI Act human oversight requirements

### Negative

- Corrections require new certificate (extra records)
- RSA-4096 keys require secure storage and rotation
- Superseded certificates remain forever (storage growth)

## References

- **Vocabulary Package**: `hub/foundation/packages/certification/`
- **Charters**: `hub/charters/surfaces/`
- **Related ADRs**: ADR-003 (immutability), ADR-006 (evidence chain), ADR-018 (cryptography)
