---
doc_type: TDS
title: "Technical Design Specification: Audit Log Governance and Protection"
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
  - "ADR-034-audit-logging-governance"
successors: []
supersedes: null
superseded_by: null

tags:
  - canon-core
  - audit
  - logging
  - governance
  - infra
related:
  - "ADR-034-audit-logging-governance"
  - "TDS-003-immutability"
  - "TDS-006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.90
  sources: 5
  docs: full
---

# Technical Design Specification: Audit Log Governance and Protection

## 1. Overview

### 1.1 Purpose

This TDS specifies the implementation of protected log types hierarchy and lifecycle governance for
CanonSys. The design ensures that compliance-critical audit logs cannot be deleted or tampered with,
while allowing standard log rotation for operational telemetry.

### 1.2 Scope

**In Scope**:

- LogType enum with three protection levels (MUTABLE, PROTECTED, IMMUTABLE)
- AuditLogEntry entity with type-based protection
- `deny_audit_log_deletion()` vocabulary gate
- Database trigger generation for IMMUTABLE logs
- Integration with evidence chain (ADR-006)
- Coverage of the Disable Audit Logging surface and related surfaces

**Out of Scope**:

- Log aggregation and shipping (external systems)
- Log search and analytics infrastructure
- Long-term archival to cold storage (separate design)
- Real-time alerting on audit events

### 1.3 Platform Invariants

1. **IMMUTABLE logs cannot be deleted**: DB triggers block DELETE for Tier 3 logs
2. **PROTECTED logs require break-glass**: Authorization trail for sensitive deletions
3. **Automatic classification**: Event type determines log type
4. **Evidence chain integration**: IMMUTABLE logs link to cryptographic chain

### 1.4 Design Goals

| Priority | Goal                              | Rationale                                        |
| -------- | --------------------------------- | ------------------------------------------------ |
| P0       | Block IMMUTABLE log deletion      | Regulatory compliance requires permanent records |
| P0       | Enforce break-glass for PROTECTED | Authorization trail for sensitive deletions      |
| P1       | Type-based protection routing     | Automatic classification reduces human error     |
| P1       | Evidence chain integration        | Cryptographic proof for litigation               |
| P2       | Minimal performance overhead      | High-volume logging must remain fast             |

---

## 2. Architecture

### 2.1 Component Hierarchy

```
LogType (Enum)
    +-- SYSTEM, DEBUG, PERFORMANCE (Tier 1: MUTABLE)
    +-- AUDIT, ACCESS, ADMIN (Tier 2: PROTECTED)
    +-- COMPLIANCE, EVIDENCE, DECISION (Tier 3: IMMUTABLE)

ProtectionLevel (Enum)
    +-- MUTABLE: Standard CRUD, auto-rotation
    +-- PROTECTED: Soft-delete, break-glass hard delete
    +-- IMMUTABLE: No deletion, supersession only

AuditLogEntry (Entity)
    +-- log_type: LogType
    +-- event_type: str
    +-- actor_id: FK[User]
    +-- resource_type, resource_id
    +-- payload: dict
    +-- chain_entry_id: FK[ChainEntry] (IMMUTABLE only)
```

### 2.2 Dependencies

**Internal Dependencies**:

| Component         | Purpose                              | Location                          |
| ----------------- | ------------------------------------ | --------------------------------- |
| Entity            | Base class with immutability support | `canon.entities.entity`         |
| ChainEntry        | Evidence chain linking               | `canon.entities.evidence`        |
| RequestContext    | Request context with actor/tenant    | `canon.enforcement.context`         |
| break_glass_token | Break-glass authorization            | `canon.enforcement.features` |

**External Dependencies**:

| Library  | Purpose                            | Version  |
| -------- | ---------------------------------- | -------- |
| asyncpg  | PostgreSQL async driver            | >=0.28.0 |
| pydantic | Model validation and serialization | >=2.0.0  |

---

## 3. Vocabulary Mapping

