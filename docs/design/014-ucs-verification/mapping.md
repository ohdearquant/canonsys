# 014-UCS-Verification - Vocabulary Mapping

## Vocabulary Packages

| Package         | Path                                                   | Purpose                             |
| --------------- | ------------------------------------------------------ | ----------------------------------- |
| `evidence`      | `hub/foundation/packages/evidence/`      | CEP and evidence chain validation   |
| `certification` | `hub/foundation/packages/certification/` | Certificate existence and integrity |

## Phrase Mapping

### Evidence Package

| Phrase                             | File                                          | ADR Section |
| ---------------------------------- | --------------------------------------------- | ----------- |
| `verify_chain_of_custody_complete` | `phrases/verify_chain_of_custody_complete.py` | D1, D3      |
| `verify_cep_sealed`                | `phrases/verify_cep_sealed.py`                | D3          |
| `verify_cep_not_expired`           | `phrases/verify_cep_not_expired.py`           | D3          |
| `require_cep_hash_match`           | `phrases/require_cep_hash_match.py`           | D3          |
| `verify_evidence_integrity`        | `phrases/verify_evidence_integrity.py`        | D3          |
| `verify_cep_reference`             | `phrases/verify_cep_reference.py`             | D3          |
| `verify_chain`                     | `phrases/verify_chain.py`                     | D3          |

### Certification Package

| Phrase                          | File                                       | ADR Section |
| ------------------------------- | ------------------------------------------ | ----------- |
| `check_certificate_exists`      | `phrases/check_certificate_exists.py`      | D1          |
| `sign_certificate`              | `phrases/sign_certificate.py`              | D3          |
| `request_timestamp_attestation` | `phrases/request_timestamp_attestation.py` | D3          |

## Control Surfaces

No dedicated control surfaces. UCS verification is infrastructure used by other surfaces.

## Design-to-Code Traceability

| Decision                       | Implementation                            |
| ------------------------------ | ----------------------------------------- |
| D1: Pre-condition verification | Phrases execute before action             |
| D2: Three-state result         | `ValidationStatus` enum in validator      |
| D3: CEP hash matching          | `require_cep_hash_match` phrase           |
| D4: Layered defense            | UCS phrases -> policy gates -> action     |
| D5: Subject tokenization       | Transform functions in `ucs_transform.py` |

## Key Patterns

### Fail-Closed Validation

All verification phrases follow fail-closed semantics. Exceptions result in BLOCKED status.

### Hash Chain Integrity

CEP validation uses `verify_chain` and `require_cep_hash_match` to ensure evidence hasn't been
tampered with since certificate creation.

### Temporal Validity

`verify_cep_not_expired` enforces validity windows. Expired CEPs automatically rejected.
