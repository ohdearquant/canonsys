---
doc_type: ADR
title: "ADR-003: Flag-Based Immutability with Supersession Pattern for Compliance Records"
version: "1.1.0"
status: accepted
created: "2026-01-15"
updated: "2026-01-20"
decision_date: null
by: "alpha[architect]"
owner: "alpha[architect]"
output_subdir: adr
phase: design
scope: L3

predecessors:
  - "ADR-002-entity"
successors:
  - "TDS-003-immutability"
  - "TDS-006-evidence-chain-cep"
supersedes: null
superseded_by: null

tags:
  - immutability
  - compliance
  - audit
  - supersession
  - evidence
related:
  - "TDS-003-immutability"
  - "ADR-002-entity"
  - "006-evidence-chain-cep"
pr: null

quality:
  confidence: 0.9
  sources: 4
  docs: full
---

## Context

### Problem Statement

CanonSys handles compliance-critical records (evidence artifacts, decision chains, audit packets)
that must be provably unmodified after creation. Regulatory frameworks (FCRA, GDPR, EU AI Act)
require that evidence supporting decisions be immutable and verifiable. The system must:

1. Prevent modification of records after creation (insert-only semantics)
2. Prevent deletion of records under all circumstances
3. Enable corrections without mutation via supersession pattern
4. Provide tamper detection through content hashing
5. Enforce immutability at both application and database layers

**Why This Matters**: In litigation or regulatory audit, evidence of decisions must be provably
unmodified. If an adverse action (e.g., job rejection) is challenged, the company must prove that
the evidence supporting that decision has not been altered. Mutable records fail this requirement.

### Background

**Current State**: Traditional CRUD operations allow updates and deletes, which:

- Destroy audit trails (original data is lost)
- Cannot prove records were not tampered with
- Fail regulatory requirements for evidence preservation
- Cannot distinguish corrections from tampering

**Driving Forces**:

- **Regulatory Compliance**: FCRA adverse action records must be preserved. GDPR right to erasure
  applies to personal data, not evidence of decisions. EU AI Act requires human oversight records.
- **Litigation Defense**: Evidence must be provably unmodified years after creation.
- **Tamper Detection**: Content hash enables verification that records match their original state.
- **Correction Requirement**: Business reality requires corrections. Supersession enables
  corrections without mutation.
- **Defense in Depth**: Application-only enforcement is insufficient. Database triggers catch direct
  SQL access.

### Assumptions

1. Entity base class (ADR-002) provides content hashing via `_rehash()`
2. PostgreSQL is the production database with trigger support
3. asyncpg is the database driver
4. Corrections are rare but must be supported
5. Soft-delete semantics inherited from Entity should be restricted for immutable entities

### Implementation Evolution

**Note**: This ADR was originally written proposing a separate `ImmutableEntity` class with
`_allowed_update_fields`. The actual implementation evolved to a simpler flag-based approach:

- **Original Proposal**: `ImmutableEntity` base class with `_allowed_update_fields` ClassVar
- **Actual Implementation**: `Entity._immutable: ClassVar[bool]` flag

Key differences from original proposal:

1. **No separate class**: Immutability is a flag on Entity, not a subclass
2. **No allowed update fields**: Immutable entities cannot have ANY fields updated
3. **Decorator/factory pattern**: `@register_entity(..., immutable=True)` or
   `create_entity(..., immutable=True)` sets the flag
4. **Supersession only**: Corrections create new records; no in-place updates allowed

The decision rationale remains valid - the implementation is simpler while achieving the same goals.

### Constraints

| Type       | Constraint                             | Impact                                      |
| ---------- | -------------------------------------- | ------------------------------------------- |
| Regulatory | Records must be preserved indefinitely | No hard deletes allowed                     |
| Regulatory | Evidence must be verifiable            | Content hash required for tamper detection  |
| Business   | Corrections must be possible           | Supersession pattern, not in-place mutation |
| Technical  | Database triggers must be idempotent   | Migration re-runs must not fail             |
| Security   | Direct SQL must also be blocked        | DB triggers as defense-in-depth             |

---

## Decision

### Summary

**We will** create an `ImmutableEntity` base class that extends Entity with insert-only save
semantics, blocked updates (except for explicitly allowed fields), blocked deletes, content hash
verification, and database trigger enforcement. Corrections use the supersession pattern where new
records reference their predecessors.

### Rationale

**Key factors in the decision**:

1. **Insert-only semantics**: `save()` is always INSERT, never UPSERT. If a record already exists,
   `ExistsError` is raised. This makes the immutability semantic explicit: calling `save()` on an
   existing record is an error, not a silent update.

