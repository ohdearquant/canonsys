---
doc_type: ADR
title: "ADR-035: Ethics Investigation Workflow"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
decision_date: "2026-01-20"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-008-policy-gates"
  - "ADR-022-consent"
  - "ADR-023-waiting-period"
successors:
  - "TDS-035-ethics-investigation"
supersedes: null
superseded_by: null

tags:
  - ethics
  - investigation
  - hr
  - legal
  - state-machine
related:
  - "TDS-035-ethics-investigation"
  - "ADR-008-policy-gates"
  - "ADR-022-consent"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# ADR-035: Ethics Investigation Workflow

## Context

### Problem Statement

Ethics investigations (harassment, retaliation, misconduct, fraud, whistleblower) represent some of
the highest-stakes HR decisions. They generate significant legal exposure when mishandled:

- **Procedural failures**: Investigations closed prematurely, without required reviews
- **Independence violations**: Investigators in subject's reporting chain
- **Pattern blindness**: Prior allegations ignored, enabling repeat misconduct
- **Selective enforcement**: Protected individuals receiving differential treatment
- **Audit gaps**: No evidence of who did what, when

**Why This Matters**: Mishandled ethics investigations lead to lawsuits, regulatory action, and
reputational damage. Title VII, state harassment laws, and SOX whistleblower provisions all require
prompt, thorough, and impartial investigations.

### Background

**Regulatory Requirements**:

| Regulation        | Section      | Requirement                              |
| ----------------- | ------------ | ---------------------------------------- |
| **Title VII**     | 42 USC 2000e | Prompt, thorough investigation           |
| **State laws**    | Harassment   | Investigation documentation requirements |
| **SOX**           | Sec 806      | Whistleblower protection procedures      |
| **EEOC Guidance** | Enforcement  | Impartial investigation standards        |

**Driving Forces**:

- **Procedural Integrity**: Investigations must follow defined steps, not ad-hoc
- **Independence Verification**: Investigator must be independent of subject (org graph check)
- **Pattern Awareness**: Prior allegations must surface during investigation
- **Review Escalation**: Senior subjects require ethics committee review
- **Legal Hold Integration**: Active investigations may require litigation hold
- **Audit Completeness**: Every step, decision, and review must be traceable

### Assumptions

1. Org graph is maintained and accurate for independence verification
2. Prior cases are queryable for pattern risk calculation
3. Legal holds can be triggered from investigation context
4. Review workflows exist for counsel, committee, and HR leadership

### Constraints

| Type         | Constraint                              | Impact                         |
| ------------ | --------------------------------------- | ------------------------------ |
| Independence | Computed from org graph, not asserted   | Objective verification         |
| Pattern Risk | Prior allegations surface automatically | Prevents selective enforcement |
| Resolution   | Gate verifies all requirements          | No premature closure           |
| Audit Trail  | Every action creates step record        | Complete provenance            |

---

## Decision

### Summary

**We will** implement ethics investigation workflow using **EthicsCase state machine** for lifecycle
management, **InvestigationStep** for immutable audit trail, and **verify_ethics_case_resolution**
gate to enforce procedural completion before case closure.

### Rationale

**Key factors in the decision**:

1. **State Machine**: EthicsCase progresses through defined states (OPEN -> INVESTIGATING ->
   PENDING_REVIEW -> RESOLVED) with validated transitions. Invalid state changes are rejected.

2. **Step-Based Audit Trail**: Every significant action creates an InvestigationStep record. Steps
   bind to evidence for complete provenance.

3. **Computed Independence**: Investigator independence verified from org graph, not self-asserted.
   Higher seniority subjects require stricter independence (different business unit, external
   investigator for Board).

4. **Pattern Risk Detection**: Prior allegations automatically computed on case open. ELEVATED risk
   band triggers ethics committee review regardless of subject seniority.

5. **Gate-Protected Resolution**: verify_ethics_case_resolution enforces all requirements before
   closure: documented findings, verified independence, required reviews, minimum duration.

### Implementation Approach

**EthicsCase State Machine**:

```python
class EthicsCaseStatus(Enum):
    OPEN = "open"                       # Case received, not yet assigned
    INVESTIGATING = "investigating"     # Active investigation
    PENDING_REVIEW = "pending_review"   # Awaiting required reviews
    ESCALATED = "escalated"             # Escalated to committee/counsel
    RESOLVED = "resolved"               # Case closed with determination
    CANCELLED = "cancelled"             # Case withdrawn or consolidated
```

**InvestigationStep Types**:

```python
class InvestigationStepType(Enum):
    CASE_OPENED = "case_opened"
    INVESTIGATOR_ASSIGNED = "investigator_assigned"
    INDEPENDENCE_VERIFIED = "independence_verified"
    SCOPE_DEFINED = "scope_defined"
    WITNESS_INTERVIEWED = "witness_interviewed"
    EVIDENCE_COLLECTED = "evidence_collected"
    FINDINGS_DOCUMENTED = "findings_documented"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_COMPLETED = "review_completed"
    ESCALATION_INITIATED = "escalation_initiated"
    CASE_RESOLVED = "case_resolved"
```

