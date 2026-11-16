"""Load data/sections_spring_2027.csv (SAU export) into terms, courses and sections.

Run from backend/:  uv run python ..\\db\\scripts\\import_sections.py [path-to-csv]

Re-running updates rows instead of duplicating them:
- terms are matched on code, courses on code, sections on (course, term, section number).
- courses already in the catalog only get department and credits filled in. A course
  that is not in the catalog gets a minimal row (code, title, department, credits).

Rules (decided Nov 16):
- The "concurrent" column is ignored.
- Sections whose title starts with CANCELED are printed and skipped.
- The sections table holds one meeting time per section. When the export lists a section
  on several rows (several meeting times), the row with the most meeting days is loaded
  and the other rows are printed as "extra meeting time, not loaded".
- Bad rows are printed and skipped, never guessed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.config import REPO_DIR  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Course, Section, Term  # noqa: E402
from app.normalize import (  # noqa: E402
    normalize_days,
    parse_count,
    parse_credits,
    parse_export_time,
    parse_term,
    split_course_section,
)

DEFAULT_PATH = REPO_DIR / "data" / "sections_spring_2027.csv"
REQUIRED_COLUMNS = [
    "course_section", "title", "term", "department", "start_time", "end_time", "days",
    "campus", "building", "room", "instructor", "level", "credits", "enrolled", "capacity",
]  # fmt: skip
SECTION_UPDATE_FIELDS = [
    "instructor", "location", "building", "room", "days", "start_time", "end_time",
    "division", "enrolled", "capacity",
]  # fmt: skip


def parse_row(row: dict) -> dict:
    """Turn one export row into clean values. Raises ValueError with the reason if it can't."""
    title = row["title"].strip()
    if not title:
        raise ValueError("blank title")
    if title.upper().startswith("CANCELED"):
        raise ValueError("canceled section")

    course_code, section_number = split_course_section(row["course_section"])
    term_code, term_name = parse_term(row["term"])
    start_time = parse_export_time(row["start_time"])
    end_time = parse_export_time(row["end_time"])
    if (start_time is None) != (end_time is None):
        raise ValueError("only one of start_time / end_time is given")
    if start_time is not None and start_time >= end_time:
        raise ValueError("start_time is not before end_time")

    return {
        "course_code": course_code,
        "section_number": section_number,
        "term_code": term_code,
        "term_name": term_name,
        "title": title,
        "department": row["department"].strip() or None,
        "credits": parse_credits(row["credits"]),
        "instructor": row["instructor"].strip() or "Staff",
        "location": row["campus"].strip() or None,
        "building": row["building"].strip() or None,
        "room": row["room"].strip() or None,
        "days": normalize_days(row["days"]),
        "start_time": start_time,
        "end_time": end_time,
        "division": row["level"].strip() or None,
        "enrolled": parse_count(row["enrolled"], "enrolled"),
        "capacity": parse_count(row["capacity"], "capacity"),
    }


