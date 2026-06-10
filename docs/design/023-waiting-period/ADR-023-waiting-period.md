---
doc_type: ADR
title: "ADR-023: Waiting Period Enforcement"
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
  - ADR-008-policy-gates
  - ADR-022-consent
successors:
  - TDS-023-waiting-period
supersedes: null
superseded_by: null

tags:
  - fcra
  - waiting-period
  - adverse-action
  - compliance
related:
  - TDS-023-waiting-period
  - ADR-008-policy-gates
  - ADR-022-consent
pr: null

quality:
  confidence: 0.95
  sources: 4
  docs: full
---

# ADR-023: Waiting Period Enforcement

## Context

### Problem Statement

FCRA and other regulations mandate waiting periods before adverse actions. These are not
suggestions - they are mandatory delays that must be enforced, auditable, support interruption
(disputes), use business days (not calendar days), and be jurisdiction-aware (holidays vary).

**Why This Matters**: A pre-adverse action notice without the required 5 business day waiting period
invalidates the entire adverse action process. Companies have lost FCRA litigation specifically
because they could not prove the waiting period was enforced. The Decision Kill Chain requires a
gate that enforces these time-based requirements with evidence-grade audit trails.

### Background

**Current State**: Regulatory waiting periods exist across multiple jurisdictions:

- **FCRA Section 604(b)(3)**: Pre-adverse action notice must be sent with 5 business day waiting
  period before final adverse action
- **NYC Fair Chance Act**: Article 23-A analysis requires response period
- **State variations**: Some jurisdictions require longer waiting periods (e.g., California requires
  7 days)

**Driving Forces**:

- **Regulatory enforcement**: Actions MUST be blocked until period elapses - not advisory
- **Audit-grade proof**: Every calculation must be reproducible and defensible in litigation
- **Business day complexity**: Weekends and holidays vary by jurisdiction
- **Pause/resume**: Disputes and extensions must pause the waiting period clock
- **Evidence binding**: Timing proof must chain to the evidence system

### Assumptions

1. Business day calculations are deterministic given jurisdiction and date range
2. Holiday data can be maintained per jurisdiction and year
3. Disputes pause the waiting period until resolved

### Constraints

| Type        | Constraint                            | Impact                                                |
| ----------- | ------------------------------------- | ----------------------------------------------------- |
| Technical   | Query-time check (no background jobs) | Must compute elapsed days at check time               |
| Business    | Business days, not calendar days      | Requires jurisdiction-aware holiday handling          |
| Regulatory  | FCRA 5 business days minimum          | Gate must block until 5 business days elapsed         |
| Operational | Disputes pause the clock              | WaitingPeriod entity needs pause/resume state machine |

---

## Decision

### Summary

**We will** implement a WaitingPeriodGate that is parameterized by event type and duration, uses a
Calendar system for business day calculations with jurisdiction-aware holidays, produces
DeadlineRecord for audit-grade evidence, and checks elapsed time at query time (no background jobs).

### Rationale

**Key factors in the decision**:

1. **Parameterized gate**: Single gate class serves all waiting period types (FCRA, Fair Chance,
   etc.)
2. **Business day correctness**: Calendar system handles weekends and jurisdiction holidays
3. **Audit defensibility**: DeadlineRecord captures the exact holidays skipped for litigation
   defense
4. **Consistency with ADR-022**: Query-time check pattern same as consent expiration

### Implementation Approach

```python
@dataclass(frozen=True, slots=True)
class WaitingPeriod:
    """A mandatory delay between events."""

    id: UUID
    tenant_id: UUID
    subject_id: UUID                    # Person subject to waiting period

    event_type: str                     # e.g., "pre_adverse_notice"
    started_at: datetime                # When period began
    required_days: int                  # Business days required
    jurisdiction: str                   # For holiday calculation

    status: WaitingPeriodStatus         # ACTIVE, PAUSED, ELAPSED, CANCELLED
    elapsed_at: datetime | None         # When period elapsed (if elapsed)

    # Pause/resume tracking
    paused_at: datetime | None
    pause_reason: str | None
    total_paused_days: int              # Cumulative pause time
```

**Parameterized Gate**:

```python
class WaitingPeriodGate:
    """Enforce mandatory waiting periods between events."""

    def __init__(
        self,
        event_type: str,
        required_days: int,
        reference_time: datetime | None = None,
    ):
        self.event_type = event_type
        self.required_days = required_days
        self.reference_time = reference_time

    @property
    def gate_id(self) -> str:
        return f"waiting_period.{self.event_type}"
```

