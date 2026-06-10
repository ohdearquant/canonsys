"""Canon entity system built on kron.Node.

Provides:
    ContentModel: Base for domain content with sensitive field handling
    Entity: Persistable node with Canon-specific config (hashing, versioning, soft-delete)
    register_entity: Decorator to bind Entity to a database table
    get_entity_registry: Get all registered Entity classes by table name
    get_entity_by_table: Look up Entity class by table name
    reset_entity_registry: Clear registry (testing only)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, Field

from kron.core import Node, NodeConfig, _register_persistable
from kron.types import HashableModel
from kron.utils import now_utc

# ---------------------------------------------------------------------------
# Entity registry: table_name -> Entity class
# ---------------------------------------------------------------------------

_entity_registry: dict[str, type[Entity]] = {}


def get_entity_registry() -> dict[str, type[Entity]]:
    """Get the registry of all Entity classes (keyed by table name)."""
    return _entity_registry.copy()


def get_entity_by_table(table_name: str) -> type[Entity] | None:
    """Get Entity class by table name."""
    return _entity_registry.get(table_name)


def reset_entity_registry() -> None:
    """Reset the entity registry. For testing only."""
    _entity_registry.clear()


def _register_entity(table_name: str, cls: type[Entity]) -> None:
    """Register an Entity class with collision detection."""
    if table_name in _entity_registry:
        existing = _entity_registry[table_name]
        if existing is not cls:
            raise ValueError(
                f"Table '{table_name}' already registered by "
                f"{existing.__module__}.{existing.__name__}, "
                f"cannot register {cls.__module__}.{cls.__name__}"
            )
        return  # Same class re-registering is OK (idempotent)
    _entity_registry[table_name] = cls


def get_canon_config_v1() -> dict[str, bool]:
    """Return default Canon v1 NodeConfig options.

    Enables: content flattening, content/integrity hashing, soft delete,
    versioning, and update/delete tracking.
    """
    return {
        "flatten_content": True,
        "content_hashing": True,
        "integrity_hashing": True,
        "soft_delete": True,
        "track_deleted_by": True,
        "track_is_active": True,
        "versioning": True,
        "track_updated_at": True,
        "track_updated_by": True,
    }


CANON_CONFIG = NodeConfig(**get_canon_config_v1())
"""Default NodeConfig for Canon entities."""


class ContentModel(HashableModel):
    """Base for domain content models.

    Pure data container. Subclass to define domain fields.
    Supports sensitive field exclusion and tenant-scoped uniqueness.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    _sensitive_fields: ClassVar[set[str]] = set()
    """Fields excluded from to_dict() output (e.g., password_hash)."""

    _unique_within_tenant: ClassVar[set[str]] = set()
    """Fields that must be unique within a tenant scope."""

    def to_dict(self) -> dict:
        """Return dict representation excluding sensitive fields."""
        return self.model_dump(exclude=self._sensitive_fields)


class Entity(Node):
    """Base class for Canon persistable entities.

    Inherits from kron.Node with CANON_CONFIG defaults:
    - Content/integrity hashing for tamper detection
    - Soft delete with deletion tracking
    - Optimistic locking via version field

    All Canon entities have these audit fields (not configurable):
    - updated_at/updated_by: Update tracking
    - is_deleted/deleted_at/deleted_by: Soft delete
    - is_active: Activation state
    - version: Optimistic locking
    - content_hash/integrity_hash: Tamper detection
    """

    node_config: ClassVar[NodeConfig] = CANON_CONFIG
    content: ContentModel

    # Audit fields - always present on Canon entities
    updated_at: datetime = Field(default_factory=now_utc)
    updated_by: UUID | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
    is_active: bool = True
    version: int = Field(default=1, ge=0)
    content_hash: str | None = None
    integrity_hash: str | None = None


def register_entity(
    table_name: str,
    *,
    schema: str = "public",
    immutable: bool = False,
) -> Callable[[type[Entity]], type[Entity]]:
    """Register an Entity subclass with a database table.

    Args:
        table_name: Database table name
        schema: Database schema (default: public)
        immutable: If True, content is frozen after creation (audit-grade)

    Returns:
        Decorator that configures and registers the Entity class
    """

    def decorator(cls: type[Entity]) -> type[Entity]:
        if not issubclass(cls, Entity):
            raise TypeError(f"{cls.__name__} must be a subclass of Entity")
        cls.node_config = CANON_CONFIG.with_updates(
            table_name=table_name,
            schema=schema,
            content_frozen=immutable,
        )
        _register_entity(table_name, cls)
        _register_persistable(table_name, cls)
        return cls

    return decorator