def describe_meeting(parsed: dict) -> str:
    if parsed["start_time"] is None:
        return f"{parsed['days'] or 'no days'}, no time ({parsed['building'] or 'no building'})"
    return f"{parsed['days'] or 'no days'} {parsed['start_time']:%H:%M}-{parsed['end_time']:%H:%M}"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        sys.exit(f"{path.name} is missing columns: {missing}")

    rejected: list[str] = []
    canceled: list[str] = []
    by_section: dict[tuple[str, str, str], list[dict]] = {}

    for line, row in enumerate(frame.to_dict("records"), start=2):  # line 1 is the header
        try:
            parsed = parse_row(row)
        except ValueError as error:
            message = f"  line {line}: {row['course_section']!r} {row['title']!r} - {error}"
            (canceled if str(error) == "canceled section" else rejected).append(message)
            continue
        parsed["line"] = line
        key = (parsed["term_code"], parsed["course_code"], parsed["section_number"])
        by_section.setdefault(key, []).append(parsed)

    # One row per section: keep the meeting with the most days (ties: first in the file).
    sections: list[dict] = []
    extra_meetings: list[str] = []
    for rows in by_section.values():
        main_row = max(rows, key=lambda parsed: (len(parsed["days"] or ""), -parsed["line"]))
        sections.append(main_row)
        for other in rows:
            if other is not main_row:
                extra_meetings.append(
                    f"  line {other['line']}: {other['course_code']} {other['section_number']} - "
                    f"not loaded: {describe_meeting(other)}  (kept: {describe_meeting(main_row)})"
                )

    # One course row per code. Department and credits come from its sections.
    courses: dict[str, dict] = {}
    credit_conflicts: set[str] = set()
    for parsed in sections:
        course = courses.setdefault(
            parsed["course_code"],
            {
                "code": parsed["course_code"],
                "title": parsed["title"],
                "department": parsed["department"],
                "credits": parsed["credits"],
            },
        )
        if course["credits"] != parsed["credits"]:
            credit_conflicts.add(parsed["course_code"])
    for code in credit_conflicts:
        courses[code]["credits"] = None  # sections disagree, so don't pick one

    terms = {parsed["term_code"]: parsed["term_name"] for parsed in sections}

    with SessionLocal.begin() as session:
        sections_before = session.scalar(select(func.count()).select_from(Section))
        known_codes = set(session.scalars(select(Course.code)))
        new_course_codes = sorted(set(courses) - known_codes)

        term_insert = insert(Term)
        session.execute(
            term_insert.on_conflict_do_update(
                index_elements=[Term.code], set_={"name": term_insert.excluded.name}
            ),
            [{"code": code, "name": name} for code, name in terms.items()],
        )
        term_ids = dict(session.execute(select(Term.code, Term.id)).all())

        course_insert = insert(Course)
        session.execute(
            course_insert.on_conflict_do_update(
                index_elements=[Course.code],
                # The catalog title wins: an existing course keeps its title and description.
                set_={
                    "department": course_insert.excluded.department,
                    "credits": course_insert.excluded.credits,
                },
            ),
            list(courses.values()),
        )
        course_ids = dict(session.execute(select(Course.code, Course.id)).all())

        section_insert = insert(Section)
        session.execute(
            section_insert.on_conflict_do_update(
                index_elements=[Section.course_id, Section.term_id, Section.section_number],
                set_={field: section_insert.excluded[field] for field in SECTION_UPDATE_FIELDS},
            ),
            [
                {
                    "course_id": course_ids[parsed["course_code"]],
                    "term_id": term_ids[parsed["term_code"]],
                    "section_number": parsed["section_number"],
                    **{field: parsed[field] for field in SECTION_UPDATE_FIELDS},
                }
                for parsed in sections
            ],
        )
        sections_after = session.scalar(select(func.count()).select_from(Section))

    new_sections = sections_after - sections_before
    no_time = sum(1 for parsed in sections if parsed["start_time"] is None)
    print(f"File: {path}")
    print(f"Rows read:                        {len(frame)}")
    print(f"Terms:                            {', '.join(f'{name} ({code})' for code, name in terms.items())}")
    print(f"Sections loaded:                  {len(sections)}  ({new_sections} new, {len(sections) - new_sections} updated)")
    print(f"  with a meeting time:            {len(sections) - no_time}")
    print(f"  online or TBA (no time):        {no_time}")
    print(f"Courses offered this term:        {len(courses)}")
    print(f"  already in the courses table:   {len(courses) - len(new_course_codes)}  (department and credits filled in)")
    print(f"  not in the courses table, minimal row created now: {len(new_course_codes)}")
    if new_course_codes:
        print(f"    {', '.join(new_course_codes)}")
    if credit_conflicts:
        print(f"Courses whose sections disagree on credits (credits left blank): {sorted(credit_conflicts)}")
    print(f"Sections in the table now:        {sections_after}")
    print(f"Extra meeting rows, not loaded:   {len(extra_meetings)}")
    for message in extra_meetings:
        print(message)
    print(f"Canceled sections, skipped:       {len(canceled)}")
    for message in canceled:
        print(message)
    print(f"Rejected rows:                    {len(rejected)}")
    for message in rejected:
        print(message)


if __name__ == "__main__":
    main()
