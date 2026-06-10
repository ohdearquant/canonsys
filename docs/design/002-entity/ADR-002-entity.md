---
doc_type: ADR
title: "ADR-002: Pydantic BaseModel with Auto-Registration Pattern for Entity Base Class"
version: "1.0.0"
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
  - "ADR-001-tenant-isolation"
successors:
  - "TDS-002-entity"
  - "ADR-003-immutability"
supersedes: null
superseded_by: null

tags:
  - entity
  - orm
  - pydantic
  - persistence
  - auto-registration
related:
  - "TDS-002-entity"
  - "ADR-001-tenant-isolation"
  - "003-immutability"
  - "004-entity-db-correspondence"
pr: null

quality:
  confidence: 0.9
  sources: 5
  docs: full
---

## Context

### Problem Statement

CanonSys requires a unified data layer that serves as the single source of truth for both database
schema definition and runtime operations. The system must:

1. Provide type-safe foreign key references with IDE autocompletion
2. Auto-discover entities for migration generation without manual registration
3. Enforce consistent audit metadata across all entities
4. Prevent sensitive fields (passwords, secrets) from appearing in API responses or logs
5. Enable tamper detection through content hashing

**Why This Matters**: Without a unified entity model, developers must maintain separate definitions
for validation, ORM, and API serialization. This leads to inconsistencies, forgotten migrations, and
security vulnerabilities when sensitive fields leak to API responses.

### Background

**Current State**: Traditional ORM approaches (SQLAlchemy declarative base) require:

- Separate model definitions from Pydantic validation schemas
- Manual migration file creation or explicit `alembic autogenerate` setup
- No built-in sensitive field protection
- No integrity hashing for tamper detection

Pydantic v2 provides a powerful validation framework but lacks:

- Database persistence operations
- Entity registry for migration discovery
- Type-safe foreign key annotations with runtime metadata

**Driving Forces**:

- **Type Safety**: IDE autocompletion and mypy checking for FK relationships reduces bugs
- **Developer Experience**: Define entity once, get validation + persistence + schema
- **Security**: Sensitive fields must never leak to API responses or logs
- **Compliance**: Content hashing enables audit-grade tamper detection
- **Circular References**: Forward FK references (`FK["User"]`) must work for bidirectional
  relationships

### Assumptions

1. Pydantic v2 is the validation framework (not v1)
2. UUID primary keys are used (not auto-increment integers)
3. JSONB is acceptable for metadata storage (PostgreSQL feature)
4. asyncpg is the database driver
5. kron provides Node base class with id, created_at, metadata

### Constraints

| Type        | Constraint                              | Impact                                             |
| ----------- | --------------------------------------- | -------------------------------------------------- |
| Technical   | Pydantic v2 BaseModel inheritance       | Must work with Pydantic's metaclass and validation |
| Technical   | asyncio runtime                         | All DB operations must be async                    |
| Security    | Sensitive fields never in API responses | Requires explicit serialization control            |
| Operational | Zero-config migration discovery         | Entities must self-register on definition          |
| Compliance  | Audit trail on all entities             | Every entity needs timestamps, version, hash       |

---

## Decision

### Summary

**We will** build Entity as a kron Node subclass with ContentModel for domain fields,
decorator-based registry registration via `@register_entity`, type-safe foreign keys via `FK[Model]`
annotation pattern (backed by `Annotated[UUID, FKMeta]`), embedded audit metadata via `ContentMeta`
with dual hashing (content_hash, integrity_hash), and sensitive field protection via
`_sensitive_fields` ClassVar.

### Rationale

**Key factors in the decision**:

1. **Pydantic + kron Node architecture**: Entity extends kron Node (which provides id,
   created_at, metadata from Element). Domain fields live in ContentModel subclass. This separation
   enables clean identity vs domain split.

2. **Decorator-based registration**: `@register_entity` decorator is explicit - you see the table
   name at the class definition site. Collision detection happens at import time. Migration tools
   discover all entities via `get_entity_registry()`.

3. **`FK[Model]` for type-safe foreign keys**: The `Annotated[UUID, FKMeta(model)]` pattern provides
   IDE autocompletion (knows it's a UUID) while carrying runtime metadata (knows it references
   Tenant). Forward references (`FK["User"]`) supported.

