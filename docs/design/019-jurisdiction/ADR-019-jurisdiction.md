---
# Core Fields (REQUIRED)
doc_type: ADR
title: "ADR-019: Multi-Jurisdiction Routing"
version: "2.0.0"
status: active
created: "2026-01-20"
updated: "2026-01-29"
decision_date: "2026-01-20"
by: "architect"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

# Chain Fields
predecessors: ["ADR-008-policy-gates"]
successors: ["ADR-021-privacy-pii"]
supersedes: null
superseded_by: null

# Context Fields
tags:
  - jurisdiction
  - compliance
  - routing
  - hr
  - legal
related: ["TDS-019-jurisdiction"]
pr: null

# Quality Metrics
quality:
  confidence: 0.90
  sources: 4
  docs: full
---

# ADR-019: Multi-Jurisdiction Routing

## Context

### Problem Statement

CanonSys operates across multiple regulatory environments with overlapping and sometimes conflicting
requirements. A hiring action in New York City must comply with NYC LL144 AND NY state law AND
federal FCRA. The system must determine which rules apply and route enforcement accordingly.

**Why This Matters**: Incorrect jurisdiction determination can result in regulatory violations,
employment lawsuits, and compliance audit failures across multiple agencies simultaneously.

### Background

**Current State**: Different jurisdictions impose different compliance requirements:

| Jurisdiction | Key Requirements                                       |
| ------------ | ------------------------------------------------------ |
| NYC LL144    | Bias audit for automated employment decision tools     |
| FCRA (US)    | Consent and adverse action notices                     |
| GDPR (EU)    | Data subject rights and cross-border transfer controls |
| CO SB 205    | AI disclosure in hiring                                |

**Driving Forces**:

- **Regulatory complexity**: Multi-level hierarchy (city, state, federal, international)
- **Inheritance requirements**: NYC should automatically include NY state and federal requirements
- **Performance**: Lookup must be O(1) for enforcement hot paths
- **Extensibility**: New jurisdictions via configuration, not code changes

### Assumptions

1. Subject jurisdiction is determinable from employment location or action location
2. Compliance teams can maintain jurisdiction configurations without code deploys
3. ANY-match semantics (action permitted in ANY context jurisdiction) is appropriate

### Constraints

| Type        | Constraint                   | Impact                                      |
| ----------- | ---------------------------- | ------------------------------------------- |
| Technical   | O(1) lookup required         | Limits to hash-based registry               |
| Regulatory  | Multi-level hierarchy        | Must support parent/child relationships     |
| Business    | Compliance team self-service | Configuration-driven, not code-driven       |
| Operational | International coverage       | Must support US, EU, UK, and future regions |

---

## Decision

### Summary

**We will** implement jurisdiction as a first-class entity with hierarchical inheritance,
data-driven configuration, and ANY-match gate semantics.

### Rationale

**Key factors in the decision**:

1. **Hierarchy traversal**: Most-specific-first ordering enables correct rule application
2. **Data-driven**: TOML files allow compliance team updates without code deploys
3. **ANY-match**: Permissive routing for multi-state employees without false blocks

### Implementation Approach

Jurisdiction is infrastructure that phrases consume from RequestContext:

```python
# canon/utils/loader.py
@dataclass(frozen=True)
class JurisdictionConfig:
    code: str              # e.g., "US-NYC"
    display_name: str      # e.g., "New York City"
    country: str           # e.g., "US"
    parent: str | None     # e.g., "US-NY"
    calendar: str          # Business day calendar
    aliases: frozenset[str]

def hierarchy(code: str) -> tuple[str, ...]:
    """Return jurisdiction hierarchy most-specific-first.

    hierarchy("US-NYC") -> ("US-NYC", "US-NY", "US-FEDERAL")
    """
```

Control surfaces using this pattern:

- the Cross-Border Data Transfer surface - cross-border data transfer with jurisdiction-based adequacy checks
- the Tax Jurisdiction Change surface - tax jurisdiction change with multi-level approval routing

### Alternatives Considered

#### Alternative 1: Hardcoded Jurisdiction Classes

**Description**: Define each jurisdiction as a Python class with methods.

| Criterion       | Score (1-5) | Notes                              |
| --------------- | ----------- | ---------------------------------- |
| Extensibility   | 1           | Code changes for new jurisdictions |
| Performance     | 5           | Direct method dispatch             |
| Maintainability | 2           | Compliance team cannot self-serve  |

**Why Not Chosen**: Code changes required for new jurisdictions; compliance team cannot self-serve.

#### Alternative 2: ALL-Must-Match Gate Logic

**Description**: Require action permitted in ALL context jurisdictions.

| Criterion    | Score (1-5) | Notes                                 |
| ------------ | ----------- | ------------------------------------- |
| Strictness   | 5           | Maximum compliance coverage           |
| Usability    | 2           | Blocks multi-state employees          |
| Practicality | 2           | Overly restrictive for real workflows |

