# 035 Ethics Investigation - Vocabulary Mapping

**Status**: Implemented (vocabulary layer)

## Package Mapping

### Primary Package: `investigation`

**Location**: `hub/domains/employee/packages/investigation/`

| Component          | Path            | Status      |
| ------------------ | --------------- | ----------- |
| Package definition | `package.py`    | Implemented |
| Service            | `service.py`    | Implemented |
| Exceptions         | `exceptions.py` | Implemented |

### Phrases

| Phrase                             | Path                                          | Regulatory Basis |
| ---------------------------------- | --------------------------------------------- | ---------------- |
| `open_ethics_case`                 | `phrases/open_ethics_case.py`                 | Title VII        |
| `assign_investigator`              | `phrases/assign_investigator.py`              | EEOC Guidance    |
| `verify_investigator_independence` | `phrases/verify_investigator_independence.py` | EEOC Guidance    |
| `compute_pattern_risk`             | `phrases/compute_pattern_risk.py`             | Title VII        |
| `resolve_ethics_case`              | `phrases/resolve_ethics_case.py`              | Title VII        |
| `verify_ethics_case_resolution`    | `phrases/verify_ethics_case_resolution.py`    | Title VII        |

### Secondary Package: `hr`

**Location**: `hub/domains/employee/packages/hr/`

| Phrase                      | Path                                   | Regulatory Basis |
| --------------------------- | -------------------------------------- | ---------------- |
| `record_investigation_step` | `phrases/record_investigation_step.py` | Documentation    |
| `request_review`            | `phrases/request_review.py`            | Process control  |
| `complete_review`           | `phrases/complete_review.py`           | Process control  |

### Secondary Package: `legal`

**Location**: `hub/domains/governance/packages/legal/`

| Phrase                      | Path                                   | Regulatory Basis |
| --------------------------- | -------------------------------------- | ---------------- |
| `check_legal_hold_required` | `phrases/check_legal_hold_required.py` | Litigation hold  |
| `trigger_legal_hold`        | `phrases/trigger_legal_hold.py`        | Litigation hold  |

## Control Surface Coverage

| Surface                          | Phrases                                                |
| -------------------------------- | ------------------------------------------------------ |
| Close Ethics Case Without Action | `verify_ethics_case_resolution`, `resolve_ethics_case` |
| Litigation Hold Release          | `check_legal_hold_required`                            |
| Privilege Waiver                 | Related to legal review                                |
| Settlement Authority             | Related to case resolution                             |

## State Machine

```python
class EthicsCaseStatus(Enum):
    OPEN = "open"                       # Case received, not yet assigned
    INVESTIGATING = "investigating"     # Active investigation
    PENDING_REVIEW = "pending_review"   # Awaiting required reviews
    ESCALATED = "escalated"             # Escalated to committee/counsel
    RESOLVED = "resolved"               # Case closed with determination
    CANCELLED = "cancelled"             # Case withdrawn or consolidated
```

## State Transitions

| From           | To             | Trigger             | Requirements                |
| -------------- | -------------- | ------------------- | --------------------------- |
| OPEN           | INVESTIGATING  | assign_investigator | Independence verified       |
| OPEN           | CANCELLED      | cancel_case         | Reason documented           |
| INVESTIGATING  | PENDING_REVIEW | document_findings   | Findings documented         |
| INVESTIGATING  | ESCALATED      | escalate_case       | Committee/counsel required  |
| PENDING_REVIEW | RESOLVED       | resolve_ethics_case | All reviews complete        |
| ESCALATED      | RESOLVED       | resolve_ethics_case | Committee resolves directly |

## Architectural Patterns

### 1. State Machine

```python
# Valid state transitions
VALID_TRANSITIONS = {
    OPEN: {INVESTIGATING, CANCELLED},
    INVESTIGATING: {PENDING_REVIEW, ESCALATED, CANCELLED},
    PENDING_REVIEW: {RESOLVED, ESCALATED, INVESTIGATING},
    ESCALATED: {PENDING_REVIEW, RESOLVED},
    RESOLVED: {},  # Terminal
    CANCELLED: {},  # Terminal
}

# Transition validation
async def transition_case(case_id, new_status, ctx):
    case = await get_ethics_case(case_id, ctx)
    if new_status not in VALID_TRANSITIONS[case.content.status]:
        raise InvalidTransitionError(case.content.status, new_status)
```

### 2. Computed Independence

```python
async def verify_investigator_independence(investigator_id, subject_id, ctx):
    """Independence computed from org graph, not asserted."""
    investigator_chain = await get_reporting_chain(investigator_id, ctx)
    subject_chain = await get_reporting_chain(subject_id, ctx)

    violations = []
    if investigator_id in subject_chain:
        violations.append("investigator_reports_to_subject")
    if subject_id in investigator_chain:
        violations.append("subject_reports_to_investigator")

    return IndependenceResult(
        independent=len(violations) == 0,
        violations=tuple(violations),
    )
```

### 3. Pattern Risk Detection

```python
async def compute_pattern_risk(subject_id, ctx):
    """Surface prior allegations for pattern awareness."""
    prior_cases = await find_ethics_cases(
        subject_id=subject_id,
        opened_after=now_utc() - timedelta(days=24*30),
        ctx=ctx,
    )
    risk_band = "ELEVATED" if len(prior_cases) >= 2 else "NORMAL"
    return PatternRiskResult(
        prior_count=len(prior_cases),
        risk_band=risk_band,
        requires_committee=risk_band == "ELEVATED",
    )
```

### 4. Resolution Gate

```python
async def verify_ethics_case_resolution(case_id, ctx):
    """Gate: Verify all requirements before case closure."""
    case = await get_ethics_case(case_id, ctx)
    missing = []

    if not case.content.investigator_independence_verified:
        missing.append("independence_not_verified")
    if case.content.finding_severity is None:
        missing.append("findings_not_documented")
    if case.content.counsel_review_required and not case.content.counsel_review_complete:
        missing.append("counsel_review_required")

    return EthicsResolutionResult(
        resolved=len(missing) == 0,
        missing=tuple(missing),
    )
```

## Dependencies

### This Design Depends On

- **ADR-008-policy-gates**: Gate framework for resolution verification
- **ADR-022-consent**: Legal hold interaction with consent processing
- **Org Graph Service**: For independence verification

### Designs That Depend On This

- Close Ethics Case Without Action surface
- Litigation Hold Release surface
- HR decision surfaces that trigger investigations

## Implementation Status

| Component                        | Status      | Notes                |
| -------------------------------- | ----------- | -------------------- |
| investigation pkg                | Implemented | 6 phrases            |
| hr pkg (investigation steps)     | Implemented | 3 phrases            |
| legal pkg (holds)                | Implemented | 2 phrases            |
| EthicsCase entity                | Implemented | State machine        |
| InvestigationStep entity         | Implemented | Audit trail          |
| EthicsCaseStatus enum            | Implemented | 6 states             |
| EthicsCaseType enum              | Implemented | 8 types              |
| verify_ethics_case_resolution    | Implemented | Resolution gate      |
| verify_investigator_independence | Implemented | Org graph check      |
| compute_pattern_risk             | Implemented | Prior allegations    |
| Legal hold integration           | Planned     | ADR-022 coordination |

## Database Tables

```sql
ethics_cases          -- Main case entity with state machine
investigation_steps   -- Immutable audit trail of actions
```

## Charter Integration

**Charter**: `investigation.canon`

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

**Control Surfaces**: Close Ethics Case Without Action, Litigation Hold Release, Privilege Waiver, Settlement Authority
