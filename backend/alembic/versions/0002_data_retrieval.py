"""data retrieval: audit fields, student requirements, refresh runs

Adds what the automated scrapers and the mySAU connect flow need (prompt 2, Stage 1).
Applies on top of existing data: every new column is nullable or has a default.

- students: audit summary fields. The audit header (name, ID, address, phones, advisor,
  GPA) is never stored; holds are only a boolean.
- completed_courses: grade, credits, term, source, requirement_name. The primary key
  moves from (student_id, course_code) to a new id, because one course can appear on
  several audit lines (counts toward two requirements, retaken, or self-reported too).
- student_requirements (new): a connected student's audit blocks. For that student
  this IS their degree plan.
- requirement_groups.note, degree_plans.source_url / scraped_at, sections.active,
  terms.is_current_registration.
- refresh_runs (new): one row per scrape or mySAU connect.
- doc_chunks.content_hash: sha256 of content, so only changed courses are re-embedded.
  Backfilled here for the existing chunks.

Never edit this file after it has been applied; add a new migration instead.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOURS = sa.Numeric(precision=5, scale=2)


def upgrade() -> None:
    # students: audit summary
    op.add_column('students', sa.Column('major', sa.Text(), nullable=True))
    op.add_column('students', sa.Column('catalog_year', sa.Text(), nullable=True))
    op.add_column('students', sa.Column('has_hold', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('students', sa.Column('total_hours_earned', HOURS, nullable=True))
    op.add_column('students', sa.Column('total_hours_needed', HOURS, nullable=True))
    op.add_column('students', sa.Column('audit_refreshed_at', sa.DateTime(timezone=True), nullable=True))

    # completed_courses: new columns, then swap the primary key to a plain id.
    # gen_random_uuid() fills id for any existing rows.
    op.add_column('completed_courses', sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False))
    op.add_column('completed_courses', sa.Column('grade', sa.Text(), nullable=True))
    op.add_column('completed_courses', sa.Column('credits', HOURS, nullable=True))
    op.add_column('completed_courses', sa.Column('term', sa.Text(), nullable=True))
    op.add_column('completed_courses', sa.Column('source', sa.Text(), server_default='manual', nullable=False))
    op.add_column('completed_courses', sa.Column('requirement_name', sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f('ck_completed_courses_source'),
        'completed_courses',
        "source IN ('audit', 'self_reported', 'manual')",
    )
    op.drop_constraint('pk_completed_courses', 'completed_courses', type_='primary')
    op.create_primary_key('pk_completed_courses', 'completed_courses', ['id'])
    op.create_index('ix_completed_courses_student_id', 'completed_courses', ['student_id'], unique=False)

    op.create_table('student_requirements',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('parent_name', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('rule', sa.Text(), server_default='all', nullable=False),
    sa.Column('hours_earned', HOURS, nullable=True),
    sa.Column('hours_required', HOURS, nullable=True),
    sa.Column('course_options', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("rule IN ('all', 'choose_hours')", name=op.f('ck_student_requirements_rule')),
    sa.CheckConstraint("status IN ('met', 'not_met', 'in_progress')", name=op.f('ck_student_requirements_status')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_student_requirements_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_student_requirements'))
    )
    op.create_index('ix_student_requirements_student_id', 'student_requirements', ['student_id'], unique=False)

    # Public catalog data
    op.add_column('requirement_groups', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('degree_plans', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('degree_plans', sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sections', sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('terms', sa.Column('is_current_registration', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    op.create_table('refresh_runs',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default='running', nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rows_changed', sa.Integer(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('student_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint("kind IN ('course_info', 'degree_maps', 'sections', 'audit')", name=op.f('ck_refresh_runs_kind')),
    sa.CheckConstraint("status IN ('running', 'ok', 'failed')", name=op.f('ck_refresh_runs_status')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_refresh_runs_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_refresh_runs'))
    )
    op.create_index('ix_refresh_runs_kind', 'refresh_runs', ['kind', 'started_at'], unique=False)

    # RAG: hash existing chunks so the next embed run skips unchanged text.
    op.add_column('doc_chunks', sa.Column('content_hash', sa.Text(), nullable=True))
    op.execute("UPDATE doc_chunks SET content_hash = encode(sha256(convert_to(content, 'UTF8')), 'hex')")


def downgrade() -> None:
    op.drop_column('doc_chunks', 'content_hash')

    op.drop_index('ix_refresh_runs_kind', table_name='refresh_runs')
    op.drop_table('refresh_runs')

    op.drop_column('terms', 'is_current_registration')
    op.drop_column('sections', 'active')
    op.drop_column('degree_plans', 'scraped_at')
    op.drop_column('degree_plans', 'source_url')
    op.drop_column('requirement_groups', 'note')

    op.drop_index('ix_student_requirements_student_id', table_name='student_requirements')
    op.drop_table('student_requirements')

    # The old key allows one row per (student, course). Keep one of each and drop the
    # extra lines (audit duplicates) before restoring it.
    op.execute(
        "DELETE FROM completed_courses a USING completed_courses b "
        "WHERE a.student_id = b.student_id AND a.course_code = b.course_code AND a.id > b.id"
    )
    op.drop_index('ix_completed_courses_student_id', table_name='completed_courses')
    op.drop_constraint('pk_completed_courses', 'completed_courses', type_='primary')
    op.create_primary_key('pk_completed_courses', 'completed_courses', ['student_id', 'course_code'])
    op.drop_constraint(op.f('ck_completed_courses_source'), 'completed_courses', type_='check')
    op.drop_column('completed_courses', 'requirement_name')
    op.drop_column('completed_courses', 'source')
    op.drop_column('completed_courses', 'term')
    op.drop_column('completed_courses', 'credits')
    op.drop_column('completed_courses', 'grade')
    op.drop_column('completed_courses', 'id')

    op.drop_column('students', 'audit_refreshed_at')
    op.drop_column('students', 'total_hours_needed')
    op.drop_column('students', 'total_hours_earned')
    op.drop_column('students', 'has_hold')
    op.drop_column('students', 'catalog_year')
    op.drop_column('students', 'major')
