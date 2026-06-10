# Canon Vocab: Incident

Incident declaration, containment verification, and root cause identification.

## Import

```python
from canon_vocab_incident import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_containment_verified`
- `require_incident_declared`
- `require_root_cause_identified`

### Verify

- `verify_containment_verified`
- `verify_root_cause_identified`


## Types

- `ContainmentStatus`
- `ContainmentVerificationStatus`
- `RootCauseStatus`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_incident import verify_containment_verified

# Use in a Canon workflow
result = await verify_containment_verified(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