### Package: `controls`

**Location**: `hub/foundation/packages/controls/`

| Phrase                    | File                                 | Purpose                  |
| ------------------------- | ------------------------------------ | ------------------------ |
| `deny_audit_log_deletion` | `phrases/deny_audit_log_deletion.py` | Block IMMUTABLE deletion |
| `log_audit_event`         | `phrases/log_audit_event.py`         | Create classified log    |
| `verify_log_integrity`    | `phrases/verify_log_integrity.py`    | Verify content hash      |

### Package: `evidence`

**Location**: `hub/foundation/packages/evidence/`

| Phrase           | File                        | Purpose            |
| ---------------- | --------------------------- | ------------------ |
| `chain_evidence` | `phrases/chain_evidence.py` | Create chain entry |

### Control Surface Coverage

| Surface                   | Phrases Used                         | Status      |
| ------------------------- | ------------------------------------ | ----------- |
| Disable Audit Logging     | `deny_audit_log_deletion`            | Implemented |
| Tamper With Audit Logs    | DB triggers + `verify_log_integrity` | Implemented |
| Bypass Audit Log Writes   | `log_audit_event` (mandatory hooks)  | Planned     |
| Log Aggregation Tampering | `chain_evidence`, hash verification  | Implemented |

---

## 4. Data Models

### 4.1 LogType and ProtectionLevel Enums

```python
class LogType(str, Enum):
    """Log type hierarchy with protection levels."""

    # Tier 1: MUTABLE
    SYSTEM = "system"
    DEBUG = "debug"
    PERFORMANCE = "performance"

    # Tier 2: PROTECTED
    AUDIT = "audit"
    ACCESS = "access"
    ADMIN = "admin"

    # Tier 3: IMMUTABLE
    COMPLIANCE = "compliance"
    EVIDENCE = "evidence"
    DECISION = "decision"


class ProtectionLevel(str, Enum):
    """Protection level determining deletion behavior."""
    MUTABLE = "mutable"
    PROTECTED = "protected"
    IMMUTABLE = "immutable"


LOG_TYPE_PROTECTION: dict[LogType, ProtectionLevel] = {
    LogType.SYSTEM: ProtectionLevel.MUTABLE,
    LogType.DEBUG: ProtectionLevel.MUTABLE,
    LogType.PERFORMANCE: ProtectionLevel.MUTABLE,
    LogType.AUDIT: ProtectionLevel.PROTECTED,
    LogType.ACCESS: ProtectionLevel.PROTECTED,
    LogType.ADMIN: ProtectionLevel.PROTECTED,
    LogType.COMPLIANCE: ProtectionLevel.IMMUTABLE,
    LogType.EVIDENCE: ProtectionLevel.IMMUTABLE,
    LogType.DECISION: ProtectionLevel.IMMUTABLE,
}
```

### 4.2 AuditLogEntry Entity

```python
class AuditLogEntryContent(ContentModel):
    """Audit log entry domain content."""
    tenant_id: FK[Tenant]
    log_type: LogType
    event_type: str
    actor_id: FK[User] | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    action: str
    payload: dict = Field(default_factory=dict)
    source_ip: str | None = None
    user_agent: str | None = None
    chain_entry_id: FK[ChainEntry] | None = None


@register_entity("audit_log_entries", immutable=True)
class AuditLogEntry(Entity):
    """Immutable audit log entry."""
    content: AuditLogEntryContent
```

### 4.3 Database Schema

