# Canon Vocab: Legal

Legal holds, NDA management, appeal channels, clean team, criteria locking, and privilege review.

## Import

```python
from canon_vocab_legal import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_appeal_exhausted`
- `require_clean_team_for_competitive_intel`
- `require_deletion_clearance`
- `require_legal_review_complete`
- `require_modification_clearance`
- `require_nda_valid`
- `require_proceedings_closed`

### Verify

- `verify_appeal_channel_available`
- `verify_clean_team_membership`
- `verify_nda_status`
- `verify_privileged_review_complete`

### Action

- `lock_criteria`


## Types

- `AppealChannelType`
- `AppealStatus`
- `CleanTeamStatus`
- `CriteriaLock`
- `HoldType`
- `NDAStatus`
- `PrivilegedReviewStatus`
- `ProceedingsStatus`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_legal import verify_appeal_channel_available

# Use in a Canon workflow
result = await verify_appeal_channel_available(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