4. **ContentMeta as flat columns**: Audit metadata (updated_at, version, is_deleted, hashes) stored
   as flat columns for direct SQL querying. Not JSONB - enables standard WHERE clauses on audit
   fields.

5. **Dual hashing strategy**: `content_hash` for domain-only integrity, `integrity_hash` includes
   meta fields. Enables both content deduplication and full tamper detection.

### Implementation Approach

**Decorator-Based Registration**

```python
_entity_registry: dict[str, type[Entity]] = {}

def _register_entity(table_name: str, cls: type[Entity]) -> None:
    if table_name in _entity_registry:
        existing = _entity_registry[table_name]
        if existing is not cls:
            raise ValueError(f"Table '{table_name}' already registered")
    _entity_registry[table_name] = cls

def register_entity(
    table_name: str,
    *,
    schema: str = "public",
    immutable: bool = False,
) -> Callable[[type[E]], type[E]]:
    def decorator(cls: type[E]) -> type[E]:
        if not issubclass(cls, Entity):
            raise TypeError(f"{cls.__name__} must be subclass of Entity")
        cls._table_name = table_name
        cls._schema = schema
        cls._immutable = immutable
        _register_entity(table_name, cls)
        return cls
    return decorator
```

**FK Type Helper**

```python
from typing import Annotated
from uuid import UUID

class FKMeta:
    """Metadata marker carrying FK target information."""
    __slots__ = ("model", "column", "on_delete", "on_update")

    def __init__(
        self,
        model: type | str,
        column: str = "id",
        on_delete: str = "CASCADE",
        on_update: str = "CASCADE",
    ):
        self.model = model
        self.column = column
        self.on_delete = on_delete
        self.on_update = on_update

class _FK:
    def __class_getitem__(cls, model: type | str):
        return Annotated[UUID, FKMeta(model)]

FK = _FK
```

**ContentMeta for Audit**

```python
class ContentMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    updated_at: datetime = Field(default_factory=ln.now_utc)
    updated_by: str | None = None
    deleted_at: datetime | None = None
    is_deleted: bool = False
    is_active: bool = True
    version: int = Field(default=1, ge=1)
    content_hash: str | None = None
    integrity_hash: str | None = None

class ContentModel(BaseModel):
    content_meta: ContentMeta = Field(default_factory=ContentMeta)

class Entity(Node):  # Node from kron
    content: ContentModel
```

**Sensitive Field Protection**

```python
class UserContent(ContentModel):
    _sensitive_fields: ClassVar[set[str]] = {"password_hash", "mfa_secret"}

    email: str
    password_hash: str
    mfa_secret: str | None = None

@register_entity("users")
class User(Entity):
    content: UserContent
```

**Rehash for Integrity**

```python
def _rehash(self) -> None:
    """Recompute content_hash and integrity_hash."""
    content_dict = self.model_dump(mode="json")
    self._meta.content_hash = compute_hash(content_dict)

    full_dict = content_dict.copy()
    full_dict.update(self._meta.to_hash_dict())
    self._meta.integrity_hash = compute_hash(full_dict)
```

### Alternatives Considered

#### Alternative 1: SQLAlchemy ORM

**Description**: Use SQLAlchemy declarative base with async session for database operations,
separate Pydantic schemas for API validation.

| Criterion               | Score (1-5) | Notes                                          |
| ----------------------- | ----------- | ---------------------------------------------- |
| Type Safety             | 3           | Good ORM typing, but separate from API schemas |
| Developer Experience    | 3           | Two model definitions per entity               |
| Pydantic Integration    | 2           | Requires manual schema conversion              |
| Auto-Registration       | 4           | `declarative_base()` registry exists           |
| Sensitive Field Control | 2           | Requires custom serialization logic            |

**Why Not Chosen**: Pydantic-first APIs require Pydantic models anyway. SQLAlchemy would mean
maintaining two parallel model definitions (ORM + Pydantic), leading to inconsistencies and extra
code. The impedance mismatch is not worth the maturity benefits.

#### Alternative 2: Metaclass-Based Registration

**Description**: Use a custom metaclass instead of decorator for entity registration.

