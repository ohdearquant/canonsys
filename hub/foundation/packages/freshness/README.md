# Canon Vocab: Freshness

Data and review freshness checks, staleness detection, and regulatory deadline derivation.

## Import

```python
from canon_vocab_freshness import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Verify

- `verify_credit_freshness`

### Derive

- `derive_extension_days`
- `derive_filing_deadline`
- `derive_quarter_end`
- `derive_regulatory_deadline`

### Action

- `check_equity_staleness`
- `check_legal_review_freshness`
- `check_privilege_review`
- `check_receipt_freshness`
- `check_tia_freshness`


## Types

- `FreshnessStatus`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_freshness import verify_credit_freshness

# Use in a Canon workflow
result = await verify_credit_freshness(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
