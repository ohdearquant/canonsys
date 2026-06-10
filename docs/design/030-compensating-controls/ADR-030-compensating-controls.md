---
doc_type: ADR
title: "ADR-030: Compensating Controls Framework with Effectiveness Scoring"
version: "2.0.0"
status: active
created: "2026-01-20"
updated: "2026-01-29"
decision_date: "2026-01-20"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-016-break-glass"
  - "ADR-008-policy-gates"
  - "ADR-006-evidence-chain-cep"
successors:
  - "TDS-030-compensating-controls"
supersedes: null
superseded_by: null

tags:
  - security
  - compensating-controls
  - compliance
  - scoring
related:
  - "ADR-016-break-glass"
  - "ADR-008-policy-gates"
  - "ADR-028-observability"
pr: null

quality:
  confidence: 0.95
  sources: 5
  docs: full
---

## Context

### Problem Statement

When primary controls (monitoring, DLP, audit logging, security tools) are disabled or exempted,
organizations must implement **compensating controls** to maintain security posture. Current
industry practice treats compensating controls as checkbox assertions ("we have alternative controls
in place") rather than quantified, evidence-bound mechanisms.

This creates several problems:

1. **Unquantified risk acceptance**: "Compensating controls exist" provides no measure of actual
   coverage or effectiveness.

2. **Assertion without evidence**: Claiming controls exist without binding to verifiable artifacts
   creates audit gaps.

3. **No threshold enforcement**: Without a scoring framework, inadequate controls can be accepted
   for high-risk situations.

4. **Inconsistent evaluation**: Different reviewers apply different standards to what constitutes
   "adequate" compensation.

**Why This Matters**: When an auditor asks "what compensating controls did you have in place?", the
answer must be quantified, evidence-bound, and verifiable.

### Background

**Current State** (before this decision):

- Exemptions approved with free-text "compensating controls" field
- No quantification of control effectiveness
- No evidence binding to prove controls exist
- No threshold enforcement by risk tier

**Driving Forces**:

- **Quantification**: Compensating control effectiveness must be measurable, not binary
- **Evidence binding**: Claims must link to verifiable artifacts (sealed CEPs)
- **Threshold enforcement**: Minimum scores required for high-risk exemptions
- **Consistency**: Same scoring algorithm across all exemption types
- **Integration**: Must work with break-glass and exception workflows

### Assumptions

1. Security team can objectively score compensating control factors
2. Five factors (coverage, detection, response, evidence, maturity) capture effectiveness
3. Risk tiers map to minimum score thresholds
4. Sealed CEPs provide tamper-evident evidence binding

### Constraints

| Type       | Constraint                                  | Impact                      |
| ---------- | ------------------------------------------- | --------------------------- |
| Compliance | PCI DSS 11.3.4 requires documented controls | Evidence binding mandatory  |
| Compliance | SOC 2 CC6.8 requires control modifications  | Audit trail for changes     |
| Security   | Cannot allow self-scoring                   | Security team must validate |
| Integrity  | Evidence must be tamper-evident             | Must use sealed CEPs        |

---

## Decision

### Summary

**We will** implement a scored compensating controls framework with three key components:

1. **Effectiveness Scoring** (0-100 scale with weighted factors)
2. **Evidence-Bound Validation** (claims linked to sealed CEPs)
3. **Risk-Tiered Thresholds** (minimum scores vary by exemption risk)

### Rationale

**Key factors in the decision**:

1. **Quantification over assertion**: A numeric score (0-100) enables consistent threshold
   enforcement while factor breakdown provides transparency.

2. **Evidence prevents gaming**: Requiring sealed CEPs means controls must actually exist and be
   configured, not just claimed.

3. **Risk-proportionate thresholds**: Disabling monitoring for a privileged admin (CRITICAL)
   requires 90+ score; disabling logging for a non-sensitive system (LOW) requires only 25+.

4. **Integration with workflows**: Compensating controls validation becomes a gate in exception
   approval workflows.

### Implementation Approach

**Effectiveness Scoring (0-100 Scale)**:

```
Score 0-49:   INADEQUATE - Cannot proceed with exemption
Score 50-74:  PARTIAL    - Additional approval required (CISO + Legal)
Score 75-89:  ADEQUATE   - Standard approval chain
Score 90-100: EQUIVALENT - Minimal additional oversight
```

**Scoring Factors** (weighted):

| Factor               | Weight | Description                                       |
| -------------------- | ------ | ------------------------------------------------- |
| Coverage Breadth     | 25%    | % of removed capability addressed by alternatives |
| Detection Capability | 25%    | Ability to detect same threats/violations         |
| Response Time        | 20%    | Latency compared to primary control               |
| Evidence Quality     | 15%    | Audit trail completeness for alternatives         |
| Operational Maturity | 15%    | How long alternatives have been in production     |

**Risk Tier Thresholds**:

| Risk Tier | Minimum Score | Max Duration | Additional Requirements      |
| --------- | ------------- | ------------ | ---------------------------- |
| CRITICAL  | 90            | 30 days      | CISO approval + Legal review |
| HIGH      | 75            | 90 days      | Security team approval       |
| MEDIUM    | 50            | 180 days     | Manager approval             |
| LOW       | 25            | 365 days     | Self-attestation             |

**Workflow Integration**:

```
Exception Request --> Compensating Controls Assessment --> Score Gate
                                                              |
                      +-----------+-----------+---------------+
                      |           |           |               |
                   INADEQUATE   PARTIAL    ADEQUATE      EQUIVALENT
                      |           |           |               |
                    DENY      ESCALATE    APPROVE        AUTO-APPROVE
```

### Alternatives Considered

#### Alternative 1: Binary Compensating Controls (Yes/No)

**Description**: Simple assertion that compensating controls exist.

| Criterion       | Score (1-5) | Notes                         |
| --------------- | ----------- | ----------------------------- |
| Simplicity      | 5           | Very easy to implement        |
| Quantification  | 1           | No measure of actual coverage |
| Auditability    | 2           | No evidence binding           |
| Risk management | 1           | No threshold enforcement      |

**Why Not Chosen**: Becomes checkbox exercise. No quantification, no evidence binding.

#### Alternative 2: Checklist-Based Validation

**Description**: Predefined checklist of compensating control types.

| Criterion         | Score (1-5) | Notes                             |
| ----------------- | ----------- | --------------------------------- |
| Simplicity        | 4           | Checklist is easy                 |
| Quantification    | 2           | Binary per item                   |
| Adaptability      | 2           | Static list                       |
| Gaming resistance | 2           | Check boxes without real controls |

**Why Not Chosen**: Does not measure effectiveness. Cannot adapt to new control types.

#### Alternative 3: Risk-Only Assessment

**Description**: Assess residual risk without measuring compensating controls.

| Criterion        | Score (1-5) | Notes                           |
| ---------------- | ----------- | ------------------------------- |
| Simplicity       | 4           | Risk assessment is familiar     |
| Control focus    | 1           | Ignores compensation quality    |
| Improvement path | 2           | No guidance on better controls  |
| Auditability     | 2           | Does not document what controls |

**Why Not Chosen**: Conflates two concerns. Does not document or improve compensation.

### Decision Matrix

| Criterion          | Weight | Binary  | Checklist | Risk-Only | **Scored** |
| ------------------ | ------ | ------- | --------- | --------- | ---------- |
| Quantification     | 30%    | 1       | 2         | 3         | **5**      |
| Evidence binding   | 25%    | 2       | 2         | 2         | **5**      |
| Auditability       | 20%    | 2       | 3         | 2         | **5**      |
| Risk management    | 15%    | 1       | 3         | 4         | **5**      |
| Simplicity         | 10%    | 5       | 4         | 4         | **3**      |
| **Weighted Total** | 100%   | **1.8** | **2.5**   | **2.9**   | **4.8**    |

---

## Consequences

### Positive Consequences

1. **Quantified Risk Acceptance**: Scores provide clear measure of compensation adequacy
2. **Evidence Trail**: Every compensating control claim is verifiable via sealed CEPs
3. **Consistent Enforcement**: Same thresholds across all exemption types
4. **Improvement Pathway**: Low scores indicate where to invest in better alternatives
5. **Audit Readiness**: Factor breakdown explains how decisions were made

### Negative Consequences

1. **Assessment Overhead**: Scoring requires security team evaluation
   - _Mitigation_: Templates for common control types; batch assessment

2. **Potential Gaming**: Factors could be optimized without real improvement
   - _Mitigation_: Evidence binding prevents claims without proof

3. **Maintenance Burden**: Scoring algorithm may need calibration over time
   - _Mitigation_: Version weights; review quarterly

### Neutral Consequences

1. **Security Team Gatekeeping**: Only security team can score (by design)

### Risks

| Risk                          | Likelihood | Impact | Mitigation                              |
| ----------------------------- | ---------- | ------ | --------------------------------------- |
| Scores gamed without evidence | L          | H      | Evidence must be sealed CEPs            |
| Stale compensating controls   | M          | M      | Expiry dates + periodic recertification |
| Factor weights inappropriate  | L          | M      | Version weights; quarterly review       |
| Security team bottleneck      | M          | L      | Templates; escalation for delays        |

### Dependencies Introduced

| Dependency | Type | Version | Stability | Notes                   |
| ---------- | ---- | ------- | --------- | ----------------------- |
| (none)     | -    | -       | -         | Uses existing CEP infra |

### Migration Impact

**Backwards Compatibility**: Compatible

Existing exemptions without compensating controls continue to work. New exemptions requiring
compensating controls use the scoring framework.

**Rollout Plan**:

1. Phase 1: Implement scoring types and actions
2. Phase 2: Add `verify_compensating_controls()` gate to exception workflow
3. Phase 3: Require scored compensating controls for new exemptions

---

## Verification

### Success Criteria

- [ ] `CompensatingControl` entity with effectiveness scoring
- [ ] `ScoringBreakdown` with five weighted factors
- [ ] `verify_compensating_controls()` gate integrated with exceptions
- [ ] Evidence refs must point to sealed CEPs
- [ ] Risk tier thresholds enforced

### Metrics to Track

| Metric                          | Baseline | Target | Review Date |
| ------------------------------- | -------- | ------ | ----------- |
| Average control score           | N/A      | > 70   | 2026-03-20  |
| Controls with evidence          | 0%       | 100%   | 2026-03-20  |
| Exemptions denied for low score | N/A      | < 10%  | 2026-03-20  |
| Score disputes                  | N/A      | < 5%   | 2026-03-20  |

### Review Schedule

- **Initial Review**: 2026-03-20 (2 months after implementation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Security Team

---

## Related Artifacts

### Builds On

- `ADR-016-break-glass`: Emergency path integration (DEGRADED + compensating = documented risk)
- `ADR-008-policy-gates`: Gate framework for `verify_compensating_controls()`
- `ADR-006-evidence-chain-cep`: Sealed CEPs for evidence binding

### Impacts

- `TDS-030-compensating-controls`: Technical specification implementing this decision
- Remove from Monitoring, Disable DLP, Disable Audit Logging: Primary use cases (supplemental domain)
- Vulnerability Exemption, Security Tool Bypass, Security Exception Grant: Security bypass surfaces

---

## Discussion Record

### Key Questions

**Q1**: Can requesters score their own compensating controls?

- **Answer**: No. Security team must validate to prevent self-serving assessments.
- **Raised By**: Compliance review
- **Date**: 2026-01-20

**Q2**: What if there are multiple compensating controls for one exemption?

- **Answer**: Aggregate score = max(individual) + redundancy bonus (up to +10).
- **Raised By**: Architecture review
- **Date**: 2026-01-20

### Approval Record

| Reviewer | Role    | Decision | Date       |
| -------- | ------- | -------- | ---------- |
| Ocean    | Creator | Approve  | 2026-01-20 |

---

## References

- Implementation: `hub/foundation/packages/controls/` (planned)
- TDS: [TDS-030-compensating-controls.md](./TDS-030-compensating-controls.md)
- Related: ADR-016-break-glass, ADR-008-policy-gates, ADR-006-evidence-chain-cep
- Standard: PCI DSS Compensating Controls guidance

---

## Vocabulary Mapping

### Package

- **Package**: `controls`
- **Location**: `hub/foundation/packages/controls/`

### Phrases

| Phrase                       | Type   | Pattern | Description                            |
| ---------------------------- | ------ | ------- | -------------------------------------- |
| `derive_control_equivalence` | derive | derive  | Compute equivalence score for controls |
| `check_exploitability`       | check  | verify  | Verify exploitability of control gap   |
| `verify_tool_controls`       | verify | verify  | Verify security tool controls in place |

### Control Surfaces

| Surface                  | Description              | Key Integration                                  |
| ------------------------ | ------------------------ | ------------------------------------------------ |
| Vulnerability Exemption  | Vulnerability Exemption  | Scored compensating controls for vuln exemptions |
| Security Tool Bypass     | Security Tool Bypass     | verify_tool_controls for bypass approval         |
| Security Exception Grant | Security Exception Grant | Full compensating controls assessment            |
| Remove from Monitoring   | Remove from Monitoring   | Coverage-based compensating controls             |
| Disable DLP              | Disable DLP              | derive_control_equivalence for DLP alternatives  |
| Disable Audit Logging    | Disable Audit Logging    | Highest-risk tier, 90+ score required            |
