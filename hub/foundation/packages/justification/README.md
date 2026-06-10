# Canon Vocab: Justification

Business justification validation, classification, and evidence mapping for waivers and reason codes.

## Import

```python
from canon_vocab_justification import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_type_specific_evidence`

### Action

- `classify_justification`
- `map_reason_code_to_evidence`
- `map_waiver_reason_to_evidence`
- `validate_business_justification`


## Types

- `EvidenceRequirement`
- `JustificationClass`
- `ReasonEvidenceMapping`
- `WaiverEvidenceMapping`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_justification import require_type_specific_evidence

# Use in a Canon workflow
result = await require_type_specific_evidence(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
