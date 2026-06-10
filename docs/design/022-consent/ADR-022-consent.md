---
doc_type: ADR
title: "ADR-022: Consent Token as Capability (Not Just Audit Trail)"
version: "2.0.0"
status: active
created: "2026-01-15"
updated: "2026-01-29"
decision_date: "2026-01-15"
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - ADR-008-policy-gates
  - ADR-006-evidence-chain-cep
successors:
  - TDS-022-consent
supersedes: null
superseded_by: null

tags:
  - consent
  - gdpr
  - fcra
  - data-subject-rights
related:
  - TDS-022-consent
  - ADR-008-policy-gates
pr: null

quality:
  confidence: 0.95
  sources: 5
  docs: full
---

# ADR-022: Consent Token as Capability (Not Just Audit Trail)

## Context

### Problem Statement

CanonSys requires consent tracking for regulatory compliance across multiple jurisdictions and use
cases. The system must both prove consent existed (for audit) AND enforce that operations cannot
proceed without valid consent.

**Why This Matters**: Consent tracking typically takes one of two forms, each with critical gaps:

1. **Audit-only**: Store evidence that consent was given, check manually - evidence exists but is
   not enforced
2. **Capability-based**: Token represents the permission itself - enforcement is automatic

Without capability-based consent, developers forget to check, consent revocation does not propagate,
and the system cannot prove it enforced consent requirements.

### Background

**Current State**: CanonSys must comply with multiple consent regulations:

- **GDPR Article 7**: Consent must be demonstrable, freely given, and withdrawable
- **FCRA 604(b)**: Written consent required before consumer report procurement
- **EU AI Act**: Automated decision-making requires explicit consent
- **Illinois BIPA**: Video/biometric consent requirements

**Driving Forces**:

- **Enforceability**: Consent must gate operations, not just record them
- **Query performance**: Consent checks happen on critical paths - must be O(1) lookup
- **Revocation semantics**: Withdrawal must immediately block processing
- **Multi-party model**: Subject, grantor, and revoker may all be different people
- **Scope clarity**: Clear what each consent permits

### Assumptions

1. Each consent scope maps to a single processing purpose (GDPR Article 7(2) - distinguishable
   consent)
2. Token status can be checked at query time without background job overhead
3. Evidence records and tokens serve different purposes (audit vs. enforcement)

### Constraints

| Type        | Constraint                            | Impact                                                 |
| ----------- | ------------------------------------- | ------------------------------------------------------ |
| Technical   | O(1) consent lookup on critical path  | Requires indexed token table, not Evidence scan        |
| Business    | GDPR requires distinguishable consent | Cannot use hierarchical consent (parent implies child) |
| Regulatory  | FCRA requires written consent         | Must track consent form version                        |
| Operational | Revocation must be immediate          | Query-time check, no background job delays             |

---

## Decision

### Summary

**We will** implement ConsentToken as a queryable capability (not just evidence) with a
primary/dependency scope model, query-time expiration checking, and multi-party tracking.

### Rationale

**Key factors in the decision**:

1. **Separation of concerns**: Token for fast enforcement checks; Evidence for immutable audit trail
2. **GDPR compliance**: Scope-based model ensures distinguishable consent per processing purpose
3. **Cascade revocation**: Revoking primary consent automatically revokes all dependent scopes

### Implementation Approach

```python
class ConsentToken(Entity):
    """A consent token granting permission for a processing scope.

    This is the queryable state that ConsentGate checks.
    Separate from Evidence which records the audit trail.
    """

# Design Pattern:
# ConsentToken (Queryable State):     Evidence (Audit Trail):
# - Fast lookup by scope              - Immutable record
# - Status: ACTIVE/REVOKED/EXPIRED    - consent_grant / consent_revoke
# - ConsentGate checks this           - Proves what happened
```

**Primary/Dependency Model**:

```python
class ConsentScope(Enum):
    # Primary consent - required before any other consent
    CONSIDERATION_AUTHORIZATION = "consideration_authorization"

    # Dependent scopes - require primary first
    AI_SCORING = "ai_scoring"
    INTERVIEW_RECORDING = "interview_recording"
    BACKGROUND_CHECK = "background_check"
    DATA_PROCESSING = "data_processing"
    COMMUNICATIONS = "communications"
    THIRD_PARTY_SHARING = "third_party_sharing"

# Dependencies - revoking primary cascades to all
_SCOPE_DEPENDENCIES = {
    ConsentScope.CONSIDERATION_AUTHORIZATION: frozenset({
        ConsentScope.AI_SCORING,
        ConsentScope.INTERVIEW_RECORDING,
        ConsentScope.BACKGROUND_CHECK,
        # ... all dependent scopes
    }),
}
```

### Alternatives Considered

#### Alternative 1: Boolean Flag on Person Entity

**Description**: Store `has_background_check_consent: bool` on Person.

| Criterion        | Score (1-5) | Notes                                    |
| ---------------- | ----------- | ---------------------------------------- |
| Simplicity       | 5           | Easy to implement                        |
| Scope support    | 1           | Need multiple fields for multiple scopes |
| Version tracking | 1           | No consent form version tracking         |
| Multi-party      | 1           | No grantor/revoker distinction           |

**Why Not Chosen**: No scope separation, no version tracking, no revocation timestamp/reason.

#### Alternative 2: Evidence-Only (No Token)

**Description**: Store consent_grant Evidence, query Evidence for checks.

| Criterion     | Score (1-5) | Notes                                      |
| ------------- | ----------- | ------------------------------------------ |
| Audit trail   | 5           | Evidence is immutable, excellent for audit |
| Query perf    | 1           | O(n) scan for subject + scope              |
| Current state | 2           | Complex logic to find latest non-revoked   |
| Enforcement   | 2           | Manual checks, easy to forget              |

**Why Not Chosen**: Slow query performance; Evidence is immutable and cannot efficiently represent
current state.

#### Alternative 3: Pure Hierarchical Consent

**Description**: Consent for parent scope implies child scopes automatically.

| Criterion       | Score (1-5) | Notes                                    |
| --------------- | ----------- | ---------------------------------------- |
| User experience | 5           | Single consent click covers everything   |
| GDPR compliance | 1           | Violates Article 7(2) - distinguishable  |
| Revocation      | 3           | Ambiguous semantics                      |
| Risk            | 1           | Over-claiming consent creates legal risk |

**Why Not Chosen**: GDPR Article 7(2) requires distinguishable consent per purpose.

#### Alternative 4: Background Job for Expiration

**Description**: Scheduled job updates token status when expired.

| Criterion      | Score (1-5) | Notes                                    |
| -------------- | ----------- | ---------------------------------------- |
| Implementation | 3           | Requires job infrastructure              |
| Consistency    | 2           | Race conditions between check and update |
| Reliability    | 2           | Job failure leaves stale states          |
| Simplicity     | 4           | Simpler token status logic               |

**Why Not Chosen**: Race conditions, job failure modes. Query-time check is simpler and always
correct.

### Decision Matrix

| Criterion          | Weight | Boolean Flag | Evidence-Only | Hierarchical | Background Job | Chosen (Token+Query) |
| ------------------ | ------ | ------------ | ------------- | ------------ | -------------- | -------------------- |
| GDPR compliance    | 30%    | 1            | 3             | 1            | 4              | 5                    |
| Query performance  | 25%    | 5            | 1             | 4            | 4              | 5                    |
| Audit clarity      | 25%    | 2            | 5             | 3            | 3              | 4                    |
| Maintainability    | 20%    | 4            | 2             | 3            | 2              | 4                    |
| **Weighted Total** | 100%   | **2.65**     | **2.65**      | **2.40**     | **3.30**       | **4.55**             |

---

## Consequences

### Positive Consequences

1. **Enforceable**: Consent gates operations automatically via ConsentGate - not just documentation
2. **Queryable**: O(1) lookup by (tenant, subject, scope) via indexed table
3. **Auditable**: Token + Evidence provide complete trail - when granted, when revoked, by whom
4. **Precise**: Scope-based model matches GDPR Article 7(2) distinguishable requirement
5. **Flexible**: Multi-party model handles all scenarios (self-service, HR-recorded, admin-revoked)

### Negative Consequences

1. **Token + Evidence redundancy**: Two records for same consent
   - **Mitigation**: By design - they serve different purposes (enforcement vs. audit)