```sql
CREATE TYPE log_type AS ENUM (
    'system', 'debug', 'performance',
    'audit', 'access', 'admin',
    'compliance', 'evidence', 'decision'
);

CREATE TABLE IF NOT EXISTS "public"."audit_log_entries" (
    "id" UUID PRIMARY KEY,
    "tenant_id" UUID NOT NULL,
    "log_type" log_type NOT NULL,
    "event_type" TEXT NOT NULL,
    "actor_id" UUID,
    "resource_type" TEXT,
    "resource_id" UUID,
    "action" TEXT NOT NULL,
    "payload" JSONB NOT NULL DEFAULT '{}',
    "source_ip" INET,
    "user_agent" TEXT,
    "chain_entry_id" UUID,
    "metadata" JSONB NOT NULL,

    FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id"),
    FOREIGN KEY ("chain_entry_id") REFERENCES "chain_entries"("id")
);

-- Partial index for IMMUTABLE logs
CREATE INDEX ix_audit_log_entries_immutable ON audit_log_entries(id)
    WHERE log_type IN ('compliance', 'evidence', 'decision');
```

### 4.4 Immutability Triggers

```sql
-- Block all updates
CREATE OR REPLACE FUNCTION tr_audit_log_entries_update_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log_entries is immutable'
        USING ERRCODE = 'integrity_constraint_violation';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Block deletes for IMMUTABLE log types
CREATE OR REPLACE FUNCTION tr_audit_log_entries_delete_immutable()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.log_type IN ('compliance', 'evidence', 'decision') THEN
        RAISE EXCEPTION 'Cannot delete IMMUTABLE audit log entry'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;
```

---

## 5. Key Operations

### 5.1 deny_audit_log_deletion Gate

```python
async def deny_audit_log_deletion(
    log_entry_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> DenyResult:
    """Gate: Block deletion of protected audit logs.

    Surfaces covered: Disable Audit Logging

    Protection behavior:
    - IMMUTABLE: Always denied (AuditLogDeletionDenied)
    - PROTECTED: Requires break-glass token (BreakGlassRequired)
    - MUTABLE: Allowed
    """
    entry = await AuditLogEntry.get(log_entry_id, ctx=ctx)
    protection = get_protection_level(entry.content.log_type)

    if protection == ProtectionLevel.IMMUTABLE:
        raise AuditLogDeletionDenied(
            log_entry_id=log_entry_id,
            log_type=entry.content.log_type,
        )

    if protection == ProtectionLevel.PROTECTED:
        if not ctx.has_break_glass_token():
            raise BreakGlassRequired(
                operation="delete_audit_log",
                resource_id=log_entry_id,
            )

    return DenyResult(allowed=True)
```

### 5.2 log_audit_event Feature

```python
async def log_audit_event(
    event_type: str,
    action: str,
    payload: dict,
    ctx: RequestContext,
    *,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    log_type: LogType | None = None,
    conn: Any | None = None,
) -> LogResult:
    """Log an audit event with automatic classification.

    Classifies event_type to LogType if not provided.
    Creates ChainEntry for IMMUTABLE logs.
    """
    # 1. Classify event type
    classified = log_type or classify_event_type(event_type)
    protection = get_protection_level(classified)

    # 2. Create chain entry for IMMUTABLE logs
    chain_entry_id = None
    if protection == ProtectionLevel.IMMUTABLE:
        chain_entry = await chain_evidence(event_type, payload, ctx)
        chain_entry_id = chain_entry.id

    # 3. Create audit log entry
    entry = AuditLogEntry(content=AuditLogEntryContent(
        tenant_id=ctx.tenant_id,
        log_type=classified,
        event_type=event_type,
        actor_id=ctx.actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        payload=payload,
        source_ip=ctx.source_ip,
        user_agent=ctx.user_agent,
        chain_entry_id=chain_entry_id,
    ))

    await insert_entity(entry, conn=conn)

    return LogResult(
        log_entry_id=entry.id,
        log_type=classified,
        protection_level=protection,
        chain_entry_id=chain_entry_id,
        created_at=entry.created_at,
    )
```

### 5.3 verify_log_integrity Feature