**DeadlineRecord for Audit**:

```python
@dataclass(frozen=True, slots=True)
class DeadlineRecord:
    """Audit record for deadline calculations."""

    start: date                         # Starting date
    days: int                           # Business days added
    result: date                        # Calculated deadline
    jurisdiction: str                   # Jurisdiction code used
    holidays_skipped: tuple[date, ...]  # Holidays skipped in calculation
    calculated_at: datetime             # Timestamp of calculation
    rule_id: str | None                 # Regulatory rule reference
```

### Alternatives Considered

#### Alternative 1: Calendar Days Instead of Business Days

**Description**: Use simple calendar day counts (e.g., 5 days = 5 calendar days).

| Criterion    | Score (1-5) | Notes                                 |
| ------------ | ----------- | ------------------------------------- |
| Simplicity   | 5           | No holiday handling needed            |
| Compliance   | 1           | FCRA specifies business days          |
| Fairness     | 2           | Over-counts (5 calendar < 5 business) |
| Jurisdiction | 1           | Not aware of local holidays           |

**Why Not Chosen**: FCRA and most regulations explicitly specify business days. Calendar days would
violate requirements.

#### Alternative 2: Background Job for Elapsed Status

**Description**: Scheduled job marks waiting periods as ELAPSED when time passes.

| Criterion      | Score (1-5) | Notes                                    |
| -------------- | ----------- | ---------------------------------------- |
| Implementation | 3           | Requires job infrastructure              |
| Consistency    | 2           | Race conditions between check and update |
| Reliability    | 2           | Job failure leaves stale states          |
| Simplicity     | 4           | Simpler status field logic               |

**Why Not Chosen**: Race conditions, job failure modes. Query-time check is simpler and always
correct. Same reasoning as ADR-022.

#### Alternative 3: Static Gate Per Event Type

**Description**: Create PreAdverseNoticeGate, FinalAdverseActionGate, etc. as separate classes.

| Criterion       | Score (1-5) | Notes                                       |
| --------------- | ----------- | ------------------------------------------- |
| Type safety     | 5           | Each gate is strongly typed                 |
| Maintainability | 1           | N event types x M jurisdictions = explosion |
| Code reuse      | 1           | Duplicated logic across gates               |
| Flexibility     | 2           | New event type = new class                  |

**Why Not Chosen**: Combinatorial explosion. Parameterized gate handles all cases with single
implementation.

#### Alternative 4: Hardcoded Holidays

**Description**: Compile holiday dates into code.

| Criterion       | Score (1-5) | Notes                                    |
| --------------- | ----------- | ---------------------------------------- |
| Simplicity      | 4           | No external data dependencies            |
| Accuracy        | 2           | Holidays change (observed dates shift)   |
| Auditability    | 2           | No record of which holidays applied      |
| Maintainability | 1           | Code changes for new years/jurisdictions |

**Why Not Chosen**: Holidays change. JurisdictionRegistry with DeadlineRecord provides audit trail
of which holidays were used.

### Decision Matrix

| Criterion             | Weight | Calendar Days | Background Job | Static Gates | Hardcoded | Chosen (Param+Query) |
| --------------------- | ------ | ------------- | -------------- | ------------ | --------- | -------------------- |
| Regulatory compliance | 35%    | 1             | 4              | 4            | 3         | 5                    |
| Audit defensibility   | 25%    | 2             | 3              | 3            | 2         | 5                    |
| Maintainability       | 20%    | 4             | 2              | 1            | 1         | 4                    |
| Consistency           | 20%    | 3             | 2              | 4            | 3         | 5                    |
| **Weighted Total**    | 100%   | **2.15**      | **2.90**       | **2.95**     | **2.30**  | **4.80**             |

---

## Consequences

### Positive Consequences

1. **Enforceable**: Actions blocked until period elapses - not advisory, mandatory
2. **Auditable**: DeadlineRecord proves calculation was correct at time of check (includes
   holidays_skipped)
3. **Jurisdiction-aware**: Holiday handling per jurisdiction via JurisdictionRegistry
4. **Interruptible**: Pause/resume handles disputes and extensions per FCRA requirements
5. **Consistent**: Query-time check eliminates race conditions
6. **Composable**: Parameterized gate serves all event types with single implementation

### Negative Consequences

