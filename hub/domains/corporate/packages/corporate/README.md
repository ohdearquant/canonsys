# Canon Vocab: Corporate

M&A compliance: clean team requirements, carve-out readiness, condition satisfaction, and findings.

## Import

```python
from canon_vocab_corporate import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Derive

- `derive_carve_out_readiness`
- `derive_clean_team_required`
- `derive_condition_satisfaction_status`
- `derive_conditional_findings_addressed`


## Types

- `CarveOutReadinessResult`
- `CarveOutStatus`
- `CleanTeamReason`
- `CleanTeamRequiredResult`
- `ConditionalFindingsAddressedResult`
- `ConditionSatisfactionResult`
- `ConditionSatisfactionStatus`
- `ConditionType`
- `DataSensitivityLevel`
- `DealPhase`
- `FindingStatus`
- `SensitiveDataCategory`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_corporate import example_phrase

# Use in a Canon workflow
result = await example_phrase(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