**Why Not Chosen**: Would block multi-state employees; overly restrictive for cross-jurisdiction
actions.

### Decision Matrix

| Criterion           | Weight | Hardcoded | ALL-Match | Data-Driven ANY |
| ------------------- | ------ | --------- | --------- | --------------- |
| Extensibility       | 30%    | 1         | 2         | 5               |
| Performance         | 20%    | 5         | 4         | 4               |
| Compliance coverage | 25%    | 3         | 5         | 4               |
| Self-service        | 25%    | 1         | 1         | 5               |
| **Weighted Total**  | 100%   | **2.15**  | **2.95**  | **4.55**        |

---

## Consequences

### Positive Consequences

1. **Regulatory coverage**: System knows which rules apply where via hierarchy
2. **Inheritance**: NYC automatically includes state and federal requirements
3. **Extensibility**: New jurisdictions via TOML configuration, not code changes
4. **Self-service**: Compliance team can update jurisdiction configurations

### Negative Consequences

1. **Complexity**: Hierarchy traversal adds logic paths to trace
2. **Configuration burden**: Must maintain TOML files for each jurisdiction
3. **ANY-match risk**: Permissive routing may miss edge cases

### Neutral Consequences

1. **Infrastructure vs vocabulary split**: JurisdictionRegistry/JurisdictionGate remain
   infrastructure; phrases consume context

### Risks

| Risk                        | Likelihood | Impact | Mitigation                           |
| --------------------------- | ---------- | ------ | ------------------------------------ |
| Missing jurisdiction config | M          | H      | Validation on startup; test coverage |
| Incorrect hierarchy         | L          | H      | Review process for TOML changes      |
| ANY-match compliance gap    | L          | M      | Audit logging of jurisdiction checks |

### Dependencies Introduced

| Dependency | Type   | Version | Stability | Notes                |
| ---------- | ------ | ------- | --------- | -------------------- |
| TOML       | Format | 1.0     | Stable    | Configuration format |

### Migration Impact

**Backwards Compatibility**: Compatible - existing actions continue with default jurisdiction.

**Migration Steps**:

1. Deploy JurisdictionRegistry with initial TOML configs
2. Update RequestContext to populate jurisdictions tuple
3. Gates automatically apply hierarchy-based routing

---

## Verification

### Success Criteria

- [x] Hierarchy lookup is O(1) via pre-computed registry
- [x] NYC actions include NY and FEDERAL in hierarchy
- [x] New jurisdiction can be added via TOML without code deploy
- [x] Gate checks complete in < 1ms

### Metrics to Track

| Metric                   | Baseline | Target | Review Date |
| ------------------------ | -------- | ------ | ----------- |
| Hierarchy lookup p99     | N/A      | < 1ms  | 2026-03-01  |
| Config validation errors | N/A      | 0      | 2026-03-01  |
| Jurisdiction coverage    | N/A      | 100%   | 2026-03-01  |

### Review Schedule

- **Initial Review**: 2026-04-01 (3 months after deployment)
- **Ongoing Reviews**: Quarterly
- **Review Owner**: Compliance Team

---

## Vocabulary Mapping

| Phrase                            | Package           | Purpose                                       |
| --------------------------------- | ----------------- | --------------------------------------------- |
| `verify_destination_allowed`      | `scope`           | Validate transfer destination is permitted    |
| `require_encrypted_transmission`  | `data_protection` | Require encryption for cross-border transfer  |
| `require_legal_review_complete`   | `legal`           | Gate on legal review completion               |
| `verify_appeal_channel_available` | `legal`           | Verify jurisdiction provides appeal mechanism |

**Note**: Core jurisdiction routing (JurisdictionGate, JurisdictionRegistry) remains infrastructure.
Phrases consume jurisdiction context from RequestContext.

---

## Control Surface Integration

| Surface                    | Charter                                     | Key Phrases                                                                             |
| -------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------- |
| Cross-Border Data Transfer | `surfaces/data/cross_border_transfer.canon` | `verify_destination_allowed`, `require_encrypted_transmission`, `verify_ofac_clearance` |
| Tax Jurisdiction Change    | `surfaces/finance/tax_jurisdiction_change.canon` | `require_legal_review_complete`, `verify_approval_chain_complete`, `record_attestation` |

---

## Related Artifacts

### Builds On

- `ADR-008-policy-gates`: Jurisdiction gates extend parameterized gate pattern

### Impacts

- `TDS-019-jurisdiction`: Technical implementation details
- `ADR-021-privacy-pii`: PII handling depends on jurisdiction for GDPR scope

---

## References

- **GDPR Art. 45-46**: Cross-border data transfer adequacy
- **NYC LL144**: Local Law 144 of 2021 (Automated Employment Decision Tools)
- **FCRA**: Fair Credit Reporting Act
- **Infrastructure**: `libs/canon/src/canon/utils/loader.py`
- **Charters**: `hub/charters/surfaces/`
