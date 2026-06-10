---
doc_type: ADR
title: "ADR-032: Segregation of Duties Conflict Matrix"
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
  - "ADR-015-jit-role"
  - "ADR-016-break-glass"
successors:
  - "TDS-032-segregation-of-duties"
supersedes: null
superseded_by: null

tags:
  - segregation-of-duties
  - sox-compliance
  - finance
  - authorization
  - anti-gaming
related:
  - "TDS-032-segregation-of-duties"
  - "ADR-015-jit-role"
  - "ADR-008-policy-gates"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# ADR-032: Segregation of Duties Conflict Matrix

## Context

### Problem Statement

SOX Section 302/404 requires segregation of duties (SoD) for financial controls. No single
individual should have conflicting permissions that allow them to both initiate and approve
financial transactions, or to modify records and also audit those modifications.

CanonSys manages privileged role assignments across finance, treasury, and audit domains. Without
explicit SoD enforcement:

1. **Fraud risk**: User granted both "initiate wire transfer" and "approve wire transfer" roles
2. **Audit failure**: User with "modify ledger" and "audit ledger" roles violates SOX
3. **Compliance gap**: No evidence trail when conflicting roles are assigned

**Why This Matters**: A single-actor bypass defeats all multi-approval workflows. SOC 2, SOX, and
employment law all require separation between conflicting roles.

### Background

**Regulatory Requirements**:

| Regulation | Section             | Requirement                                        |
| ---------- | ------------------- | -------------------------------------------------- |
| **SOX**    | Section 302         | CEO/CFO certify internal controls                  |
| **SOX**    | Section 404         | Document and test internal controls over reporting |
| **COSO**   | Control Environment | Segregation of duties as fundamental control       |
| **PCAOB**  | AS 2201             | Evaluate segregation of duties in audit            |
| **SOC 2**  | CC6.1               | Segregation of incompatible duties                 |

**Driving Forces**:

- **Fraud Prevention**: No single person should control complete transaction lifecycle
- **Audit Compliance**: SOX 302/404 certification requires demonstrable SoD controls
- **Anti-Gaming**: Prevent role accumulation that enables self-approval
- **Evidence Trail**: Every SoD check must produce audit evidence

### Assumptions

1. User identity is reliably established (authentication is not in scope)
2. Role assignments are accurate and up-to-date in source systems
3. Time-bounded exemptions are sufficient for legitimate exceptions
4. Cross-system role aggregation is feasible via HRIS/ERP APIs

### Constraints

| Type          | Constraint                              | Impact                        |
| ------------- | --------------------------------------- | ----------------------------- |
| Fail-Closed   | If matrix unavailable, all grants block | High availability requirement |
| Bidirectional | (A,B) conflict implies (B,A) conflict   | Symmetric rule application    |
| Time-Bounded  | No permanent exemptions                 | Max 365 days per exemption    |
| Cross-System  | Must aggregate roles from all systems   | HRIS/ERP/Treasury integration |

---

## Decision

### Summary

**We will** implement SoD conflict matrix as a data-driven gate with exemption workflow. The
`verify_no_sod_conflict()` vocabulary feature checks all role grants against a versioned conflict
matrix, with documented exemptions requiring CFO/CISO/GC approval.

### Rationale

**Key factors in the decision**:

1. **Data-Driven Matrix**: Conflicts defined declaratively, not in code. Changes don't require
   deployment. The matrix can be versioned and audited.

2. **Early Detection**: Block conflicts at role grant time, not execution time. User knows
   immediately if a role combination is prohibited.

3. **Exemption Workflow**: Legitimate business exceptions are supported with:
   - Business justification (minimum 100 characters)
   - Compensating controls documentation
   - CFO/CISO/GC approval
   - Evidence binding (sealed CEPs)
   - Time-bounded validity (max 1 year)

4. **Cross-System Aggregation**: SoD checks aggregate roles from all connected systems (Workday,
   SAP, Treasury, CanonSys) to prevent siloed conflicts.

5. **Vocabulary Integration**: `verify_no_sod_conflict()` is a vocabulary feature, consistent with
   CanonSys architecture. The phrase IS the implementation.

### Implementation Approach

The SoD system has three components:

```
Role Grant Request
        |
        +---[1]--- Load SoDConflictMatrix (versioned)
        |
        +---[2]--- Aggregate user's current roles (all systems)
        |
        +---[3]--- Check requested_role vs current_roles
        |
        +--- No conflict --> PROCEED with grant
        |
        +--- Conflict found
                |
                +---[4]--- Check for valid SoDExemption
                |
                +--- Exemption valid --> PROCEED (DEGRADED defensibility)
                |
                +--- No exemption --> DENY with conflict details
```

**Conflict Type Taxonomy**:

