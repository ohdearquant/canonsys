# 034 Audit Logging Governance - Vocabulary Mapping

**Status**: Implemented (vocabulary layer)

## Package Mapping

### Primary Package: `controls`

**Location**: `hub/foundation/packages/controls/`

| Component          | Path            | Status      |
| ------------------ | --------------- | ----------- |
| Package definition | `package.py`    | Implemented |
| Service            | `service.py`    | Implemented |
| Exceptions         | `exceptions.py` | Implemented |

### Phrases

| Phrase                    | Path                                 | Regulatory Basis |
| ------------------------- | ------------------------------------ | ---------------- |
| `deny_audit_log_deletion` | `phrases/deny_audit_log_deletion.py` | SOC2 CC6.2       |
| `log_audit_event`         | `phrases/log_audit_event.py`         | SOC2 CC6.2       |
| `verify_log_integrity`    | `phrases/verify_log_integrity.py`    | NIST SP 800-92   |

### Secondary Package: `evidence`

**Location**: `hub/foundation/packages/evidence/`

| Phrase           | Path                        | Regulatory Basis |
| ---------------- | --------------------------- | ---------------- |
| `chain_evidence` | `phrases/chain_evidence.py` | FRE 901          |

## Control Surface Coverage

| Surface                      | Phrases                               |
| ---------------------------- | ------------------------------------- |
| Disable audit logging        | `deny_audit_log_deletion`             |
| Tamper with audit logs       | DB triggers + `verify_log_integrity`  |
| Bypass audit log writes      | `log_audit_event` (mandatory hooks)   |
| Access audit log contents    | RLS + tenant isolation                |
| Export audit logs en masse   | Rate limiting + authorization         |
| Audit log injection          | Input validation in `log_audit_event` |
| Log timestamp manipulation   | Server-side timestamp (now_utc())     |
| Log source IP spoofing       | Trusted proxy header validation       |
| Audit log enumeration        | UUIDs (no sequential IDs)             |
| Log retention bypass         | DB-level retention enforcement        |
| Admin self-audit suppression | Mandatory admin action logging        |
| Audit log overflow           | Volume limits + alerts                |
| Log aggregation tampering    | `chain_evidence`, hash verification   |
| Backup audit log deletion    | Separate backup retention policy      |
| Audit log schema migration   | Backward-compatible migrations only   |

## Log Type Hierarchy

```python
class LogType(str, Enum):
    # Tier 1: MUTABLE - standard retention, deletable
    SYSTEM = "system"
    DEBUG = "debug"
    PERFORMANCE = "performance"

    # Tier 2: PROTECTED - deletion requires break-glass
    AUDIT = "audit"
    ACCESS = "access"
    ADMIN = "admin"

    # Tier 3: IMMUTABLE - deletion blocked at DB level
    COMPLIANCE = "compliance"
    EVIDENCE = "evidence"
    DECISION = "decision"
```

## Protection Matrix

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

## Architectural Patterns

### 1. Protection-Level Routing

```python
async def deny_audit_log_deletion(log_entry_id, ctx):
    entry = await AuditLogEntry.get(log_entry_id)
    protection = get_protection_level(entry.content.log_type)

    if protection == ProtectionLevel.IMMUTABLE:
        raise AuditLogDeletionDenied(...)  # Always blocked
    if protection == ProtectionLevel.PROTECTED:
        if not ctx.has_break_glass_token():
            raise BreakGlassRequired(...)  # Requires authorization
    return DenyResult(allowed=True)  # MUTABLE: allowed
```

### 2. Evidence Chain Integration (ADR-006)

```python
async def log_audit_event(event_type, action, payload, ctx):
    log_type = classify_event_type(event_type)
    chain_entry_id = None

    if get_protection_level(log_type) == ProtectionLevel.IMMUTABLE:
        chain_entry = await chain_evidence(event_type, payload, ctx)
        chain_entry_id = chain_entry.id

    # Create log entry with chain link
    entry = AuditLogEntry(content=AuditLogEntryContent(
        log_type=log_type,
        chain_entry_id=chain_entry_id,
        ...
    ))
```

### 3. DB-Level Trigger Enforcement

```sql
-- Block deletes for IMMUTABLE log types
CREATE TRIGGER tr_audit_log_entries_delete_immutable
    BEFORE DELETE ON audit_log_entries
    FOR EACH ROW EXECUTE FUNCTION tr_audit_log_entries_delete_immutable();
```

## Dependencies

### This Design Depends On

- **ADR-003-immutability**: Entity._immutable flag, DB triggers
- **ADR-006-evidence-chain-cep**: ChainEntry for IMMUTABLE logs
- **ADR-016-break-glass**: BreakGlassRequired exception
- **ADR-001-tenant-isolation**: RLS policies

### Designs That Depend On This

- All services creating audit trails
- Compliance reporting
- Security investigation tools

## Implementation Status

| Component                  | Status      | Notes                        |
| -------------------------- | ----------- | ---------------------------- |
| controls pkg               | Implemented | 3 phrases                    |
| LogType enum               | Implemented | 9 log types                  |
| ProtectionLevel enum       | Implemented | 3 levels                     |
| AuditLogEntry entity       | Implemented | Immutable entity             |
| deny_audit_log_deletion    | Implemented | Gate for Disable Audit Logging surface |
| log_audit_event            | Implemented | Auto-classification          |
| verify_log_integrity       | Implemented | Hash verification            |
| DB triggers (UPDATE block) | Implemented | All log types                |
| DB triggers (DELETE block) | Implemented | IMMUTABLE types only         |
| Event type classification  | Implemented | Pattern matching             |
| Retention job              | Planned     | pg_cron for MUTABLE rotation |
| Cold storage archival      | Planned     | S3 for old IMMUTABLE logs    |

## Database Tables

```sql
audit_log_entries    -- Main audit log table (immutable entity)
```

## Evidence Integration

IMMUTABLE logs link to evidence chain:

- `chain_entry_id` references `chain_entries` table
- Chain provides cryptographic proof of ordering
- `verify_log_integrity` checks both content_hash and chain_hash

## Charter Integration

**Charter**: None (infrastructure-level controls)

**Control Surfaces**: Audit logging governance surfaces (Disable Audit Logging through Audit Log Schema Migration)
