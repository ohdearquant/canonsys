# 004 - Entity-DB Correspondence - Code Mapping

- **Updated**: 2026-01-29
- **Status**: Infrastructure

## Summary

Entity-DB Correspondence is **infrastructure** that enables phrase persistence. It does not define
vocabulary packages itself.

## Implementation Files

| File                          | Purpose                               |
| ----------------------------- | ------------------------------------- |
| `libs/canon/src/canon/entities/entity.py`  | Entity, ContentModel, ContentMeta     |
| `libs/canon/src/canon/db/crud.py`       | insert, upsert, update, select, count |
| `libs/canon/src/canon/db/ddl.py`        | TYPE_MAP, EntitySchema, generate_ddl  |
| `libs/canon/src/canon/db/types.py`      | FK[Model], Vector[dim] annotations    |
| `libs/canon/src/canon/db/validation.py` | validate_identifier()                 |

## Key Functions

| Function                | Location        | Purpose                             |
| ----------------------- | --------------- | ----------------------------------- |
| `insert()`              | `crud.py`       | Parameterized INSERT with RETURNING |
| `upsert()`              | `crud.py`       | INSERT ON CONFLICT DO UPDATE        |
| `update()`              | `crud.py`       | UPDATE with WHERE clause            |
| `select()`              | `crud.py`       | SELECT with filters, ORDER, LIMIT   |
| `get_column_type()`     | `ddl.py`        | Python type to PostgreSQL type      |
| `generate_ddl()`        | `ddl.py`        | Generate CREATE TABLE from Entity   |
| `validate_identifier()` | `validation.py` | SQL injection prevention            |

## Type Mapping

```python
TYPE_MAP = {
    str: "TEXT",
    int: "INTEGER",
    float: "DOUBLE PRECISION",
    bool: "BOOLEAN",
    UUID: "UUID",
    datetime: "TIMESTAMP WITH TIME ZONE",
    dict: "JSONB",
    list: "JSONB",
}
# + Enum -> TEXT, BaseModel -> JSONB, FK[Model] -> UUID, Vector[dim] -> VECTOR(dim)
```

## Downstream Dependencies

All vocabulary packages depend on this infrastructure:

| Package  | Usage                                           |
| -------- | ----------------------------------------------- |
| evidence | CRUD for Evidence, ChainEntry, CEP persistence  |
| consent  | CRUD for ConsentToken lifecycle                 |
| All 50+  | Entity base class, type mapping, DDL generation |

## Design Documents

- **ADR**: ADR-004-entity-db-correspondence.md
- **TDS**: TDS-004-entity-db-correspondence.md
