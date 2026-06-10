---
doc_type: ADR
title: "ADR-033: Corporate Transaction Compliance Workflows"
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
  - "ADR-006-evidence-chain-cep"
successors:
  - "TDS-033-corporate-transactions"
supersedes: null
superseded_by: null

tags:
  - corporate-transactions
  - m-and-a
  - anti-gaming
  - due-diligence
  - gun-jumping
related:
  - "TDS-033-corporate-transactions"
  - "ADR-022-consent"
  - "ADR-008-policy-gates"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# ADR-033: Corporate Transaction Compliance Workflows

## Context

### Problem Statement

M&A transactions require specialized compliance workflows that differ fundamentally from hiring
workflows. Corporate transactions involve:

- **Due Diligence**: Data room access, clean team requirements, sensitive data handling
- **Integration Planning**: Post-close integration with HR system handoffs
- **Carve-Out Compliance**: Regulatory divestiture requirements (FTC/DOJ)
- **Material Change Disclosure**: Ongoing disclosure obligations during deal lifecycle
- **Closing Conditions**: Conditions precedent satisfaction tracking

**Why This Matters**: Without explicit anti-gaming controls, users can assert "conditions satisfied"
or "clean team not required" to bypass compliance gates. Gun-jumping violations under the HSR Act
carry penalties up to $51,744 per day.

### Background

**Regulatory Requirements**:

| Regulation      | Section           | Requirement                                          |
| --------------- | ----------------- | ---------------------------------------------------- |
| **HSR Act**     | 7A                | Pre-merger notification and waiting period           |
| **HSR Act**     | 7A                | Gun-jumping prevention (no premature integration)    |
| **Sherman Act** | Section 1         | Information sharing restrictions between competitors |
| **FTC/DOJ**     | Merger Guidelines | Clean team requirements for sensitive data           |
| **SEC**         | 8-K               | Material change disclosure obligations               |

**Driving Forces**:

- **Anti-Gaming**: Transaction status must be derived from evidence, not user assertions
- **Gun-Jumping Prevention**: Phase gates block premature integration activities
- **Audit-Grade Evidence**: Every transaction phase needs complete evidence trail
- **Phase-Gated Operations**: Actions blocked until phase-appropriate
- **Data Room Controls**: Consent-based access to sensitive transaction data

### Assumptions

1. Transaction lifecycle phases are well-defined (PRE_LOI through CLOSED/TERMINATED)
2. Clean team requirements can be derived from data categories present
3. Regulatory approval status is trackable via external integrations
4. Evidence chain exists for all compliance-relevant data (ADR-006)

### Constraints

| Type           | Constraint                           | Impact                  |
| -------------- | ------------------------------------ | ----------------------- |
| Anti-Gaming    | Status derived, not asserted         | Prevents user bypass    |
| Phase-Gated    | Operations blocked until phase-ready | No premature activities |
| Evidence-Bound | Every decision has CEP reference     | Complete audit trail    |
| Time-Bounded   | Regulatory deadlines are enforced    | Disclosure compliance   |

---

## Decision

### Summary

**We will** implement corporate transaction compliance using **anti-gaming derivation patterns**
where the system derives compliance status from evidence rather than accepting user assertions.
Transaction lifecycle is managed through **phase gates** that block inappropriate activities.

### Rationale

**Key factors in the decision**:

1. **Anti-Gaming Derivations**: The `derive_*` pattern examines evidence and determines status.
   Users cannot assert "clean team not required" - the system derives this from data categories.

2. **Phase-Gated Operations**: DealPhaseGate blocks actions until the transaction reaches the
   appropriate phase. Integration planning is blocked until CLOSING_CONDITIONS phase.

3. **Evidence-Bound Decisions**: Every derivation produces an evidence hash linking the decision to
   the data examined. This provides audit-grade defense.

4. **Consent Integration**: Data room access integrates with ADR-022 consent model. Sensitive data
   requires explicit consent tokens.

5. **Vocabulary Integration**: Derivations are vocabulary features - `derive_clean_team_required`,
   `derive_carve_out_readiness`, etc. The phrase IS the implementation.

### Implementation Approach

**Phase Lifecycle**:

```python
class DealPhase(StrEnum):
    PRE_LOI = "pre_loi"                      # Pre-letter of intent
    LOI_SIGNED = "loi_signed"                # LOI executed
    DUE_DILIGENCE = "due_diligence"          # Active DD
    DEFINITIVE_AGREEMENT = "definitive_agreement"
    HSR_FILING = "hsr_filing"                # HSR filing submitted
    REGULATORY_REVIEW = "regulatory_review"  # Awaiting approval
    CLOSING_CONDITIONS = "closing_conditions" # Satisfying conditions
    CLOSED = "closed"                        # Transaction complete
    TERMINATED = "terminated"                # Deal terminated
```

**Anti-Gaming Pattern**:

```python
# WRONG: Verification (user can game)
# User asserts: "clean team not required"
# System verifies: check if assertion valid

# CORRECT: Derivation (anti-gaming)
# System examines: data categories present in deal
# System derives: clean team IS required because competitive_pricing found
result = await derive_clean_team_required(deal_id, ctx)
```

**Derivation Actions**:

| Derivation                              | Purpose                   | Regulation           |
| --------------------------------------- | ------------------------- | -------------------- |
| `derive_clean_team_required`            | Data room access controls | HSR Act, Sherman Act |
| `derive_conditional_findings_addressed` | Due diligence completion  | SEC, Fiduciary duty  |
| `derive_carve_out_readiness`            | Divestiture compliance    | FTC/DOJ Guidelines   |
| `derive_condition_satisfaction_status`  | Closing conditions        | M&A contract law     |

### Alternatives Considered

#### Alternative 1: User-Asserted Compliance Status

**Description**: Allow users to assert "clean team not required" or "conditions satisfied."

| Criterion        | Score (1-5) | Notes                         |
| ---------------- | ----------- | ----------------------------- |
| Gaming Risk      | 1           | Users can shortcut compliance |
| Regulatory Def   | 2           | "User said it was fine"       |
| Evidence Quality | 2           | Depends on user honesty       |
| Simplicity       | 5           | Easy to implement             |

**Why Not Chosen**: Gaming risk is unacceptable for SOX/HSR compliance.

#### Alternative 2: Flat Transaction Status

**Description**: Store transaction as simple status string without phase gates.

| Criterion   | Score (1-5) | Notes                         |
| ----------- | ----------- | ----------------------------- |
| Enforcement | 2           | No phase-appropriate blocking |
| Gun-jumping | 2           | Depends on user discipline    |
| Audit Trail | 3           | Status changes logged         |
| Flexibility | 5           | Any transition allowed        |

**Why Not Chosen**: No enforcement of phase-appropriate activities.

#### Alternative 3: External Compliance System Integration

**Description**: Integrate with external M&A compliance tools (Intralinks, Datasite).

| Criterion        | Score (1-5) | Notes                         |
| ---------------- | ----------- | ----------------------------- |
| Evidence Control | 2           | External system owns evidence |
| Integration      | 3           | API dependencies              |
| Consistency      | 2           | Split compliance logic        |
| Vendor Lock-in   | 2           | Dependency on vendor roadmap  |

**Why Not Chosen**: Evidence must be in CanonSys chain for unified compliance.

### Decision Matrix

| Criterion          | Weight | User-Assert | Flat Status | External | Anti-Gaming |
| ------------------ | ------ | ----------- | ----------- | -------- | ----------- |
| Gaming Prevention  | 30%    | 1           | 2           | 3        | 5           |
| Regulatory Defense | 30%    | 2           | 3           | 3        | 5           |
| Evidence Quality   | 25%    | 2           | 3           | 2        | 5           |
| Simplicity         | 15%    | 5           | 5           | 3        | 3           |
| **Weighted Total** | 100%   | **2.05**    | **2.90**    | **2.75** | **4.70**    |

---

## Consequences

### Positive Consequences

1. **Gun-Jumping Prevention**: Phase gates block premature integration activities. Operations
   requiring CLOSING_CONDITIONS phase are blocked in earlier phases.

2. **Anti-Gaming Protection**: Derivation pattern prevents status manipulation. Users cannot assert
   "conditions satisfied" - the system derives from evidence.

3. **Audit-Grade Evidence**: Every derivation produces evidence hash linking to data examined.
   Complete trail for regulatory defense.

4. **Consent Integration**: Data room access uses existing consent model (ADR-022). Clean team
   requirements integrate with consent tokens.

5. **Typed Conditions**: Clear condition categories (REGULATORY_APPROVAL, FINANCING, NO_MAC) enable
   per-type reporting and tracking.

### Negative Consequences

1. **Transaction Complexity**: M&A transactions are inherently complex. The derivation pattern adds
   computation overhead. Mitigation: Caching with invalidation on evidence changes.

