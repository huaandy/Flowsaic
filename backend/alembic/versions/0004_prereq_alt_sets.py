"""prereq alternative sets: course_prereqs.alt_set

Lets a prereq group say "(PHYS 2103 and PHYS 2101) or (PHYS 2213 and PHYS 2211)". Before this,
every row in an option_group was its own alternative, so a lecture+lab pair could only be
written as two separate AND groups, which was wrong for 13 courses (AGENTS.md, Data loading).

- alt_set: which alternative of its option_group a row belongs to. Rows sharing
  (course_code, option_group, alt_set) are all required together; different alt_sets in one
  group are alternatives (any one counts).
- Existing rows get a different alt_set each (1, 2, ... per group), so what is in the table
  keeps its meaning exactly. load_course_info.py rewrites the rows from the CSV anyway.
- alt_set joins the primary key, so one course may appear in two alternatives of a group.

Downgrade folds the sets back into single-course alternatives (a looser rule: any one course
of any set counts) and drops the column.

Written by Victor for Aaron to review (Nov 20). Never edit this file after it has been applied;
add a new migration instead.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | Sequence[str] | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('course_prereqs', sa.Column('alt_set', sa.Integer(), nullable=True))
    op.execute(
        "UPDATE course_prereqs AS p SET alt_set = r.n "
        "FROM (SELECT course_code, option_group, requires_code, "
        "      row_number() OVER (PARTITION BY course_code, option_group ORDER BY requires_code) AS n "
        "      FROM course_prereqs) AS r "
        "WHERE p.course_code = r.course_code AND p.option_group = r.option_group "
        "AND p.requires_code = r.requires_code"
    )
    op.alter_column('course_prereqs', 'alt_set', nullable=False)
    op.drop_constraint('pk_course_prereqs', 'course_prereqs', type_='primary')
    op.create_primary_key('pk_course_prereqs', 'course_prereqs',
                          ['course_code', 'option_group', 'alt_set', 'requires_code'])


def downgrade() -> None:
    # One row per (course, group, code) again: keep the lowest alt_set of any duplicate.
    op.execute(
        "DELETE FROM course_prereqs AS p USING course_prereqs AS q "
        "WHERE p.course_code = q.course_code AND p.option_group = q.option_group "
        "AND p.requires_code = q.requires_code AND p.alt_set > q.alt_set"
    )
    op.drop_constraint('pk_course_prereqs', 'course_prereqs', type_='primary')
    op.drop_column('course_prereqs', 'alt_set')
    op.create_primary_key('pk_course_prereqs', 'course_prereqs', ['course_code', 'option_group', 'requires_code'])
