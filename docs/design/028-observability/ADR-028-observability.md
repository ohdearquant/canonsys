---
doc_type: ADR
title: "ADR-028: Observability Architecture with Compliance-Aware Telemetry"
version: "2.0.0"
status: active
created: "2026-01-16"
updated: "2026-01-29"
decision_date: "2026-01-16"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-001-immutability"
  - "ADR-006-evidence-chain-cep"
successors:
  - "TDS-028-observability"
supersedes: null
superseded_by: null

tags:
  - observability
  - otel
  - enterprise
  - compliance
related:
  - "ADR-009-opa"
  - "ADR-030-compensating-controls"
  - "CONSTRAINTS-001-enterprise-ilities"
pr: null

quality:
  confidence: 0.95
  sources: 4
  docs: full
---

## Context

### Problem Statement

Enterprise infrastructure requires governance operations to be as visible as execution operations.
The enterprise-ilities constraints framework (CONSTRAINTS-001) mandates:

- **Observability** (Section 7): Governance visible in standard APM tools (DataDog, Grafana, New
  Relic)
- **Performability** (Section 6): Declared latency budgets, SLO tracking, error budget management
- **Frugality** (Section 9): Cost attribution by tenant, decision class, and operation type

**Why This Matters**: Without observability, governance becomes a black box. Operators cannot:

- Answer "why was this action blocked?" during incidents
- Track governance latency against SLOs
- Attribute costs to tenants for chargeback
- Detect degraded mode usage or quota exhaustion

### Background

**Current State** (before this decision):

- Gate evaluations logged but not metriced
- Policy evaluations had timing but no OTEL export
- No SLO definitions for governance operations
- No cost attribution or tenant quotas
- Metrics failures were silent (swallowed exceptions)

**Driving Forces**:

1. **Enterprise Integration**: DataDog/Grafana dashboards must show governance alongside application
   traces
2. **Multi-Tenant Cost Control**: Tenants need visibility into governance consumption
3. **SLO-Driven Operations**: SRE teams need formal SLOs to manage error budgets
4. **Fail-Open Metrics**: Metrics collection must never block governance (compliance > telemetry)
5. **Compliance Coverage**: Vocabulary phrases to verify logging meets regulatory requirements

### Assumptions

1. OTEL is the industry standard for observability (OpenTelemetry won over vendor-specific APIs)
2. Optional dependencies are acceptable (graceful degradation when OTEL not installed)
3. Tenants are identified by `tenant_id` passed through RequestContext
4. Cost attribution uses compute units as an abstract currency
5. Compliance audit logs have higher integrity requirements than operational logs

### Constraints

| Type         | Constraint                               | Impact                                            |
| ------------ | ---------------------------------------- | ------------------------------------------------- |
| Technical    | OTEL libraries must be optional          | Graceful degradation pattern required             |
| Compliance   | Metrics failures cannot block governance | Fail-open for telemetry, fail-closed for policies |
| Enterprise   | Must integrate with existing APM tools   | OTLP export required                              |
| Multi-tenant | Cost attribution by tenant required      | tenant_id label on all metrics                    |
| Regulatory   | GDPR Article 17 right to erasure         | Personal data in logs must be redactable          |

---

## Decision

### Summary

**We will** implement a three-tier observability architecture:

1. **OTEL Layer**: OpenTelemetry for operational metrics, traces, and logs
2. **SLO/Frugality Layer**: SLO tracking and tenant cost attribution
3. **Coverage Verification Layer**: Vocabulary phrases to verify logging completeness

### Rationale

**Key factors in the decision**:

1. **Industry Standard**: OpenTelemetry is vendor-neutral and supported by all major APM providers
2. **Graceful Degradation**: OTEL can be optional - governance works without it
3. **Structured Attribution**: Labels enable slicing by tenant, gate, policy, decision class
4. **SLO Integration**: Latency histograms feed directly into SLI calculations
5. **Coverage Vocabulary**: `derive_logging_coverage()` and `assess_coverage()` provide programmatic
   verification that logging meets compliance requirements

### Implementation Approach

**Three Layers**:

```
Layer 1: OTEL Telemetry
├── Metrics (Prometheus-compatible)
│   ├── gate_evaluation_total (counter)
│   ├── gate_evaluation_duration_seconds (histogram)
│   ├── policy_evaluation_total (counter)
│   ├── policy_evaluation_duration_seconds (histogram)
│   └── decision_cost_units_total (counter)
├── Traces (OTLP-compatible)
│   ├── governance.gate.evaluate (span)
│   ├── governance.policy.evaluate (span)
│   └── governance.decision.certify (span)
└── Logs (structlog + OTEL log exporter)

Layer 2: SLO + Frugality
├── SLORegistry
│   ├── gate_p99_latency < 100ms
│   ├── policy_p99_latency < 200ms
│   └── error_budget tracking
├── DecisionMeter
│   └── Cost attribution by tenant/decision class
└── QuotaEnforcer
    └── Tenant quota enforcement

Layer 3: Coverage Verification
├── derive_logging_coverage(scope) -> CoverageResult
├── assess_coverage(scope, threshold) -> AssessmentResult
└── Integration with the Disable Audit Logging surface
```

**Fail-Open Pattern**:

```python
try:
    self._record_metric(gate_id, latency, outcome)
except Exception:
    logger.warning("Telemetry emission failed, continuing")
    # Governance continues - telemetry is non-blocking
```

### Alternatives Considered

#### Alternative 1: Vendor-Specific APM (Rejected)

**Description**: Use DataDog or New Relic SDKs directly

| Criterion      | Score (1-5) | Notes                      |
| -------------- | ----------- | -------------------------- |
| Ease of use    | 4           | Simpler integration        |
| Vendor lock-in | 1           | Tied to one APM            |
| Flexibility    | 2           | Limited to vendor features |

**Why Not Chosen**: Vendor lock-in unacceptable for enterprise customers with diverse APM choices

#### Alternative 2: Custom Metrics Without OTEL (Rejected)

**Description**: Build custom metrics export without OTEL

| Criterion   | Score (1-5) | Notes                 |
| ----------- | ----------- | --------------------- |
| Control     | 5           | Full control          |
| Ecosystem   | 1           | No standard exporters |
| Maintenance | 2           | Build everything      |

**Why Not Chosen**: Reinventing telemetry is wasted effort

#### Alternative 3: Metrics Without SLOs (Rejected)

**Description**: Export metrics without formal SLO framework

| Criterion     | Score (1-5) | Notes                      |
| ------------- | ----------- | -------------------------- |
| Simplicity    | 4           | Less code                  |
| SRE alignment | 2           | No error budget management |
| Enterprise    | 2           | SLOs expected              |

**Why Not Chosen**: Enterprise customers expect SLO-driven operations

### Decision Matrix

| Criterion          | Weight | Vendor APM | Custom  | No SLO  | **OTEL+SLO** |
| ------------------ | ------ | ---------- | ------- | ------- | ------------ |
| Ecosystem          | 25%    | 3          | 1       | 4       | **5**        |
| SLO support        | 25%    | 3          | 3       | 1       | **5**        |
| Multi-vendor       | 20%    | 1          | 5       | 5       | **5**        |
| Enterprise needs   | 20%    | 4          | 2       | 2       | **5**        |
| Maintenance        | 10%    | 4          | 2       | 4       | **4**        |
| **Weighted Total** | 100%   | **2.8**    | **2.4** | **3.0** | **4.9**      |

---

## Consequences

### Positive Consequences

1. **Vendor Neutral**: Works with DataDog, Grafana, New Relic, Jaeger
2. **SLO-Driven**: Formal error budgets enable mature SRE practices
3. **Cost Attribution**: Tenants have visibility into governance consumption
4. **Quota Enforcement**: Runaway tenants don't exhaust shared resources
5. **Graceful Degradation**: Governance works even if telemetry fails
6. **Coverage Verification**: Vocabulary phrases verify logging completeness

### Negative Consequences

1. **Complexity**: SLO and frugality add code beyond basic OTEL
   - _Mitigation_: Clear module boundaries; SLO/frugality are optional features

2. **Learning Curve**: OTEL concepts not universally known
   - _Mitigation_: Documentation and training

3. **Storage Cost**: Metrics/traces require storage infrastructure
   - _Mitigation_: Sampling strategies; retention policies

### Neutral Consequences

1. **OTEL Optional**: Can run without OTEL installed (graceful degradation)

### Risks