**Resolution Verification**:

```python
async def verify_ethics_case_resolution(case_id, ctx) -> EthicsResolutionResult:
    """Verify ethics investigation meets resolution requirements.

    Requirements (from the Close Ethics Case Without Action surface):
    1. Investigation complete with documented findings
    2. Investigator independence verified
    3. Required reviews obtained (counsel, committee, HR)
    4. Rationale for disposition documented
    5. Minimum investigation duration met
    """
```

### Alternatives Considered

#### Alternative 1: Status as String Field

**Description**: Store status as free-text field on a single case record.

| Criterion   | Score (1-5) | Notes                     |
| ----------- | ----------- | ------------------------- |
| Audit Trail | 2           | No step granularity       |
| Enforcement | 1           | No transition validation  |
| Flexibility | 5           | Any status allowed        |
| Gaming Risk | 5           | Easy to bypass procedures |

**Why Not Chosen**: No enforcement of procedural requirements.

#### Alternative 2: BPMN Workflow Engine

**Description**: Use external workflow engine (Camunda, Temporal) for investigation orchestration.

| Criterion        | Score (1-5) | Notes                     |
| ---------------- | ----------- | ------------------------- |
| Audit Trail      | 4           | Engine provides history   |
| Enforcement      | 5           | Full workflow enforcement |
| Integration      | 2           | External dependency       |
| Evidence Binding | 2           | State outside CanonSys    |

**Why Not Chosen**: External dependency for core compliance feature.

#### Alternative 3: Asserted Independence

**Description**: Let investigator self-assert their independence.

| Criterion     | Score (1-5) | Notes                    |
| ------------- | ----------- | ------------------------ |
| Simplicity    | 5           | Just a checkbox          |
| Verification  | 1           | Cannot verify claims     |
| Gaming Risk   | 5           | Easy to lie              |
| Audit Defense | 1           | "They said they were OK" |

**Why Not Chosen**: Gaming risk is unacceptable.

### Decision Matrix

| Criterion          | Weight | String Status | BPMN Engine | **State Machine** |
| ------------------ | ------ | ------------- | ----------- | ----------------- |
| Procedural Enforce | 30%    | 1             | 5           | **4**             |
| Audit Trail        | 25%    | 2             | 4           | **5**             |
| Evidence Binding   | 25%    | 2             | 2           | **5**             |
| Operational Simple | 20%    | 4             | 2           | **4**             |
| **Weighted Total** | 100%   | **2.05**      | **3.40**    | **4.50**          |

---

## Consequences

### Positive Consequences

1. **Procedural Enforcement**: State machine prevents skipping steps. Cannot close case without
   documented findings, verified independence, and required reviews.

2. **Complete Audit Trail**: Every action recorded as InvestigationStep with performer, timestamp,
   and evidence binding. Timeline is reconstructable.

3. **Independence Assurance**: Org graph verification is objective. Cannot self-assert independence
   when org graph shows reporting relationship.

4. **Pattern Awareness**: Prior allegations surface automatically. ELEVATED pattern risk triggers
   committee review, preventing repeat offenders from escaping scrutiny.

5. **Legal Hold Coordination**: Active investigations trigger appropriate holds. Hold release
   requires separate certification (the Litigation Hold Release surface).

### Negative Consequences

1. **State Complexity**: Multiple states to manage. Mitigation: Clear state diagram, validated
   transitions, helpful error messages.

2. **Step Overhead**: Every action creates a record. Mitigation: Steps are lightweight, indexed for
   fast queries.

3. **Org Graph Dependency**: Requires maintained org structure. Mitigation: Independence check fails
   safe (requires manual override with justification).

### Neutral Consequences

1. **New HR Feature Module**: Creates `features/hr/` vertical slice for ethics investigation domain.

2. **Parameterized Gate Pattern**: EthicsInvestigationGate follows parameterized gate pattern from
   other domains.

### Risks

| Risk                          | Likelihood | Impact | Mitigation                              |
| ----------------------------- | ---------- | ------ | --------------------------------------- |
| Org graph inaccurate          | M          | H      | Fail safe, require manual review        |
| Pattern risk false positives  | L          | M      | Configurable threshold, manual override |
| Resolution gate too strict    | L          | M      | Clear remediation messages              |
| Step volume for complex cases | L          | L      | Pagination, archival for closed cases   |

### Migration Impact

**Backwards Compatibility**: Additive. New ethics investigation feature module.

**Migration Steps**:

1. Deploy EthicsCase and InvestigationStep entities
2. Deploy verification actions
3. Deploy EthicsInvestigationGate
4. Configure pattern risk thresholds
5. Train investigators on workflow

---

## Verification

### Success Criteria

