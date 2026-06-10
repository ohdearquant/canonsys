"""Tests for schema diff engine (D4.1).

Tests cover:
- Column diff operations
- FK diff operations
- Index diff operations
- Trigger diff operations
- Constraint diff operations
- Table diff operations
- Schema diff operations
- Risk classification
"""

from __future__ import annotations

from canon.db.migration.diff import (
    MigrationPlan,
    OperationRisk,
    OperationType,
    diff_check_constraints,
    diff_columns,
    diff_foreign_keys,
    diff_indexes,
    diff_schemas,
    diff_tables,
    diff_triggers,
    diff_unique_constraints,
)
from canon.db.migration.schema import (
    CheckConstraintSpec,
    ColumnSpec,
    ForeignKeySpec,
    IndexSpec,
    OnAction,
    SchemaSpec,
    TableSpec,
    TriggerSpec,
    UniqueConstraintSpec,
)


class TestDiffColumns:
    """Tests for column diff operations."""

    def test_add_nullable_column(self):
        """Adding nullable column should be SAFE."""
        desired = ColumnSpec(name="email", type="TEXT", nullable=True)
        ops = diff_columns(None, desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ADD_COLUMN
        assert op.risk == OperationRisk.SAFE
        assert op.object_name == "email"
        assert 'ADD COLUMN "email"' in op.ddl

    def test_add_not_null_column(self):
        """Adding NOT NULL column should be CAREFUL."""
        desired = ColumnSpec(name="email", type="TEXT", nullable=False)
        ops = diff_columns(None, desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ADD_COLUMN
        assert op.risk == OperationRisk.CAREFUL

    def test_drop_column(self):
        """Dropping column should be DANGEROUS."""
        current = ColumnSpec(name="email", type="TEXT")
        ops = diff_columns(current, None, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_COLUMN
        assert op.risk == OperationRisk.DANGEROUS
        assert 'DROP COLUMN "email"' in op.ddl

    def test_widen_type_safe(self):
        """Widening INTEGER to BIGINT should be SAFE."""
        current = ColumnSpec(name="count", type="INTEGER")
        desired = ColumnSpec(name="count", type="BIGINT")
        ops = diff_columns(current, desired, "stats")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ALTER_COLUMN_TYPE
        assert op.risk == OperationRisk.SAFE

    def test_narrow_type_dangerous(self):
        """Narrowing BIGINT to INTEGER should be DANGEROUS."""
        current = ColumnSpec(name="count", type="BIGINT")
        desired = ColumnSpec(name="count", type="INTEGER")
        ops = diff_columns(current, desired, "stats")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ALTER_COLUMN_TYPE
        assert op.risk == OperationRisk.DANGEROUS

    def test_set_not_null_careful(self):
        """Setting NOT NULL should be CAREFUL."""
        current = ColumnSpec(name="email", type="TEXT", nullable=True)
        desired = ColumnSpec(name="email", type="TEXT", nullable=False)
        ops = diff_columns(current, desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ALTER_COLUMN_NULLABLE
        assert op.risk == OperationRisk.CAREFUL
        assert "SET NOT NULL" in op.ddl

    def test_drop_not_null_safe(self):
        """Dropping NOT NULL should be SAFE."""
        current = ColumnSpec(name="email", type="TEXT", nullable=False)
        desired = ColumnSpec(name="email", type="TEXT", nullable=True)
        ops = diff_columns(current, desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ALTER_COLUMN_NULLABLE
        assert op.risk == OperationRisk.SAFE
        assert "DROP NOT NULL" in op.ddl

    def test_change_default_safe(self):
        """Changing default should be SAFE."""
        current = ColumnSpec(name="status", type="TEXT", default="'pending'")
        desired = ColumnSpec(name="status", type="TEXT", default="'active'")
        ops = diff_columns(current, desired, "tasks")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ALTER_COLUMN_DEFAULT
        assert op.risk == OperationRisk.SAFE

    def test_no_change_no_ops(self):
        """Identical columns should produce no operations."""
        col = ColumnSpec(name="email", type="TEXT", nullable=True)
        ops = diff_columns(col, col, "users")
        assert len(ops) == 0


class TestDiffForeignKeys:
    """Tests for FK diff operations."""

    def test_add_fk_uses_not_valid(self):
        """Adding FK should use NOT VALID pattern."""
        desired = (
            ForeignKeySpec(
                name="fk_users_tenant",
                columns=("tenant_id",),
                ref_table="tenants",
            ),
        )
        ops = diff_foreign_keys((), desired, "users")

        assert len(ops) == 2
        # Phase A: Add NOT VALID
        add_op = ops[0]
        assert add_op.op_type == OperationType.ADD_FOREIGN_KEY
        assert add_op.risk == OperationRisk.SAFE
        assert add_op.phase == "A"
        assert "NOT VALID" in add_op.ddl

        # Phase B: Validate
        validate_op = ops[1]
        assert validate_op.phase == "B"
        assert "VALIDATE CONSTRAINT" in validate_op.ddl

    def test_drop_fk_careful(self):
        """Dropping FK should be CAREFUL."""
        current = (
            ForeignKeySpec(
                name="fk_users_tenant",
                columns=("tenant_id",),
                ref_table="tenants",
            ),
        )
        ops = diff_foreign_keys(current, (), "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_FOREIGN_KEY
        assert op.risk == OperationRisk.CAREFUL

    def test_modify_fk_drop_and_recreate(self):
        """Modifying FK should drop and recreate."""
        current = (
            ForeignKeySpec(
                name="fk_users_tenant",
                columns=("tenant_id",),
                ref_table="tenants",
                on_delete=OnAction.CASCADE,
            ),
        )
        desired = (
            ForeignKeySpec(
                name="fk_users_tenant",
                columns=("tenant_id",),
                ref_table="tenants",
                on_delete=OnAction.SET_NULL,
            ),
        )
        ops = diff_foreign_keys(current, desired, "users")

        assert len(ops) == 2
        assert ops[0].op_type == OperationType.DROP_FOREIGN_KEY
        assert ops[1].op_type == OperationType.ADD_FOREIGN_KEY


class TestDiffIndexes:
    """Tests for index diff operations."""

    def test_create_index_uses_concurrently(self):
        """Creating index should use CONCURRENTLY."""
        desired = (IndexSpec(name="idx_email", columns=("email",)),)
        ops = diff_indexes((), desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.CREATE_INDEX
        assert op.risk == OperationRisk.SAFE
        assert op.phase == "B"  # Non-transactional
        assert "CONCURRENTLY" in op.ddl

    def test_drop_index_careful(self):
        """Dropping index should be CAREFUL."""
        current = (IndexSpec(name="idx_email", columns=("email",)),)
        ops = diff_indexes(current, (), "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_INDEX
        assert op.risk == OperationRisk.CAREFUL

    def test_modify_index_drop_and_recreate(self):
        """Modifying index should drop and recreate."""
        current = (IndexSpec(name="idx_email", columns=("email",)),)
        desired = (IndexSpec(name="idx_email", columns=("email",), unique=True),)
        ops = diff_indexes(current, desired, "users")

        assert len(ops) == 2
        assert ops[0].op_type == OperationType.DROP_INDEX
        assert ops[1].op_type == OperationType.CREATE_INDEX


class TestDiffTriggers:
    """Tests for trigger diff operations."""

    def test_create_trigger_safe(self):
        """Creating trigger should be SAFE."""
        desired = (
            TriggerSpec(
                name="trg_updated_at",
                timing="BEFORE",
                events=("UPDATE",),
                function="public.update_timestamp",
            ),
        )
        ops = diff_triggers((), desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.CREATE_TRIGGER
        assert op.risk == OperationRisk.SAFE

    def test_drop_trigger_careful(self):
        """Dropping trigger should be CAREFUL."""
        current = (
            TriggerSpec(
                name="trg_updated_at",
                timing="BEFORE",
                events=("UPDATE",),
                function="public.update_timestamp",
            ),
        )
        ops = diff_triggers(current, (), "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_TRIGGER
        assert op.risk == OperationRisk.CAREFUL

    def test_modify_trigger_emits_drop_and_create(self):
        """Modifying trigger should emit separate DROP and CREATE ops for atomicity."""
        current = (
            TriggerSpec(
                name="trg_updated_at",
                timing="BEFORE",
                events=("UPDATE",),
                function="public.update_timestamp",
            ),
        )
        desired = (
            TriggerSpec(
                name="trg_updated_at",
                timing="AFTER",  # Changed from BEFORE
                events=("UPDATE",),
                function="public.update_timestamp",
            ),
        )
        ops = diff_triggers(current, desired, "users")

        # Should emit two separate ops (not one combined REPLACE_TRIGGER)
        assert len(ops) == 2
        assert ops[0].op_type == OperationType.DROP_TRIGGER
        assert ops[1].op_type == OperationType.CREATE_TRIGGER
        # Verify descriptions indicate replacement
        assert (
            "replacement" in ops[0].description.lower()
            or "for replacement" in ops[0].description.lower()
        )


class TestDiffCheckConstraints:
    """Tests for CHECK constraint diff operations."""

    def test_add_check_constraint(self):
        """Adding CHECK constraint should be CAREFUL."""
        desired = (
            CheckConstraintSpec(
                name="chk_age_positive",
                expression="age >= 0",
            ),
        )
        ops = diff_check_constraints((), desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ADD_CHECK_CONSTRAINT
        assert op.risk == OperationRisk.CAREFUL

    def test_drop_check_constraint(self):
        """Dropping CHECK constraint should be CAREFUL."""
        current = (
            CheckConstraintSpec(
                name="chk_age_positive",
                expression="age >= 0",
            ),
        )
        ops = diff_check_constraints(current, (), "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_CHECK_CONSTRAINT
        assert op.risk == OperationRisk.CAREFUL

    def test_modify_check_constraint_emits_drop_and_add(self):
        """Modifying CHECK constraint should emit DROP then ADD."""
        current = (
            CheckConstraintSpec(
                name="chk_age_valid",
                expression="age >= 0",
            ),
        )
        desired = (
            CheckConstraintSpec(
                name="chk_age_valid",
                expression="age >= 18",  # Changed expression
            ),
        )
        ops = diff_check_constraints(current, desired, "users")

        assert len(ops) == 2
        assert ops[0].op_type == OperationType.DROP_CHECK_CONSTRAINT
        assert ops[1].op_type == OperationType.ADD_CHECK_CONSTRAINT
        assert (
            "modification" in ops[0].description.lower()
            or "for modification" in ops[0].description.lower()
        )
        assert "modified" in ops[1].description.lower()

    def test_no_change_no_ops(self):
        """Identical CHECK constraints should produce no operations."""
        constraint = CheckConstraintSpec(name="chk_age", expression="age >= 0")
        ops = diff_check_constraints((constraint,), (constraint,), "users")
        assert len(ops) == 0


class TestDiffUniqueConstraints:
    """Tests for UNIQUE constraint diff operations."""

    def test_add_unique_constraint(self):
        """Adding UNIQUE constraint should be CAREFUL."""
        desired = (
            UniqueConstraintSpec(
                name="uq_email",
                columns=("email",),
            ),
        )
        ops = diff_unique_constraints((), desired, "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ADD_UNIQUE_CONSTRAINT
        assert op.risk == OperationRisk.CAREFUL

    def test_drop_unique_constraint(self):
        """Dropping UNIQUE constraint should be CAREFUL."""
        current = (
            UniqueConstraintSpec(
                name="uq_email",
                columns=("email",),
            ),
        )
        ops = diff_unique_constraints(current, (), "users")

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_UNIQUE_CONSTRAINT
        assert op.risk == OperationRisk.CAREFUL

    def test_modify_unique_constraint_emits_drop_and_add(self):
        """Modifying UNIQUE constraint should emit DROP then ADD."""
        current = (
            UniqueConstraintSpec(
                name="uq_user_email",
                columns=("email",),
            ),
        )
        desired = (
            UniqueConstraintSpec(
                name="uq_user_email",
                columns=("email", "tenant_id"),  # Added column
            ),
        )
        ops = diff_unique_constraints(current, desired, "users")

        assert len(ops) == 2
        assert ops[0].op_type == OperationType.DROP_UNIQUE_CONSTRAINT
        assert ops[1].op_type == OperationType.ADD_UNIQUE_CONSTRAINT
        assert (
            "modification" in ops[0].description.lower()
            or "for modification" in ops[0].description.lower()
        )
        assert "modified" in ops[1].description.lower()

    def test_no_change_no_ops(self):
        """Identical UNIQUE constraints should produce no operations."""
        constraint = UniqueConstraintSpec(name="uq_email", columns=("email",))
        ops = diff_unique_constraints((constraint,), (constraint,), "users")
        assert len(ops) == 0


class TestDiffTables:
    """Tests for table diff operations."""

    def test_create_table_safe(self):
        """Creating table should be SAFE."""
        desired = TableSpec(
            name="users",
            columns=(
                ColumnSpec(name="id", type="UUID", is_primary_key=True),
                ColumnSpec(name="email", type="TEXT", nullable=False),
            ),
        )
        ops = diff_tables(None, desired)

        assert len(ops) >= 1
        create_op = ops[0]
        assert create_op.op_type == OperationType.CREATE_TABLE
        assert create_op.risk == OperationRisk.SAFE

    def test_drop_table_dangerous(self):
        """Dropping table should be DANGEROUS."""
        current = TableSpec(
            name="users",
            columns=(ColumnSpec(name="id", type="UUID"),),
        )
        ops = diff_tables(current, None)

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.DROP_TABLE
        assert op.risk == OperationRisk.DANGEROUS
        assert "CASCADE" in op.ddl

    def test_add_column_to_existing_table(self):
        """Adding column to existing table should produce ADD COLUMN."""
        current = TableSpec(
            name="users",
            columns=(ColumnSpec(name="id", type="UUID"),),
        )
        desired = TableSpec(
            name="users",
            columns=(
                ColumnSpec(name="id", type="UUID"),
                ColumnSpec(name="email", type="TEXT"),
            ),
        )
        ops = diff_tables(current, desired)

        assert len(ops) == 1
        op = ops[0]
        assert op.op_type == OperationType.ADD_COLUMN
        assert op.object_name == "email"


class TestDiffSchemas:
    """Tests for schema diff operations."""

    def test_empty_schemas_no_ops(self):
        """Diffing empty schemas should produce no operations."""
        current = SchemaSpec()
        desired = SchemaSpec()
        plan = diff_schemas(current, desired)

        assert len(plan.operations) == 0

    def test_add_new_table(self):
        """Adding new table should produce CREATE TABLE."""
        current = SchemaSpec()
        desired = SchemaSpec(
            tables=(
                TableSpec(
                    name="users",
                    columns=(ColumnSpec(name="id", type="UUID"),),
                ),
            )
        )
        plan = diff_schemas(current, desired)

        assert len(plan.operations) >= 1
        assert any(op.op_type == OperationType.CREATE_TABLE for op in plan.operations)

    def test_drop_table(self):
        """Removing table should produce DROP TABLE."""
        current = SchemaSpec(
            tables=(
                TableSpec(
                    name="users",
                    columns=(ColumnSpec(name="id", type="UUID"),),
                ),
            )
        )
        desired = SchemaSpec()
        plan = diff_schemas(current, desired)

        assert len(plan.operations) == 1
        op = plan.operations[0]
        assert op.op_type == OperationType.DROP_TABLE
        assert plan.has_dangerous is True

    def test_plan_preserves_hashes(self):
        """Plan should preserve schema hashes."""
        current = SchemaSpec(version="hash_before")
        desired = SchemaSpec(version="hash_after")
        plan = diff_schemas(current, desired)

        assert plan.schema_hash_before == "hash_before"
        assert plan.schema_hash_after == "hash_after"


class TestMigrationPlan:
    """Tests for MigrationPlan dataclass."""

    def test_has_dangerous(self):
        """has_dangerous should detect dangerous operations."""
        from canon.db.migration.diff import MigrationOp

        safe_plan = MigrationPlan(
            operations=(
                MigrationOp(
                    op_type=OperationType.ADD_COLUMN,
                    risk=OperationRisk.SAFE,
                    table_name="users",
                ),
            )
        )
        assert safe_plan.has_dangerous is False

        dangerous_plan = MigrationPlan(
            operations=(
                MigrationOp(
                    op_type=OperationType.DROP_TABLE,
                    risk=OperationRisk.DANGEROUS,
                    table_name="users",
                ),
            )
        )
        assert dangerous_plan.has_dangerous is True

    def test_phase_separation(self):
        """Should separate Phase A and Phase B operations."""
        from canon.db.migration.diff import MigrationOp

        plan = MigrationPlan(
            operations=(
                MigrationOp(
                    op_type=OperationType.ADD_COLUMN,
                    risk=OperationRisk.SAFE,
                    table_name="users",
                    phase="A",
                ),
                MigrationOp(
                    op_type=OperationType.CREATE_INDEX,
                    risk=OperationRisk.SAFE,
                    table_name="users",
                    phase="B",
                ),
            )
        )

        assert len(plan.phase_a_ops) == 1
        assert len(plan.phase_b_ops) == 1
        assert plan.phase_a_ops[0].op_type == OperationType.ADD_COLUMN
        assert plan.phase_b_ops[0].op_type == OperationType.CREATE_INDEX

    def test_to_sql(self):
        """to_sql should generate SQL with comments."""
        from canon.db.migration.diff import MigrationOp

        plan = MigrationPlan(
            operations=(
                MigrationOp(
                    op_type=OperationType.ADD_COLUMN,
                    risk=OperationRisk.SAFE,
                    table_name="users",
                    ddl='ALTER TABLE "users" ADD COLUMN "email" TEXT;',
                    description="Add column email",
                ),
            )
        )

        sql = plan.to_sql()
        assert "-- Add column email" in sql
        assert 'ALTER TABLE "users"' in sql
