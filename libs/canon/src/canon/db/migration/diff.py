"""Schema diff engine for state-based migration.

Compares two SchemaSpec objects and produces a MigrationPlan with classified operations.

Risk Classification:
    SAFE: ADD COLUMN nullable, CREATE INDEX CONCURRENTLY
    CAREFUL: ADD CONSTRAINT NOT VALID + VALIDATE, ALTER COLUMN SET NOT NULL
    DANGEROUS: DROP COLUMN/TABLE, type narrowing, renames
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

__all__ = (
    "MigrationOp",
    "MigrationPlan",
    "OperationRisk",
    "OperationType",
    "diff_columns",
    "diff_schemas",
    "diff_tables",
)

from .schema import IndexSpec

if TYPE_CHECKING:
    from .schema import (
        CheckConstraintSpec,
        ColumnSpec,
        ForeignKeySpec,
        SchemaSpec,
        TableSpec,
        TriggerSpec,
        UniqueConstraintSpec,
    )


class OperationRisk(StrEnum):
    """Risk classification for migration operations (D4.5)."""

    SAFE = "safe"
    CAREFUL = "careful"
    DANGEROUS = "dangerous"


class OperationType(StrEnum):
    """Types of schema migration operations."""

    # Table operations
    CREATE_TABLE = "create_table"
    DROP_TABLE = "drop_table"

    # Column operations
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    ALTER_COLUMN_TYPE = "alter_column_type"
    ALTER_COLUMN_NULLABLE = "alter_column_nullable"
    ALTER_COLUMN_DEFAULT = "alter_column_default"

    # Constraint operations
    ADD_FOREIGN_KEY = "add_foreign_key"
    DROP_FOREIGN_KEY = "drop_foreign_key"
    ADD_CHECK_CONSTRAINT = "add_check_constraint"
    DROP_CHECK_CONSTRAINT = "drop_check_constraint"
    ADD_UNIQUE_CONSTRAINT = "add_unique_constraint"
    DROP_UNIQUE_CONSTRAINT = "drop_unique_constraint"

    # Index operations
    CREATE_INDEX = "create_index"
    DROP_INDEX = "drop_index"

    # Trigger operations
    CREATE_TRIGGER = "create_trigger"
    DROP_TRIGGER = "drop_trigger"
    REPLACE_TRIGGER = "replace_trigger"


@dataclass(frozen=True, slots=True)
class MigrationOp:
    """A single schema migration operation.

    Attributes:
        op_type: Type of operation.
        risk: Risk classification.
        table_name: Target table.
        object_name: Name of column/constraint/index/trigger.
        ddl: SQL DDL statement(s) to execute.
        phase: Execution phase (A for atomic, B for non-transactional).
        description: Human-readable description.
    """

    op_type: OperationType
    risk: OperationRisk
    table_name: str
    object_name: str | None = None
    ddl: str = ""
    phase: str = "A"  # A = atomic, B = non-transactional
    description: str = ""


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    """Complete migration plan from diff (D4.4).

    Attributes:
        operations: Tuple of migration operations.
        schema_hash_before: Hash of current schema.
        schema_hash_after: Hash of target schema.
        has_dangerous: Whether plan contains dangerous operations.
    """

    operations: tuple[MigrationOp, ...] = ()
    schema_hash_before: str | None = None
    schema_hash_after: str | None = None

    @property
    def has_dangerous(self) -> bool:
        """Check if plan contains dangerous operations."""
        return any(op.risk == OperationRisk.DANGEROUS for op in self.operations)

    @property
    def phase_a_ops(self) -> tuple[MigrationOp, ...]:
        """Get Phase A (atomic) operations."""
        return tuple(op for op in self.operations if op.phase == "A")

    @property
    def phase_b_ops(self) -> tuple[MigrationOp, ...]:
        """Get Phase B (non-transactional) operations."""
        return tuple(op for op in self.operations if op.phase == "B")

    def to_sql(self, phase: str | None = None) -> str:
        """Generate SQL for the migration plan.

        Args:
            phase: If specified, only include operations from this phase.

        Returns:
            SQL string with all DDL statements.
        """
        ops = self.operations
        if phase:
            ops = tuple(op for op in ops if op.phase == phase)

        statements = []
        for op in ops:
            if op.ddl:
                statements.append(f"-- {op.description}")
                statements.append(op.ddl)
                statements.append("")

        return "\n".join(statements)


def diff_columns(
    current: ColumnSpec | None,
    desired: ColumnSpec | None,
    table_name: str,
) -> list[MigrationOp]:
    """Diff two column specs and produce operations.

    Args:
        current: Current column spec (None if column doesn't exist).
        desired: Desired column spec (None if column should be dropped).
        table_name: Name of the table.

    Returns:
        List of migration operations.
    """
    ops = []

    if current is None and desired is not None:
        # ADD COLUMN
        risk = OperationRisk.SAFE if desired.nullable else OperationRisk.CAREFUL
        ddl = f'ALTER TABLE "{table_name}" ADD COLUMN {desired.to_ddl()};'

        ops.append(
            MigrationOp(
                op_type=OperationType.ADD_COLUMN,
                risk=risk,
                table_name=table_name,
                object_name=desired.name,
                ddl=ddl,
                description=f"Add column {desired.name} to {table_name}",
            )
        )

    elif current is not None and desired is None:
        # DROP COLUMN
        ddl = f'ALTER TABLE "{table_name}" DROP COLUMN "{current.name}";'

        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_COLUMN,
                risk=OperationRisk.DANGEROUS,
                table_name=table_name,
                object_name=current.name,
                ddl=ddl,
                description=f"Drop column {current.name} from {table_name}",
            )
        )

    elif current is not None and desired is not None:
        # Check for changes
        if current.type != desired.type:
            # Type change - dangerous if narrowing
            risk = _classify_type_change(current.type, desired.type)
            ddl = f'ALTER TABLE "{table_name}" ALTER COLUMN "{desired.name}" TYPE {desired.type};'

            ops.append(
                MigrationOp(
                    op_type=OperationType.ALTER_COLUMN_TYPE,
                    risk=risk,
                    table_name=table_name,
                    object_name=desired.name,
                    ddl=ddl,
                    description=f"Change type of {desired.name} from {current.type} to {desired.type}",
                )
            )

        if current.nullable != desired.nullable:
            if desired.nullable:
                # DROP NOT NULL - safe
                ddl = f'ALTER TABLE "{table_name}" ALTER COLUMN "{desired.name}" DROP NOT NULL;'
                risk = OperationRisk.SAFE
            else:
                # SET NOT NULL - careful (needs backfill verification)
                ddl = f'ALTER TABLE "{table_name}" ALTER COLUMN "{desired.name}" SET NOT NULL;'
                risk = OperationRisk.CAREFUL

            ops.append(
                MigrationOp(
                    op_type=OperationType.ALTER_COLUMN_NULLABLE,
                    risk=risk,
                    table_name=table_name,
                    object_name=desired.name,
                    ddl=ddl,
                    description=f"{'Allow' if desired.nullable else 'Disallow'} NULL for {desired.name}",
                )
            )

        if current.default != desired.default:
            if desired.default is None:
                ddl = f'ALTER TABLE "{table_name}" ALTER COLUMN "{desired.name}" DROP DEFAULT;'
            else:
                ddl = f'ALTER TABLE "{table_name}" ALTER COLUMN "{desired.name}" SET DEFAULT {desired.default};'

            ops.append(
                MigrationOp(
                    op_type=OperationType.ALTER_COLUMN_DEFAULT,
                    risk=OperationRisk.SAFE,
                    table_name=table_name,
                    object_name=desired.name,
                    ddl=ddl,
                    description=f"Change default of {desired.name}",
                )
            )

    return ops


def _classify_type_change(from_type: str, to_type: str) -> OperationRisk:
    """Classify the risk of a type change.

    Args:
        from_type: Current column type.
        to_type: Desired column type.

    Returns:
        Risk classification.
    """
    from_upper = from_type.upper()
    to_upper = to_type.upper()

    # Safe widenings
    safe_widenings = {
        ("INTEGER", "BIGINT"),
        ("SMALLINT", "INTEGER"),
        ("SMALLINT", "BIGINT"),
        ("REAL", "DOUBLE PRECISION"),
        ("VARCHAR", "TEXT"),
    }

    # Check exact matches
    if (from_upper, to_upper) in safe_widenings:
        return OperationRisk.SAFE

    # VARCHAR length changes
    if from_upper.startswith("VARCHAR") and to_upper.startswith("VARCHAR"):
        # Extract lengths
        try:
            from_len = int(from_upper.split("(")[1].rstrip(")"))
            to_len = int(to_upper.split("(")[1].rstrip(")"))
            if to_len >= from_len:
                return OperationRisk.SAFE
        except (IndexError, ValueError):
            pass

    # Default to dangerous for any type change
    return OperationRisk.DANGEROUS


def diff_foreign_keys(
    current: tuple[ForeignKeySpec, ...],
    desired: tuple[ForeignKeySpec, ...],
    table_name: str,
) -> list[MigrationOp]:
    """Diff foreign key constraints.

    Args:
        current: Current FK specs.
        desired: Desired FK specs.
        table_name: Name of the table.

    Returns:
        List of migration operations.
    """
    ops = []
    current_by_name = {fk.name: fk for fk in current}
    desired_by_name = {fk.name: fk for fk in desired}

    # FKs to drop
    for name in set(current_by_name) - set(desired_by_name):
        fk = current_by_name[name]
        ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_FOREIGN_KEY,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Drop FK {name}",
            )
        )

    # FKs to add (use NOT VALID pattern per D4.3)
    for name in set(desired_by_name) - set(current_by_name):
        fk = desired_by_name[name]
        # Phase A: Add NOT VALID
        add_ddl = fk.to_ddl(table_name) + " NOT VALID;"
        ops.append(
            MigrationOp(
                op_type=OperationType.ADD_FOREIGN_KEY,
                risk=OperationRisk.SAFE,
                table_name=table_name,
                object_name=name,
                ddl=add_ddl,
                phase="A",
                description=f"Add FK {name} (NOT VALID)",
            )
        )
        # Phase B: Validate
        validate_ddl = f'ALTER TABLE "{table_name}" VALIDATE CONSTRAINT "{name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.ADD_FOREIGN_KEY,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=validate_ddl,
                phase="B",
                description=f"Validate FK {name}",
            )
        )

    # Check for FK changes (columns, ref_table, actions)
    for name in set(current_by_name) & set(desired_by_name):
        curr = current_by_name[name]
        des = desired_by_name[name]
        if curr != des:
            # Drop and recreate
            drop_ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
            ops.append(
                MigrationOp(
                    op_type=OperationType.DROP_FOREIGN_KEY,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=drop_ddl,
                    description=f"Drop FK {name} (modified)",
                )
            )
            add_ddl = des.to_ddl(table_name)
            ops.append(
                MigrationOp(
                    op_type=OperationType.ADD_FOREIGN_KEY,
                    risk=OperationRisk.SAFE,
                    table_name=table_name,
                    object_name=name,
                    ddl=add_ddl,
                    description=f"Add FK {name} (modified)",
                )
            )

    return ops


def diff_indexes(
    current: tuple[IndexSpec, ...],
    desired: tuple[IndexSpec, ...],
    table_name: str,
) -> list[MigrationOp]:
    """Diff indexes.

    Args:
        current: Current index specs.
        desired: Desired index specs.
        table_name: Name of the table.

    Returns:
        List of migration operations.
    """
    ops = []
    current_by_name = {idx.name: idx for idx in current}
    desired_by_name = {idx.name: idx for idx in desired}

    # Indexes to drop
    for name in set(current_by_name) - set(desired_by_name):
        ddl = f'DROP INDEX "{name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_INDEX,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Drop index {name}",
            )
        )

    # Indexes to create (use CONCURRENTLY per D4.3)
    for name in set(desired_by_name) - set(current_by_name):
        idx = desired_by_name[name]
        # Create concurrently in Phase B
        idx_concurrent = IndexSpec(
            name=idx.name,
            columns=idx.columns,
            unique=idx.unique,
            method=idx.method,
            where=idx.where,
            concurrently=True,
            include=idx.include,
        )
        ddl = idx_concurrent.to_ddl(table_name) + ";"
        ops.append(
            MigrationOp(
                op_type=OperationType.CREATE_INDEX,
                risk=OperationRisk.SAFE,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                phase="B",  # Non-transactional
                description=f"Create index {name} CONCURRENTLY",
            )
        )

    # Check for index changes (columns, unique, method, where)
    for name in set(current_by_name) & set(desired_by_name):
        curr = current_by_name[name]
        des = desired_by_name[name]
        if curr != des:
            # Drop and recreate
            drop_ddl = f'DROP INDEX "{name}";'
            ops.append(
                MigrationOp(
                    op_type=OperationType.DROP_INDEX,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=drop_ddl,
                    description=f"Drop index {name} (modified)",
                )
            )
            idx_concurrent = IndexSpec(
                name=des.name,
                columns=des.columns,
                unique=des.unique,
                method=des.method,
                where=des.where,
                concurrently=True,
                include=des.include,
            )
            create_ddl = idx_concurrent.to_ddl(table_name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.CREATE_INDEX,
                    risk=OperationRisk.SAFE,
                    table_name=table_name,
                    object_name=name,
                    ddl=create_ddl,
                    phase="B",
                    description=f"Create index {name} CONCURRENTLY (modified)",
                )
            )

    return ops


def diff_triggers(
    current: tuple[TriggerSpec, ...],
    desired: tuple[TriggerSpec, ...],
    table_name: str,
    schema: str = "public",
) -> list[MigrationOp]:
    """Diff triggers.

    Args:
        current: Current trigger specs.
        desired: Desired trigger specs.
        table_name: Name of the table.
        schema: Schema name.

    Returns:
        List of migration operations.
    """
    ops = []
    current_by_name = {t.name: t for t in current}
    desired_by_name = {t.name: t for t in desired}

    # Triggers to drop
    for name in set(current_by_name) - set(desired_by_name):
        ddl = f'DROP TRIGGER "{name}" ON "{schema}"."{table_name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_TRIGGER,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Drop trigger {name}",
            )
        )

    # Triggers to create
    for name in set(desired_by_name) - set(current_by_name):
        trigger = desired_by_name[name]
        ddl = trigger.to_ddl(table_name) + ";"
        ops.append(
            MigrationOp(
                op_type=OperationType.CREATE_TRIGGER,
                risk=OperationRisk.SAFE,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Create trigger {name}",
            )
        )

    # Check for trigger changes - emit separate DROP and CREATE for atomicity
    # This ensures if CREATE fails, we don't leave the table without its trigger
    for name in set(current_by_name) & set(desired_by_name):
        curr = current_by_name[name]
        des = desired_by_name[name]
        if curr != des:
            # Drop old trigger first
            drop_ddl = f'DROP TRIGGER "{name}" ON "{schema}"."{table_name}";'
            ops.append(
                MigrationOp(
                    op_type=OperationType.DROP_TRIGGER,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=drop_ddl,
                    description=f"Drop trigger {name} (for replacement)",
                )
            )
            # Then create new trigger
            create_ddl = des.to_ddl(table_name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.CREATE_TRIGGER,
                    risk=OperationRisk.SAFE,
                    table_name=table_name,
                    object_name=name,
                    ddl=create_ddl,
                    description=f"Create trigger {name} (replacement)",
                )
            )

    return ops


def diff_check_constraints(
    current: tuple[CheckConstraintSpec, ...],
    desired: tuple[CheckConstraintSpec, ...],
    table_name: str,
) -> list[MigrationOp]:
    """Diff CHECK constraints.

    Args:
        current: Current CHECK constraints.
        desired: Desired CHECK constraints.
        table_name: Name of the table.

    Returns:
        List of migration operations for add/drop/modify.
    """
    ops = []
    current_by_name = {c.name: c for c in current}
    desired_by_name = {c.name: c for c in desired}

    # Constraints to drop
    for name in set(current_by_name) - set(desired_by_name):
        ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_CHECK_CONSTRAINT,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Drop CHECK constraint {name}",
            )
        )

    # Constraints to add
    for name in set(desired_by_name) - set(current_by_name):
        constraint = desired_by_name[name]
        ddl = constraint.to_ddl(table_name) + ";"
        ops.append(
            MigrationOp(
                op_type=OperationType.ADD_CHECK_CONSTRAINT,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Add CHECK constraint {name}",
            )
        )

    # Check for constraint modifications (same name, different expression)
    for name in set(current_by_name) & set(desired_by_name):
        curr = current_by_name[name]
        des = desired_by_name[name]
        if curr != des:
            # Drop old constraint first
            drop_ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
            ops.append(
                MigrationOp(
                    op_type=OperationType.DROP_CHECK_CONSTRAINT,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=drop_ddl,
                    description=f"Drop CHECK constraint {name} (for modification)",
                )
            )
            # Add new constraint
            add_ddl = des.to_ddl(table_name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.ADD_CHECK_CONSTRAINT,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=add_ddl,
                    description=f"Add CHECK constraint {name} (modified)",
                )
            )

    return ops


def diff_unique_constraints(
    current: tuple[UniqueConstraintSpec, ...],
    desired: tuple[UniqueConstraintSpec, ...],
    table_name: str,
) -> list[MigrationOp]:
    """Diff UNIQUE constraints.

    Args:
        current: Current UNIQUE constraints.
        desired: Desired UNIQUE constraints.
        table_name: Name of the table.

    Returns:
        List of migration operations for add/drop/modify.
    """
    ops = []
    current_by_name = {c.name: c for c in current}
    desired_by_name = {c.name: c for c in desired}

    # Constraints to drop
    for name in set(current_by_name) - set(desired_by_name):
        ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_UNIQUE_CONSTRAINT,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Drop UNIQUE constraint {name}",
            )
        )

    # Constraints to add
    for name in set(desired_by_name) - set(current_by_name):
        constraint = desired_by_name[name]
        ddl = constraint.to_ddl(table_name) + ";"
        ops.append(
            MigrationOp(
                op_type=OperationType.ADD_UNIQUE_CONSTRAINT,
                risk=OperationRisk.CAREFUL,
                table_name=table_name,
                object_name=name,
                ddl=ddl,
                description=f"Add UNIQUE constraint {name}",
            )
        )

    # Check for constraint modifications (same name, different columns)
    for name in set(current_by_name) & set(desired_by_name):
        curr = current_by_name[name]
        des = desired_by_name[name]
        if curr != des:
            # Drop old constraint first
            drop_ddl = f'ALTER TABLE "{table_name}" DROP CONSTRAINT "{name}";'
            ops.append(
                MigrationOp(
                    op_type=OperationType.DROP_UNIQUE_CONSTRAINT,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=drop_ddl,
                    description=f"Drop UNIQUE constraint {name} (for modification)",
                )
            )
            # Add new constraint
            add_ddl = des.to_ddl(table_name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.ADD_UNIQUE_CONSTRAINT,
                    risk=OperationRisk.CAREFUL,
                    table_name=table_name,
                    object_name=name,
                    ddl=add_ddl,
                    description=f"Add UNIQUE constraint {name} (modified)",
                )
            )

    return ops


def diff_tables(current: TableSpec | None, desired: TableSpec | None) -> list[MigrationOp]:
    """Diff two table specs and produce operations.

    Args:
        current: Current table spec (None if table doesn't exist).
        desired: Desired table spec (None if table should be dropped).

    Returns:
        List of migration operations.
    """
    ops = []

    if current is None and desired is not None:
        # CREATE TABLE
        ddl = desired.to_create_table_ddl()
        ops.append(
            MigrationOp(
                op_type=OperationType.CREATE_TABLE,
                risk=OperationRisk.SAFE,
                table_name=desired.name,
                ddl=ddl,
                description=f"Create table {desired.name}",
            )
        )

        # Add FKs, indexes, triggers for new table
        for fk in desired.foreign_keys:
            ddl = fk.to_ddl(desired.name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.ADD_FOREIGN_KEY,
                    risk=OperationRisk.SAFE,
                    table_name=desired.name,
                    object_name=fk.name,
                    ddl=ddl,
                    description=f"Add FK {fk.name}",
                )
            )

        for idx in desired.indexes:
            ddl = idx.to_ddl(desired.name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.CREATE_INDEX,
                    risk=OperationRisk.SAFE,
                    table_name=desired.name,
                    object_name=idx.name,
                    ddl=ddl,
                    description=f"Create index {idx.name}",
                )
            )

        for trigger in desired.triggers:
            ddl = trigger.to_ddl(desired.name) + ";"
            ops.append(
                MigrationOp(
                    op_type=OperationType.CREATE_TRIGGER,
                    risk=OperationRisk.SAFE,
                    table_name=desired.name,
                    object_name=trigger.name,
                    ddl=ddl,
                    description=f"Create trigger {trigger.name}",
                )
            )

    elif current is not None and desired is None:
        # DROP TABLE
        ddl = f'DROP TABLE "{current.schema}"."{current.name}" CASCADE;'
        ops.append(
            MigrationOp(
                op_type=OperationType.DROP_TABLE,
                risk=OperationRisk.DANGEROUS,
                table_name=current.name,
                ddl=ddl,
                description=f"Drop table {current.name}",
            )
        )

    elif current is not None and desired is not None:
        # Diff columns
        current_cols = {c.name: c for c in current.columns}
        desired_cols = {c.name: c for c in desired.columns}

        # Process columns
        all_col_names = set(current_cols) | set(desired_cols)
        for col_name in all_col_names:
            col_ops = diff_columns(
                current_cols.get(col_name),
                desired_cols.get(col_name),
                desired.name,
            )
            ops.extend(col_ops)

        # Diff constraints and indexes
        ops.extend(diff_foreign_keys(current.foreign_keys, desired.foreign_keys, desired.name))
        ops.extend(diff_indexes(current.indexes, desired.indexes, desired.name))
        ops.extend(diff_triggers(current.triggers, desired.triggers, desired.name, desired.schema))
        ops.extend(
            diff_check_constraints(
                current.check_constraints, desired.check_constraints, desired.name
            )
        )
        ops.extend(
            diff_unique_constraints(
                current.unique_constraints, desired.unique_constraints, desired.name
            )
        )

    return ops


def diff_schemas(current: SchemaSpec, desired: SchemaSpec) -> MigrationPlan:
    """Diff two schema specs and produce a migration plan.

    Args:
        current: Current schema spec (from introspection).
        desired: Desired schema spec (from Entity classes).

    Returns:
        MigrationPlan with all operations.
    """
    ops = []

    current_tables = {t.name: t for t in current.tables}
    desired_tables = {t.name: t for t in desired.tables}

    all_table_names = set(current_tables) | set(desired_tables)

    for table_name in sorted(all_table_names):
        table_ops = diff_tables(
            current_tables.get(table_name),
            desired_tables.get(table_name),
        )
        ops.extend(table_ops)

    return MigrationPlan(
        operations=tuple(ops),
        schema_hash_before=current.version,
        schema_hash_after=desired.version,
    )
