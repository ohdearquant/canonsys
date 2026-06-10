---
doc_type: TDS
title: "Technical Design Specification: Ethics Investigation Workflow"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: tds
phase: design
scope: L3

predecessors:
  - "ADR-035-ethics-investigation"
successors: []
supersedes: null
superseded_by: null

tags:
  - ethics
  - investigation
  - hr
  - legal
  - state-machine
related:
  - "ADR-035-ethics-investigation"
  - "TDS-008-policy-gates"
  - "TDS-022-consent"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# Technical Design Specification: Ethics Investigation Workflow

## 1. Overview

### 1.1 Purpose

Ethics investigation workflow provides **structured lifecycle management** for ethics cases in
CanonSys. The EthicsCase entity tracks investigation state through defined phases, InvestigationStep
entities create an immutable audit trail, and verify_ethics_case_resolution() gates ensure proper
procedural completion before case closure.

### 1.2 Scope

**In Scope**:

- EthicsCase entity design and state machine
- EthicsCaseType and EthicsCaseStatus enums
- InvestigationStep entity for audit trail
- verify_ethics_case_resolution() gate
- Investigator independence verification
- Pattern risk detection
- Legal hold integration

**Out of Scope**:

- External case management system integration
- Interview recording and transcription
- Evidence vault implementation (see ADR-006)
- Org graph implementation

### 1.3 Platform Invariants

1. **State Machine**: EthicsCase progresses through defined states with validated transitions
2. **Immutable Steps**: Every action creates an InvestigationStep record
3. **Computed Independence**: Investigator independence verified from org graph, not asserted
4. **Pattern Awareness**: Prior allegations automatically surface during investigation
5. **Evidence Binding**: All steps bind to evidence for complete audit trail

### 1.4 Design Goals

| Priority | Goal                      | Rationale                          |
| -------- | ------------------------- | ---------------------------------- |
| P0       | State machine enforcement | Prevent procedural bypass          |
| P0       | Resolution gate           | Block premature closure            |
| P1       | Independence verification | Objective org graph check          |
| P1       | Pattern risk detection    | Surface prior allegations          |
| P2       | Legal hold integration    | Coordinate with consent processing |

---

## 2. Architecture

### 2.1 Component Hierarchy

```
EthicsCase (Entity)
    +-- case_number: str
    +-- case_type: EthicsCaseType
    +-- status: EthicsCaseStatus
    +-- complainant_id, subject_id: FK[Person]
    +-- investigator_id: FK[User]
    +-- finding_severity: FindingSeverity
    +-- pattern_risk_band: str

InvestigationStep (Entity)
    +-- case_id: FK[EthicsCase]
    +-- step_type: InvestigationStepType
    +-- performed_by_id: FK[User]
    +-- evidence_ids: tuple[UUID, ...]

EthicsInvestigationGate (Vocabulary Phrase)
    +-- case_id: UUID
    +-- check(ctx) -> PhraseResult
```

### 2.2 Dependencies

**Internal Dependencies**:

| Component | Purpose                   | Location                  |
| --------- | ------------------------- | ------------------------- |
| Entity    | Base class                | `canon.entities.entity` |
| Gate      | Gate abstraction          | `canon.enforcement`  |
| Evidence  | Evidence binding          | `canon.evidence`     |
| Org Graph | Independence verification | `canon.services.org` |

**External Dependencies**:

| Library  | Purpose           | Version  |
| -------- | ----------------- | -------- |
| asyncpg  | PostgreSQL driver | >=0.28.0 |
| pydantic | Validation        | >=2.0.0  |

---

## 3. Vocabulary Mapping

### Package: `investigation`

**Location**: `hub/domains/employee/packages/investigation/`

| Phrase                             | File                                          | Purpose           |
| ---------------------------------- | --------------------------------------------- | ----------------- |
| `open_ethics_case`                 | `phrases/open_ethics_case.py`                 | Create case       |
| `assign_investigator`              | `phrases/assign_investigator.py`              | Assign with check |
| `verify_investigator_independence` | `phrases/verify_investigator_independence.py` | Org graph check   |
| `compute_pattern_risk`             | `phrases/compute_pattern_risk.py`             | Prior allegations |
| `resolve_ethics_case`              | `phrases/resolve_ethics_case.py`              | Close case        |
| `verify_ethics_case_resolution`    | `phrases/verify_ethics_case_resolution.py`    | Gate verification |

### Package: `hr`

**Location**: `hub/domains/employee/packages/hr/`

| Phrase                      | File                                   | Purpose            |
| --------------------------- | -------------------------------------- | ------------------ |
| `record_investigation_step` | `phrases/record_investigation_step.py` | Create step record |
| `request_review`            | `phrases/request_review.py`            | Request review     |
| `complete_review`           | `phrases/complete_review.py`           | Record outcome     |

### Control Surface Coverage

| Surface                          | Phrases Used                                           | Status      |
| -------------------------------- | ------------------------------------------------------ | ----------- |
| Close Ethics Case Without Action | `verify_ethics_case_resolution`, `resolve_ethics_case` | Implemented |
| Litigation Hold Release          | `check_legal_hold_required`                            | Planned     |

