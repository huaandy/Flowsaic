"""Schema checks for migration 0002 (data retrieval). No database needed.

`uv run alembic check` against a migrated database confirms the models and the
migrations agree; these tests pin the parts other code relies on.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def columns(table_name: str) -> dict:
    return {column.name: column for column in Base.metadata.tables[table_name].columns}


def check_constraints(table_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {str(constraint.sqltext) for constraint in table.constraints if hasattr(constraint, "sqltext")}


def test_migrations_form_one_line_ending_at_0002():
    script = ScriptDirectory.from_config(Config(str(BACKEND_DIR / "alembic.ini")))
    assert script.get_heads() == ["0002"]
    assert script.get_revision("0002").down_revision == "0001"


def test_students_store_only_the_allowed_audit_fields():
    student = columns("students")
    for name in ("major", "catalog_year", "has_hold", "total_hours_earned",
                 "total_hours_needed", "audit_refreshed_at"):
        assert student[name].nullable or student[name].server_default is not None
    assert student["has_hold"].server_default.arg.text == "false"
    # Privacy: the audit header and hold details never get a column.
    for forbidden in ("gpa", "student_number", "id_number", "address", "phone", "advisor",
                      "hold_name", "hold_description"):
        assert forbidden not in student


def test_completed_courses_allow_several_lines_per_course():
    table = Base.metadata.tables["completed_courses"]
    assert [column.name for column in table.primary_key.columns] == ["id"]
    completed = columns("completed_courses")
    assert completed["source"].server_default.arg == "manual"
    for name in ("grade", "credits", "term", "requirement_name"):
        assert completed[name].nullable
    assert "source IN ('audit', 'self_reported', 'manual')" in check_constraints("completed_courses")


def test_student_requirements_shape():
    requirement = columns("student_requirements")
    assert set(requirement) == {
        "id", "student_id", "name", "parent_name", "status", "rule", "hours_earned",
        "hours_required", "course_options", "note", "sort_order",
    }
    rules = check_constraints("student_requirements")
    assert "status IN ('met', 'not_met', 'in_progress')" in rules
    assert "rule IN ('all', 'choose_hours')" in rules
    student_fk = next(iter(requirement["student_id"].foreign_keys))
    assert student_fk.ondelete == "CASCADE"


def test_refresh_runs_shape():
    run = columns("refresh_runs")
    assert set(run) == {
        "id", "kind", "status", "started_at", "finished_at", "rows_changed", "error", "student_id",
    }
    assert run["student_id"].nullable  # null for public runs
    rules = check_constraints("refresh_runs")
    assert "kind IN ('course_info', 'degree_maps', 'sections', 'audit')" in rules
    assert "status IN ('running', 'ok', 'failed')" in rules


def test_public_data_columns():
    assert columns("sections")["active"].server_default.arg.text == "true"
    assert columns("terms")["is_current_registration"].server_default.arg.text == "false"
    assert columns("requirement_groups")["note"].nullable
    assert columns("degree_plans")["source_url"].nullable
    assert columns("degree_plans")["scraped_at"].nullable
    assert columns("doc_chunks")["content_hash"].nullable
