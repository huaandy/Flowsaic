"""student planning: calendar events, scheduling preferences, app settings

Three new tables, one set per student. Nothing existing changes, so this applies on top of
any data. Each row belongs to one student and goes with them (ON DELETE CASCADE).

- calendar_events: the student's own commitments on the weekly calendar. Fixed events make
  the checker report commitment_overlap (a conflict); flexible ones commitment_overlap_flexible
  (a warning). day is one letter of MTWRF; times are Postgres time.
- student_preferences: one row per student. Defaults for Create Schedule, AI suggest and Flow.
  The front end's travel distance and minimum rating stay mock and are not stored.
- student_settings: one row per student. Notifications, appearance, accessibility, profile
  visibility and the profile photo (an image data URL, at most ~1 MB, checked by the API).

A missing preferences or settings row means the defaults; the API never returns 404 for it.

Never edit this file after it has been applied; add a new migration instead.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: str | Sequence[str] | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _student_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f(f'fk_{table}_student_id_students'),
                                   ondelete='CASCADE')


def upgrade() -> None:
    op.create_table('calendar_events',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('day', sa.Text(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('category', sa.Text(), server_default='personal_study', nullable=False),
    sa.Column('recurrence', sa.Text(), server_default='weekly', nullable=False),
    sa.Column('priority', sa.Text(), server_default='normal', nullable=False),
    sa.Column('fixed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("day IN ('M', 'T', 'W', 'R', 'F')", name=op.f('ck_calendar_events_day')),
    sa.CheckConstraint('start_time < end_time', name=op.f('ck_calendar_events_times')),
    sa.CheckConstraint("category IN ('work', 'personal_study', 'extracurricular')", name=op.f('ck_calendar_events_category')),
    sa.CheckConstraint("recurrence IN ('none', 'weekly')", name=op.f('ck_calendar_events_recurrence')),
    sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name=op.f('ck_calendar_events_priority')),
    _student_fk('calendar_events'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calendar_events'))
    )
    op.create_index('ix_calendar_events_student_id', 'calendar_events', ['student_id'], unique=False)

    op.create_table('student_preferences',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('preferred_time', sa.Text(), server_default='none', nullable=False),
    sa.Column('preferred_days', sa.Text(), server_default='', nullable=False),
    sa.Column('min_credits', sa.Integer(), server_default='12', nullable=False),
    sa.Column('max_credits', sa.Integer(), server_default='18', nullable=False),
    sa.Column('delivery', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{in_person,online}'::text[]"), nullable=False),
    sa.Column('flexibility', sa.Text(), server_default='balanced', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("preferred_time IN ('morning', 'midday', 'afternoon', 'evening', 'none')", name=op.f('ck_student_preferences_preferred_time')),
    sa.CheckConstraint("flexibility IN ('flexible', 'balanced', 'strict')", name=op.f('ck_student_preferences_flexibility')),
    sa.CheckConstraint('min_credits <= max_credits', name=op.f('ck_student_preferences_credits')),
    sa.CheckConstraint("delivery <@ ARRAY['in_person', 'online']::text[]", name=op.f('ck_student_preferences_delivery')),
    _student_fk('student_preferences'),
    sa.PrimaryKeyConstraint('student_id', name=op.f('pk_student_preferences'))
    )

    op.create_table('student_settings',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('email_notifications', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('push_notifications', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('advisor_updates', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('schedule_alerts', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('appearance', sa.Text(), server_default='light', nullable=False),
    sa.Column('high_contrast', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('larger_text', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('reduce_motion', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('profile_visibility', sa.Text(), server_default='advisors', nullable=False),
    sa.Column('photo', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("appearance IN ('light', 'dark', 'system')", name=op.f('ck_student_settings_appearance')),
    sa.CheckConstraint("profile_visibility IN ('private', 'advisors', 'community')", name=op.f('ck_student_settings_profile_visibility')),
    sa.CheckConstraint("photo IS NULL OR photo LIKE 'data:image/%'", name=op.f('ck_student_settings_photo')),
    _student_fk('student_settings'),
    sa.PrimaryKeyConstraint('student_id', name=op.f('pk_student_settings'))
    )


def downgrade() -> None:
    op.drop_table('student_settings')
    op.drop_table('student_preferences')
    op.drop_index('ix_calendar_events_student_id', table_name='calendar_events')
    op.drop_table('calendar_events')