| Conflict Type              | Description                                    | Example                         |
| -------------------------- | ---------------------------------------------- | ------------------------------- |
| `TRANSACTION_DUAL_CONTROL` | Same person cannot initiate AND approve        | Wire initiator + Wire approver  |
| `RECORD_CUSTODY`           | Same person cannot modify AND have custody     | Ledger editor + Asset custodian |
| `AUDIT_INDEPENDENCE`       | Same person cannot operate AND audit           | System admin + Audit reviewer   |
| `APPROVAL_CHAIN`           | Same person cannot be multiple approval levels | L1 approver + L2 approver       |
| `ACCESS_CONTROL`           | Same person cannot grant AND use access        | Access admin + Privileged user  |

### Alternatives Considered

#### Alternative 1: Static Role Exclusion Rules

**Description**: Hardcode role pairs that cannot coexist in authorization layer.

| Criterion       | Score (1-5) | Notes                             |
| --------------- | ----------- | --------------------------------- |
| Flexibility     | 2           | No exemption path for edge cases  |
| Maintainability | 2           | Adding roles requires code change |
| Audit           | 2           | Violations blocked but not logged |
| Performance     | 5           | Simple in-memory lookup           |

**Why Not Chosen**: No exemption path for legitimate business needs. Too rigid.

#### Alternative 2: Runtime Permission Check Only

**Description**: Check SoD conflicts at action time, not at role grant time.

| Criterion       | Score (1-5) | Notes                              |
| --------------- | ----------- | ---------------------------------- |
| Flexibility     | 4           | Allows role assignment flexibility |
| Maintainability | 3           | Checks scattered across actions    |
| Audit           | 3           | Catches at execution               |
| Performance     | 3           | Check on every action              |

**Why Not Chosen**: Late detection leads to user confusion. Conflicting roles still exist in system.

#### Alternative 3: OPA Policy for SoD

**Description**: Use OPA policies to evaluate separation requirements.

| Criterion       | Score (1-5) | Notes                          |
| --------------- | ----------- | ------------------------------ |
| Flexibility     | 5           | Full Rego expressiveness       |
| Maintainability | 3           | Policy bundles need management |
| Audit           | 4           | OPA logs decisions             |
| Performance     | 2           | OPA evaluation overhead        |

**Why Not Chosen**: OPA adds complexity for fundamentally simple membership check.

### Decision Matrix

| Criterion          | Weight | Static Rules | Runtime Check | OPA      | Conflict Matrix |
| ------------------ | ------ | ------------ | ------------- | -------- | --------------- |
| Flexibility        | 25%    | 2            | 4             | 5        | 4               |
| Maintainability    | 25%    | 2            | 3             | 3        | 5               |
| Audit              | 30%    | 2            | 3             | 4        | 5               |
| Performance        | 20%    | 5            | 3             | 2        | 4               |
| **Weighted Total** | 100%   | **2.50**     | **3.25**      | **3.70** | **4.55**        |

---

## Consequences

### Positive Consequences

1. **SOX Compliance**: Explicit enforcement of Section 302/404 controls. Auditors can review matrix
   and exemption evidence.

2. **Early Detection**: Conflicts caught at role grant time, not execution. Clear feedback to users.

3. **Complete Audit Trail**: Every SoD check produces evidence with matrix version, conflicts found,
   exemption used (if any), and evidence hash.

4. **Exemption Support**: Legitimate business exceptions are documented with compensating controls
   and CFO/CISO/GC oversight.

5. **Data-Driven**: Matrix changes don't require code deployment. Rules can be versioned and
   scheduled (effective_from/until).

### Negative Consequences

1. **Integration Complexity**: Must aggregate roles from multiple systems (Workday, SAP, Treasury).
   Mitigation: Role caching with invalidation on change.

2. **Matrix Maintenance**: New roles require conflict analysis. Mitigation: Review process for new
   roles.

3. **Exemption Overhead**: Exemption workflow adds process friction. Mitigation: Clear criteria and
   fast turnaround.

4. **Cache Invalidation**: Role changes must invalidate SoD caches. Mitigation: Event-driven cache
   invalidation.

### Neutral Consequences

1. **Vocabulary Growth**: Adds `verify_no_sod_conflict()`, `require_segregation_analysis()`,
   `require_distinct_identities()`, `require_dual_approval()` to vocabulary layer.

### Risks

| Risk                               | Likelihood | Impact | Mitigation                         |
| ---------------------------------- | ---------- | ------ | ---------------------------------- |
| Stale role data leads to wrong SoD | M          | H      | Real-time sync, cache TTL          |
| Exemption abuse                    | L          | H      | CFO/CISO/GC approval, audit review |
| Matrix not loaded                  | L          | H      | Fail-closed, monitoring, fallback  |
| Role normalization errors          | M          | M      | Comprehensive mapping validation   |

