# Canon Vocab: Charter

Charter lifecycle management, surface binding, and decision evaluation.

## Import

```python
from canon_vocab_charter import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Action

- `activate_charter`
- `bind_surface`
- `create_charter`
- `evaluate_decision`


## Types

- `ActivateCharterResult`
- `BindSurfaceResult`
- `Charter`
- `CharterContent`
- `CharterStatus`
- `CharterSurfaceBinding`
- `CharterSurfaceBindingContent`
- `CreateCharterResult`
- `DecisionResult`
- `SurfaceBinding`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_charter import activate_charter

# Use in a Canon workflow
result = await activate_charter(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