| Risk                          | Likelihood | Impact | Mitigation                                |
| ----------------------------- | ---------- | ------ | ----------------------------------------- |
| OTEL version churn            | M          | L      | Pin versions; test upgrades               |
| Metrics cardinality explosion | M          | M      | Limit label combinations; quota alerts    |
| SLO budget gaming             | L          | L      | Clear ownership; budget reviews           |
| Tenant quota disputes         | M          | L      | Clear quota communication; appeal process |

### Dependencies Introduced

| Dependency             | Type    | Version | Stability | Notes                    |
| ---------------------- | ------- | ------- | --------- | ------------------------ |
| opentelemetry-api      | Library | 1.x     | Stable    | OTEL API (optional)      |
| opentelemetry-sdk      | Library | 1.x     | Stable    | OTEL SDK (optional)      |
| opentelemetry-exporter | Library | 1.x     | Stable    | OTLP exporter (optional) |
| prometheus-client      | Library | 0.x     | Stable    | Prometheus metrics       |

### Migration Impact

**Backwards Compatibility**: N/A (new capability)

**Rollout Plan**:

1. Phase 1: OTEL instrumentation (spans, basic metrics)
2. Phase 2: SLO definitions and tracking
3. Phase 3: Frugality (cost metering, quotas)
4. Phase 4: Coverage verification vocabulary

---

## Verification

### Success Criteria

- [x] OTEL spans exported to collector
- [x] Prometheus metrics exposed on /metrics
- [x] SLO definitions for gate/policy latency
- [ ] `derive_logging_coverage()` implemented
- [ ] `assess_coverage()` implemented
- [ ] QuotaEnforcer integrated with gates

### Metrics to Track

| Metric                | Baseline | Target  | Review Date |
| --------------------- | -------- | ------- | ----------- |
| Gate p99 latency      | N/A      | < 100ms | 2026-02-16  |
| Policy p99 latency    | N/A      | < 200ms | 2026-02-16  |
| Telemetry error rate  | N/A      | < 0.01% | 2026-02-16  |
| Coverage verification | 0%       | 100%    | 2026-03-16  |

### Review Schedule

- **Initial Review**: 2026-02-16 (1 month after implementation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Platform Team + SRE

---

## Related Artifacts

### Builds On

- `CONSTRAINTS-001`: Enterprise-ilities framework (Observability, Performability, Frugality)
- `ADR-009-opa`: OPA integration (policy evaluation telemetry)
- `ADR-001-immutability`: Immutable evidence for audit trail

### Impacts

- `TDS-028-observability`: Technical specification implementing this decision
- `ADR-030-compensating-controls`: Coverage used for the Disable Audit Logging surface

---

## Discussion Record

### Key Questions

**Q1**: Should OTEL be a required dependency?

- **Answer**: No. Governance must work without OTEL for simpler deployments. Graceful degradation.
- **Raised By**: Architecture review
- **Date**: 2026-01-16

**Q2**: How do we handle high-cardinality labels?

- **Answer**: Limit to tenant_id, gate_id, policy_id, outcome. No request IDs in metrics.
- **Raised By**: SRE review
- **Date**: 2026-01-16

### Approval Record

| Reviewer | Role    | Decision | Date       |
| -------- | ------- | -------- | ---------- |
| Ocean    | Creator | Approve  | 2026-01-16 |

---

## References

- Implementation: `libs/canon/src/canon/utils/telemetry.py`
- Implementation: `libs/canon/src/canon/utils/slo.py`
- Implementation: `libs/canon/src/canon/services/metering/`
- TDS: [TDS-028-observability.md](./TDS-028-observability.md)
- OTEL: https://opentelemetry.io/docs/python/
- CONSTRAINTS-001: Enterprise-ilities framework

---

## Vocabulary Mapping

### Package

- **Package**: `controls`
- **Location**: `hub/foundation/packages/controls/`

### Phrases

| Phrase                    | Type   | Pattern | Description                           |
| ------------------------- | ------ | ------- | ------------------------------------- |
| `derive_logging_coverage` | derive | derive  | Compute logging coverage for a scope  |
| `assess_coverage`         | assess | verify  | Evaluate coverage against a threshold |

### Control Surfaces

| Surface                | Description            | Key Integration                                 |
| ---------------------- | ---------------------- | ----------------------------------------------- |
| Disable Audit Logging  | Disable Audit Logging  | Coverage verification for compensating controls |
| Disable DLP            | Disable DLP            | Coverage derivation for security controls       |
| Remove from Monitoring | Remove from Monitoring | Coverage assessment for monitoring exemptions   |
