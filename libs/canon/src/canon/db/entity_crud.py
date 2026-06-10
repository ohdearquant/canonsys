"""Entity-based CRUD operations.

High-level CRUD that operates on Entity objects directly.
Uses kron.Node.to_dict(mode="db") and from_dict(from_row=True) for serialization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from ..entities.entity import Entity
from .connection import TenantScope
from .crud import (
    delete as raw_delete,
    insert as raw_insert,
    select_one as raw_select_one,
    update as raw_update,
)

if TYPE_CHECKING:
    from uuid import UUID

    import asyncpg

__all__ = (
    "delete_entity",
    "get_entity",
    "insert_entity",
    "update_entity",
)

E = TypeVar("E", bound=Entity)

# DB tracking fields that are stored in the database but not in the Node model.
# These are written by the database layer but filtered before deserialization.
_DB_TRACKING_FIELDS = frozenset(
    {
        "updated_at",
        "updated_by",
        "deleted_at",
        "deleted_by",
        "is_deleted",
        "is_active",
        "version",
        "content_hash",
        "integrity_hash",
    }
)


def _filter_tracking_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Remove DB tracking fields that aren't part of the Node model."""
    return {k: v for k, v in row.items() if k not in _DB_TRACKING_FIELDS}


async def insert_entity(
    entity: E,
    *,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> E:
    """Insert an Entity into the database."""
    entity_cls = type(entity)

    if not isinstance(entity, Entity):
        raise TypeError(f"Expected Entity, got {type(entity).__name__}")

    config = entity_cls.get_config()
    if not config.is_persisted:
        raise ValueError(f"{entity_cls.__name__} has no table_name")

    entity.rehash()
    data = entity.to_dict(mode="db")

    row = await raw_insert(
        config.table_name,
        data,
        schema=config.schema,
        returning=True,
        dsn=dsn,
        conn=conn,
        tenant_scope=tenant_scope,
    )

    if row is None:
        raise RuntimeError(f"Insert returned no data for {entity_cls.__name__}")

    return entity_cls.from_dict(_filter_tracking_fields(row), from_row=True)


async def update_entity(
    entity: E,
    *,
    by: UUID | str | None = None,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> E:
    """Update an Entity in the database."""
    entity_cls = type(entity)

    if not isinstance(entity, Entity):
        raise TypeError(f"Expected Entity, got {type(entity).__name__}")

    config = entity_cls.get_config()
    if not config.is_persisted:
        raise ValueError(f"{entity_cls.__name__} has no table_name")

    if config.content_frozen:
        raise ValueError(f"{entity_cls.__name__} is immutable and cannot be updated")

    entity.touch(by)
    data = entity.to_dict(mode="db")

    entity_id = data.pop("id")
    data.pop("created_at")

    row = await raw_update(
        config.table_name,
        data,
        where={"id": entity_id},
        schema=config.schema,
        dsn=dsn,
        conn=conn,
        tenant_scope=tenant_scope,
    )

    if row is None:
        raise RuntimeError(f"Update returned no data for {entity_cls.__name__} id={entity_id}")

    return entity_cls.from_dict(_filter_tracking_fields(row), from_row=True)


async def get_entity(
    entity_cls: type[E],
    *,
    id: UUID,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
    include_deleted: bool = False,
) -> E | None:
    """Get an Entity by ID."""
    if not issubclass(entity_cls, Entity):
        raise TypeError(f"Expected Entity subclass, got {entity_cls.__name__}")

    config = entity_cls.get_config()
    if not config.is_persisted:
        raise ValueError(f"{entity_cls.__name__} has no table_name")

    where: dict[str, Any] = {"id": id}
    if not include_deleted:
        where["is_deleted"] = False

    row = await raw_select_one(
        config.table_name,
        where=where,
        schema=config.schema,
        dsn=dsn,
        conn=conn,
        tenant_scope=tenant_scope,
    )

    if row is None:
        return None

    return entity_cls.from_dict(_filter_tracking_fields(row), from_row=True)


async def delete_entity(
    entity: Entity,
    *,
    by: UUID | str | None = None,
    hard: bool = False,
    dsn: str | None = None,
    conn: asyncpg.Connection | None = None,
    tenant_scope: TenantScope = TenantScope.REQUIRED,
) -> bool:
    """Delete an Entity (soft by default, hard if specified)."""
    entity_cls = type(entity)

    if not isinstance(entity, Entity):
        raise TypeError(f"Expected Entity, got {type(entity).__name__}")

    config = entity_cls.get_config()
    if not config.is_persisted:
        raise ValueError(f"{entity_cls.__name__} has no table_name")

    if hard and config.content_frozen:
        raise ValueError(f"{entity_cls.__name__} is immutable and cannot be hard deleted")

    if hard:
        count = await raw_delete(
            config.table_name,
            where={"id": entity.id},
            schema=config.schema,
            dsn=dsn,
            conn=conn,
            tenant_scope=tenant_scope,
        )
        return count > 0

    # Soft delete
    entity.soft_delete(by)
    data = entity.to_dict(mode="db")
    entity_id = data.pop("id")
    data.pop("created_at")

    row = await raw_update(
        config.table_name,
        data,
        where={"id": entity_id},
        schema=config.schema,
        dsn=dsn,
        conn=conn,
        tenant_scope=tenant_scope,
    )

    return row is not None
