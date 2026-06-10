---
doc_type: ADR
title: "ADR-006: Evidence, Chain, and CEP Integrity Design"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["evidence"]
charters: ["cep.canon"]
---

# ADR-006: Evidence, Chain, and CEP Integrity Design

## Status

Accepted

## Context

CanonSys must maintain legal-grade evidence records that prove decisions were justified. The system
must ensure evidence cannot be tampered with, provide tamper-evident audit trails (FRE 901(b)(9)
compliance), support corrections without mutation, and enforce disciplined evidence collection.

### Decision Drivers

- Evidence once created cannot be modified or deleted
- Hash chains prove "this existed at this time in this order"
- CEPs meet FRE 901(b)(9) and litigation-hold requirements
- Strict taxonomy prevents opinions masquerading as evidence

## Decision

### D1: Hash-Chain Integrity

Each chain entry includes hash of previous entry for tamper-evidence.

```python
chain_hash = SHA256(payload_hash + previous_hash)
```

**Implementation**: See vocabulary package `evidence` - specifically:

- `chain_evidence` - append entry to hash chain
- `verify_chain` - verify entire chain integrity
- `get_case_history` - retrieve chain entries for a subject

### D2: Backward-Only Supersession

New evidence points to old via `supersedes_id`. Original never modified.

```python
supersedes_id: FK["Evidence"] | None = None  # Backward pointer (immutable)
# NO superseded_by_id field - forward pointer is derived via indexed query
```

**Implementation**: See vocabulary package `evidence` - specifically:

- `supersede_evidence` - create correction pointing back to original
- `save_evidence` - persist new evidence artifact

### D3: Strict CEP Type Taxonomy

Only predefined CEP types allowed. If you cannot fit your reason into a type, it's not evidence.

| CEP Type               | Legal Basis                   |
| ---------------------- | ----------------------------- |
| `perf_metric`          | Objective, measurable data    |
| `policy_log`           | System-generated event        |
| `conduct_record`       | Observable, documented facts  |
| `investigation_ruling` | Process-generated outcome     |
| `pip_fail`             | Documented process completion |
| `background_check`     | Third-party verified records  |

**Implementation**: See vocabulary package `evidence` - specifically:

- `create_cep` - create CEP with validated type
- `seal_cep` - cryptographically seal CEP

### D4: PII Safety Gate

Block on PII detection as defense-in-depth.

**Implementation**: See `libs/canon/src/canon/utils/pii.py`

## Vocabulary Mapping

| Phrase                             | Package    | Purpose                                              |
| ---------------------------------- | ---------- | ---------------------------------------------------- |
| `create_cep`                       | `evidence` | Create Certified Evidence Packet with validated type |
| `seal_cep`                         | `evidence` | Cryptographically seal CEP for immutability          |
| `chain_evidence`                   | `evidence` | Append entry to hash-linked audit chain              |
| `get_case_history`                 | `evidence` | Retrieve chronological chain entries for subject     |
| `verify_chain`                     | `evidence` | Verify entire chain integrity (tamper detection)     |
| `verify_chain_of_custody_complete` | `evidence` | Verify custody chain completeness                    |
| `save_evidence`                    | `evidence` | Persist immutable evidence artifact                  |
| `supersede_evidence`               | `evidence` | Create correction via backward pointer               |

## Control Surface Integration

| Surface          | Charter                    | Key Phrases Used                                     |
| ---------------- | -------------------------- | ---------------------------------------------------- |
| Data Sharing     | `data_sharing.canon`       | `chain_evidence`, `verify_chain_of_custody_complete` |
| PII Export       | `pii_export.canon`         | `save_evidence`, `seal_cep`                          |
| Dataset Publish  | `dataset_publish.canon`    | `create_cep`, `chain_evidence`                       |

**Charter Integration**: See `hub/charters/cep.canon` for the CEP
certification workflow with phases: source_classification, fact_extraction, sanitization,
attestation, sealing.

## Alternatives Considered

### Alternative 1: Timestamp-Only Audit

**Why Rejected**: Timestamps can be spoofed, no cryptographic integrity proof.

### Alternative 2: Bidirectional Pointers for Supersession

**Why Rejected**: Requires transaction for atomic update of both. Backward-only allows single atomic
INSERT.

### Alternative 3: Free-Form Evidence Types

**Why Rejected**: No discipline, opinions creep in. Strict taxonomy forces categorization.

## Consequences

### Positive

- Cryptographic proof of ordering and integrity
- True immutability: original evidence never modified
- Double-supersession prevented by DB constraint
- Every CEP auditable against type definition

### Negative

- Cannot delete individual entries (breaks chain)
- Forward lookup requires indexed query (not direct field)
- May need to add types for new use cases (requires code change)

## References

- **Vocabulary Package**: `hub/foundation/packages/evidence/`
- **Charter**: `hub/charters/cep.canon`
- **TDS**: `/docs-shared/canonsys/01_design/006-evidence-chain-cep/TDS-006-evidence-chain-cep.md`
- **Related ADRs**: ADR-003-immutability, ADR-005-rls-migration
