# 030-compensating-controls - Vocabulary Mapping

## Package Mapping

| Aspect   | Value                                             |
| -------- | ------------------------------------------------- |
| Package  | `controls`                                        |
| Location | `hub/foundation/packages/controls/` |
| Status   | Planned                                           |

## Phrases

| Phrase                       | Type   | Pattern | Description                            |
| ---------------------------- | ------ | ------- | -------------------------------------- |
| `derive_control_equivalence` | derive | derive  | Compute equivalence score for controls |
| `check_exploitability`       | check  | verify  | Verify exploitability of control gap   |
| `verify_tool_controls`       | verify | verify  | Verify security tool controls in place |

## Control Surfaces

| Surface                  | Description              | Key Integration                             |
| ------------------------ | ------------------------ | ------------------------------------------- |
| Vulnerability Exemption  | Vulnerability Exemption  | Scored compensating controls for exemptions |
| Security Tool Bypass     | Security Tool Bypass     | verify_tool_controls for bypass approval    |
| Security Exception Grant | Security Exception Grant | Full compensating controls assessment       |
| Remove from Monitoring   | Remove from Monitoring   | Coverage-based compensating controls        |
| Disable DLP              | Disable DLP              | derive_control_equivalence for alternatives |
| Disable Audit Logging    | Disable Audit Logging    | Highest-risk tier, 90+ score required       |

## Code Paths

### Primary Implementation (Planned)

- `hub/foundation/packages/controls/types/compensating.py`
- `hub/foundation/packages/controls/actions/compensating.py`
- `hub/foundation/packages/controls/gates/compensating.py`

### Key Types

| Type                         | Purpose                                 |
| ---------------------------- | --------------------------------------- |
| `CompensatingControlType`    | StrEnum for control categories          |
| `ScoringBreakdown`           | Factor-by-factor scoring transparency   |
| `CompensatingControl`        | Single control with effectiveness score |
| `CompensatingControlSet`     | Set of controls for one exemption       |
| `CompensatingControlsResult` | Gate validation result                  |

### Key Actions

| Action                         | Purpose                                |
| ------------------------------ | -------------------------------------- |
| `create_compensating_control`  | Create control with evidence binding   |
| `score_compensating_control`   | Security team scores control           |
| `verify_compensating_controls` | Gate: validate controls meet threshold |

## Scoring Algorithm

```python
effectiveness_score = (
    coverage_breadth * 0.25 +
    detection_capability * 0.25 +
    response_time * 0.20 +
    evidence_quality * 0.15 +
    operational_maturity * 0.15
)
```

## Risk Tier Thresholds

| Risk Tier | Minimum Score | Max Duration | Approval Required       |
| --------- | ------------- | ------------ | ----------------------- |
| CRITICAL  | 90            | 30 days      | CISO + Legal + CTO      |
| HIGH      | 75            | 90 days      | Security Lead + Manager |
| MEDIUM    | 50            | 180 days     | Manager                 |
| LOW       | 25            | 365 days     | Self-attestation        |

## Dependencies

### Upstream

| Component      | Purpose                      |
| -------------- | ---------------------------- |
| Evidence Chain | Sealed CEPs for binding      |
| Gate Framework | verify_compensating_controls |
| Break-Glass    | Integration with overrides   |

### Downstream

| Component          | Purpose                                 |
| ------------------ | --------------------------------------- |
| Exception workflow | Gate in approval flow                   |
| Remove from Monitoring, Disable DLP, Disable Audit Logging | Primary use cases (supplemental domain) |
| Vulnerability Exemption, Security Tool Bypass, Security Exception Grant | Security bypass surfaces |

## Verification

- **Last verified**: 2026-01-29
- **Design doc version**: 2.0.0
