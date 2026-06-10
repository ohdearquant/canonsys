# 006 - Evidence, Chain, and CEP - Code Mapping

**Updated**: 2026-01-29 | **Vocabulary Package**: `evidence` | **Charter**: `cep.canon`

## Summary

Evidence, Chain, and CEP is implemented by the **evidence** vocabulary package at
`hub/foundation/packages/evidence/`.

## Vocabulary Package

### Phrase Mapping

| Phrase                             | File                                          | Purpose                            |
| ---------------------------------- | --------------------------------------------- | ---------------------------------- |
| `create_cep`                       | `phrases/create_cep.py`                       | Create CEP with validated type     |
| `seal_cep`                         | `phrases/seal_cep.py`                         | Cryptographically seal CEP         |
| `chain_evidence`                   | `phrases/chain_evidence.py`                   | Append to hash chain               |
| `get_case_history`                 | `phrases/get_case_history.py`                 | Retrieve chain entries for subject |
| `verify_chain`                     | `phrases/verify_chain.py`                     | Verify chain integrity             |
| `verify_chain_of_custody_complete` | `phrases/verify_chain_of_custody_complete.py` | Verify custody completeness        |
| `save_evidence`                    | `phrases/save_evidence.py`                    | Persist evidence artifact          |
| `supersede_evidence`               | `phrases/supersede_evidence.py`               | Create correction via backward ptr |
| `verify_cep_sealed`                | `phrases/verify_cep_sealed.py`                | Verify CEP is sealed               |
| `verify_cep_not_expired`           | `phrases/verify_cep_not_expired.py`           | Verify CEP not expired             |
| `require_evidence_present`         | `phrases/require_evidence_present.py`         | Gate: evidence must exist          |
| `compute_evidence_hash`            | `phrases/compute_evidence_hash.py`            | Compute SHA-256 for evidence       |

### Type Definitions

| Type                 | File             | Values                                                  |
| -------------------- | ---------------- | ------------------------------------------------------- |
| `CEPType`            | `types/cep.py`   | perf_metric, policy_log, conduct_record, pip_fail, etc. |
| `CEPStatus`          | `types/cep.py`   | DRAFT, SEALED, SUPERSEDED                               |
| `ChainEventType`     | `types/chain.py` | Chain event classifications                             |
| `CustodyChainStatus` | `types/chain.py` | Custody verification status                             |

### Exceptions

| Exception                       | Purpose                        |
| ------------------------------- | ------------------------------ |
| `CEPNotFoundError`              | CEP not found by ID            |
| `CEPAlreadySealedError`         | Attempt to modify sealed CEP   |
| `ChainIntegrityError`           | Hash chain verification failed |
| `ChainOfCustodyIncompleteError` | Custody chain gaps detected    |
| `EvidenceNotFoundError`         | Evidence artifact not found    |

## Charter Integration

**Location**: `hub/charters/cep.canon`

```
charter "Certified Evidence Packet" v1.0

workflow cep_certification:
    phase source_classification -> fact_extraction -> sanitization -> attestation -> sealing
```

## Control Surfaces Using This Pattern

| Surface          | Charter                    | Key Phrases                             |
| ---------------- | -------------------------- | --------------------------------------- |
| Data Sharing     | `data_sharing.canon`       | chain_evidence, verify_chain_of_custody |
| PII Export       | `pii_export.canon`         | save_evidence, seal_cep                 |
| Dataset Publish  | `dataset_publish.canon`    | create_cep, chain_evidence              |

## Infrastructure Dependencies

| Dependency                    | Purpose                                    |
| ----------------------------- | ------------------------------------------ |
| 003-immutability              | Evidence and ChainEntry use immutable=True |
| 005-rls-migration             | evidence_active view, RLS policies         |
| `libs/canon/src/canon/utils/hashing.py` | compute_hash, compute_chain_hash           |
| `libs/canon/src/canon/utils/pii.py`     | PII safety gate scanning                   |

## Design Documents

- **ADR**: ADR-006-evidence-chain-cep.md
- **TDS**: TDS-006-evidence-chain-cep.md
