"""Load data/course_info.csv into courses and course_prereqs.

Run from backend/:  uv run python ..\\db\\scripts\\load_course_info.py [path-to-csv]

Re-running updates rows instead of duplicating them:
- courses are matched on code; title, description and other_requirements are updated.
  department and credits are left alone (they come from import_sections.py).
- each course's prereq rows are replaced with what the file says now.
Bad rows are printed and skipped, never guessed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.config import REPO_DIR  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Course, CoursePrereq  # noqa: E402
from app.normalize import normalize_course_code, parse_prereqs  # noqa: E402

DEFAULT_PATH = REPO_DIR / "data" / "course_info.csv"
REQUIRED_COLUMNS = ["code", "title", "description", "prereqs", "other_requirements"]


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        sys.exit(f"{path.name} is missing columns: {missing}")

    courses: dict[str, dict] = {}
    prereq_rows: list[dict] = []
    rejected: list[str] = []

    for line, row in enumerate(frame.to_dict("records"), start=2):  # line 1 is the header
        try:
            code = normalize_course_code(row["code"])
            title = row["title"].strip()
            if not title:
                raise ValueError("blank title")
            if code in courses:
                raise ValueError(f"duplicate course code {code}")
            groups = parse_prereqs(row["prereqs"])
        except ValueError as error:
            rejected.append(f"  line {line}: {row['code']!r} - {error}")
            continue

        courses[code] = {
            "code": code,
            "title": title,
            "description": row["description"].strip() or None,
            "other_requirements": row["other_requirements"].strip() or None,
        }
        for option_group, options in enumerate(groups, start=1):
            for requires_code in options:
                prereq_rows.append(
                    {"course_code": code, "option_group": option_group, "requires_code": requires_code}
                )

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

        after = session.scalar(select(func.count()).select_from(Course))

    inserted = after - before
    with_description = sum(1 for course in courses.values() if course["description"])
    print(f"File: {path}")
    print(f"Rows read:                  {len(frame)}")
    print(f"Courses loaded:             {len(courses)}  ({inserted} new, {len(courses) - inserted} updated)")
    print(f"  with a description:       {with_description}")
    print(f"  without a description:    {len(courses) - with_description}")
    print(f"Courses with prereqs:       {len({row['course_code'] for row in prereq_rows})}")
    print(f"Prereq rows loaded:         {len(prereq_rows)}")
    print(f"Courses in the table now:   {after}")
    print(f"Rejected rows:              {len(rejected)}")
    for message in rejected:
        print(message)


if __name__ == "__main__":
    main()
