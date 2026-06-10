"""Schema specification for state-based migration.

Extends kron's SQL DDL specs with Entity-specific conversion methods.
Most spec dataclasses are re-exported from kron.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kron.specs.adapters.sql_ddl import (
    CheckConstraintSpec,
    ColumnSpec,
    ForeignKeySpec,
    IndexMethod,
    IndexSpec,
    OnAction,
    SchemaSpec as KronSchemaSpec,
    TableSpec as KronTableSpec,
    TriggerSpec,
    UniqueConstraintSpec,
    python_type_to_sql,
)

if TYPE_CHECKING:
    from canon.entities.entity import Entity

__all__ = (
    # Re-exported from canon.kron
    "CheckConstraintSpec",
    "ColumnSpec",
    "ForeignKeySpec",
    "IndexMethod",
    "IndexSpec",
    "OnAction",
    "TriggerSpec",
    "UniqueConstraintSpec",
    "python_type_to_sql",
    # Extended for Entity
    "TableSpec",
    "SchemaSpec",
)


class TableSpec(KronTableSpec):
    """TableSpec with Entity-specific factory method."""

    @classmethod
    def from_entity(cls, entity_cls: type[Entity]) -> TableSpec:
        """Create TableSpec from an Entity class.

        Extracts schema from Entity class definition:
        - Column types from model_fields
        - FK constraints from FK[Model] annotations
        - Indexes from _indexes class variable
        - Triggers for immutable entities
        """
        columns: list[ColumnSpec] = []
        foreign_keys: list[ForeignKeySpec] = []
        indexes: list[IndexSpec] = []

        pk_name = entity_cls._primary_key

        for field_name, field_info in entity_cls.model_fields.items():
            annotation = field_info.annotation

            # Get SQL type, nullability, and FK/Vector metadata
            sql_type, type_nullable, fk, _ = python_type_to_sql(annotation)

            if fk is not None:
                fk_spec = ForeignKeySpec(
                    name=f"fk_{entity_cls._table_name}_{field_name}",
                    columns=(field_name,),
                    ref_table=fk.table_name,
                    ref_columns=(fk.column,),
                    on_delete=OnAction(fk.on_delete),
                    on_update=OnAction(fk.on_update),
                )
                foreign_keys.append(fk_spec)

            # Determine nullability from field
            nullable = not field_info.is_required() if type_nullable is None else type_nullable

            # Get DB default if specified
            db_default = None
            if hasattr(field_info, "json_schema_extra"):
                extra = field_info.json_schema_extra
                if isinstance(extra, dict) and "db" in extra:
                    db_default = extra["db"].get("default")

            is_pk = field_name == pk_name

            col_spec = ColumnSpec(
                name=field_name,
                type=sql_type,
                nullable=nullable and not is_pk,
                default=db_default,
                is_primary_key=is_pk,
            )
            columns.append(col_spec)

        # Extract indexes from _indexes class variable
        entity_indexes = getattr(entity_cls, "_indexes", None) or []
        for idx_def in entity_indexes:
            idx_columns = tuple(idx_def.get("columns", []))
            idx_name = idx_def.get(
                "name",
                f"idx_{entity_cls._table_name}_{'_'.join(idx_columns)}",
            )
            idx_spec = IndexSpec(
                name=idx_name,
                columns=idx_columns,
                unique=idx_def.get("unique", False),
                method=IndexMethod(idx_def.get("method", "btree")),
                where=idx_def.get("where"),
            )
            indexes.append(idx_spec)

        # Add triggers for immutable entities
        triggers: list[TriggerSpec] = []
        if _is_immutable_entity(entity_cls):
            allowed = getattr(entity_cls, "_allowed_update_fields", set())
            if not allowed:
                triggers.append(
                    TriggerSpec(
                        name=f"trg_{entity_cls._table_name}_immutable",
                        timing="BEFORE",
                        events=("UPDATE", "DELETE"),
                        function="public.block_immutable",
                    )
                )

        return cls(
            name=entity_cls._table_name,
            schema=entity_cls._schema,
            columns=tuple(columns),
            primary_key=(pk_name,),
            foreign_keys=tuple(foreign_keys),
            indexes=tuple(indexes),
            triggers=tuple(triggers),
        )


def _is_immutable_entity(entity_cls: type[Entity]) -> bool:
    """Check if entity class is immutable via NodeConfig."""
    config = entity_cls.get_config()
    return getattr(config, "content_frozen", False)


class SchemaSpec(KronSchemaSpec):
    """SchemaSpec with Entity registry factory method."""

    @classmethod
    def from_registry(cls) -> SchemaSpec:
        """Create SchemaSpec from entity registry."""
        from kron.core import PERSISTABLE_NODE_REGISTRY
        from kron.utils import compute_hash

        registry = PERSISTABLE_NODE_REGISTRY
        tables = [TableSpec.from_entity(entity_cls) for entity_cls in registry.values()]

        # Compute version hash from table specs
        table_data = [
            {
                "name": t.name,
                "schema": t.schema,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "nullable": c.nullable,
                        "default": c.default,
                    }
                    for c in t.columns
                ],
                "foreign_keys": [
                    {"name": fk.name, "columns": fk.columns, "ref_table": fk.ref_table}
                    for fk in t.foreign_keys
                ],
                "indexes": [
                    {"name": idx.name, "columns": idx.columns, "unique": idx.unique}
                    for idx in t.indexes
                ],
                "triggers": [
                    {
                        "name": tr.name,
                        "timing": tr.timing,
                        "events": tr.events,
                        "function": tr.function,
                    }
                    for tr in t.triggers
                ],
                "check_constraints": [
                    {"name": cc.name, "expression": cc.expression} for cc in t.check_constraints
                ],
                "unique_constraints": [
                    {"name": uc.name, "columns": uc.columns} for uc in t.unique_constraints
                ],
            }
            for t in sorted(tables, key=lambda t: t.name)
        ]
        version = compute_hash(table_data)

        return cls(tables=tuple(tables), version=version)
