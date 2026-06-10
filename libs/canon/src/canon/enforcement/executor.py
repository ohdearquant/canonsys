"""Canon phrase executor - entity-aware CRUD handler factory.

canon_phrase() wraps kron's Phrase with entity-aware handlers:
- READ: raw select_one (queries don't need entity lifecycle)
- INSERT: create Entity, insert_entity (rehash, content_hash)
- UPDATE: fetch Entity, modify, update_entity (touch, version, rehash)
- SOFT_DELETE: fetch Entity, entity.soft_delete(), update_entity

For custom handlers (decorator mode), canon_phrase() passes through
to kron's Phrase directly — custom handlers are already entity-aware.

Usage:
    from canon.enforcement.executor import canon_phrase, canon_query_fn
    from kron.specs import CrudPattern, Operable

    # Declarative (entity-aware CRUD)
    verify = canon_phrase(
        operable,
        inputs={"subject_id", "scope"},
        outputs={"has_consent"},
        crud=CrudPattern(table="consent_tokens", operation="read",
                         lookup={"subject_id", "scope"}),
        result_parser=my_parser,
        name="verify_consent_token",
    )

    # Custom handler (decorator mode, same as kron.phrase)
    @canon_phrase(operable, inputs={"scope"}, outputs={"result"})
    async def my_phrase(options, ctx):
        ...
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from kron.core.node import PERSISTABLE_NODE_REGISTRY
from kron.specs import CrudOperation, CrudPattern, Phrase
from kron.specs.operable import Operable

from ..db import TenantScope, select_one as raw_select_one
from ..db.entity_crud import update_entity

__all__ = ("canon_phrase", "canon_query_fn")


async def canon_query_fn(
    table: str,
    operation: str,
    where: dict[str, Any] | None,
    data: dict[str, Any] | None,
    ctx: Any,
) -> dict[str, Any] | None:
    """Raw query function for kron CrudPattern (dict-level operations).

    Implements the QueryFn protocol from canon.enforcement.context.
    Used by kron's default _make_crud_handler for dict-level CRUD.
    Prefer canon_phrase() for entity-aware operations.
    """
    from ..db import insert, update

    conn = ctx.conn

    if operation == "select_one":
        return await raw_select_one(
            table,
            where=where,
            conn=conn,
            tenant_scope=TenantScope.REQUIRED,
        )

    elif operation == "insert":
        return await insert(
            table,
            data=data,
            conn=conn,
            returning="*",
        )

    elif operation == "update":
        return await update(
            table,
            where=where,
            data=data,
            conn=conn,
            returning="*",
        )

    else:
        raise ValueError(f"Unknown operation: {operation}")


def _get_entity_cls(table: str) -> type:
    """Look up Entity class from table name via PERSISTABLE_NODE_REGISTRY."""
    cls = PERSISTABLE_NODE_REGISTRY.get(table)
    if cls is None:
        raise ValueError(
            f"No Entity registered for table '{table}'. "
            f"Ensure the Entity class is imported before canon_phrase() is called."
        )
    return cls


def _make_entity_handler(
    crud: CrudPattern,
    inputs: set[str],
    outputs: set[str],
    result_parser: Callable[[dict | None], dict] | None,
) -> Callable[..., Awaitable]:
    """Generate entity-aware CRUD handler from CrudPattern config.

    READ: raw select_one (no entity lifecycle needed for queries).
    UPDATE: fetch entity → modify → update_entity (touch/rehash/version).
    SOFT_DELETE: fetch entity → entity.soft_delete() → update_entity.
    INSERT: not supported via CrudPattern (use custom handler).
    """

    async def _handler(options: Any, ctx: Any) -> dict:
        row = None

        if crud.operation == CrudOperation.READ:
            # READ: raw select is fine — queries don't mutate
            where = {f: getattr(options, f) for f in crud.lookup}
            where.update(crud.filters)
            if ctx.tenant_id is not None:
                where["tenant_id"] = ctx.tenant_id
            row = await raw_select_one(
                crud.table,
                where=where,
                conn=ctx.conn,
                tenant_scope=TenantScope.REQUIRED,
            )

        elif crud.operation == CrudOperation.UPDATE:
            # UPDATE: fetch entity → modify → update_entity
            entity_cls = _get_entity_cls(crud.table)
            where = {f: getattr(options, f) for f in crud.lookup}
            where.update(crud.filters)
            if ctx.tenant_id is not None:
                where["tenant_id"] = ctx.tenant_id

            raw_row = await raw_select_one(
                crud.table,
                where=where,
                conn=ctx.conn,
                tenant_scope=TenantScope.REQUIRED,
            )
            if raw_row is not None:
                entity = entity_cls.from_dict(raw_row, from_row=True)
                # Apply set_fields to content
                for key, value in crud.set_fields.items():
                    if isinstance(value, str) and value.startswith("ctx."):
                        resolved = getattr(ctx, value[4:])
                    elif isinstance(value, str) and hasattr(options, value):
                        resolved = getattr(options, value)
                    else:
                        resolved = value
                    # Set on content if it has the field, else on entity
                    if hasattr(entity.content, key):
                        setattr(entity.content, key, resolved)
                    else:
                        setattr(entity, key, resolved)
                updated = await update_entity(entity, by=ctx.actor_id, conn=ctx.conn)
                row = updated.to_dict(mode="db")
            else:
                row = None

        elif crud.operation == CrudOperation.SOFT_DELETE:
            # SOFT_DELETE: fetch entity → entity.soft_delete() → persist
            entity_cls = _get_entity_cls(crud.table)
            where = {f: getattr(options, f) for f in crud.lookup}
            where.update(crud.filters)
            if ctx.tenant_id is not None:
                where["tenant_id"] = ctx.tenant_id

            raw_row = await raw_select_one(
                crud.table,
                where=where,
                conn=ctx.conn,
                tenant_scope=TenantScope.REQUIRED,
            )
            if raw_row is not None:
                entity = entity_cls.from_dict(raw_row, from_row=True)
                entity.soft_delete(by=ctx.actor_id)
                # update_entity calls touch() internally but soft_delete
                # already called touch(), so pass by=None to avoid double-touch
                data = entity.to_dict(mode="db")
                entity_id = data.pop("id")
                data.pop("created_at")
                from ..db import update as raw_update

                await raw_update(
                    crud.table,
                    data,
                    where={"id": entity_id},
                    conn=ctx.conn,
                    tenant_scope=TenantScope.REQUIRED,
                )
                row = entity.to_dict(mode="db")
            else:
                row = None

        elif crud.operation == CrudOperation.INSERT:
            raise NotImplementedError(
                "INSERT via CrudPattern is not supported in canon_phrase. "
                "Use a custom handler with insert_entity() instead."
            )

        # Build result with auto-mapping
        result = {}
        for field in outputs:
            # Priority 1: ctx attribute
            if getattr(ctx, field, None) is not None:
                result[field] = getattr(ctx, field)
            # Priority 2: pass-through from options
            elif field in inputs and hasattr(options, field):
                result[field] = getattr(options, field)
            # Priority 3: direct from row
            elif row and field in row:
                result[field] = row[field]

        # Priority 4: computed fields from result_parser
        if result_parser is not None:
            computed = result_parser(row)
            if computed:
                result.update(computed)

        return result

    return _handler


def canon_phrase(
    operable: Operable,
    *,
    inputs: set[str],
    outputs: set[str],
    name: str | None = None,
    crud: CrudPattern | None = None,
    result_parser: Callable[[dict | None], dict] | None = None,
) -> Phrase | Callable[[Callable[..., Awaitable]], Phrase]:
    """Create a Phrase with entity-aware CRUD handlers.

    Two usage modes:

    1. Declarative mode (CrudPattern → entity-aware handler):
        verify = canon_phrase(
            operable,
            inputs={...},
            outputs={...},
            crud=CrudPattern(table="consent_tokens", operation="read", ...),
            result_parser=my_parser,
            name="verify_consent_token",
        )

    2. Decorator mode (custom handler, pass-through):
        @canon_phrase(operable, inputs={...}, outputs={...})
        async def my_phrase(options, ctx):
            ...

    Args:
        operable: Operable defining the field specs for inputs/outputs.
        inputs: Set of field names that form the options type.
        outputs: Set of field names that form the result type.
        name: Phrase name. Required for declarative mode.
        crud: CrudPattern config. If provided, returns Phrase with
            entity-aware handler.
        result_parser: Function (row) -> dict for computed output fields.
            Only used with crud pattern.

    Returns:
        Phrase instance (declarative mode) or decorator (custom handler mode).
    """
    # Declarative mode: crud provided, generate entity-aware handler
    if crud is not None:
        if name is None:
            raise ValueError("name is required when using crud pattern")
        handler = _make_entity_handler(crud, set(inputs), set(outputs), result_parser)
        return Phrase(
            name=name,
            operable=operable,
            inputs=inputs,
            outputs=outputs,
            handler=handler,
        )

    # Decorator mode: return decorator function
    def decorator(func: Callable[..., Awaitable]) -> Phrase:
        phrase_name = name or func.__name__
        return Phrase(
            name=phrase_name,
            operable=operable,
            inputs=inputs,
            outputs=outputs,
            handler=func,
        )

    return decorator