1. **Calendar complexity**: Must maintain JurisdictionRegistry with holiday data per year
   - **Mitigation**: Holiday data is relatively stable; can be automated from public sources
2. **State management**: WaitingPeriod entity adds state to track
   - **Mitigation**: State machine is simple (ACTIVE, PAUSED, ELAPSED, CANCELLED)
3. **Business day overhead**: Calculation is more complex than calendar days
   - **Mitigation**: Complexity is essential - calendar days would violate regulations

### Neutral Consequences

1. **Same pattern as ADR-022**: Query-time elapsed check is consistent with consent expiration check

### Risks

| Risk                     | Likelihood | Impact | Mitigation                                         |
| ------------------------ | ---------- | ------ | -------------------------------------------------- |
| Holiday data incorrect   | L          | H      | DeadlineRecord captures holidays_skipped for audit |
| Cross-timezone confusion | M          | M      | Use action location timezone, document in TDS      |
| Pause not resumed        | L          | M      | Alert on paused periods > threshold                |

### Dependencies Introduced

| Dependency             | Type     | Version | Stability | Notes                              |
| ---------------------- | -------- | ------- | --------- | ---------------------------------- |
| `JurisdictionRegistry` | Internal | N/A     | Stable    | Holiday data per jurisdiction/year |

### Migration Impact

**Backwards Compatibility**: New system - no migration required

**Migration Steps**:

1. Populate JurisdictionRegistry with holiday data for supported jurisdictions
2. Deploy WaitingPeriodGate and Calendar system
3. Create WaitingPeriod records for existing in-flight adverse actions
4. Enable gate enforcement on adverse action services

**Rollback Plan**:

1. Disable WaitingPeriodGate via feature flag
2. WaitingPeriod records remain for audit

---

## Verification

### Success Criteria

- [ ] Final adverse action blocked without 5 business day waiting period
- [ ] DeadlineRecord correctly captures holidays_skipped for jurisdiction
- [ ] Pause/resume correctly stops and restarts the waiting period clock
- [ ] WaitingPeriodGate latency < 10ms at p99 (includes calendar calculation)

### Metrics to Track

| Metric                          | Baseline | Target | Review Date |
| ------------------------------- | -------- | ------ | ----------- |
| WaitingPeriodGate latency (p99) | N/A      | < 10ms | 2026-02-15  |
| Paused periods > 7 days         | N/A      | < 5    | 2026-02-15  |
| Holiday data accuracy           | N/A      | 100%   | 2026-02-15  |

### Review Schedule

- **Initial Review**: 2026-02-15 (30 days after activation)
- **Ongoing Reviews**: Quarterly (holiday data update before each year)
- **Review Owner**: alpha[architect]

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate protocol for WaitingPeriodGate implementation
- `ADR-022-consent`: Query-time check pattern (same design rationale)

### Impacts

- `TDS-023-waiting-period`: Technical implementation specification
- FCRA adverse action workflows
- NYC Fair Chance Act compliance

---

## Vocabulary Mapping

### Package Reference

**Primary Packages**:

- `hub/foundation/packages/timing/`
- `hub/domains/governance/packages/notice/`

### Vocabulary Phrases

| Phrase                    | Pattern | Regulatory Basis            |
| ------------------------- | ------- | --------------------------- |
| `check_waiting_period`    | check   | FCRA Section 604(b)(3)      |
| `verify_notice_delivered` | verify  | FCRA Section 1681m          |
| `derive_notice_required`  | derive  | State-specific notice rules |

### Control Surfaces

| Surface                       | Key Integration                              |
| ----------------------------- | -------------------------------------------- |
| Layoff RIF Inclusion          | WARN Act 60-day notice via WaitingPeriodGate |
| Severance Calculation         | State-specific notice periods                |
| Severance Agreement Execution | OWBPA 21/45-day periods via Calendar         |

### Charter Reference

**Charter**: `fcra_adverse_action.canon`

---

## References

- TDS: `docs-shared/canonsys/01_design/023-waiting-period/TDS-023-waiting-period.md`
- WaitingPeriodGate: `libs/canon/src/canon/enforcement/catalog/waiting_period.py`
- Calendar: `libs/canon/src/canon/utils/calendar.py`
- JurisdictionRegistry: `libs/canon/src/canon/utils/loader.py`
- FCRA Section 604(b)(3): Pre-adverse action requirements
- FCRA Section 1681m: Duties upon taking adverse action
- NYC Fair Chance Act: Article 23-A response period