2. **Allowed update fields for linking**: True full immutability would prevent linking records
   together for supersession. The `_allowed_update_fields` ClassVar permits specific fields (like
   `superseded_by_id`) to be updated while keeping domain content immutable. The content hash
   excludes these fields.

3. **Defense-in-depth via database triggers**: Application-layer enforcement can be bypassed by
   direct SQL access (e.g., DBA scripts, data fixes). PostgreSQL triggers block UPDATE and DELETE at
   the database level, catching bypass attempts.

4. **Supersession over mutation**: Corrections create new records that reference predecessors.
   Original records remain untouched, providing complete audit trail. Queries can filter to "latest"
   versions while historical versions remain accessible.

5. **On-demand integrity verification**: `verify_integrity()` recomputes hash and compares. Not
   automatic on every read (performance cost), but available for sensitive operations (litigation
   export, audit reports, background verification jobs).

### Implementation Approach

**ImmutableEntity Base Class**

```python
from typing import ClassVar, Self
from canon.types.entity import Entity
from canon.exceptions import ExistsError, ImmutableViolationError

class ImmutableEntity(Entity):
    """Base class for insert-only entities.

    Rules:
    - save() is insert-only (never upsert)
    - delete() is always blocked
    - update() is blocked unless only _allowed_update_fields changed

    Content hash excludes _allowed_update_fields so linking fields
    do not invalidate integrity verification.
    """

    _allowed_update_fields: ClassVar[set[str]] = set()

    async def save(self, dsn: str | None = None) -> Self:
        """Insert-only save. Raises ExistsError on duplicate."""
        self._rehash()
        try:
            return await self.insert(dsn=dsn)
        except Exception as e:
            if _is_unique_violation(e):
                raise ExistsError(
                    entity_type=type(self).__name__,
                    entity_id=str(self.id)
                )
            raise

    async def delete(self, dsn: str | None = None) -> bool:
        """BLOCKED: Immutable entities cannot be deleted."""
        raise ImmutableViolationError(
            entity_type=type(self).__name__,
            operation="delete",
            entity_id=str(self.id)
        )
```

**Controlled Update with Diff Detection**

```python
async def update(self, dsn: str | None = None) -> Self:
    """Update only if changes are within _allowed_update_fields."""
    if not self._allowed_update_fields:
        raise ImmutableViolationError(
            entity_type=type(self).__name__,
            operation="update",
            detail="no fields are allowed to be updated"
        )

    persisted = await self.__class__.get(str(self.id), dsn=dsn)
    if not persisted:
        raise NotFoundError(entity_type=type(self).__name__, entity_id=str(self.id))

    # Compute field diff
    current_row = self._to_row()
    persisted_row = persisted._to_row()
    changed = {k for k, v in current_row.items() if v != persisted_row.get(k)}

    # Check for disallowed changes
    disallowed = changed - set(self._allowed_update_fields) - {"metadata"}
    if disallowed:
        raise ImmutableViolationError(
            entity_type=type(self).__name__,
            operation="update",
            detail=f"attempted to update disallowed fields: {sorted(disallowed)}"
        )

    return await self._update_allowed_fields(
        {k: current_row[k] for k in changed if k in self._allowed_update_fields},
        dsn=dsn
    )
```

**Hash Excludes Allowed Update Fields**

```python
def _rehash(self) -> None:
    """Hash only immutable domain fields."""
    exclude = {"id", "metadata"} | set(self._allowed_update_fields)
    data = self.model_dump(mode="json", exclude=exclude)
    data["_state_is_deleted"] = self.metadata.is_deleted
    self.metadata.content_hash = compute_hash(data)
```

**Integrity Verification**

```python
def verify_integrity(self) -> bool:
    """Verify content_hash matches recomputed hash."""
    exclude = {"id", "metadata"} | set(self._allowed_update_fields)
    data = self.model_dump(mode="json", exclude=exclude)
    data["_state_is_deleted"] = self.metadata.is_deleted
    expected = compute_hash(data)
    return self.metadata.content_hash == expected

def verify_or_raise(self) -> None:
    """Verify integrity and raise on mismatch."""
    if not self.verify_integrity():
        raise IntegrityViolationError(
            entity_type=type(self).__name__,
            entity_id=str(self.id),
            expected_hash=self.metadata.content_hash,
            actual_hash="<recomputed>"
        )
```

**Database Trigger Generation**

