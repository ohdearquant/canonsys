---
doc_type: ADR
title: "ADR-004: Entity-Database Correspondence"
version: "2.0.0"
status: accepted
created: "2026-01-20"
updated: "2026-01-29"
vocabulary_packages: []
charters: []
---

# ADR-004: Entity-Database Correspondence

## Status

Accepted

## Context

CanonSys needs a consistent, type-safe mapping between Python Entity classes and PostgreSQL tables.
Without explicit correspondence rules, developers face type mismatches, inconsistent serialization,
FK ambiguity, nullable confusion, and injection vulnerabilities.

**Why This Matters**: Compliance systems require deterministic behavior. If `datetime` maps to
different SQL types in different contexts, audit queries become unreliable. Evidence integrity
depends on consistent serialization for content hashing.

### Decision Drivers

- Type annotations should deterministically produce SQL types
- All identifiers must be validated, all values parameterized
- RETURNING * must capture database-generated values for evidence
- Pydantic as single source of truth for schema definition

## Decision

### D1: Deterministic Type Mapping

Python types map deterministically to PostgreSQL types.

| Python Type          | PostgreSQL Type          | Notes                       |
| -------------------- | ------------------------ | --------------------------- |
| `str`                | TEXT                     | Unbounded string            |
| `int`                | INTEGER                  | 32-bit signed               |
| `float`              | DOUBLE PRECISION         | 64-bit IEEE 754             |
| `bool`               | BOOLEAN                  | true/false                  |
| `datetime`           | TIMESTAMP WITH TIME ZONE | Always timezone-aware       |
| `UUID`               | UUID                     | Native UUID type            |
| `dict`, `list`       | JSONB                    | Nested structures           |
| `BaseModel` subclass | JSONB                    | Nested Pydantic models      |
| `Enum` subclass      | TEXT                     | Enum value as string        |
| `FK[Model]`          | UUID                     | With REFERENCES constraint  |
| `Vector[dim]`        | VECTOR(dim)              | pgvector extension          |
| `T \| None`          | Same as T (nullable)     | WITHOUT NOT NULL constraint |

**Implementation**: See `libs/canon/src/canon/db/ddl.py`

### D2: NOT NULL Semantics

A field is NOT NULL if and only if its type does not include `None`. Default values do NOT affect
nullability.

```python
name: str                    # NOT NULL
status: str = "pending"      # NOT NULL (default used for INSERT, but NULL cannot be stored)
phone: str | None = None     # NULLABLE
```

### D3: SQL Injection Prevention

All identifiers validated against injection patterns before use.

```python
def validate_identifier(name: str, kind: str = "identifier") -> None:
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise ValidationError(f"Invalid {kind}: {name}")
```

**Implementation**: See `libs/canon/src/canon/db/validation.py`

### D4: CRUD with RETURNING

All mutations use `RETURNING *` to capture database-generated values for evidence hashes.

**Implementation**: See `libs/canon/src/canon/db/crud.py`

## Vocabulary Mapping

This ADR is **infrastructure** - it enables phrase persistence but does not define vocabulary.

| Concept                | Implementation                   | Purpose                 |
| ---------------------- | -------------------------------- | ----------------------- |
| `_to_row()`            | `canon.entities.entity.Entity` | Entity to dict for DB   |
| `_from_row()`          | `canon.entities.entity.Entity` | Dict to Entity from DB  |
| `python_type_to_sql()` | `kron.specs.adapters.sql_ddl` | Type mapping for DDL    |
| `FK[Model]`            | `kron.types.db_types`         | Type-safe FK annotation |

## Alternatives Considered

### Alternative 1: SQLAlchemy ORM

**Why Rejected**: Compliance requires precise SQL control. RETURNING * behavior, trigger timing, and
tenant isolation predicates are easier to reason about with raw SQL.

### Alternative 2: JSON Instead of JSONB

**Why Rejected**: JSONB's read performance and indexing capabilities outweigh marginal write
overhead. Compliance queries often filter on nested fields.

### Alternative 3: Auto-Increment Primary Keys

**Why Rejected**: Evidence chains need to reference entities before database insertion. UUIDs enable
this pattern and avoid information disclosure.

## Consequences

### Positive

- Deterministic mapping: Given a Python type, SQL type is unambiguous
- Type-safe FK generation: `FK[Tenant]` generates correct REFERENCES clause
- SQL injection prevention: All column names validated, all values parameterized
- Audit-ready CRUD: RETURNING * captures database-generated values

### Negative

- PostgreSQL lock-in: Type mapping assumes PostgreSQL-specific types
- UUID storage overhead: 16 bytes vs 4-8 for integers (acceptable for compliance)
- No ORM relationship loading: Must implement `load_fk()` manually

## References

- **TDS**:
  `/docs-shared/canonsys/01_design/004-entity-db-correspondence/TDS-004-entity-db-correspondence.md`
- **Implementation**: `libs/canon/src/canon/db/`
- **Related ADRs**: ADR-002-entity, ADR-001-tenant-isolation