### Migration Impact

**Backwards Compatibility**: Additive. Existing role grants continue working. New matrix-based
checks applied going forward.

**Migration Steps**:

1. Deploy matrix infrastructure
2. Seed initial conflict rules from SOX control documentation
3. Enable monitoring-only mode (log but don't block)
4. Review conflict detections for false positives
5. Enable enforcement mode

---

## Verification

### Success Criteria

- [ ] SoDConflictMatrix entity with versioning
- [ ] verify_no_sod_conflict() gate function
- [ ] SoDExemption workflow with approval
- [ ] Cross-system role aggregation (at least 2 sources)
- [ ] Evidence emission on all checks
- [ ] Integration with JIT role grants (ADR-015)

### Metrics to Track

| Metric                        | Baseline | Target   | Review Date |
| ----------------------------- | -------- | -------- | ----------- |
| SoD checks performed          | N/A      | Track    | 2026-02-20  |
| Conflicts detected            | N/A      | Track    | 2026-02-20  |
| Conflicts blocked (no exempt) | N/A      | Track    | 2026-02-20  |
| Exemptions granted            | N/A      | < 10/mo  | 2026-03-20  |
| Matrix version changes        | N/A      | < 4/year | 2026-06-20  |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Quarterly (aligned with SOX audit cycle)
- **Review Owner**: Compliance & Finance Teams

---

## Vocabulary Mapping

### Package: `authorization`

**Location**: `hub/foundation/packages/authorization/`

| Phrase                           | Purpose                              | Surfaces                                         |
| -------------------------------- | ------------------------------------ | ------------------------------------------------ |
| `require_segregation_analysis`   | Compute separation level             | Candidate Advancement, Adverse Action Sign-Off   |
| `require_distinct_identities`    | Enforce initiator != approver        | Comment/Document Approval                        |
| `require_dual_approval`          | Enforce two-party sign-off           | Adverse Action Sign-Off                          |
| `require_separation_of_duties`   | Generic SoD check                    | Multiple                                         |
| `verify_approval_chain_complete` | Verify all required approvers signed | Adverse Action Sign-Off                          |
| `check_er_clearance`             | Check ER clearance status            | Candidate Advancement                            |

### Control Surface Coverage

| Surface                    | Decision                  | SoD Requirement                          |
| -------------------------- | ------------------------- | ---------------------------------------- |
| Candidate Advancement      | Candidate advancement     | require_segregation_analysis (REPORTING) |
| Comment/Document Approval  | Comment/document approval | require_distinct_identities (IDENTITY)   |
| Adverse Action Sign-Off    | Adverse action sign-off   | require_dual_approval (DEPARTMENT)       |

### Financial Control Surfaces (SOX)

| PRD | Surface                            | SoD Check                                |
| --- | ---------------------------------- | ---------------------------------------- |
| 84  | PROMOTE_TO_PRIVILEGED_FINANCE_ROLE | All finance role conflicts               |
| 09  | LARGE_WIRE_TRANSFER_EXECUTION      | wire_initiator vs wire_approver          |
| 56  | LARGE_PAYMENT_APPROVAL             | payment_requestor vs payment_approver    |
| 57  | REFUND_APPROVAL_ABOVE_THRESHOLD    | refund_requestor vs refund_approver      |
| 60  | FINANCIAL_GUARANTEE_ISSUANCE       | guarantee_requestor vs risk_assessor     |
| 61  | BUDGET_LOCK_UNLOCK                 | budget_modifier vs budget_approver       |
| 62  | CAP_TABLE_CHANGE                   | cap_table_preparer vs cap_table_approver |
| 63  | EQUITY_ISSUANCE                    | equity_preparer vs equity_approver       |
| 64  | EQUITY_CANCELLATION                | equity_preparer vs legal_reviewer        |
| 70  | SIGN_COMPLIANCE_ATTESTATION        | controls_tester vs attestation_signer    |
| 91  | DISABLE_AUDIT_LOGGING_FOR_SYSTEM   | logging_operator vs logging_approver     |

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate framework for SoD checks
- `ADR-015-jit-role`: JIT role grants pass through SoD check
- `ADR-016-break-glass`: Emergency override for SoD (logged)

### Impacts

- `TDS-032-segregation-of-duties`: Technical specification
- All finance/treasury control surfaces requiring maker-checker pattern

---

## References

- TDS: `docs-shared/canonsys/01_design/032-segregation-of-duties/TDS-032-segregation-of-duties.md`
- Authorization package: `hub/foundation/packages/authorization/`
- SOX Section 302/404: Management certification requirements
- COSO Framework: Segregation of duties principle
- PCAOB AS 2201: Audit standards for internal controls
- SOC 2 CC6.1: Logical and physical access controls

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
