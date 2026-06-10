# Canon Vocab: Policy

Policy definition, adapter creation, release lifecycle, evaluation, resolution, conditional evaluation, and exception management.

## Import

```python
from canon_vocab_policy import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_policy_active`
- `require_policy_pass`
- `require_policy_version_current`

### Verify

- `verify_policy_not_overridden`

### Derive

- `derive_risk_tier`

### Action

- `create_policy_adapter`
- `create_policy_definition`
- `create_policy_release`
- `evaluate_conditional_policy`
- `evaluate_policy`
- `get_applicable_policies`
- `publish_policy_release`
- `resolve_policy`


## Types

- `PolicyAdapter`
- `PolicyAdapterContent`
- `PolicyAuthority`
- `PolicyDecision`
- `PolicyDefinition`
- `PolicyDefinitionContent`
- `PolicyRelease`
- `PolicyReleaseContent`
- `PolicyScope`
- `PolicyStatus`
- `RiskTier`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_policy import verify_policy_not_overridden

# Use in a Canon workflow
result = await verify_policy_not_overridden(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
