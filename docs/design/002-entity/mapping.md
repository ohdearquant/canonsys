# 002 - Entity Base Class - Code Mapping

## Primary Code Paths

| File                                              | Lines    | Description                                        |
| ------------------------------------------------- | -------- | -------------------------------------------------- |
| `/libs/canon/src/canon/entities/entity.py` | L108-156 | ContentMeta - audit metadata embedded in entities  |
| `/libs/canon/src/canon/entities/entity.py` | L177-244 | ContentModel - base class for domain content       |
| `/libs/canon/src/canon/entities/entity.py` | L246-268 | Entity base class (extends kron Node)              |
| `/libs/canon/src/canon/entities/entity.py` | L27-56   | Entity registry functions                          |
| `/libs/canon/src/canon/entities/entity.py` | L59-99   | `register_entity()` - decorator-based registration |
| `/libs/canon/src/canon/entities/entity.py` | L271-320 | `create_entity()` - factory function               |
| `/libs/canon/src/canon/db/types.py`     | L78-92   | FK type helper definition                          |
| `/libs/canon/src/canon/db/types.py`     | L31-75   | FKMeta class for FK metadata                       |

## Key Classes/Functions

| Name                      | Location               | Purpose                                    |
| ------------------------- | ---------------------- | ------------------------------------------ |
| `Entity`                  | `core/content.py:L246` | Base class for all database entities       |
| `ContentModel`            | `core/content.py:L177` | Base class for domain content models       |
| `ContentMeta`             | `core/content.py:L108` | Audit metadata: timestamps, version, hash  |
| `register_entity()`       | `core/content.py:L59`  | Decorator to register Entity classes       |
| `create_entity()`         | `core/content.py:L271` | Factory function for Entity classes        |
| `get_entity_registry()`   | `core/content.py:L30`  | Get registry dict of all Entity subclasses |
| `reset_entity_registry()` | `core/content.py:L40`  | Reset registry (testing only)              |
| `FK`                      | `db/types.py:L78`      | Type helper for foreign keys               |
| `FKMeta`                  | `db/types.py:L31`      | Metadata marker carrying FK info           |
| `Vector`                  | `db/types.py:L153`     | Type helper for pgvector embeddings        |
| `fk_meta()`               | `db/types.py:L95`      | Extract FKMeta from Pydantic FieldInfo     |

## Architectural Patterns

### 1. Decorator-Based Registration

```python
@register_entity("tenants")
class Tenant(Entity):
    content: TenantContent
```

- Entity subclasses register via `@register_entity` decorator
- Decorator sets `_table_name`, `_schema`, `_immutable` class vars
- Collision detection raises `ValueError` if same table registered twice

### 2. Entity = Node + ContentModel

```python
class Entity(Node):
    content: ContentModel
```

- Entity extends kron Node (provides id, created_at, metadata)
- Domain fields live in ContentModel subclass
- Clean separation: identity (Node) vs domain (ContentModel)

### 3. ContentMeta as Flat Columns

```python
class ContentMeta(BaseModel):
    updated_at: datetime
    updated_by: str | None
    deleted_at: datetime | None
    is_deleted: bool
    is_active: bool
    version: int
    content_hash: str | None
    integrity_hash: str | None
```

- Audit metadata stored as flat columns
- `content_hash`: hash of domain fields only
- `integrity_hash`: hash of domain + meta fields

### 3. FK[Model] Type-Safe Foreign Keys

```python
tenant_id: FK[Tenant]  # Annotated[UUID, FKMeta(Tenant)]
```

- Compile-time: Type annotation for IDE/mypy
- Runtime: FKMeta carries model reference for DDL generation
- Forward refs supported: `FK["User"]`

### 4. Factory Pattern for Entity Creation

```python
Evidence = create_entity("Evidence", EvidenceContent, immutable=True)
```

- `create_entity()` dynamically creates Entity subclass
- `register_entity()` decorator for class-based definition
- Both register in global `_entity_registry`

### 5. Sensitive Field Protection

```python
_sensitive_fields: ClassVar[set[str]] = {"password_hash", "mfa_secret"}
```

- Defined in ContentModel subclass (e.g., UserContent)
- Prevents secrets from appearing in API responses

### 6. Integrity Hashing

```python
def _rehash(self):
    content_dict = self.model_dump(mode="json")
    self._meta.content_hash = compute_hash(content_dict)
    # Also computes integrity_hash including meta fields
```

- SHA-256 over domain fields for content_hash
- SHA-256 over domain + meta for integrity_hash
- Enables tamper detection and versioning

## Dependencies

- **Depends on**:
  - 001-tenant-isolation (uses FK[Tenant] via TenantAwareContent)
  - kron (Node base class provides id, created_at, metadata)
- **Depended by**:
  - 003-immutability (immutable=True flag on entities)
  - 004-entity-db-correspondence (Entity provides content structure)
  - 006-evidence-chain-cep (Evidence/Chain/CEP extend Entity hierarchy)

## Key Decisions (for ADR candidates)

1. **Decorator-based registration over **init_subclass****: Chose explicit `@register_entity`
   decorator for clarity. Class config visible at definition site.

2. **Entity extends Node**: Leverages kron Node for identity (id, created_at). Cleaner than
   reimplementing UUID generation and timestamps.

3. **ContentModel as separate class**: Domain fields in ContentModel, not directly on Entity.
   Enables `content: ConsentTokenContent` typed field pattern.

4. **ContentMeta as flat columns**: Not JSONB. Audit fields (updated_at, version) are flat columns
   for direct SQL querying.

5. **Dual hash strategy**: `content_hash` for domain-only, `integrity_hash` for full state. Enables
   both content deduplication and full tamper detection.

6. **create_entity() factory**: Dynamic Entity creation for programmatic use. Decorator for
   class-based definition.

## Open Questions

1. **Registry cleanup for tests**: `reset_entity_registry()` exists - called in test fixtures via
   `@pytest.fixture(autouse=True)`.

2. **ContentMeta extra fields**: Now `extra="forbid"` - no arbitrary extension. Add fields
   explicitly to ContentMeta class.

3. **Vector indexing strategy**: VectorMeta captures dimension. Index strategy defined in DDL
   generation layer (db/ddl.py).

4. **FKMeta on_delete/on_update defaults**: CASCADE default. Override per-FK with
   `FK[Model, on_delete="SET NULL"]` syntax if needed.
