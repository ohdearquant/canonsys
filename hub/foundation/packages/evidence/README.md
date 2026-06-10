# Canon Vocab: Evidence

Evidence creation, chaining, sealing, custody verification, integrity, and timeline.

## Import

```python
from canon_vocab_evidence import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_cep_hash_match`
- `require_chain_of_custody_complete`
- `require_evidence_not_superseded`
- `require_evidence_present`

### Verify

- `verify_cep_reference`
- `verify_cep_sealed`
- `verify_cep_not_expired`
- `verify_evidence_integrity`
- `verify_case_integrity`
- `verify_chain`
- `verify_chain_of_custody_complete`

### Action

- `chain_evidence`
- `create_genesis_entry`
- `lock_evidence_chain`
- `create_cep`
- `seal_cep`
- `save_evidence`
- `supersede_evidence`
- `compute_evidence_hash`
- `get_case_evidence`
- `get_case_history`
- `get_evidence_timeline`


## Types

- `CEP`
- `CEPStatus`
- `CEPType`
- `ChainEventType`
- `CustodyChainStatus`
- `TimelineEntry`
- `TimelineEvent`
- `ChainEvidenceSpecs`
- `ComputeEvidenceHashSpecs`
- `CreateCEPSpecs`
- `CreateGenesisEntrySpecs`
- `GetCaseEvidenceSpecs`
- `GetCaseHistorySpecs`
- `GetEvidenceTimelineSpecs`
- `LockEvidenceChainSpecs`
- `RequireChainOfCustodyCompleteSpecs`
- `RequireCEPHashMatchSpecs`
- `RequireEvidenceNotSupersededSpecs`
- `RequireEvidencePresentSpecs`
- `SaveEvidenceSpecs`
- `SealCEPSpecs`
- `SupersedeEvidenceSpecs`
- `VerifyCaseIntegritySpecs`
- `VerifyCEPNotExpiredSpecs`
- `VerifyCEPReferenceSpecs`
- `VerifyCEPSealedSpecs`
- `VerifyChainOfCustodyCompleteSpecs`
- `VerifyChainSpecs`
- `VerifyEvidenceIntegritySpecs`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_evidence import verify_cep_reference

# Use in a Canon workflow
result = await verify_cep_reference(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