- [ ] EthicsCase state machine with validated transitions
- [ ] InvestigationStep created for every significant action
- [ ] verify_investigator_independence computes from org graph
- [ ] compute_pattern_risk surfaces prior allegations
- [ ] verify_ethics_case_resolution gate blocks premature closure
- [ ] Legal hold triggers for appropriate case types
- [ ] Close Ethics Case Without Action surface covered by gate

### Metrics to Track

| Metric                          | Baseline | Target | Review Date |
| ------------------------------- | -------- | ------ | ----------- |
| Cases closed without review     | N/A      | 0%     | Weekly      |
| Independence verification rate  | N/A      | 100%   | Weekly      |
| Pattern risk detection accuracy | N/A      | > 95%  | Monthly     |
| Average investigation duration  | N/A      | Track  | Monthly     |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Quarterly compliance audit
- **Review Owner**: Legal & HR Leadership

---

## Vocabulary Mapping

### Package: `investigation`

**Location**: `hub/domains/employee/packages/investigation/`

| Phrase                             | Purpose                          | Surfaces                                |
| ---------------------------------- | -------------------------------- | --------------------------------------- |
| `open_ethics_case`                 | Create case with pattern risk    | Close Ethics Case Without Action        |
| `assign_investigator`              | Assign with independence check   | Close Ethics Case Without Action        |
| `verify_investigator_independence` | Org graph independence check     | Close Ethics Case Without Action        |
| `compute_pattern_risk`             | Calculate prior allegations      | Close Ethics Case Without Action        |
| `resolve_ethics_case`              | Close with gate verification     | Close Ethics Case Without Action        |
| `verify_ethics_case_resolution`    | Gate for resolution requirements | Close Ethics Case Without Action        |

### Package: `hr`

**Location**: `hub/domains/employee/packages/hr/`

| Phrase                      | Purpose                      | Surfaces                         |
| --------------------------- | ---------------------------- | -------------------------------- |
| `record_investigation_step` | Create immutable step record | Close Ethics Case Without Action |
| `request_review`            | Request counsel/committee/HR | Close Ethics Case Without Action |
| `complete_review`           | Record review outcome        | Close Ethics Case Without Action |

### Package: `legal`

**Location**: `hub/domains/governance/packages/legal/`

| Phrase                      | Purpose                  | Surfaces                    |
| --------------------------- | ------------------------ | --------------------------- |
| `check_legal_hold_required` | Determine if hold needed | Litigation Hold Release     |
| `trigger_legal_hold`        | Initiate litigation hold | Litigation Hold Release     |

### Control Surface Coverage

| Surface                          | Decision                         | Phrases                                                |
| -------------------------------- | -------------------------------- | ------------------------------------------------------ |
| Close Ethics Case Without Action | Close ethics case without action | `verify_ethics_case_resolution`, `resolve_ethics_case` |
| Litigation Hold Release          | Litigation hold release          | `check_legal_hold_required`                            |

### Charter: `investigation.canon`

The ethics investigation workflow is defined in `investigation.canon` charter:

```
charter "Ethics Investigation" v1.0

workflow investigation_workflow:
    phase intake:
        action open_ethics_case()
        action compute_pattern_risk()

    phase assignment:
        require intake.passed
        action assign_investigator()
        action verify_investigator_independence()

    phase investigation:
        require assignment.passed
        action record_investigation_step()
        action collect_evidence()
        action document_findings()

    phase review:
        require investigation.passed
        action request_review()
        action complete_review()

    phase resolution:
        require review.passed
        action verify_ethics_case_resolution()
        action resolve_ethics_case()
```

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate framework for resolution verification
- `ADR-022-consent`: Legal hold interaction with consent processing
- `ADR-023-waiting-period`: Query-time check pattern

### Impacts

- `TDS-035-ethics-investigation`: Technical specification
- Close Ethics Case Without Action surface
- Litigation Hold Release surface
- HR decision surfaces that trigger investigations

---

## References

- TDS: `docs-shared/canonsys/01_design/035-ethics-investigation/TDS-035-ethics-investigation.md`
- Investigation package: `hub/domains/employee/packages/investigation/`
- HR package: `hub/domains/employee/packages/hr/`
- Legal package: `hub/domains/governance/packages/legal/`
- Title VII: 42 USC 2000e
- SOX Section 806: Whistleblower protection
- EEOC Guidance: Investigation requirements

---

## Validation Checklist

### Nygard Format Compliance

- [x] Context explains forces at play
- [x] Decision is clearly stated
- [x] Consequences cover positive, negative, and neutral outcomes

### Completeness

- [x] Problem clearly stated
- [x] Background and constraints documented
- [x] At least 2 alternatives considered
- [x] Decision matrix completed
- [x] Risks identified with mitigations

### Quality

- [x] Rationale is convincing
- [x] Trade-offs are honest
- [x] Success criteria are measurable
- [x] Review schedule defined

### Traceability

- [x] Related artifacts linked
- [x] Vocabulary mapping provided
- [x] References provided