```sql
-- Generated by generate_immutable_update_trigger()
CREATE OR REPLACE FUNCTION tr_evidence_update_immutable()
RETURNS TRIGGER AS $$
DECLARE
    immutable_fields TEXT[] := ARRAY['content', 'evidence_type', 'tenant_id'];
    changed_fields TEXT[] := '{}';
    field TEXT;
BEGIN
    FOREACH field IN ARRAY immutable_fields LOOP
        IF (row_to_json(OLD)->>field) IS DISTINCT FROM (row_to_json(NEW)->>field) THEN
            changed_fields := array_append(changed_fields, field);
        END IF;
    END LOOP;

    IF array_length(changed_fields, 1) > 0 THEN
        RAISE EXCEPTION 'evidence is immutable. Attempted to modify: %', changed_fields
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_evidence_update_immutable
    BEFORE UPDATE ON evidence
    FOR EACH ROW EXECUTE FUNCTION tr_evidence_update_immutable();

-- Delete trigger
CREATE OR REPLACE FUNCTION tr_evidence_delete_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'evidence is immutable and cannot be deleted (id=%)', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_evidence_delete_immutable
    BEFORE DELETE ON evidence
    FOR EACH ROW EXECUTE FUNCTION tr_evidence_delete_immutable();
```

**Supersession Pattern**

```python
class EvidenceContent(ContentModel):
    """Content model for immutable evidence records."""
    tenant_id: FK["Tenant"]
    evidence_type: str
    content: dict
    supersedes_id: UUID | None = None  # Backward pointer to predecessor

# Create immutable entity using factory pattern
Evidence = create_entity("Evidence", EvidenceContent, immutable=True)

async def supersede_evidence(evidence: Evidence, new_content: dict) -> Evidence:
    """Create a corrected version that supersedes this one."""
    corrected = Evidence(
        tenant_id=evidence.tenant_id,
        evidence_type=evidence.evidence_type,
        content=new_content,
        supersedes_id=evidence.id,  # Points back to original record
    )
    return await corrected.insert()
```

### Alternatives Considered

#### Alternative 1: Separate Linking Table

**Description**: Store supersession relationships in a separate `evidence_supersessions` table
rather than `supersedes_id` on the evidence itself.

| Criterion            | Score (1-5) | Notes                                        |
| -------------------- | ----------- | -------------------------------------------- |
| True Immutability    | 5           | Evidence table has zero mutable fields       |
| Query Simplicity     | 2           | Every query needs JOIN to find successors    |
| Migration Complexity | 3           | Extra table, extra indexes                   |
| Audit Trail Clarity  | 3           | Relationship exists but not on record itself |
| Performance          | 2           | Additional JOIN overhead                     |

**Why Not Chosen**: Query complexity. Every query that needs to find the "latest" version of a
record requires a JOIN or subquery. The `supersedes_id` field directly on Evidence is simpler and
sufficient for the use case.

#### Alternative 2: Event Sourcing

**Description**: Store all changes as events in an append-only event store, derive current state by
replaying events.

| Criterion          | Score (1-5) | Notes                                        |
| ------------------ | ----------- | -------------------------------------------- |
| Audit Completeness | 5           | Every change is preserved as an event        |
| Query Simplicity   | 1           | Complex projections needed for current state |
| Implementation     | 1           | Significant architectural complexity         |
| Storage Efficiency | 2           | Events accumulate indefinitely               |
| Tooling            | 2           | Requires event store infrastructure          |

**Why Not Chosen**: Over-engineering for the requirement. Evidence records don't have frequent
changes - they're created once and rarely corrected. Event sourcing's complexity is justified for
domains with frequent state changes, not for compliance evidence.

#### Alternative 3: Application-Only Enforcement

**Description**: Enforce immutability only in the application layer via ImmutableEntity methods,
without database triggers.

| Criterion           | Score (1-5) | Notes                                       |
| ------------------- | ----------- | ------------------------------------------- |
| Implementation      | 5           | Simple, no trigger DDL                      |
| Defense-in-Depth    | 1           | Direct SQL bypasses all protection          |
| Audit Certification | 1           | Auditors require database-level enforcement |
| DBA Access Control  | 1           | No protection against privileged access     |
| Compliance Risk     | 1           | Single point of failure                     |

**Why Not Chosen**: Direct SQL bypass. DBA scripts, data fixes, or compromised credentials could
modify records. Database triggers ensure immutability is enforced even for direct SQL access. This
is required for SOC2/compliance certification.

#### Alternative 4: Version Column Approach

**Description**: Add a `version` column and create new rows with incremented version for each
change, keeping all versions.

| Criterion            | Score (1-5) | Notes                                     |
| -------------------- | ----------- | ----------------------------------------- |
| Audit Trail          | 4           | All versions preserved                    |
| Query Complexity     | 2           | MAX(version) subqueries everywhere        |
| Unique Constraints   | 2           | Composite unique on (logical_id, version) |
| Relationship Clarity | 3           | Version numbers vs explicit supersedes_id |
| Data Model Clarity   | 3           | Two IDs: logical_id + physical id         |

