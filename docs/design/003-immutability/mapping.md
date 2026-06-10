# 003 - Immutability - Code Mapping

## Primary Code Paths

| File                                                        | Lines    | Description                                        |
| ----------------------------------------------------------- | -------- | -------------------------------------------------- |
| `/libs/canon/src/canon/entities/entity.py`           | L59-99   | `@register_entity` decorator with `immutable` flag |
| `/libs/canon/src/canon/entities/entity.py`           | L246-269 | Entity class with `_immutable` ClassVar            |
| `/libs/canon/src/canon/entities/entity.py`           | L271-320 | `create_entity()` factory with immutable support   |
| `/libs/canon/src/canon/entities/entity.py`           | L207-217 | `_rehash()` computing content_hash and integrity   |
| `/libs/canon/src/canon/db/migration/migration.py` | L142-250 | Immutability trigger generation                    |
| `/libs/canon/src/canon/exceptions.py`             | -        | ImmutableViolationError                            |

## Key Classes/Functions

| Name                                  | Location          | Purpose                                          |
| ------------------------------------- | ----------------- | ------------------------------------------------ |
| `Entity`                              | `content.py:L246` | Base class extending kron Node                   |
| `_immutable`                          | `content.py:L268` | ClassVar[bool] flag for append-only entities     |
| `@register_entity`                    | `content.py:L59`  | Decorator with `immutable=True` parameter        |
| `create_entity()`                     | `content.py:L271` | Factory function with `immutable` parameter      |
| `ContentModel`                        | `content.py:L177` | Base for domain content with lifecycle methods   |
| `ContentMeta`                         | `content.py:L108` | Audit metadata with content_hash, integrity_hash |
| `_rehash()`                           | `content.py:L207` | Recomputes content_hash and integrity_hash       |
| `generate_immutable_update_trigger()` | `migration.py`    | Generates UPDATE block trigger (DB layer)        |
| `generate_immutable_delete_trigger()` | `migration.py`    | Generates DELETE block trigger (DB layer)        |

## Architectural Patterns

### 1. Flag-Based Immutability

```python
# Using decorator
@register_entity("evidence", immutable=True)
class Evidence(Entity):
    content: EvidenceContent

# Using factory function
Evidence = create_entity("Evidence", EvidenceContent, immutable=True)
```

- Immutability is a boolean flag on Entity: `_immutable: ClassVar[bool]`
- Set via `@register_entity(..., immutable=True)` or `create_entity(..., immutable=True)`
- DB triggers enforce append-only semantics when `_immutable=True`

### 2. Content + Integrity Hashing

```python
class ContentModel(BaseModel):
    content_meta: ContentMeta = Field(default_factory=ContentMeta)

    def _rehash(self) -> None:
        # Content hash: domain fields only
        content_dict = self.model_dump(mode="json")
        self._meta.content_hash = compute_hash(content_dict)

        # Integrity hash: content + meta (for full state verification)
        full_dict = content_dict.copy()
        full_dict.update(self._meta.to_hash_dict())
        self._meta.integrity_hash = compute_hash(full_dict)
```

- `content_hash`: Domain fields only (for content verification)
- `integrity_hash`: Content + meta fields (for full state verification)
- Hashes updated on every touch/mutation via `@with_rehash` decorator

### 3. Entity = Node + ContentModel

```python
class Entity(Node):
    """Base entity combining Node identity with ContentModel."""
    content: ContentModel
    _table_name: ClassVar[str] = ""
    _schema: ClassVar[str] = "public"
    _immutable: ClassVar[bool] = False
```

- Extends kron's Node (provides id, created_at, metadata)
- Contains a ContentModel with audit metadata and domain fields
- Configuration via class variables (\_table_name, \_schema, \_immutable)

### 4. Database-Level Trigger Enforcement

```sql
CREATE TRIGGER tr_evidence_update_immutable
    BEFORE UPDATE ON evidence
    FOR EACH ROW
    EXECUTE FUNCTION tr_evidence_update_immutable();
```

- Generated via `generate_immutable_update_trigger()`
- Compares OLD vs NEW row_to_json()
- Raises exception with ERRCODE 'integrity_constraint_violation'

### 5. Lifecycle Methods with @with_rehash

```python
@with_rehash
def soft_delete(self) -> None:
    """Mark as deleted (reversible)."""
    self._meta.deleted_at = ln.now_utc()
    self._meta.is_deleted = True

@with_rehash
def restore(self) -> None:
    """Restore from soft-deleted state."""
    self._meta.deleted_at = None
    self._meta.is_deleted = False
```

- Lifecycle methods on ContentModel: soft_delete, restore, activate, deactivate
- All decorated with `@with_rehash` to maintain hash integrity
- For immutable entities, these should be blocked at DB trigger level

### 6. Entity Registry Pattern

```python
def register_entity(
    table_name: str,
    *,
    schema: str = "public",
    immutable: bool = False,
) -> Callable[[type[E]], type[E]]:
    """Decorator to register an Entity class."""
    def decorator(cls: type[E]) -> type[E]:
        cls._table_name = table_name
        cls._schema = schema
        cls._immutable = immutable
        _register_entity(table_name, cls)
        return cls
    return decorator
```

- Global registry for Entity classes (keyed by table name)
- Used by migration discovery
- Collision detection prevents duplicate registration

## Dependencies

- **Depends on**:
  - kron Node class (provides Element/id/metadata)
  - 002-entity (Entity + ContentModel pattern)
- **Depended by**:
  - 006-evidence-chain-cep (Evidence uses `_immutable=True`)
  - DB migration triggers (checks `_immutable` flag)

## Key Decisions (for ADR candidates)

1. **Flag-based immutability**: Uses `_immutable: ClassVar[bool]` instead of separate
   ImmutableEntity class. Simpler inheritance, consistent Entity interface.

2. **Dual hash strategy**: `content_hash` for domain content, `integrity_hash` for full state.
   Enables flexible verification depending on use case.

3. **Decorator-based registration**: `@register_entity(..., immutable=True)` sets configuration and
   registers for migration discovery in one step.

4. **Trigger enforcement at DB layer**: Application-level lifecycle methods still exist, but
   immutable entities have DB triggers that block UPDATE/DELETE regardless.

5. **kron integration**: Entity extends Node (from kron), gaining id/created_at/metadata.
   ContentModel contains domain fields and audit metadata.

## Open Questions

1. **Trigger generation timing**: Triggers generated in `migrate_with_rls()` but what about existing
   tables during upgrade? Need idempotent trigger creation.

2. **Lifecycle method blocking**: ContentModel has soft_delete/restore/activate/deactivate. For
   immutable entities, should these raise or be blocked at trigger level?

3. **Supersession pattern**: With flag-based immutability, how are supersession links handled? No
   `_allowed_update_fields` exists - supersession creates new records only.
