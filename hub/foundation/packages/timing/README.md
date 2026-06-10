# Canon Vocab: Timing

Timing gates, business day computation, notice delivery, waiting period management, SLA verification, and timing constraint queries.

## Import

```python
from canon_vocab_timing import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_deadline_not_passed`
- `require_minimum_elapsed`

### Verify

- `verify_notice_delivered`
- `verify_sla_met`

### Action

- `check_waiting_period_elapsed`
- `get_waiting_period`
- `pause_waiting_period`
- `resume_waiting_period`
- `get_acknowledgment`
- `get_delivery_attempts`
- `get_notice`
- `compute_business_days`
- `get_timing_constraints`


## Types

- `AcknowledgmentMethod`
- `ConstraintType`
- `DeliveryStatus`
- `Jurisdiction`
- `NoticeChannel`
- `NoticeDeliveryStatus`
- `NoticeType`
- `SlaType`
- `WaitingPeriodState`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_timing import verify_notice_delivered

# Use in a Canon workflow
result = await verify_notice_delivered(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
