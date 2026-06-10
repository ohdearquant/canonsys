# Canon Vocab: Identity

Identity assurance, authentication posture, IdP attestation, and scope risk assessment.

## Import

```python
from canon_vocab_identity import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Verify

- `verify_assurance_equivalent`
- `verify_idp_posture_attestation`
- `verify_request_source_authenticated`
- `verify_strong_auth_posture`

### Action

- `assess_scope_risk_level`
- `get_ca_level`


## Types

- `AALLevel`
- `AuthPosture`
- `RiskLevel`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_identity import verify_assurance_equivalent

# Use in a Canon workflow
result = await verify_assurance_equivalent(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