| Criterion            | Score (1-5) | Notes                                             |
| -------------------- | ----------- | ------------------------------------------------- |
| Type Safety          | 4           | Same as decorator                                 |
| Developer Experience | 2           | Metaclass conflicts are hard to debug             |
| Pydantic Integration | 1           | Pydantic uses its own metaclass, conflicts likely |
| Auto-Registration    | 4           | Full control over class creation                  |
| Debugging            | 2           | Metaclass errors are opaque                       |

**Why Not Chosen**: Pydantic v2 uses its own metaclass (`ModelMetaclass`). Attempting to use a
custom metaclass would conflict with Pydantic's class creation. Decorator is explicit and visible.

#### Alternative 3: JSONB for Audit Metadata

**Description**: Store ContentMeta as single JSONB column instead of flat columns.

| Criterion               | Score (1-5) | Notes                            |
| ----------------------- | ----------- | -------------------------------- |
| Query Performance       | 3           | Requires JSON operators          |
| Schema Simplicity       | 4           | Single column for all audit      |
| Migration Complexity    | 5           | Add fields without schema change |
| Flexibility             | 5           | Arbitrary extension allowed      |
| PostgreSQL Optimization | 3           | GIN index needed for queries     |

**Why Not Chosen**: Direct SQL querying is important for audit workflows. Flat columns enable
standard WHERE clauses like `WHERE updated_at > '2024-01-01'` without JSON operators.

#### Alternative 4: Domain Fields on Entity Directly

**Description**: Put domain fields directly on Entity class instead of in ContentModel.

```python
class User(Entity):
    email: str
    password_hash: str
```

| Criterion              | Score (1-5) | Notes                                   |
| ---------------------- | ----------- | --------------------------------------- |
| Simplicity             | 5           | Less indirection                        |
| Type Safety            | 4           | Same as ContentModel approach           |
| Separation of Concerns | 2           | Mixes identity with domain              |
| Reusability            | 2           | Can't reuse content model               |
| Compatibility          | 2           | Harder to integrate with kron Node      |

**Why Not Chosen**: Entity = Node + ContentModel separation is cleaner. ContentModel can have its
own lifecycle methods, and the pattern matches kron's architecture.

### Decision Matrix

| Criterion              | Weight | SQLAlchemy | Metaclass | JSONB Audit | Direct Fields | **Node+ContentModel** |
| ---------------------- | ------ | ---------- | --------- | ----------- | ------------- | --------------------- |
| Pydantic Integration   | 30%    | 2          | 1         | 4           | 4             | **5**                 |
| Developer Experience   | 25%    | 3          | 2         | 4           | 4             | **5**                 |
| Type Safety            | 20%    | 3          | 4         | 4           | 4             | **5**                 |
| Separation of Concerns | 15%    | 3          | 3         | 3           | 2             | **5**                 |
| Extensibility          | 10%    | 4          | 3         | 5           | 3             | **4**                 |
| **Weighted Total**     | 100%   | **2.65**   | **2.15**  | **3.85**    | **3.55**      | **4.90**              |

---

## Consequences

### Positive Consequences

1. **Clean separation**: Entity = Node + ContentModel. Identity (id, created_at) separate from
   domain (content). Clear mental model.

2. **Explicit registration**: `@register_entity` decorator visible at class definition. Migration
   tools call `get_entity_registry()` to discover all entities.

3. **Type-safe FK references**: `tenant_id: FK[Tenant]` provides IDE autocompletion on Tenant while
   carrying FKMeta for DDL generation. Forward refs (`FK["User"]`) supported.

4. **Sensitive field protection**: `_sensitive_fields` ClassVar defined on ContentModel subclass.
   Fields like `password_hash` explicitly marked for exclusion.

5. **Dual hashing for integrity**: `content_hash` for domain-only, `integrity_hash` for full state.
   Enables both content deduplication and tamper detection.

6. **Audit metadata consistency**: Every ContentModel has `updated_at`, `version`, hashes via
   ContentMeta. No entity can forget audit fields.

### Negative Consequences

1. **Extra indirection**: Domain fields accessed via `entity.content.field`. Mitigation: Clear
   pattern, IDE autocompletion works.

