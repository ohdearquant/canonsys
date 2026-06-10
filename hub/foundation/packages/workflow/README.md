# Canon Vocab: Workflow

Workflow lifecycle, step recording, vendor call provenance, and completion tracking.

## Import

```python
from canon_vocab_workflow import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Action

- `record_vendor_call`
- `record_workflow_step`
- `complete_workflow_run`
- `create_workflow_run`


## Types

- `VendorCallStatus`
- `WorkflowRunStatus`
- `WorkflowType`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_workflow import record_vendor_call

# Use in a Canon workflow
result = await record_vendor_call(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
