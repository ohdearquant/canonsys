---
doc_type: TDS
title: "Technical Design Specification: Segregation of Duties Conflict Matrix"
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
  - "ADR-032-segregation-of-duties"
successors: []
supersedes: null
superseded_by: null

tags:
  - segregation-of-duties
  - sox-compliance
  - finance
  - authorization
related:
  - "ADR-032-segregation-of-duties"
  - "ADR-015-jit-role"
  - "TDS-007-decision-certificate"
  - "TDS-006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# Technical Design Specification: Segregation of Duties Conflict Matrix

## 1. Overview

### 1.1 Purpose

The Segregation of Duties (SoD) Conflict Matrix enforces SOX 302/404 compliance by preventing
incompatible role combinations. It operates as a **gate** in the role grant flow, blocking
assignments that would create audit violations while supporting documented exemptions.

### 1.2 Scope

**In Scope**:

- SoDConflictMatrix entity and rule definitions
- `verify_no_sod_conflict()` gate function
- SoDExemption workflow with evidence binding
- Integration with JIT role grants (ADR-015)
- Cross-system role aggregation patterns

**Out of Scope**:

- HRIS connector implementation details
- Role hierarchy inheritance
- Cross-tenant role conflicts

### 1.3 Platform Invariants

1. **Fail-Closed**: If matrix cannot be loaded, all role grants are blocked
2. **Bidirectional**: If (A, B) conflicts, then (B, A) also conflicts
3. **Evidence Required**: Every SoD check produces audit evidence
4. **Exemptions Time-Bounded**: No permanent exemptions (max 365 days)
5. **Cross-System Aggregation**: SoD checks include roles from all connected systems

### 1.4 Design Goals

| Priority | Goal                     | Rationale                        |
| -------- | ------------------------ | -------------------------------- |
| P0       | Block conflicting roles  | SOX 302/404 compliance           |
| P0       | Complete audit trail     | Every check produces evidence    |
| P1       | Exemption workflow       | Legitimate exceptions documented |
| P1       | Cross-system aggregation | Prevent siloed conflicts         |
| P2       | JIT integration          | Consistent with ADR-015          |

---

## 2. Architecture

### 2.1 Component Hierarchy

```
SoDConflictMatrix (Definition)
    +-- matrix_id: UUID
    +-- version: str
    +-- rules: tuple[SoDConflictRule, ...]
    +-- effective_from: datetime

SoDConflictRule (Rule Definition)
    +-- rule_id: UUID
    +-- role_a: str
    +-- role_b: str
    +-- conflict_type: ConflictType
    +-- sox_control_id: str

SoDCheckResult (Gate Output)
    +-- passed: bool
    +-- conflicts: tuple[SoDConflict, ...]
    +-- exemption: SoDExemption | None
    +-- evidence_hash: str

SoDExemption (Documented Exception)
    +-- exemption_id: UUID
    +-- user_id: UUID
    +-- rule_id: UUID
    +-- granted_by: UUID (CFO/CISO/GC)
    +-- compensating_controls: tuple[str, ...]
    +-- cep_ids: tuple[UUID, ...]
    +-- valid_until: datetime
```

### 2.2 Dependencies

**Internal Dependencies**:

| Component | Purpose                | Location                 |
| --------- | ---------------------- | ------------------------ |
| Gate      | Gate abstraction       | `canon.enforcement` |
| Evidence  | Audit trail            | `canon.evidence`    |
| CEP       | Evidence binding       | `canon.evidence`    |
| JIT Role  | Role grant integration | ADR-015                  |

**External Dependencies**:

| Library  | Purpose           | Version  |
| -------- | ----------------- | -------- |
| asyncpg  | PostgreSQL driver | >=0.28.0 |
| pydantic | Validation        | >=2.0.0  |

---

## 3. Vocabulary Mapping

### Package: `authorization`

**Location**: `hub/foundation/packages/authorization/`

| Phrase                           | File                                        | Purpose                  |
| -------------------------------- | ------------------------------------------- | ------------------------ |
| `require_segregation_analysis`   | `phrases/require_segregation_analysis.py`   | Compute separation level |
| `require_distinct_identities`    | `phrases/require_distinct_identities.py`    | Different user check     |
| `require_dual_approval`          | `phrases/require_dual_approval.py`          | Two-party sign-off       |
| `require_separation_of_duties`   | `phrases/require_separation_of_duties.py`   | Generic SoD check        |
| `verify_approval_chain_complete` | `phrases/verify_approval_chain_complete.py` | All approvers signed     |