2. **Learning curve**: ContentModel pattern and `@register_entity` are custom patterns. New
   developers need to understand Entity = Node + ContentModel. Mitigation: Clear documentation.

3. **Pydantic version lock-in**: Implementation assumes Pydantic v2 APIs (`model_rebuild`,
   `model_fields`, `ConfigDict`). Mitigation: Pydantic v2 is stable; v3 migration would require work
   but is years away.

4. **kron dependency**: Entity extends kron Node. Mitigation: kron is internal
   library under our control.

### Neutral Consequences

1. **UUID primary keys**: All entities use UUID instead of auto-increment. This is a project-wide
   decision, not specific to this ADR.

2. **asyncpg-specific**: CRUD operations use asyncpg patterns. Switching to psycopg3 or SQLAlchemy
   async would require CRUD module changes, not Entity changes.

### Risks

| Risk                             | Likelihood | Impact | Mitigation                              |
| -------------------------------- | ---------- | ------ | --------------------------------------- |
| Duplicate table name in registry | L          | M      | ValueError at import time catches early |
| ContentModel pattern confusion   | M          | L      | Clear documentation and examples        |
| Content hash drift               | L          | M      | Always call touch() before save         |
| kron API changes                 | L          | M      | Pin version, kron is internal           |

### Dependencies Introduced

| Dependency | Type     | Version | Stability | Notes                         |
| ---------- | -------- | ------- | --------- | ----------------------------- |
| pydantic   | Library  | ^2.0.0  | Stable    | BaseModel, validation         |
| kron       | Internal | ^1.0.0  | Stable    | Node base class, utils.now_utc() |
| hashlib    | stdlib   | N/A     | Stable    | SHA-256 for content hashing   |

### Migration Impact

**Backwards Compatibility**: N/A (foundational component for new system)

**Migration Steps**:

1. Create `ContentMeta` model
2. Create `ContentModel` base class
3. Create `Entity` base class extending kron Node
4. Create `FK` type helper and `FKMeta`
5. Create `@register_entity` decorator and `create_entity()` factory
6. Define domain ContentModels and Entity classes

**Rollback Plan**:

1. Revert to separate Pydantic schemas + SQLAlchemy models
2. Manual migration discovery
3. Significant refactoring required (not recommended)

---

## Verification

### Success Criteria

- [ ] Entity subclasses register via `@register_entity` (verified via unit test)
- [ ] `FK[Model]` provides correct type annotation (verified via unit test)
- [ ] ContentModel lifecycle methods work (soft_delete, restore) (verified via unit test)
- [ ] `_sensitive_fields` defined on ContentModel subclass (verified via unit test)
- [ ] `ValueError` raised for duplicate table names (verified via unit test)
- [ ] content_hash changes when domain fields change (verified via unit test)
- [ ] integrity_hash includes meta field changes (verified via unit test)

### Metrics to Track

| Metric                   | Baseline | Target | Review Date |
| ------------------------ | -------- | ------ | ----------- |
| Entity registry size     | N/A      | <100   | Monthly     |
| Content hash computation | N/A      | <1ms   | Monthly     |
| Sensitive field leaks    | N/A      | 0      | Per release |
| Model sync errors        | N/A      | 0      | Per release |

### Review Schedule

- **Initial Review**: 2026-02-15 (1 month after implementation)
- **Ongoing Reviews**: Quarterly architecture review
- **Review Owner**: Platform architect

---

## Related Artifacts

### Builds On

- `ADR-001-tenant-isolation`: Entity uses `FK[Tenant]` pattern established there

### Impacts

- `TDS-002-entity`: Technical design implementing this decision
- `ADR-003-immutability`: ImmutableEntity extends Entity base class
- `TDS-004-entity-db-correspondence`: CRUD operations build on Entity
- `TDS-006-evidence-chain-cep`: Evidence/Chain/CEP extend Entity hierarchy

---

## References

- Pydantic v2 Documentation: <https://docs.pydantic.dev/latest/>
- kron Node/Element: Internal library for composable AI components
- Python `typing.Annotated`: <https://peps.python.org/pep-0593/>
- PostgreSQL JSONB: <https://www.postgresql.org/docs/current/datatype-json.html>
- SHA-256 for integrity: NIST FIPS 180-4

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
