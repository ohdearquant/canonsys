# 007 Decision Certificate - Code Mapping

## Overview

The Decision Certificate is the **primary product artifact** of CanonSys - a verifiable record that
proves process was followed, not that the outcome was correct.

## Vocabulary Package

```
hub/foundation/packages/certification/
```

## Phrase Mapping

| Phrase                          | File                                       | Purpose                               |
| ------------------------------- | ------------------------------------------ | ------------------------------------- |
| `emit_certificate`              | `phrases/emit_certificate.py`              | Create provisional certificate        |
| `mint_certificate`              | `phrases/emit_certificate.py`              | Finalize certificate (temporal cliff) |
| `sign_certificate`              | `phrases/sign_certificate.py`              | RSA-4096 cryptographic signing        |
| `supersede_certificate`         | `phrases/supersede_certificate.py`         | Replace with audit trail              |
| `record_attestation`            | `phrases/record_attestation.py`            | Human sign-off with non-repudiation   |
| `build_certificate_summary`     | `phrases/build_certificate_summary.py`     | Aggregate for display                 |
| `check_certificate_exists`      | `phrases/check_certificate_exists.py`      | Verify certificate presence           |
| `certify_fcra_notice`           | `phrases/certify_fcra_notice.py`           | FCRA-specific certification           |
| `certify_termination`           | `phrases/certify_termination.py`           | Termination certification             |
| `certify_decision`              | `phrases/certify_decision.py`              | Generic decision certification        |
| `request_timestamp_attestation` | `phrases/request_timestamp_attestation.py` | RFC 3161 TSA                          |

## Entity Definition

- `DecisionCertificate` - `certificate.py`
- `DecisionCertificateContent` - `certificate.py`

## Embedded Models

- `CertificateStatus` - Lifecycle enum
- `CertificateClass` - Defensibility classification
- `DefensibilityState` - Legal weight
- `ActionType` - Certifiable actions
- `ModelIdentity` - AI model provenance
- `InputFingerprint` - Input hash
- `GateEvaluation` - Gate check record
- `ReviewBehavior` - Anti-rubber stamp metrics
- `JurisdictionContext` - Jurisdiction data
- `AttestationRecord` - Human sign-off

## Control Surface Usage

| Surface              | Charter File                        | Phrases Used                             |
| -------------------- | ----------------------------------- | ---------------------------------------- |
| RIF Layoff           | `hr/layoff_rif.canon`               | `emit_certificate`, `record_attestation` |
| Wire Transfer        | `finance/wire_transfer.canon`       | `emit_certificate`, `record_attestation` |
| Settlement Authority | `legal/settlement_authority.canon`  | `emit_certificate`, `record_attestation` |

## Architectural Patterns

1. **Supersession Doctrine**: Never revoke, only supersede
2. **Temporal Cliff**: MINTED = immutable
3. **Zero-Warnings Rule**: All gates must pass before minting
4. **Kill Chain Integration**: UCS validation required

## Dependencies

- `ImmutableEntity` (from kron)
- ADR-006 (evidence chain)
- ADR-008 (gate evaluations)

## References

- ADR: `docs-shared/canonsys/01_design/007-decision-certificate/ADR-007-decision-certificate.md`
- TDS: `docs-shared/canonsys/01_design/007-decision-certificate/TDS-007-decision-certificate.md`