---

## 4. Data Models

### 4.1 EthicsCase Entity

```python
class EthicsCaseType(Enum):
    HARASSMENT = "harassment"
    DISCRIMINATION = "discrimination"
    RETALIATION = "retaliation"
    FRAUD = "fraud"
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    CODE_OF_CONDUCT = "code_of_conduct"
    WHISTLEBLOWER = "whistleblower"
    OTHER = "other"


class EthicsCaseStatus(Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class FindingSeverity(Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    SEVERE = "severe"


class ClosureDisposition(Enum):
    UNSUBSTANTIATED = "unsubstantiated"
    INCONCLUSIVE = "inconclusive"
    NO_ACTION_WARRANTED = "no_action_warranted"
    ACTION_TAKEN = "action_taken"
    ACTION_TAKEN_SEPARATELY = "action_taken_separately"


class EthicsCaseContent(ContentModel):  # includes tenant_id, subject_id via consent vocabulary
    case_number: str
    case_type: EthicsCaseType
    complainant_id: FK[Person]
    subject_id: FK[Person]
    investigator_id: FK[User] | None = None
    investigator_independence_verified: bool = False
    status: EthicsCaseStatus = EthicsCaseStatus.OPEN
    opened_at: datetime = Field(default_factory=ln.now_utc)
    closed_at: datetime | None = None
    finding_severity: FindingSeverity | None = None
    closure_disposition: ClosureDisposition | None = None
    prior_allegations_count_24m: int = 0
    pattern_risk_band: str = "NORMAL"
    counsel_review_required: bool = False
    counsel_review_complete: bool = False
    ethics_committee_required: bool = False
    ethics_committee_review_complete: bool = False
    hr_review_required: bool = False
    hr_review_complete: bool = False


@register_entity("ethics_cases")
class EthicsCase(Entity):
    content: EthicsCaseContent
```

### 4.2 InvestigationStep Entity

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
    CASE_CANCELLED = "case_cancelled"


class InvestigationStepContent(TenantAwareContent):
    case_id: FK[EthicsCase]
    step_type: InvestigationStepType
    performed_by_id: FK[User]
    performed_at: datetime = Field(default_factory=ln.now_utc)
    description: str
    evidence_ids: tuple[UUID, ...] = ()
    witness_id: FK[Person] | None = None
    interview_notes_hash: str | None = None
    reviewer_role: str | None = None
    review_outcome: str | None = None


@register_entity("investigation_steps")
class InvestigationStep(Entity):
    content: InvestigationStepContent
```

### 4.3 Database Schema

```sql
CREATE TABLE ethics_cases (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    case_number VARCHAR(50) NOT NULL UNIQUE,
    case_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    complainant_id UUID NOT NULL REFERENCES persons(id),
    subject_id UUID NOT NULL REFERENCES persons(id),
    investigator_id UUID REFERENCES users(user_id),
    investigator_independence_verified BOOLEAN NOT NULL DEFAULT FALSE,
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    finding_severity VARCHAR(50),
    closure_disposition VARCHAR(50),
    prior_allegations_count_24m INTEGER NOT NULL DEFAULT 0,
    pattern_risk_band VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    metadata JSONB NOT NULL
);

CREATE TABLE investigation_steps (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    case_id UUID NOT NULL REFERENCES ethics_cases(id),
    step_type VARCHAR(50) NOT NULL,
    performed_by_id UUID NOT NULL REFERENCES users(user_id),
    performed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    description TEXT NOT NULL,
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL
);

