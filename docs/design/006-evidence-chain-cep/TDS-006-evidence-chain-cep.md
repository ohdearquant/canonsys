---
doc_type: TDS
title: "Technical Design Specification: Evidence, Chain, and Certified Evidence Packet"
version: "2.0.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-29"
vocabulary_packages: ["evidence"]
charters: ["cep.canon"]
predecessors: ["TDS-001-tenant-isolation", "TDS-002-entity", "TDS-003-immutability", "TDS-005-rls-migration"]
---

# Technical Design Specification: Evidence, Chain, and Certified Evidence Packet

## 1. Overview

### 1.1 Purpose

This specification defines the evidence subsystem - the legal-grade infrastructure for storing,
chaining, and certifying evidence artifacts that support people operations decisions.

### 1.2 Scope

**In Scope**: Evidence entity with supersession, ChainEntry with hash chain, CEP with strict type
taxonomy, PII safety gate, race-safe chain append.

**Out of Scope**: Decision Certificate generation (TDS-007), policy gates that evaluate evidence
(TDS-008), evidence storage backends, full-text search.

### 1.3 Goals

1. **Immutability**: Evidence cannot be modified or deleted
2. **Tamper Evidence**: Hash chains prove temporal ordering
3. **Legal Grade**: FRE 901(b)(9) and litigation-hold compliance
4. **Type Discipline**: Strict CEP taxonomy - "if it doesn't fit, it's an opinion"

## 2. Vocabulary Package

This TDS is implemented by the `evidence` vocabulary package.

### 2.1 Package Location

`hub/foundation/packages/evidence/`

### 2.2 Phrase Mapping

| Phrase                             | File                                          | Purpose                        |
| ---------------------------------- | --------------------------------------------- | ------------------------------ |
| `create_cep`                       | `phrases/create_cep.py`                       | Create CEP with validated type |
| `seal_cep`                         | `phrases/seal_cep.py`                         | Cryptographically seal CEP     |
| `chain_evidence`                   | `phrases/chain_evidence.py`                   | Append to hash chain           |
| `get_case_history`                 | `phrases/get_case_history.py`                 | Retrieve chain entries         |
| `verify_chain`                     | `phrases/verify_chain.py`                     | Verify chain integrity         |
| `verify_chain_of_custody_complete` | `phrases/verify_chain_of_custody_complete.py` | Verify custody completeness    |
| `save_evidence`                    | `phrases/save_evidence.py`                    | Persist evidence artifact      |
| `supersede_evidence`               | `phrases/supersede_evidence.py`               | Create correction              |

### 2.3 Types

| Type                 | File             | Values                                                                                                |
| -------------------- | ---------------- | ----------------------------------------------------------------------------------------------------- |
| `CEPType`            | `types/cep.py`   | `perf_metric`, `policy_log`, `conduct_record`, `investigation_ruling`, `pip_fail`, `background_check` |
| `CEPStatus`          | `types/cep.py`   | `DRAFT`, `SEALED`, `SUPERSEDED`                                                                       |
| `ChainEventType`     | `types/chain.py` | Chain event classifications                                                                           |
| `CustodyChainStatus` | `types/chain.py` | Custody verification status                                                                           |

## 3. Charter Integration

### 3.1 CEP Charter

**Location**: `hub/charters/cep.canon`

```
charter "Certified Evidence Packet" v1.0

workflow cep_certification:
    phase source_classification:
        action classify_evidence_type()
        action validate_source_class()
        evidence source_classification_record

    phase fact_extraction:
        require source_classification.passed
        action extract_observable_facts()
        action validate_fact_constraints()
        evidence fact_extraction_record

    phase sanitization:
        require fact_extraction.passed
        action redact_third_party_pii()
        evidence sanitization_record

    phase attestation:
        require sanitization.passed
        action verify_certifying_role()
        action record_attestation()
        evidence attestation_record

    phase sealing:
        require attestation.passed
        action compute_content_hash()
        action chain_evidence()
        certify immutable
        evidence cep_seal_record
```

