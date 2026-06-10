# Canon Vocab: Ai Governance

AI/ML model governance, bias assessment, and human review requirements

## Import

```python
from canon_vocab_ai_governance import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_bias_assessment_documented`
- `require_human_review_for_high_risk`
- `require_human_review_present`

### Verify

- `verify_bias_assessment_complete`
- `verify_human_review_complete`
- `verify_same_tool`


## Types

- `RiskLevel`
- `BiasAssessmentStatus`
- `HumanReviewStatus`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_ai_governance import verify_bias_assessment_complete

# Use in a Canon workflow
result = await verify_bias_assessment_complete(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
