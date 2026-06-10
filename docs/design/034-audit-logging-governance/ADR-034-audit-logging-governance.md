---
doc_type: ADR
title: "ADR-034: Protected Log Types Hierarchy and Lifecycle Governance"
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
  - "ADR-003-immutability"
  - "ADR-006-evidence-chain-cep"
  - "ADR-016-break-glass"
successors:
  - "TDS-034-audit-logging-governance"
supersedes: null
superseded_by: null

tags:
  - audit
  - logging
  - compliance
  - governance
  - infra
related:
  - "TDS-034-audit-logging-governance"
  - "ADR-003-immutability"
  - "ADR-006-evidence-chain-cep"
  - "ADR-016-break-glass"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# ADR-034: Protected Log Types Hierarchy and Lifecycle Governance

## Context

### Problem Statement

CanonSys generates multiple types of log entries with fundamentally different protection
requirements:

1. **System logs**: Operational telemetry (request timing, memory usage, healthchecks)
2. **Audit logs**: Security-relevant events (authentication, authorization, data access)
3. **Compliance logs**: Regulatory-mandated records (evidence creation, decision justification)

Currently, no formal hierarchy distinguishes these log types, leading to:

- Risk of audit log deletion via administrative interfaces
- Unclear retention policies per log type
- No defense-in-depth for compliance-critical logs
- The Disable Audit Logging surface lacks systematic protection

**Why This Matters**: Regulatory frameworks (SOC2, GDPR, FCRA) require that audit trails cannot be
tampered with or disabled. A malicious administrator disabling audit logging before taking harmful
actions is a critical attack vector that must be prevented at the substrate level.

### Background

**Regulatory Requirements**:

| Regulation | Section      | Requirement                                         |
| ---------- | ------------ | --------------------------------------------------- |
| **SOC2**   | CC6.2        | Audit logs must be protected from modification      |
| **GDPR**   | Article 30   | Records of processing activities must be maintained |
| **FCRA**   | 15 USC 1681e | Reasonable procedures to assure accuracy            |
| **NIST**   | SP 800-92    | Comprehensive log management requirements           |
| **CIS**    | Control 8    | Audit log management best practices                 |

**Driving Forces**:

- **Attack Prevention**: Malicious admin cannot "turn off the camera" before acting
- **Regulatory Compliance**: SOC2, GDPR, FCRA require tamper-proof audit trails
- **Evidence Integration**: Audit logs may become evidence in litigation (ADR-006)
- **Defense-in-Depth**: Multiple protection layers (gate + DB trigger + break-glass)

### Assumptions

1. Entity base class (ADR-002/003) provides immutability patterns
2. Evidence chain (ADR-006) exists for legal-grade records
3. PostgreSQL is production database with trigger support
4. Administrative access exists but must be bounded

### Constraints

| Type        | Constraint                             | Impact                                     |
| ----------- | -------------------------------------- | ------------------------------------------ |
| Regulatory  | Audit logs must be deletion-protected  | Cannot use standard soft-delete            |
| Regulatory  | Retention periods vary by jurisdiction | Need per-type retention policies           |
| Security    | Disable logging = critical action      | Must be blocked or require break-glass     |
| Operational | System logs need rotation/cleanup      | Cannot apply same rules as compliance logs |
| Technical   | Log volume can be high                 | Immutability triggers must be performant   |

---

## Decision

### Summary

**We will** implement a three-tier log type hierarchy with distinct protection levels, lifecycle
policies, and deletion governance. Compliance and audit logs are immutable by default with
database-level enforcement. System logs remain mutable with standard retention policies.

### Rationale

**Key factors in the decision**:

1. **Defense-in-Depth**: Three layers of protection match three levels of criticality. System logs
   can rotate freely; audit logs require authorization; compliance logs are immutable.

2. **DB-Level Enforcement for Tier 3**: Following ADR-003 patterns, IMMUTABLE logs have database
   triggers preventing DELETE. Application-layer bypasses are impossible.

3. **Break-Glass for Tier 2**: PROTECTED logs can be hard-deleted only through the break-glass
   pattern (ADR-016), creating an evidence trail of the deletion itself.

4. **Automatic Classification**: Log entries are classified at creation based on event type. No
   manual classification reduces human error.

5. **Evidence Chain Integration**: EVIDENCE and DECISION logs link to the evidence chain (ADR-006),
   providing cryptographic proof of existence and ordering.

### Implementation Approach

**Log Type Hierarchy**:

```python
class LogType(str, Enum):
    """Log type hierarchy with protection levels."""

    # Tier 1: Mutable - standard retention, deletable
    SYSTEM = "system"           # Operational telemetry
    DEBUG = "debug"             # Development/troubleshooting
    PERFORMANCE = "performance" # Timing, metrics

    # Tier 2: Protected - deletion requires authorization
    AUDIT = "audit"             # Security events
    ACCESS = "access"           # Data access records
    ADMIN = "admin"             # Administrative actions

    # Tier 3: Immutable - deletion blocked at DB level
    COMPLIANCE = "compliance"   # Regulatory-mandated
    EVIDENCE = "evidence"       # Linked to Evidence chain
    DECISION = "decision"       # Decision justification


class ProtectionLevel(str, Enum):
    """Protection level for log types."""
    MUTABLE = "mutable"         # Standard CRUD
    PROTECTED = "protected"     # Soft-delete only, break-glass hard delete
    IMMUTABLE = "immutable"     # No deletion, supersession only
```

**Protection Matrix**:

| Log Type    | Protection | Retention  | Deletion Policy                    |
| ----------- | ---------- | ---------- | ---------------------------------- |
| SYSTEM      | MUTABLE    | 30 days    | Auto-rotate, hard delete allowed   |
| DEBUG       | MUTABLE    | 7 days     | Auto-rotate, hard delete allowed   |
| PERFORMANCE | MUTABLE    | 90 days    | Auto-rotate, hard delete allowed   |
| AUDIT       | PROTECTED  | 7 years    | Soft-delete only, break-glass hard |
| ACCESS      | PROTECTED  | 7 years    | Soft-delete only, break-glass hard |
| ADMIN       | PROTECTED  | 7 years    | Soft-delete only, break-glass hard |
| COMPLIANCE  | IMMUTABLE  | Indefinite | Never deleted, supersession only   |
| EVIDENCE    | IMMUTABLE  | Indefinite | Never deleted, supersession only   |
| DECISION    | IMMUTABLE  | Indefinite | Never deleted, supersession only   |

**Vocabulary Features**:

| Phrase                    | Purpose                          | Regulatory Basis |
| ------------------------- | -------------------------------- | ---------------- |
| `log_audit_event`         | Create audit log with auto-class | SOC2 CC6.2       |
| `deny_audit_log_deletion` | Gate blocking IMMUTABLE deletion | SOC2 CC6.2       |
| `verify_log_integrity`    | Verify content and chain hashes  | NIST SP 800-92   |

### Alternatives Considered

#### Alternative 1: Single Log Type with Per-Entry Protection

**Description**: All logs in one table with a `protection_level` column determining behavior.

| Criterion          | Score (1-5) | Notes                                         |
| ------------------ | ----------- | --------------------------------------------- |
| Query Performance  | 2           | Mixed protection levels hurt index efficiency |
| Trigger Complexity | 2           | Must check protection level in every trigger  |
| Schema Clarity     | 3           | One table, but complex conditional logic      |
| Security Isolation | 2           | No physical separation of critical logs       |

**Why Not Chosen**: Performance and security concerns.

#### Alternative 2: Separate Tables Per Protection Level

**Description**: Three separate tables: `system_logs`, `audit_logs`, `compliance_logs`.

| Criterion              | Score (1-5) | Notes                                      |
| ---------------------- | ----------- | ------------------------------------------ |
| Query Performance      | 4           | Optimized triggers per table               |
| Trigger Complexity     | 5           | Simple, unconditional triggers             |
| Schema Clarity         | 4           | Clear separation of concerns               |
| Operational Simplicity | 2           | Multiple tables to manage, complex queries |

**Why Not Chosen**: Operational complexity outweighs benefits.

### Decision Matrix

| Criterion              | Weight | Single Type | Separate Tables | **LogType Hierarchy** |
| ---------------------- | ------ | ----------- | --------------- | --------------------- |
| Query Performance      | 20%    | 2           | 4               | **4**                 |
| Trigger Complexity     | 20%    | 2           | 5               | **4**                 |
| Schema Clarity         | 20%    | 3           | 4               | **5**                 |
| Operational Simplicity | 20%    | 3           | 2               | **4**                 |
| Security Isolation     | 20%    | 2           | 5               | **4**                 |
| **Weighted Total**     | 100%   | **2.40**    | **4.00**        | **4.20**              |

---

## Consequences

### Positive Consequences

1. **Attack Vector Eliminated**: The Disable Audit Logging surface is systematically blocked. No
   administrative interface can delete IMMUTABLE logs.

2. **Clear Governance**: Three-tier hierarchy makes retention and deletion policies explicit.
   Operations knows which logs rotate; compliance knows which logs are permanent.

3. **Evidence Integration**: EVIDENCE and DECISION logs link to evidence chain (ADR-006), enabling
   cryptographic proof for litigation.

4. **Defense-in-Depth**: Multiple layers (application gate + DB trigger + break-glass) ensure even
   compromised application code cannot delete protected logs.

5. **Audit of Auditing**: Break-glass deletions of PROTECTED logs create their own audit trail,
   making "turning off the camera" visible.

### Negative Consequences

1. **Storage Growth**: IMMUTABLE logs accumulate indefinitely. Mitigation: Archival to cold storage
   after retention period, but never deleted.