### 3.2 Control Surfaces Using This Pattern

| Surface          | Charter                    | Usage                                     |
| ---------------- | -------------------------- | ----------------------------------------- |
| Data Sharing     | `data_sharing.canon`       | Chain evidence for data sharing decisions |
| PII Export       | `pii_export.canon`         | CEP for PII export justification          |
| Dataset Publish  | `dataset_publish.canon`    | Evidence chain for dataset publication    |

## 4. Hash Chain Integrity

```python
def compute_hashes(payload: dict, previous_entry: ChainEntry | None) -> tuple:
    payload_hash = SHA256(canonical_json(payload))
    previous_hash = previous_entry.chain_hash if previous_entry else None
    chain_hash = SHA256(payload_hash + (previous_hash or ""))
    sequence = (previous_entry.sequence + 1) if previous_entry else 0
    return payload_hash, previous_hash, chain_hash, sequence
```

**Properties**: FRE 901(b)(9) compliant, tamper-evident, O(n) verification.

## 5. Supersession Pattern

```
Evidence A (original) <-- supersedes_id -- Evidence B (correction)
                                            <-- supersedes_id -- Evidence C (latest)

Forward pointer derived via: SELECT WHERE supersedes_id = original.id
evidence_active view: non-superseded heads only
```

**Unique constraint on supersedes_id prevents double-supersession.**

## 6. CEP Type Taxonomy

| Type                   | Legal Basis           | Example                                       |
| ---------------------- | --------------------- | --------------------------------------------- |
| `perf_metric`          | Objective, measurable | "Closed 42 tickets vs 50 target"              |
| `policy_log`           | System-generated      | "Logged into prohibited system at 2:34 AM"    |
| `conduct_record`       | Observable facts      | "Three consecutive no-shows to standup"       |
| `investigation_ruling` | Process outcome       | "Investigation concluded harassment occurred" |
| `pip_fail`             | Documented process    | "PIP goals not met after 90-day period"       |
| `background_check`     | Third-party verified  | "Criminal background check completed"         |

**Anti-Patterns** (rejected): "Poor attitude", "Not a team player", "Cultural misfit"

## 7. PII Safety Gate

```python
def _check_pii_gate(self) -> None:
    """Defense-in-depth. Catches upstream redaction failures."""
    if not self.data:
        return
    result = scan_for_pii(json.dumps(self.data), blocking_only=True)
    if not result.safe_to_persist:
        raise PIIBlockedError(block_reason=result.block_reason())
```

**Blocking categories**: SSN, Credit Card, Passport.

## 8. Race-Safe Chain Append

```python
async def append(cls, ..., max_retries: int = 3) -> ChainEntry:
    for attempt in range(max_retries):
        previous = await cls.select(order_by="sequence DESC", limit=1)
        hashes = cls.compute_hashes(payload, previous)
        try:
            await entry.insert()
            return entry
        except UniqueViolation:
            if attempt < max_retries - 1:
                continue  # Retry with new sequence
            raise
```

## 9. Key Files

| File                               | Purpose                    |
| ---------------------------------- | -------------------------- |
| `packages/evidence/__init__.py`    | Package exports            |
| `packages/evidence/phrases/*.py`   | Phrase implementations     |
| `packages/evidence/types/cep.py`   | CEP types and status       |
| `packages/evidence/types/chain.py` | Chain event types          |
| `packages/evidence/exceptions.py`  | Domain exceptions          |
| `charters/cep.canon`               | CEP certification workflow |

## 10. References

- **ADR**: ADR-006-evidence-chain-cep
- **Vocabulary Package**: `hub/foundation/packages/evidence/`
- **Charter**: `hub/charters/cep.canon`
- **Related**: TDS-003-immutability, TDS-007-decision-certificate
