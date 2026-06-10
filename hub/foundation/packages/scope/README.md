# Canon Vocab: Scope

Scope management: destination and channel allowlists, dataset snapshots, group membership, and minimization.

## Import

```python
from canon_vocab_scope import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Verify

- `verify_channel_allowed`
- `verify_dataset_snapshot_match`
- `verify_destination_allowed`
- `verify_group_membership_snapshot`
- `verify_scope_definition`
- `verify_scope_manifest`
- `verify_stakeholder_notification_complete`

### Derive

- `derive_scope_minimization`

### Action

- `check_environment_scope`
- `create_scope_manifest`


## Types

- `ChannelAllowlistResult`
- `DatasetSnapshotResult`
- `DestinationAllowlistResult`
- `EnvironmentScopeResult`
- `GroupSnapshotResult`
- `ManifestResult`
- `ManifestVerificationResult`
- `ScopeDefinitionResult`
- `ScopeMinimizationResult`
- `StakeholderNotificationResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_scope import verify_channel_allowed

# Use in a Canon workflow
result = await verify_channel_allowed(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