2. **Phase Enforcement Rigidity**: May require exception handling for edge cases. Mitigation:
   Break-glass with evidence binding (ADR-016).

3. **Integration Requirements**: HSR filing status requires external integration. Mitigation: Define
   clear API contracts for regulatory status updates.

### Neutral Consequences

1. **Vocabulary Growth**: Adds 4 derivation functions to vocabulary layer. These are anti-gaming
   features, distinct from standard verify/require patterns.

### Risks

| Risk                               | Likelihood | Impact | Mitigation                           |
| ---------------------------------- | ---------- | ------ | ------------------------------------ |
| External regulatory status stale   | M          | H      | Polling + webhook integration        |
| Derivation performance on large DD | M          | M      | Evidence caching, incremental derive |
| Clean team membership disputes     | L          | M      | Clear derivation criteria, audit log |
| Phase transition race conditions   | L          | H      | Optimistic locking on phase changes  |

### Migration Impact

**Backwards Compatibility**: Additive. Existing corporate workflows continue. New derivation-based
checks applied to new transactions.

**Migration Steps**:

1. Deploy derivation functions and result types
2. Deploy DealPhaseGate infrastructure
3. Migrate existing transactions to phase model
4. Enable enforcement on new transactions
5. Backfill phase history for existing deals

---

## Verification

### Success Criteria

- [ ] `derive_clean_team_required` examines data categories and returns derived result
- [ ] `derive_carve_out_readiness` checks standard carve-out components
- [ ] `derive_condition_satisfaction_status` aggregates all condition types
- [ ] DealPhaseGate blocks operations in inappropriate phases
- [ ] Evidence hash computed for all derivations
- [ ] Data room access integrates with consent model

### Metrics to Track

| Metric                         | Baseline | Target  | Review Date |
| ------------------------------ | -------- | ------- | ----------- |
| Gun-jumping violations blocked | N/A      | 100%    | 2026-02-20  |
| Derivation accuracy            | N/A      | > 99%   | 2026-03-20  |
| Phase gate enforcement         | N/A      | 100%    | 2026-02-20  |
| Clean team derivation time     | N/A      | < 100ms | 2026-03-20  |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Per-transaction audits
- **Review Owner**: Legal & Compliance Teams

---

## Vocabulary Mapping

### Package: `corporate`

**Location**: `hub/domains/corporate/packages/corporate/`

| Phrase                                  | Purpose                      | Surfaces             |
| --------------------------------------- | ---------------------------- | -------------------- |
| `derive_clean_team_required`            | Derive clean team necessity  | Due Diligence        |
| `derive_conditional_findings_addressed` | Derive DD completion status  | Due Diligence        |
| `derive_carve_out_readiness`            | Derive divestiture readiness | Carve-Out Compliance |
| `derive_condition_satisfaction_status`  | Derive closing conditions    | Closing Conditions   |

### Control Surface Coverage

| Surface              | Decision             | Anti-Gaming Derivation                                                |
| -------------------- | -------------------- | --------------------------------------------------------------------- |
| Due Diligence        | Due Diligence        | `derive_clean_team_required`, `derive_conditional_findings_addressed` |
| Integration Planning | Integration Planning | DealPhaseGate (CLOSING_CONDITIONS)                                    |
| Carve-Out Compliance | Carve-Out Compliance | `derive_carve_out_readiness`                                          |
| Material Change      | Material Change      | MaterialChange entity with disclosure deadlines                       |
| Closing Conditions   | Closing Conditions   | `derive_condition_satisfaction_status`                                |

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate framework for phase gates
- `ADR-022-consent`: Consent integration for data room access
- `ADR-006-evidence-chain-cep`: Evidence binding for derivations

### Impacts

- `TDS-033-corporate-transactions`: Technical specification
- Due Diligence, Integration Planning, Carve-Out Compliance, Material Change Disclosure, and Closing Conditions control surfaces
- Future M&A workflow automation

---

## References

- TDS: `docs-shared/canonsys/01_design/033-corporate-transactions/TDS-033-corporate-transactions.md`
- Corporate package: `hub/domains/corporate/packages/corporate/`
- Hart-Scott-Rodino Act: Antitrust filing/waiting requirements
- Sherman Act Section 1: Information sharing restrictions
- FTC/DOJ Merger Guidelines: Gun-jumping prevention
- SEC 8-K: Material change disclosure rules

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