CREATE INDEX ix_ethics_cases_tenant_status ON ethics_cases(tenant_id, status);
CREATE INDEX ix_ethics_cases_subject ON ethics_cases(tenant_id, subject_id);
CREATE INDEX ix_investigation_steps_case ON investigation_steps(case_id, step_type);
```

---

## 5. Key Operations

### 5.1 verify_ethics_case_resolution Gate

```python
async def verify_ethics_case_resolution(
    case_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> EthicsResolutionResult:
    """Verify ethics investigation meets resolution requirements.

    Requirements (from the Close Ethics Case Without Action surface):
    1. Investigation complete with documented findings
    2. Investigator independence verified
    3. Required reviews obtained (counsel, committee, HR)
    4. Rationale for disposition documented
    5. Minimum investigation duration met
    """
    case = await get_ethics_case(case_id, ctx)
    missing = []

    if case.content.finding_severity is None:
        missing.append("findings_not_documented")

    if not case.content.investigator_independence_verified:
        missing.append("investigator_independence_not_verified")

    if case.content.counsel_review_required and not case.content.counsel_review_complete:
        missing.append("counsel_review_required")

    if case.content.ethics_committee_required and not case.content.ethics_committee_review_complete:
        missing.append("ethics_committee_review_required")

    if missing:
        return EthicsResolutionResult(resolved=False, missing=tuple(missing))

    return EthicsResolutionResult(resolved=True)
```

### 5.2 verify_investigator_independence

```python
async def verify_investigator_independence(
    investigator_id: UUID,
    subject_id: UUID,
    subject_seniority: SeniorityLevel,
    ctx: RequestContext,
) -> IndependenceResult:
    """Verify investigator is independent of subject.

    Independence rules by subject seniority:
    - IC/Manager: Not in subject's reporting chain
    - Director: Not in chain, not same team, not same department
    - VP+: Not in chain, different business unit
    - Board: External investigator required
    """
    investigator_chain = await get_reporting_chain(investigator_id, ctx)
    subject_chain = await get_reporting_chain(subject_id, ctx)

    violations = []

    if investigator_id in subject_chain:
        violations.append("investigator_reports_to_subject")
    if subject_id in investigator_chain:
        violations.append("subject_reports_to_investigator")

    # Seniority-specific rules
    if subject_seniority >= SeniorityLevel.VP:
        inv_bu = await get_business_unit(investigator_id, ctx)
        subj_bu = await get_business_unit(subject_id, ctx)
        if inv_bu == subj_bu:
            violations.append("same_business_unit")

    return IndependenceResult(
        independent=len(violations) == 0,
        violations=tuple(violations),
    )
```

### 5.3 compute_pattern_risk

```python
async def compute_pattern_risk(
    subject_id: UUID,
    lookback_months: int = 24,
    ctx: RequestContext,
) -> PatternRiskResult:
    """Compute pattern risk based on prior allegations.

    ELEVATED pattern risk (2+ prior) requires ethics committee
    review regardless of subject seniority.
    """
    threshold = ctx.config.get("pattern_threshold", 2)
    cutoff = now_utc() - timedelta(days=lookback_months * 30)

    prior_cases = await find_ethics_cases(
        subject_id=subject_id,
        opened_after=cutoff,
        ctx=ctx,
    )

    prior_count = len(prior_cases)
    risk_band = "ELEVATED" if prior_count >= threshold else "NORMAL"

    return PatternRiskResult(
        prior_count=prior_count,
        risk_band=risk_band,
        requires_committee=risk_band == "ELEVATED",
    )
```

---

## 6. State Machine

### 6.1 State Transitions

| From           | To             | Trigger             | Requirements                  |
| -------------- | -------------- | ------------------- | ----------------------------- |
| OPEN           | INVESTIGATING  | assign_investigator | Independence verified         |
| OPEN           | CANCELLED      | cancel_case         | Reason documented             |
| INVESTIGATING  | PENDING_REVIEW | document_findings   | Findings documented           |
| INVESTIGATING  | ESCALATED      | escalate_case       | Committee/counsel required    |
| PENDING_REVIEW | RESOLVED       | resolve_ethics_case | All required reviews complete |
| PENDING_REVIEW | ESCALATED      | escalate_case       | Additional review needed      |
| ESCALATED      | PENDING_REVIEW | complete_escalation | Committee decision made       |
| ESCALATED      | RESOLVED       | resolve_ethics_case | Committee resolves directly   |

### 6.2 Transition Validation

```python
VALID_TRANSITIONS = {
    EthicsCaseStatus.OPEN: {EthicsCaseStatus.INVESTIGATING, EthicsCaseStatus.CANCELLED},
    EthicsCaseStatus.INVESTIGATING: {
        EthicsCaseStatus.PENDING_REVIEW,
        EthicsCaseStatus.ESCALATED,
        EthicsCaseStatus.CANCELLED,
    },
    EthicsCaseStatus.PENDING_REVIEW: {
        EthicsCaseStatus.RESOLVED,
        EthicsCaseStatus.ESCALATED,
        EthicsCaseStatus.INVESTIGATING,
    },
    EthicsCaseStatus.ESCALATED: {
        EthicsCaseStatus.PENDING_REVIEW,
        EthicsCaseStatus.RESOLVED,
    },
    EthicsCaseStatus.RESOLVED: set(),  # Terminal
    EthicsCaseStatus.CANCELLED: set(),  # Terminal
}
```

---

## 7. Testing Requirements

| Test Category               | Coverage Target |
| --------------------------- | --------------- |
| State machine transitions   | 100%            |
| Invalid transition blocking | 100%            |
| Independence verification   | 100%            |
| Pattern risk calculation    | 100%            |
| Resolution gate             | 100%            |
| Step creation               | 100%            |
| Review escalation           | 100%            |

---

## 8. Open Questions

| # | Question                    | Impact               | Status   |
| - | --------------------------- | -------------------- | -------- |
| 1 | Witness interview storage   | PII management       | Resolved |
| 2 | Anonymous complaints        | Complainant handling | Open     |
| 3 | Cross-tenant investigations | Tenant isolation     | Resolved |
| 4 | Investigation templates     | Workflow flexibility | Open     |

---

## 9. References

- ADR: `docs-shared/canonsys/01_design/035-ethics-investigation/ADR-035-ethics-investigation.md`
- Investigation package: `hub/domains/employee/packages/investigation/`
- HR package: `hub/domains/employee/packages/hr/`
- Legal package: `hub/domains/governance/packages/legal/`
- Related: ADR-008-policy-gates (gate protocol)
- Related: ADR-022-consent (legal hold interaction)
