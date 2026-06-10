# 020-Timestamp-TSA - Code Mapping

## Vocabulary Package

**Primary Package**: `hub/foundation/packages/certification/`

## Phrases

| Phrase                          | File                                       | Pattern | Regulatory Basis     |
| ------------------------------- | ------------------------------------------ | ------- | -------------------- |
| `request_timestamp_attestation` | `phrases/request_timestamp_attestation.py` | action  | RFC 3161             |
| `record_attestation`            | `phrases/record_attestation.py`            | action  | SOX 302/404, FRE 901 |
| `emit_certificate`              | `phrases/emit_certificate.py`              | action  | SOX 404              |
| `sign_certificate`              | `phrases/sign_certificate.py`              | action  | eIDAS Art. 41        |
| `build_certificate_summary`     | `phrases/build_certificate_summary.py`     | derive  | Audit reporting      |
| `certify_fcra_notice`           | `phrases/certify_fcra_notice.py`           | action  | FCRA Section 1681m   |
| `certify_termination`           | `phrases/certify_termination.py`           | action  | Employment law       |
| `check_certificate_exists`      | `phrases/check_certificate_exists.py`      | verify  | SOC 2 CC6.1          |
| `supersede_certificate`         | `phrases/supersede_certificate.py`         | action  | ISO 27001            |

## Types

| Type                    | File                   | Purpose                       |
| ----------------------- | ---------------------- | ----------------------------- |
| `AttestationType`       | `types/attestation.py` | Enum of attestation types     |
| `CertificateType`       | `types/certificate.py` | Certificate type definitions  |
| `WorkflowCertification` | `types/workflow.py`    | Workflow certification status |

## TSA Infrastructure

| Component                     | File                                   | Purpose                          |
| ----------------------------- | -------------------------------------- | -------------------------------- |
| `ExternalTSAService`          | `libs/canon/src/canon/utils/tsa/external_tsa.py` | RFC 3161 client + OpenSSL verify |
| `TSAConfig`                   | `libs/canon/src/canon/utils/tsa/types.py`        | TSA endpoint configuration       |
| `TSA_PRESETS`                 | `libs/canon/src/canon/utils/tsa/config.py`       | Pre-configured TSA endpoints     |
| `TimestampToken`              | `libs/canon/src/canon/utils/tsa/types.py`        | Parsed RFC 3161 token            |
| `TimestampVerificationResult` | `libs/canon/src/canon/utils/tsa/types.py`        | Verification result              |
| `BatchTimestampService`       | `libs/canon/src/canon/utils/tsa/batch.py`        | Merkle tree batch timestamping   |
| `MerkleTree`                  | `libs/canon/src/canon/utils/tsa/merkle.py`       | Merkle tree for batch hashing    |

## Control Surfaces Using This Pattern

| Surface                    | Charter                                          | Phrases Used                             |
| -------------------------- | ------------------------------------------------ | ---------------------------------------- |
| Tax Jurisdiction Change    | `surfaces/finance/tax_jurisdiction_change.canon` | `record_attestation`, `emit_certificate` |
| Cross-Border Data Transfer | `surfaces/data/cross_border_transfer.canon`      | (via evidence package)                   |

## Verification Modes

| Method                               | signature_valid | chain_validated | Use Case                      |
| ------------------------------------ | --------------- | --------------- | ----------------------------- |
| `verify()`                           | False (honest)  | False           | Quick hash check, development |
| `verify_with_openssl()`              | True            | False           | Signature verified, no CA     |
| `verify_with_openssl(ca_bundle=...)` | True            | True            | Full legal defensibility      |

## Package Dependencies

**certification depends on**:

- `core` - Base phrase infrastructure
- `evidence` - Evidence chain for certificate binding

**Depended by**:

- Charter DSL certification phases
- Decision certificate workflows
- FCRA adverse action workflows

## Migration from Legacy Paths

| Legacy Path                                                                  | New Path                                                                    |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `hub/foundation/packages/certification/actions/request_timestamp_attestation.py` | `hub/foundation/packages/certification/phrases/request_timestamp_attestation.py` |
| `hub/foundation/packages/certification/actions/record_attestation.py`            | `hub/foundation/packages/certification/phrases/record_attestation.py`            |
| `libs/canon/src/canon/entities/evidence/evidence.py`                                             | `hub/foundation/packages/certification/types/certificate.py`                     |

## Key Decisions

1. **OpenSSL for Verification**: Use `openssl ts -verify` instead of hand-rolled CMS verification
2. **Honest signature_valid**: Never lie about verification status
3. **Separate Attestation Entity**: TimestampAttestation separate from Evidence for immutability
4. **Nonce Enabled by Default**: Anti-replay protection via 128-bit nonce
5. **Independent Circuit Breakers**: Primary/backup TSA have separate failure detection

## Related Documents

- **ADR**: `ADR-020-timestamp-tsa.md`
- **TDS**: `TDS-020-timestamp-tsa.md`
- **Related**: ADR-018-cryptography-rsa, ADR-006-evidence-chain-cep, ADR-003-immutability
