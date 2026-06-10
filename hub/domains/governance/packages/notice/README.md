# Canon Vocab: Notice

Formal compliance notice delivery, acknowledgment tracking, and waiting period management.

## Import

```python
from canon_vocab_notice import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Action

- `record_delivery`
- `record_acknowledgment`
- `create_pre_adverse`
- `create_adverse`
- `check_waiting`
- `pause_waiting`
- `resume_waiting`
- `get_waiting`
- `get_deliveries`
- `create_notice`
- `get_notice`


## Types

- `CheckWaitingOptions`
- `CreateAdverseOptions`
- `CreatePreAdverseOptions`
- `CreateNoticeOptions`
- `DeliveryAttempt`
- `DeliveryMethod`
- `DeliveryStatus`
- `GetDeliveriesOptions`
- `GetNoticeOptions`
- `GetWaitingOptions`
- `NoticeAction`
- `NoticePayload`
- `NoticeRequest`
- `NoticeType`
- `PauseWaitingOptions`
- `RecordAcknowledgmentOptions`
- `RecordDeliveryOptions`
- `ResumeWaitingOptions`
- `WaitingPeriod`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_notice import record_delivery

# Use in a Canon workflow
result = await record_delivery(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
