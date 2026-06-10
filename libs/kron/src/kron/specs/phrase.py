"""Phrase - typed operation template with auto-generated Options/Result types.

A Phrase wraps an async handler with:
- Typed inputs (auto-generates FrozenOptions dataclass)
- Typed outputs (auto-generates FrozenResult dataclass)
- Validation via Operable

Usage with decorator (custom handler):
    from kron.specs import Operable, phrase

    consent_operable = Operable([
        Spec("subject_id", UUID),
        Spec("scope", str),
        Spec("has_consent", bool),
        Spec("token_id", UUID | None),
    ])

    @phrase(consent_operable, inputs={"subject_id", "scope"}, outputs={"has_consent", "token_id"})
    async def verify_consent(options, ctx):
        # options is VerifyConsentOptions (frozen dataclass)
        # return dict with output fields
        return {"has_consent": True, "token_id": some_id}

    # Call it
    result = await verify_consent({"subject_id": id, "scope": "background"}, ctx)

Usage with CrudPattern (declarative):
    from kron.specs import Operable, phrase, CrudPattern

    def check_has_consent(row):
        return {"has_consent": row["status"] in {"active"} if row else False}

    verify_consent = phrase(
        consent_operable,
        inputs={"subject_id", "scope"},
        outputs={"has_consent", "token_id"},
        crud=CrudPattern(
            table="consent_tokens",
            operation="read",
            lookup={"subject_id", "scope"},
        ),
        result_parser=check_has_consent,
        name="verify_consent",
    )
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from kron.types import Unset, is_unset
from kron.utils.sql import validate_identifier

from .operable import Operable

__all__ = ("CrudOperation", "CrudPattern", "Phrase", "phrase")


class CrudOperation(str, Enum):
    """CRUD operation types for declarative phrases."""

    READ = "read"
    INSERT = "insert"
    UPDATE = "update"
    SOFT_DELETE = "soft_delete"


_EMPTY_MAP: MappingProxyType = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class CrudPattern:
    """Declarative CRUD pattern for auto-generating phrase handlers.

    Attributes:
        table: Validated database table name (alphanumeric + underscores).
        operation: CRUD operation type (read, insert, update, soft_delete).
        lookup: Fields from options used in WHERE clause (for read/update/delete).
        filters: Static key-value pairs added to WHERE clause. Use for
            hardcoded filters like {"status": "active"}.
        set_fields: Explicit field mappings for update. Values can be:
            - Field name (str): copy from options
            - "ctx.{attr}": read from context (e.g., "ctx.now", "ctx.user_id")
            - Literal value: use directly
        defaults: Static default values for insert.

    The auto-handler resolves output fields in order:
        1. ctx metadata attribute (e.g., tenant_id -- only if explicitly set)
        2. options pass-through (if field in inputs)
        3. row column (direct from query result)
        4. result_parser (for computed fields)
    """

    table: str
    operation: CrudOperation | str = CrudOperation.READ
    lookup: frozenset[str] = frozenset()
    filters: Mapping[str, Any] = None  # type: ignore[assignment]
    set_fields: Mapping[str, Any] = None  # type: ignore[assignment]
    defaults: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self):
        # Validate table name against SQL injection
        validate_identifier(self.table, "table")
        # Normalize operation to enum
        if isinstance(self.operation, str):
            object.__setattr__(self, "operation", CrudOperation(self.operation))
        # Normalize lookup to frozenset
        if not isinstance(self.lookup, frozenset):
            object.__setattr__(self, "lookup", frozenset(self.lookup))
        # Normalize None mappings to immutable empty maps; freeze mutable dicts
        object.__setattr__(
            self,
            "filters",
            (_EMPTY_MAP if self.filters is None else MappingProxyType(dict(self.filters))),
        )
        object.__setattr__(
            self,
            "set_fields",
            (_EMPTY_MAP if self.set_fields is None else MappingProxyType(dict(self.set_fields))),
        )
        object.__setattr__(
            self,
            "defaults",
            (_EMPTY_MAP if self.defaults is None else MappingProxyType(dict(self.defaults))),
        )


class Phrase:
    """A typed operation template with auto-generated Options/Result types.

    Phrases can be created two ways:
    1. With a custom handler (decorator pattern)
    2. With a CrudPattern (declarative pattern, auto-generates handler)
    """

    def __init__(
        self,
        name: str,
        operable: Operable,
        inputs: set[str],
        outputs: set[str],
        handler: Callable[..., Awaitable] | None = None,
        crud: CrudPattern | None = None,
        result_parser: Callable[[dict | None], dict] | None = None,
    ):
        """
        Args:
            name: Snake_case phrase name.
            operable: Operable defining field specs for inputs/outputs.
            inputs: Set of field names that form the options type.
            outputs: Set of field names that form the result type.
            handler: Async function (options, ctx) -> result dict. Required if no crud.
            crud: CrudPattern for declarative CRUD operations. If provided, handler
                is auto-generated.
            result_parser: Function (row) -> dict for computed output fields.
                Only used with crud pattern. Row may be None if not found.
        """
        if handler is None and crud is None:
            raise ValueError("Either handler or crud must be provided")

        self.name = name
        self.operable = Operable(operable.get_specs(), adapter="dataclass")
        self.inputs = tuple(inputs)
        self.outputs = tuple(outputs)
        self.crud = crud
        self.result_parser = result_parser
        self._options_type: Any = Unset
        self._result_type: Any = Unset

        # Use provided handler or generate from crud
        if handler is not None:
            self.handler = handler
        else:
            self.handler = self._make_crud_handler()

    def _make_crud_handler(self) -> Callable[..., Awaitable]:
        """Generate handler from CrudPattern."""
        crud = self.crud
        inputs = set(self.inputs)
        outputs = set(self.outputs)
        result_parser = self.result_parser

        async def _crud_handler(options: Any, ctx: Any) -> dict:
            # Get the query backend from context
            query_fn = getattr(ctx, "query_fn", None)
            if query_fn is None:
                raise RuntimeError(
                    "Context must provide query_fn for crud patterns. Ensure ctx.query_fn is set."
                )

            # Helper: check ctx metadata for a key
            _meta = getattr(ctx, "metadata", {})

            row = None

            if crud.operation == CrudOperation.READ:
                # Build WHERE from lookup fields + filters + tenant_id
                where = {field: getattr(options, field) for field in crud.lookup}
                where.update(crud.filters)
                if "tenant_id" in _meta:
                    where["tenant_id"] = _meta["tenant_id"]
                row = await query_fn(crud.table, "select_one", where, None, ctx)

            elif crud.operation == CrudOperation.INSERT:
                # Build data from input fields + defaults
                data = {}
                for field in inputs:
                    if hasattr(options, field):
                        data[field] = getattr(options, field)
                # Add defaults
                for key, value in crud.defaults.items():
                    if key not in data:
                        data[key] = value
                # Add tenant_id
                if "tenant_id" in _meta:
                    data["tenant_id"] = _meta["tenant_id"]
                row = await query_fn(crud.table, "insert", None, data, ctx)

            elif crud.operation == CrudOperation.UPDATE:
                # Build WHERE from lookup fields
                where = {field: getattr(options, field) for field in crud.lookup}
                if "tenant_id" in _meta:
                    where["tenant_id"] = _meta["tenant_id"]
                # Build SET data
                data = {}
                for key, value in crud.set_fields.items():
                    if isinstance(value, str) and value.startswith("ctx."):
                        attr_name = value[4:]
                        if attr_name in _meta:
                            data[key] = _meta[attr_name]
                        else:
                            data[key] = getattr(ctx, attr_name)
                    elif isinstance(value, str) and hasattr(options, value):
                        data[key] = getattr(options, value)
                    else:
                        data[key] = value
                row = await query_fn(crud.table, "update", where, data, ctx)

            elif crud.operation == CrudOperation.SOFT_DELETE:
                # Build WHERE from lookup fields
                where = {field: getattr(options, field) for field in crud.lookup}
                if "tenant_id" in _meta:
                    where["tenant_id"] = _meta["tenant_id"]
                # Soft delete sets is_deleted=True, deleted_at=now
                data = {"is_deleted": True}
                if ctx.now is not None:
                    data["deleted_at"] = ctx.now
                row = await query_fn(crud.table, "update", where, data, ctx)

            # Build result from auto-mapping + result_parser
            result = {}

            for field in outputs:
                # Priority 1: ctx metadata attribute (only if explicitly set)
                if field in _meta:
                    result[field] = _meta[field]
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

        return _crud_handler

    async def __call__(self, options: Any, ctx: Any) -> Any:
        # If options is already the correct type, use it directly
        # Otherwise validate/construct from dict
        if not isinstance(options, self.options_type):
            options = self.operable.validate_instance(self.options_type, options)
        result = await self.handler(options, ctx)
        return self.operable.validate_instance(self.result_type, result)

    @property
    def options_type(self) -> Any:
        if not is_unset(self._options_type):
            return self._options_type

        _opt_type_name = _to_pascal(self.name) + "Options"
        self._options_type = self.operable.compose_structure(
            _opt_type_name,
            include=set(self.inputs),
            frozen=True,
        )
        return self._options_type

    @property
    def result_type(self) -> Any:
        if not is_unset(self._result_type):
            return self._result_type

        _res_type_name = _to_pascal(self.name) + "Result"
        self._result_type = self.operable.compose_structure(
            _res_type_name,
            include=set(self.outputs),
            frozen=True,
        )
        return self._result_type


def _to_pascal(snake_name: str) -> str:
    """Convert snake_case name to PascalCase.

    Examples:
        require_monitoring_active -> RequireMonitoringActive
        verify_consent_token -> VerifyConsentToken
    """
    return "".join(word.capitalize() for word in snake_name.split("_"))


def phrase(
    operable: Operable,
    *,
    inputs: set[str],
    outputs: set[str],
    name: str | None = None,
    crud: CrudPattern | None = None,
    result_parser: Callable[[dict | None], dict] | None = None,
) -> Phrase | Callable[[Callable[..., Awaitable]], Phrase]:
    """Create a Phrase, either as decorator or directly with CrudPattern.

    Two usage modes:

    1. Decorator mode (custom handler):
        @phrase(operable, inputs={...}, outputs={...})
        async def my_phrase(options, ctx):
            return {...}

    2. Direct mode (declarative crud):
        my_phrase = phrase(
            operable,
            inputs={...},
            outputs={...},
            crud=CrudPattern(table="...", operation="read", lookup={...}),
            result_parser=lambda row: {...},
            name="my_phrase",
        )

    Args:
        operable: Operable defining the field specs for inputs/outputs.
        inputs: Set of field names that form the options type.
        outputs: Set of field names that form the result type.
        name: Phrase name. Required for direct mode, optional for decorator mode.
        crud: CrudPattern for declarative CRUD. If provided, returns Phrase directly.
        result_parser: Function (row) -> dict for computed fields. Only with crud.

    Returns:
        - If crud provided: Phrase instance directly
        - If no crud: Decorator that wraps async function into Phrase

    Examples:
        # Decorator mode
        @phrase(my_operable, inputs={"subject_id", "scope"}, outputs={"valid", "reason"})
        async def verify_consent(options, ctx):
            return {"valid": True, "reason": None}

        # Direct mode with CrudPattern
        verify_consent = phrase(
            my_operable,
            inputs={"subject_id", "scope"},
            outputs={"has_consent", "token_id"},
            crud=CrudPattern(
                table="consent_tokens",
                operation="read",
                lookup={"subject_id", "scope"},
            ),
            result_parser=lambda row: {"has_consent": row["status"] == "active" if row else False},
            name="verify_consent",
        )
    """
    # Direct mode: crud provided, return Phrase immediately
    if crud is not None:
        if name is None:
            raise ValueError("name is required when using crud pattern")
        return Phrase(
            name=name,
            operable=operable,
            inputs=inputs,
            outputs=outputs,
            crud=crud,
            result_parser=result_parser,
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