2. **Primary dependency overhead**: Requires primary consent before any other scope
   - **Mitigation**: Clear UX flow - primary consent is first step in onboarding
3. **Cascade complexity**: Revoking primary triggers cascade to all dependent scopes
   - **Mitigation**: `cascade_revoke_consent_token` action handles atomically

### Neutral Consequences

1. **Parameterized gate pattern**: ConsentGate uses dynamic gate_id (`consent.{scope}`) - consistent
   with other parameterized gates

### Risks

| Risk                        | Likelihood | Impact | Mitigation                               |
| --------------------------- | ---------- | ------ | ---------------------------------------- |
| Stale token not cleaned up  | L          | L      | Query-time expiration check handles this |
| Cascade revocation partial  | L          | H      | Atomic transaction for cascade           |
| Scope creep (adding scopes) | M          | M      | Require ADR review for new scopes        |

### Dependencies Introduced

| Dependency                | Type     | Version | Stability | Notes                          |
| ------------------------- | -------- | ------- | --------- | ------------------------------ |
| Consent vocabulary (`hub/foundation/packages/consent/`) | Internal | N/A | Stable | Provides tenant_id, subject_id via ContentModel |

### Migration Impact

**Backwards Compatibility**: New system - no migration required

**Migration Steps**:

1. Deploy ConsentToken entity and ConsentService
2. Create initial consent tokens for existing subjects with known consent
3. Enable ConsentGate enforcement on relevant actions

**Rollback Plan**:

1. Disable ConsentGate via feature flag
2. ConsentTokens remain as audit records

---

## Verification

### Success Criteria

- [ ] All background check operations blocked without valid `background_check` consent
- [ ] Revocation of primary consent cascades to all dependent scopes within 1 transaction
- [ ] Query-time expiration check returns correct `is_valid()` result
- [ ] ConsentGate latency < 5ms at p99

### Metrics to Track

| Metric                    | Baseline | Target  | Review Date |
| ------------------------- | -------- | ------- | ----------- |
| ConsentGate latency (p99) | N/A      | < 5ms   | 2026-02-15  |
| Consent grant rate        | N/A      | > 95%   | 2026-02-15  |
| Revocation cascade time   | N/A      | < 100ms | 2026-02-15  |

### Review Schedule

- **Initial Review**: 2026-02-15 (30 days after activation)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: alpha[architect]

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Gate protocol for ConsentGate implementation
- `ADR-006-evidence-chain-cep`: Evidence emission on consent lifecycle events

### Impacts

- `TDS-022-consent`: Technical implementation specification
- All services requiring consent verification before processing

---

## Vocabulary Mapping

### Package Reference

**Primary Package**: `hub/foundation/packages/consent/`

### Vocabulary Phrases

| Phrase                   | Pattern | Regulatory Basis                       |
| ------------------------ | ------- | -------------------------------------- |
| `verify_token`           | verify  | GDPR Art. 7(1), FCRA 604(b)            |
| `grant_token`            | action  | GDPR Art. 7(1)                         |
| `revoke_token`           | action  | GDPR Art. 7(3)                         |
| `require_active_consent` | require | GDPR Art. 6                            |
| `require_valid_consent`  | require | FCRA 604(b)(2)(A)                      |
| `cascade_revoke_token`   | action  | GDPR Art. 7(3) - withdrawal            |
| `verify_scope_covers`    | verify  | GDPR Art. 5(1)(b) - purpose limitation |

### Control Surfaces

| Surface                  | Key Integration                                   |
| ------------------------ | ------------------------------------------------- |
| PII Export Authorization | consent_status fact derived from ConsentToken     |
| Cross-Border Transfer    | ConsentGate verifies data_sharing consent         |
| Training Data Inclusion  | ConsentScope.AI_SCORING validates AI training use |

---

## References

- TDS: `docs-shared/canonsys/01_design/022-consent/TDS-022-consent.md`
- Consent feature: `hub/foundation/packages/consent/`
- Token: `hub/foundation/packages/consent/types/token.py`
- Scope: `hub/foundation/packages/consent/types/scope.py`
- GDPR Article 7: Conditions for consent
- FCRA Section 604: Permissible purposes of consumer reports
