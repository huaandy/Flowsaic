"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-16 12:26:20.552349
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op


revision: str = '0001'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector must exist before doc_chunks.embedding can be created.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table('course_prereqs',
    sa.Column('course_code', sa.Text(), nullable=False),
    sa.Column('option_group', sa.Integer(), nullable=False),
    sa.Column('requires_code', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('course_code', 'option_group', 'requires_code', name=op.f('pk_course_prereqs'))
    )
    op.create_table('courses',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('department', sa.Text(), nullable=True),
    sa.Column('credits', sa.Integer(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('other_requirements', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_courses')),
    sa.UniqueConstraint('code', name=op.f('uq_courses_code'))
    )
    op.create_table('degree_plans',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('catalog_year', sa.Text(), nullable=False),
    sa.Column('total_hours', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_degree_plans')),
    sa.UniqueConstraint('name', 'catalog_year', name=op.f('uq_degree_plans_name'))
    )
    op.create_table('doc_chunks',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('source_type', sa.Text(), nullable=False),
    sa.Column('source_code', sa.Text(), nullable=False),
    sa.Column('chunk_index', sa.Integer(), server_default='0', nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_doc_chunks')),
    sa.UniqueConstraint('source_type', 'source_code', 'chunk_index', name=op.f('uq_doc_chunks_source_type'))
    )
    op.create_index('ix_doc_chunks_embedding_hnsw', 'doc_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_table('terms',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_terms')),
    sa.UniqueConstraint('code', name=op.f('uq_terms_code'))
    )
    op.create_table('requirement_groups',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('degree_plan_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('rule', sa.Text(), nullable=False),
    sa.Column('hours_required', sa.Integer(), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.CheckConstraint("rule IN ('all', 'choose_hours')", name=op.f('ck_requirement_groups_rule')),
    sa.ForeignKeyConstraint(['degree_plan_id'], ['degree_plans.id'], name=op.f('fk_requirement_groups_degree_plan_id_degree_plans'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['requirement_groups.id'], name=op.f('fk_requirement_groups_parent_id_requirement_groups'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_requirement_groups'))
    )
    op.create_table('sections',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('course_id', sa.Uuid(), nullable=False),
    sa.Column('term_id', sa.Uuid(), nullable=False),
    sa.Column('section_number', sa.Text(), nullable=False),
    sa.Column('instructor', sa.Text(), server_default='Staff', nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('building', sa.Text(), nullable=True),
    sa.Column('room', sa.Text(), nullable=True),
    sa.Column('days', sa.Text(), nullable=True),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('division', sa.Text(), nullable=True),
    sa.Column('enrolled', sa.Integer(), server_default='0', nullable=False),
    sa.Column('capacity', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_sections_course_id_courses'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['term_id'], ['terms.id'], name=op.f('fk_sections_term_id_terms'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sections')),
    sa.UniqueConstraint('course_id', 'term_id', 'section_number', name=op.f('uq_sections_course_id'))
    )
    op.create_table('students',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('email', sa.Text(), nullable=False),
    sa.Column('password', sa.Text(), nullable=False),
    sa.Column('degree_plan_id', sa.Uuid(), nullable=True),
    sa.Column('classification', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['degree_plan_id'], ['degree_plans.id'], name=op.f('fk_students_degree_plan_id_degree_plans')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_students')),
    sa.UniqueConstraint('email', name=op.f('uq_students_email'))
    )
    op.create_table('completed_courses',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('course_code', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.CheckConstraint("status IN ('completed', 'in_progress')", name=op.f('ck_completed_courses_status')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_completed_courses_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('student_id', 'course_code', name=op.f('pk_completed_courses'))
    )
    op.create_table('requirement_courses',
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.Column('course_code', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['requirement_groups.id'], name=op.f('fk_requirement_courses_group_id_requirement_groups'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('group_id', 'course_code', name=op.f('pk_requirement_courses'))
    )
    op.create_table('schedules',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('term_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('manual', 'ai')", name=op.f('ck_schedules_source')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_schedules_student_id_students'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['term_id'], ['terms.id'], name=op.f('fk_schedules_term_id_terms')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_schedules'))
    )
    op.create_table('schedule_sections',
    sa.Column('schedule_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], name=op.f('fk_schedule_sections_schedule_id_schedules'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_schedule_sections_section_id_sections'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('schedule_id', 'section_id', name=op.f('pk_schedule_sections'))
    )


def downgrade() -> None:
    # Drops every table. The vector extension is left installed.
    op.drop_table('schedule_sections')
    op.drop_table('schedules')
    op.drop_table('requirement_courses')
    op.drop_table('completed_courses')
    op.drop_table('students')
    op.drop_table('sections')
    op.drop_table('requirement_groups')
    op.drop_table('terms')
    op.drop_index('ix_doc_chunks_embedding_hnsw', table_name='doc_chunks', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_table('doc_chunks')
    op.drop_table('degree_plans')
    op.drop_table('courses')
    op.drop_table('course_prereqs')
