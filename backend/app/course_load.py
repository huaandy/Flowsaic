"""Load data/course_info.csv into courses and course_prereqs.

Used by db/scripts/load_course_info.py and by the public data refresh. Re-running updates
rows instead of duplicating them:
- courses are matched on code; title, description and other_requirements are updated.
  department and credits are left alone (they come from the sections export).
- each course's prereq rows are replaced with what the file says now. prereqs use
  ';' (all groups), '|' (alternatives) and '+' (courses needed together, Nov 20).
Bad rows are reported and skipped, never guessed.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Course, CoursePrereq
from app.normalize import normalize_course_code, parse_prereq_sets

REQUIRED_COLUMNS = ["code", "title", "description", "prereqs", "other_requirements"]


@dataclass
class LoadResult:
    rows_read: int = 0
    courses: int = 0
    inserted: int = 0
    with_description: int = 0
    courses_with_prereqs: int = 0
    prereq_rows: int = 0
    table_total: int = 0
    rejected: list[str] = field(default_factory=list)


def prereq_table_rows(code: str, groups: list[list[list[str]]]) -> list[dict]:
    """course_prereqs rows for one course. Each '|' alternative gets its own alt_set; the
    courses of a '+' set share one. Without '+' every row is its own alternative (as before)."""
    return [
        {"course_code": code, "option_group": option_group, "alt_set": alt_set, "requires_code": requires_code}
        for option_group, options in enumerate(groups, start=1)
        for alt_set, codes in enumerate(options, start=1)
        for requires_code in codes
    ]


def load_course_info_csv(path: Path) -> LoadResult:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")

    courses: dict[str, dict] = {}
    prereq_rows: list[dict] = []
    result = LoadResult(rows_read=len(frame))

    for line, row in enumerate(frame.to_dict("records"), start=2):  # line 1 is the header
        try:
            code = normalize_course_code(row["code"])
            title = row["title"].strip()
            if not title:
                raise ValueError("blank title")
            if code in courses:
                raise ValueError(f"duplicate course code {code}")
            groups = parse_prereq_sets(row["prereqs"])
        except ValueError as error:
            result.rejected.append(f"line {line}: {row['code']!r} - {error}")
            continue

        courses[code] = {
            "code": code,
            "title": title,
            "description": row["description"].strip() or None,
            "other_requirements": row["other_requirements"].strip() or None,
        }
        prereq_rows.extend(prereq_table_rows(code, groups))

    with SessionLocal.begin() as session:
        before = session.scalar(select(func.count()).select_from(Course))

        statement = insert(Course)
        statement = statement.on_conflict_do_update(
            index_elements=[Course.code],
            set_={
                "title": statement.excluded.title,
                "description": statement.excluded.description,
                "other_requirements": statement.excluded.other_requirements,
            },
        )
        session.execute(statement, list(courses.values()))

        # Replace the prereqs of the courses in this file, so a fixed CSV fixes the table.
        session.execute(delete(CoursePrereq).where(CoursePrereq.course_code.in_(list(courses))))
        if prereq_rows:
            session.execute(insert(CoursePrereq), prereq_rows)

        result.table_total = session.scalar(select(func.count()).select_from(Course))

    result.courses = len(courses)
    result.inserted = result.table_total - before
    result.with_description = sum(1 for course in courses.values() if course["description"])
    result.courses_with_prereqs = len({row["course_code"] for row in prereq_rows})
    result.prereq_rows = len(prereq_rows)
    return result
