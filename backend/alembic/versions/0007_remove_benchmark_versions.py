"""remove benchmark versions and bind seeds directly to benchmarks

Revision ID: 0007_remove_benchmark_versions
Revises: 0006_task_seed_selection
Create Date: 2026-10-21

Destructive schema consolidation: benchmark_versions is removed and all
test cases move from benchmark_version_id to benchmark_id.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "0007_remove_benchmark_versions"
down_revision = "0006_task_seed_selection"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _drop_foreign_keys_to(table_name: str, target_table: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    inspector = inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if foreign_key.get("referred_table") == target_table and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def _deduplicate_external_ids() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, benchmark_id, external_id FROM test_cases "
            "ORDER BY benchmark_id, id"
        )
    ).mappings()
    seen: dict[tuple[int, str], int] = {}
    for row in rows:
        benchmark_id = row["benchmark_id"]
        if benchmark_id is None:
            continue
        key = (int(benchmark_id), str(row["external_id"]))
        if key not in seen:
            seen[key] = int(row["id"])
            continue
        bind.execute(
            sa.text(
                "UPDATE test_cases SET external_id = :external_id WHERE id = :id"
            ),
            {
                "external_id": f"{row['external_id']}-dup-{row['id']}",
                "id": row["id"],
            },
        )


def _has_benchmark_foreign_key(table_name: str) -> bool:
    return any(
        foreign_key.get("referred_table") == "benchmarks"
        and foreign_key.get("constrained_columns") == ["benchmark_id"]
        for foreign_key in inspect(op.get_bind()).get_foreign_keys(table_name)
    )


def _has_benchmark_external_unique() -> bool:
    return any(
        set(item.get("column_names") or []) == {"benchmark_id", "external_id"}
        for item in inspect(op.get_bind()).get_unique_constraints("test_cases")
    )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    tables = _table_names()

    _add_column_if_missing(
        "benchmarks",
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
    )
    _add_column_if_missing("benchmarks", sa.Column("raw_schema", sa.JSON(), nullable=True))
    _add_column_if_missing(
        "benchmarks",
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("benchmarks", sa.Column("checksum", sa.String(128), nullable=True))
    _add_column_if_missing(
        "benchmarks",
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
    )

    _add_column_if_missing(
        "test_cases",
        sa.Column("benchmark_id", sa.BigInteger(), nullable=True),
    )
    _add_column_if_missing(
        "evaluation_tasks",
        sa.Column("benchmark_id", sa.BigInteger(), nullable=True),
    )

    if "benchmark_versions" in tables and "benchmark_version_id" in _column_names("test_cases"):
        bind.execute(
            sa.text(
                "UPDATE test_cases SET benchmark_id = ("
                "SELECT benchmark_id FROM benchmark_versions "
                "WHERE benchmark_versions.id = test_cases.benchmark_version_id"
                ")"
            )
        )

    if "benchmark_versions" in tables and "benchmark_version_id" in _column_names("evaluation_tasks"):
        bind.execute(
            sa.text(
                "UPDATE evaluation_tasks SET benchmark_id = ("
                "SELECT benchmark_id FROM benchmark_versions "
                "WHERE benchmark_versions.id = evaluation_tasks.benchmark_version_id"
                ")"
            )
        )

    if "benchmark_versions" in tables:
        latest_versions: dict[int, dict] = {}
        for row in bind.execute(
            sa.text(
                "SELECT benchmark_id, source_file_id, checksum, imported_at "
                "FROM benchmark_versions ORDER BY benchmark_id, imported_at, id"
            )
        ).mappings():
            latest_versions[int(row["benchmark_id"])] = dict(row)
        for benchmark_id, row in latest_versions.items():
            bind.execute(
                sa.text(
                    "UPDATE benchmarks SET source_file_id = :source_file_id, "
                    "checksum = :checksum, imported_at = :imported_at "
                    "WHERE id = :benchmark_id"
                ),
                {
                    "source_file_id": row["source_file_id"],
                    "checksum": row["checksum"],
                    "imported_at": row["imported_at"],
                    "benchmark_id": benchmark_id,
                },
            )

    # Orphan rows cannot be represented after the old parent table is removed.
    bind.execute(sa.text("DELETE FROM test_cases WHERE benchmark_id IS NULL"))
    bind.execute(
        sa.text(
            "UPDATE benchmarks SET case_count = ("
            "SELECT COUNT(*) FROM test_cases WHERE test_cases.benchmark_id = benchmarks.id"
            ")"
        )
    )
    _deduplicate_external_ids()
    test_has_benchmark_fk = _has_benchmark_foreign_key("test_cases")
    task_has_benchmark_fk = _has_benchmark_foreign_key("evaluation_tasks")
    test_has_external_unique = _has_benchmark_external_unique()

    if dialect == "sqlite":
        constraints = {
            item["name"]
            for item in inspect(bind).get_unique_constraints("test_cases")
            if item.get("name")
        }
        with op.batch_alter_table("test_cases", recreate="always") as batch_op:
            if "uq_test_cases_version_external" in constraints:
                batch_op.drop_constraint(
                    "uq_test_cases_version_external",
                    type_="unique",
                )
            if "benchmark_version_id" in _column_names("test_cases"):
                batch_op.drop_column("benchmark_version_id")
            batch_op.alter_column(
                "benchmark_id",
                existing_type=sa.BigInteger(),
                nullable=False,
            )
            if not test_has_benchmark_fk:
                batch_op.create_foreign_key(
                    "fk_test_cases_benchmark_id",
                    "benchmarks",
                    ["benchmark_id"],
                    ["id"],
                )
            if not test_has_external_unique:
                batch_op.create_unique_constraint(
                    "uq_test_cases_benchmark_external",
                    ["benchmark_id", "external_id"],
                )

        with op.batch_alter_table("evaluation_tasks", recreate="always") as batch_op:
            if "benchmark_version_id" in _column_names("evaluation_tasks"):
                batch_op.drop_column("benchmark_version_id")
            if not task_has_benchmark_fk:
                batch_op.create_foreign_key(
                    "fk_evaluation_tasks_benchmark_id",
                    "benchmarks",
                    ["benchmark_id"],
                    ["id"],
                )
    else:
        _drop_foreign_keys_to("test_cases", "benchmark_versions")
        _drop_foreign_keys_to("evaluation_tasks", "benchmark_versions")
        if "benchmark_version_id" in _column_names("test_cases"):
            op.drop_column("test_cases", "benchmark_version_id")
        if "benchmark_version_id" in _column_names("evaluation_tasks"):
            op.drop_column("evaluation_tasks", "benchmark_version_id")
        op.alter_column(
            "test_cases",
            "benchmark_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )
        if not test_has_benchmark_fk:
            op.create_foreign_key(
                "fk_test_cases_benchmark_id",
                "test_cases",
                "benchmarks",
                ["benchmark_id"],
                ["id"],
            )
        if not task_has_benchmark_fk:
            op.create_foreign_key(
                "fk_evaluation_tasks_benchmark_id",
                "evaluation_tasks",
                "benchmarks",
                ["benchmark_id"],
                ["id"],
            )
        if not test_has_external_unique:
            op.create_unique_constraint(
                "uq_test_cases_benchmark_external",
                "test_cases",
                ["benchmark_id", "external_id"],
            )

    if "benchmark_versions" in _table_names():
        op.drop_table("benchmark_versions")


def downgrade() -> None:
    raise RuntimeError(
        "0007_remove_benchmark_versions is destructive; restore a pre-0007 "
        "database backup instead of downgrading."
    )