```python
async def verify_log_integrity(
    log_entry_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> IntegrityResult:
    """Verify integrity of an audit log entry.

    Checks:
    1. Content hash matches stored hash
    2. Chain entry hash is valid if present
    """
    entry = await AuditLogEntry.get(log_entry_id, ctx=ctx)

    # Verify content hash
    content_hash_valid = entry.verify_content_hash()

    # Verify chain hash if present
    chain_hash_valid = None
    if entry.content.chain_entry_id:
        chain_entry = await ChainEntry.get(entry.content.chain_entry_id, ctx=ctx)
        chain_hash_valid = chain_entry.verify_chain_hash()

    return IntegrityResult(
        log_entry_id=log_entry_id,
        content_hash_valid=content_hash_valid,
        chain_hash_valid=chain_hash_valid,
        verified_at=now_utc(),
    )
```

---

## 6. Event Type Classification

```python
EVENT_TYPE_CLASSIFICATION: dict[str, LogType] = {
    # System events -> SYSTEM
    "health.check": LogType.SYSTEM,
    "cache.invalidate": LogType.SYSTEM,

    # Debug events -> DEBUG
    "debug.*": LogType.DEBUG,

    # Performance events -> PERFORMANCE
    "request.timing": LogType.PERFORMANCE,
    "query.slow": LogType.PERFORMANCE,

    # Audit events -> AUDIT
    "user.login": LogType.AUDIT,
    "user.logout": LogType.AUDIT,
    "session.create": LogType.AUDIT,

    # Access events -> ACCESS
    "resource.read": LogType.ACCESS,
    "export.request": LogType.ACCESS,

    # Admin events -> ADMIN
    "user.create": LogType.ADMIN,
    "role.assign": LogType.ADMIN,
    "break_glass.use": LogType.ADMIN,

    # Compliance events -> COMPLIANCE
    "consent.grant": LogType.COMPLIANCE,
    "consent.revoke": LogType.COMPLIANCE,
    "fcra_notice.send": LogType.COMPLIANCE,

    # Evidence events -> EVIDENCE
    "evidence.create": LogType.EVIDENCE,
    "cep.seal": LogType.EVIDENCE,

    # Decision events -> DECISION
    "adverse_action.certify": LogType.DECISION,
    "termination.certify": LogType.DECISION,
    "hire.approve": LogType.DECISION,
}


def classify_event_type(event_type: str) -> LogType:
    """Classify event_type to LogType."""
    if event_type in EVENT_TYPE_CLASSIFICATION:
        return EVENT_TYPE_CLASSIFICATION[event_type]

    prefix = event_type.rsplit(".", 1)[0] + ".*"
    if prefix in EVENT_TYPE_CLASSIFICATION:
        return EVENT_TYPE_CLASSIFICATION[prefix]

    # Default to AUDIT (PROTECTED)
    return LogType.AUDIT
```

---

## 7. Testing Requirements

| Test Category               | Coverage Target |
| --------------------------- | --------------- |
| IMMUTABLE deletion blocking | 100%            |
| PROTECTED break-glass flow  | 100%            |
| MUTABLE standard delete     | 100%            |
| Event type classification   | 100%            |
| Evidence chain integration  | 100%            |
| DB trigger enforcement      | 100%            |

---

## 8. Open Questions

| # | Question                     | Impact                | Status   |
| - | ---------------------------- | --------------------- | -------- |
| 1 | Retention policy enforcement | MUTABLE auto-rotation | Open     |
| 2 | Archival to cold storage     | IMMUTABLE growth      | Open     |
| 3 | Cross-tenant investigation   | Super-admin queries   | Open     |
| 4 | Break-glass token lifetime   | Security/usability    | Resolved |

---

## 9. References

- ADR:
  `docs-shared/canonsys/01_design/034-audit-logging-governance/ADR-034-audit-logging-governance.md`
- Controls package: `hub/foundation/packages/controls/`
- Evidence package: `hub/foundation/packages/evidence/`
- Related: ADR-003-immutability (DB triggers)
- Related: ADR-006-evidence-chain-cep (chain linking)
- Related: ADR-016-break-glass (authorization)
