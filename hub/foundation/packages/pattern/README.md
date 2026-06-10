# Canon Vocab: Pattern

Pattern detection for compliance monitoring: prior action counts, thresholds, and cumulative amount tracking.

## Import

```python
from canon_vocab_pattern import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Derive

- `derive_cumulative_amount`
- `derive_cumulative_exception_amount`
- `derive_cumulative_reallocation_amount`
- `derive_manager_bypass_count_12m`
- `derive_manager_salary_exception_count_12m`
- `derive_prior_action_count`

### Action

- `check_pattern_threshold`
- `check_prior_bypasses`
- `check_prior_escalations`
- `check_prior_exemptions`


## Types

- `CumulativeAmountResult`
- `PatternThresholdResult`
- `PriorActionCountResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_pattern import check_pattern_threshold

# Use in a Canon workflow
result = await check_pattern_threshold(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
