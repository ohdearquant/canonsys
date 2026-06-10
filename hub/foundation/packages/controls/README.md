# Canon Vocab: Controls

Control assessment, exploitability checks, logging coverage, and sanitization verification.

## Import

```python
from canon_vocab_controls import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Verify

- `verify_required_controls_for_tool`
- `verify_sanitization_profile`

### Derive

- `derive_compensating_logging_coverage`
- `derive_control_equivalence_score`

### Action

- `assess_control_coverage`
- `check_exploitability_status`


## Types

- `ControlCoverageResult`
- `ControlEquivalenceResult`
- `ExploitabilityResult`
- `LoggingCoverageResult`
- `SanitizationResult`
- `ToolControlResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_controls import verify_required_controls_for_tool

# Use in a Canon workflow
result = await verify_required_controls_for_tool(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