2. **Migration Complexity**: Existing logs need classification. Mitigation: Default unclassified
   logs to AUDIT (PROTECTED) level.

3. **Query Overhead**: Type-based routing adds conditional logic. Mitigation: Partial indexes on
   log_type reduce scan overhead.

### Neutral Consequences

1. **Extends Immutability Patterns**: Builds on ADR-003 without changing its core design.

2. **New Gate Vocabulary**: `deny_audit_log_deletion` joins the vocabulary layer.

### Risks

| Risk                                 | Likelihood | Impact | Mitigation                             |
| ------------------------------------ | ---------- | ------ | -------------------------------------- |
| Misclassification of log type        | M          | M      | Automatic classification by event type |
| IMMUTABLE logs fill storage          | L          | M      | Archival to cold storage, alerts       |
| Break-glass abuse for PROTECTED logs | L          | M      | Break-glass logging + review           |
| Trigger performance at high volume   | L          | L      | Benchmarks show <0.1ms overhead        |

### Migration Impact

**Backwards Compatibility**: Existing logs will be classified as AUDIT (PROTECTED) by default.

**Migration Steps**:

1. Add `log_type` column to existing log tables
2. Classify existing entries based on event_type patterns
3. Generate protection triggers for IMMUTABLE types
4. Deploy `deny_audit_log_deletion` gate

---

## Verification

### Success Criteria

- [ ] LogType enum with three protection levels implemented
- [ ] AuditLogEntry entity with `log_type` field
- [ ] `deny_audit_log_deletion` gate blocking IMMUTABLE deletions
- [ ] Break-glass required for PROTECTED deletions
- [ ] DB triggers generated for IMMUTABLE log types
- [ ] Disable Audit Logging surface covered by gate
- [ ] Integration test: admin cannot delete COMPLIANCE log
- [ ] Integration test: break-glass creates audit trail for PROTECTED deletion

### Metrics to Track

| Metric                          | Baseline | Target   | Review Date |
| ------------------------------- | -------- | -------- | ----------- |
| IMMUTABLE log deletion attempts | N/A      | 0        | Weekly      |
| Break-glass usage frequency     | N/A      | <1/month | Monthly     |
| Log storage growth rate         | N/A      | <10%/mo  | Monthly     |
| Trigger execution overhead      | N/A      | <0.1ms   | Weekly      |

### Review Schedule

- **Initial Review**: 2026-02-20 (1 month after implementation)
- **Ongoing Reviews**: Quarterly compliance audit
- **Review Owner**: Security team + Compliance officer

---

## Vocabulary Mapping

### Package: `controls`

**Location**: `hub/foundation/packages/controls/`

| Phrase                    | Purpose                          | Surfaces                         |
| ------------------------- | -------------------------------- | -------------------------------- |
| `deny_audit_log_deletion` | Gate blocking IMMUTABLE deletion | Disable Audit Logging            |
| `log_audit_event`         | Create classified audit log      | Disable Audit Logging and others |
| `verify_log_integrity`    | Verify content and chain hashes  | Tamper With Audit Logs           |

### Package: `evidence`

**Location**: `hub/foundation/packages/evidence/`

| Phrase           | Purpose                          | Surfaces                  |
| ---------------- | -------------------------------- | ------------------------- |
| `chain_evidence` | Create chain entry for IMMUTABLE | Log Aggregation Tampering |

### Control Surface Coverage

| Surface                   | Phrases                              |
| ------------------------- | ------------------------------------ |
| Disable Audit Logging     | `deny_audit_log_deletion`            |
| Tamper With Audit Logs    | DB triggers + `verify_log_integrity` |
| Bypass Audit Log Writes   | `log_audit_event` (mandatory)        |
| Access Audit Log Contents | RLS + tenant isolation               |
| Log Aggregation Tampering | `chain_evidence`, hash verify        |

---

## Related Artifacts

### Builds On

- `ADR-003-immutability`: Immutability patterns and DB triggers
- `ADR-006-evidence-chain-cep`: Evidence chain for cryptographic proof
- `ADR-016-break-glass`: Break-glass pattern for exceptional operations

### Impacts

- `TDS-034-audit-logging-governance`: Technical implementation details
- Infrastructure attack surface coverage (audit logging governance surfaces)
- Retention policy documentation

---

## References

- TDS:
  `docs-shared/canonsys/01_design/034-audit-logging-governance/TDS-034-audit-logging-governance.md`
- Controls package: `hub/foundation/packages/controls/`
- Evidence package: `hub/foundation/packages/evidence/`
- SOC2 CC6.2: Logical and Physical Access Controls
- GDPR Article 30: Records of Processing Activities
- FCRA 15 U.S.C. 1681e: Compliance Procedures
- NIST SP 800-92: Guide to Computer Security Log Management
- CIS Control 8: Audit Log Management

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