### Control Surface Coverage

| Surface                   | Phrases Used                                              | Status      |
| ------------------------- | --------------------------------------------------------- | ----------- |
| Candidate Advancement     | `require_segregation_analysis`, `check_er_clearance`      | Implemented |
| Comment/Document Approval | `require_distinct_identities`                             | Implemented |
| Adverse Action Sign-Off   | `require_dual_approval`, `verify_approval_chain_complete` | Implemented |

---

## 4. Data Models

### 4.1 Database Schema

```sql
-- Conflict matrix versions
CREATE TABLE sod_conflict_matrices (
    matrix_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    version VARCHAR(50) NOT NULL,
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, version)
);

-- Conflict rules
CREATE TABLE sod_conflict_rules (
    rule_id UUID PRIMARY KEY,
    matrix_id UUID NOT NULL REFERENCES sod_conflict_matrices(matrix_id),
    role_a VARCHAR(255) NOT NULL,
    role_b VARCHAR(255) NOT NULL,
    conflict_type VARCHAR(50) NOT NULL,
    sox_control_id VARCHAR(50) NOT NULL,
    UNIQUE (matrix_id, role_a, role_b)
);

-- Exemptions
CREATE TABLE sod_exemptions (
    exemption_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(tenant_id),
    user_id UUID NOT NULL,
    rule_id UUID NOT NULL REFERENCES sod_conflict_rules(rule_id),
    granted_by UUID NOT NULL,
    business_justification TEXT NOT NULL CHECK (length(business_justification) >= 100),
    compensating_controls TEXT[] NOT NULL,
    cep_ids UUID[] NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    CONSTRAINT max_exemption_duration CHECK (valid_until <= valid_from + INTERVAL '1 year')
);

-- Check audit log (immutable)
CREATE TABLE sod_check_log (
    check_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    user_id UUID NOT NULL,
    requested_role VARCHAR(255) NOT NULL,
    matrix_version VARCHAR(50) NOT NULL,
    conflicts_found JSONB NOT NULL,
    result VARCHAR(20) NOT NULL,
    evidence_hash VARCHAR(64) NOT NULL,
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

---

## 5. Key Operations

### 5.1 verify_no_sod_conflict Gate

```python
async def verify_no_sod_conflict(
    user_id: UUID,
    requested_role: str,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> SoDCheckResult:
    """Gate: Verify that granting requested_role doesn't create SoD conflict."""
    # 1. Load current matrix
    # 2. Aggregate user's current roles (all systems)
    # 3. Check for conflicts
    # 4. If conflicts, check for exemption
    # 5. Log check (always)
    # 6. Raise if blocked
```

### 5.2 SoDCheckResult States

| State    | Passed | Defensibility | Meaning                  |
| -------- | ------ | ------------- | ------------------------ |
| FULL     | True   | Full          | No conflicts found       |
| DEGRADED | True   | Degraded      | Conflicts with exemption |
| BLOCKED  | False  | N/A           | Conflicts, no exemption  |

---

## 6. Testing Requirements

| Test Category                | Coverage Target |
| ---------------------------- | --------------- |
| Conflict detection logic     | 100%            |
| Bidirectional conflict check | 100%            |
| Exemption validation         | 100%            |
| Role aggregation             | 100%            |
| JIT integration              | 100%            |

---

## 7. Open Questions

| # | Question                   | Impact             | Status   |
| - | -------------------------- | ------------------ | -------- |
| 1 | Cross-tenant roles         | Tenant boundaries  | Open     |
| 2 | Role hierarchy inheritance | Implicit conflicts | Open     |
| 3 | Retroactive conflict rules | Existing users     | Resolved |

---

## 8. References

- ADR: `docs-shared/canonsys/01_design/032-segregation-of-duties/ADR-032-segregation-of-duties.md`
- Authorization package: `hub/foundation/packages/authorization/`
- ADR-015: JIT role grant integration
- SOX Section 302/404, COSO Framework, PCAOB AS 2201