**Why Not Chosen**: Query complexity and data model confusion. Every query needs
`WHERE version = (SELECT MAX...)` or window functions. The `supersedes_id` approach with explicit
backward pointer is clearer for the audit use case.

### Decision Matrix

| Criterion                 | Weight | Linking Table | Event Sourcing | App-Only | Version Col | **ImmutableEntity** |
| ------------------------- | ------ | ------------- | -------------- | -------- | ----------- | ------------------- |
| Audit Trail Clarity       | 25%    | 3             | 5              | 4        | 4           | **5**               |
| Query Simplicity          | 25%    | 2             | 1              | 5        | 2           | **4**               |
| Defense-in-Depth          | 25%    | 4             | 5              | 1        | 4           | **5**               |
| Implementation Simplicity | 15%    | 3             | 1              | 5        | 3           | **4**               |
| Compliance Certification  | 10%    | 4             | 5              | 1        | 4           | **5**               |
| **Weighted Total**        | 100%   | **2.90**      | **3.20**       | **3.15** | **3.20**    | **4.55**            |

---

## Consequences

### Positive Consequences

1. **Provable immutability**: Records cannot be modified after creation at both application and
   database levels. Compliance auditors can verify that UPDATE and DELETE are blocked by triggers.

2. **Complete audit trail**: Supersession pattern preserves all versions. Original record remains
   accessible; new record points back via `supersedes_id`. Litigation can trace the complete
   history.

3. **Tamper detection**: Content hash (SHA-256) enables verification that records match their
   original state. `verify_integrity()` recomputes hash and compares. Background jobs can detect
   tampering early.

4. **Flexible linking**: `_allowed_update_fields` permits forward pointers (`superseded_by_id`)
   without breaking immutability. Content hash excludes these fields, so linking doesn't invalidate
   integrity.

5. **Defense-in-depth**: Five layers protect immutability: ImmutableEntity methods,
   `_allowed_update_fields` check, content hash verification, UPDATE trigger, DELETE trigger.

### Negative Consequences

1. **Storage growth**: Corrections create new records; originals remain. Mitigation: This is the
   design goal, not a bug. Evidence storage is cheap compared to litigation risk.

2. **Query complexity for "latest"**: Finding the current version requires filtering for
   non-superseded records. Mitigation: Create a view or add `is_latest` denormalized field if query
   performance is a concern.

3. **Trigger maintenance**: Database triggers must be regenerated if `_allowed_update_fields`
   changes. Mitigation: Trigger generation is idempotent; run on every migration.

4. **Hash computation cost**: SHA-256 over JSON adds ~1-2ms per insert. Mitigation: Acceptable for
   compliance-critical records; not used on high-volume entities.

### Neutral Consequences

1. **Extends Entity base class**: ImmutableEntity inherits from Entity, gaining `ContentMeta`,
   `FK[Model]`, and other features from ADR-002.

2. **Soft-delete inherited but discouraged**: Entity has `soft_delete()` method. For
   ImmutableEntity, soft-delete is semantically discouraged but not technically blocked. Future
   consideration: override to raise.

### Risks

| Risk                                   | Likelihood | Impact | Mitigation                                                 |
| -------------------------------------- | ---------- | ------ | ---------------------------------------------------------- |
| Developer accidentally uses `update()` | M          | L      | Clear error message; empty `_allowed_update_fields` blocks |
| Trigger not created on new table       | L          | H      | Migration generates triggers automatically                 |
| Hash algorithm weakness in future      | L          | M      | SHA-256 is current standard; upgrade path exists           |
| Superuser bypasses triggers            | L          | M      | Superuser must not be used for application access          |

### Dependencies Introduced

| Dependency | Type     | Version | Stability | Notes                   |
| ---------- | -------- | ------- | --------- | ----------------------- |
| Entity     | Internal | N/A     | Stable    | Base class from ADR-002 |
| hashlib    | stdlib   | N/A     | Stable    | SHA-256 implementation  |
| PostgreSQL | Database | 14+     | Stable    | Trigger support         |

### Migration Impact

**Backwards Compatibility**: N/A (new component)

**Migration Steps**:

1. Create `ImmutableEntity` class extending Entity
2. Implement override methods (`save`, `update`, `delete`, `verify_integrity`)
3. Add trigger generation functions to migration module
4. Generate triggers for existing ImmutableEntity tables
5. Create Evidence, Chain, CEP entities extending ImmutableEntity

