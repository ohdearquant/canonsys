# Canon Vocab: Export Control

ITAR, EAR, OFAC screening, BIS licensing, and destination country validation.

## Import

```python
from canon_vocab_export_control import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_allowed_destination`

### Verify

- `verify_bis_approval`
- `verify_itar_authorization`
- `verify_ofac_clearance`

### Action

- `bis_license_must_be_valid`
- `check_enhanced_government_screening_complete`
- `check_military_end_use_license_obtained`
- `destination_must_not_be_prohibited`
- `itar_must_be_authorized`
- `ofac_must_be_cleared`
- `validate_destination_country`


## Types

- `BISLicenseType`
- `ExportSubjectType`
- `ITARAuthorizationType`
- `OFACEntityType`
- `ScreeningScope`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_export_control import verify_bis_approval

# Use in a Canon workflow
result = await verify_bis_approval(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
