# Canon Vocab: Infra

Infrastructure operations: DR testing, risk classification, SLA tracking, backup dependencies, and traffic drain.

## Import

```python
from canon_vocab_infra import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Verify

- `verify_traffic_drained`

### Derive

- `derive_data_loss_risk`
- `derive_degraded_hours_last_30d`
- `derive_dependent_backup_count`
- `derive_rows_read_band`
- `derive_subdomain_depth`
- `derive_tag_risk_class`
- `derive_utilization_volatility`
- `derive_write_acceptance_mode`

### Action

- `check_dr_test_cooldown`


## Types

- `DataLossRiskResult`
- `DegradedHoursResult`
- `DependentBackupsResult`
- `DRTestCooldownResult`
- `RowsReadBandResult`
- `SubdomainDepthResult`
- `TagRiskClassResult`
- `TrafficDrainResult`
- `UtilizationVolatilityResult`
- `WriteAcceptanceModeResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_infra import verify_traffic_drained

# Use in a Canon workflow
result = await verify_traffic_drained(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