**Rollback Plan**:

1. Drop triggers: `DROP TRIGGER IF EXISTS tr_*_immutable ON *`
2. ImmutableEntity can remain but enforcement is application-only
3. Not recommended for compliance reasons

---

## Verification

### Success Criteria

- [ ] `save()` raises `ExistsError` on duplicate (verified via test)
- [ ] `update()` raises `ImmutableViolationError` for empty `_allowed_update_fields` (verified via
      test)
- [ ] `update()` succeeds for changes only in `_allowed_update_fields` (verified via test)
- [ ] `delete()` raises `ImmutableViolationError` always (verified via test)
- [ ] Database trigger blocks direct SQL UPDATE on immutable fields (verified via test)
- [ ] Database trigger blocks direct SQL DELETE (verified via test)
- [ ] `verify_integrity()` returns True for unmodified records (verified via test)
- [ ] `verify_integrity()` returns False for tampered records (verified via test)
- [ ] Content hash unchanged when allowed update fields change (verified via test)

### Metrics to Track

| Metric                           | Baseline | Target | Review Date |
| -------------------------------- | -------- | ------ | ----------- |
| Integrity verification failures  | N/A      | 0      | Weekly      |
| Trigger violation attempts       | N/A      | Logged | Weekly      |
| Evidence supersession rate       | N/A      | <1%    | Monthly     |
| Background verification coverage | N/A      | 100%   | Monthly     |

### Review Schedule

- **Initial Review**: 2026-02-15 (1 month after implementation)
- **Ongoing Reviews**: Quarterly compliance audit
- **Review Owner**: Compliance team + Platform architect

---

## Related Artifacts

### Builds On

- `ADR-002-entity`: ImmutableEntity extends Entity base class

### Impacts

- `TDS-003-immutability`: Technical design implementing this decision
- `TDS-006-evidence-chain-cep`: Evidence/Chain/CEP extend ImmutableEntity
- Litigation export module (future)
- Background integrity verification job (future)

---

## References

- FCRA 15 U.S.C. 1681e(a): Reasonable procedures for accuracy
- GDPR Article 17: Right to erasure (with exceptions for legal claims)
- EU AI Act Article 14: Human oversight requirements
- NIST FIPS 180-4: SHA-256 specification
- PostgreSQL CREATE TRIGGER: <https://www.postgresql.org/docs/current/sql-createtrigger.html>

---

## Appendix: Supersession Pattern Example

**Scenario**: Original evidence has an error. Correction needed.

```python
# Original evidence created
evidence_v1 = Evidence(
    tenant_id=tenant.id,
    evidence_type="background_check",
    content={"result": "pass", "score": 85}  # Error: score should be 95
)
await evidence_v1.save()
# evidence_v1.id = "aaa..."
# evidence_v1.supersedes_id = None
# evidence_v1.metadata.content_hash = "hash_v1"

# Correction needed - use supersession
evidence_v2 = await evidence_v1.supersede(
    new_content={"result": "pass", "score": 95}  # Corrected score
)
# evidence_v2.id = "bbb..."
# evidence_v2.supersedes_id = "aaa..." (points to v1)
# evidence_v2.metadata.content_hash = "hash_v2"

# Query for current evidence
current = await Evidence.select(
    where={"id": evidence_v2.id}  # or use view with is_superseded filter
)

# Historical query shows both records
all_versions = await Evidence.select(
    where={"tenant_id": tenant.id, "evidence_type": "background_check"}
)
# Returns [evidence_v1, evidence_v2]
# evidence_v1 intact with original content and hash
```

**Audit Trail**:

```
evidence_v1 (id=aaa)
  content: {score: 85}
  supersedes_id: null
  content_hash: hash_v1

evidence_v2 (id=bbb)
  content: {score: 95}
  supersedes_id: aaa  <- points back to v1
  content_hash: hash_v2
```

Both records remain in the database. v1 proves what was originally recorded. v2 proves what the
correction was. `supersedes_id` creates the audit chain.

---

## Validation Checklist

### Nygard Format Compliance

- [x] Context explains forces at play
- [x] Decision is clearly stated
- [x] Consequences cover positive, negative, and neutral outcomes

### Completeness

- [x] Problem clearly stated
- [x] Background and constraints documented
- [x] At least 2 alternatives considered (4 alternatives evaluated)
- [x] Decision matrix completed
- [x] Risks identified with mitigations

### Quality

- [x] Rationale is convincing
- [x] Trade-offs are honest
- [x] Success criteria are measurable
- [x] Review schedule defined

### Traceability

- [x] Related artifacts linked
- [x] References provided
