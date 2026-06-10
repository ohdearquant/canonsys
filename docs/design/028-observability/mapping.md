# 028-observability - Vocabulary Mapping

## Package Mapping

| Aspect   | Value                                             |
| -------- | ------------------------------------------------- |
| Package  | `controls`                                        |
| Location | `hub/foundation/packages/controls/` |
| Status   | Active                                            |

## Phrases

| Phrase                    | Type   | Pattern | Description                           |
| ------------------------- | ------ | ------- | ------------------------------------- |
| `derive_logging_coverage` | derive | derive  | Compute logging coverage for a scope  |
| `assess_coverage`         | assess | verify  | Evaluate coverage against a threshold |

## Control Surfaces

| Surface                | Description            | Key Integration                                 |
| ---------------------- | ---------------------- | ----------------------------------------------- |
| Disable Audit Logging  | Disable Audit Logging  | Coverage verification for compensating controls |
| Disable DLP            | Disable DLP            | Coverage derivation for security controls       |
| Remove from Monitoring | Remove from Monitoring | Coverage assessment for monitoring exemptions   |

## Code Paths

### Primary Implementation

- `libs/canon/src/canon/utils/telemetry.py` - CanonTelemetry
- `libs/canon/src/canon/utils/slo.py` - SLO Registry
- `libs/canon/src/canon/services/metering/` - Cost metering
- `hub/foundation/packages/controls/phrases/` - Coverage phrases

### Key Files

| File                                 | Purpose                          |
| ------------------------------------ | -------------------------------- |
| `utils/telemetry.py`                 | Fail-open OTEL telemetry wrapper |
| `utils/slo.py`                       | SLO, SLI, SLOBudget, SLORegistry |
| `services/metering/`                 | DecisionMeter, QuotaEnforcer     |
| `phrases/assess_coverage.py`         | Coverage assessment phrase       |
| `phrases/derive_logging_coverage.py` | Coverage derivation phrase       |

## Dependencies

### Upstream

| Component     | Purpose             |
| ------------- | ------------------- |
| opentelemetry | OTEL API (optional) |
| prometheus    | Metrics export      |
| structlog     | Structured logging  |

### Downstream

| Component         | Purpose                                 |
| ----------------- | --------------------------------------- |
| EnforcementRunner | Emits governance telemetry              |
| PolicyEngine      | Policy evaluation metrics               |
| Gates             | Gate evaluation metrics                 |
| Disable Audit Logging surface | Coverage used for compensating controls |

## Verification

- **Last verified**: 2026-01-29
- **Design doc version**: 2.0.0
