"""Import a course schedule export (mySAU Course Schedule -> Export -> CSV).

Shared by mySAU connect and db/scripts/import_sections.py, so both normalize the same way:
- Times '09:00:AM' -> 09:00, days 'M W F' -> 'MWF', credits '3.0' -> 3. Blank = online/TBA.
- The last token of course_section is the section ('001', '002L'); the rest is the course.
- Sections whose title starts with CANCELED are skipped. Bad rows are reported, never guessed.
- One meeting time per section: the row with the most days is kept (ties: first in file).

Loading (Nov 17):
- Sections upsert by (course, term, section number) and are marked active.
- A section of an exported term that is missing from the export is set active=false,
  never deleted, because saved schedules point at it.
- The export's term becomes terms.is_current_registration; every other term is cleared.
- A course not in the catalog gets a minimal row and is reported as having no description.
"""

import io
import re
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import Course, Section, Term
from app.normalize import (
    normalize_days,
    parse_count,
    parse_credits,
    parse_export_time,
    parse_term,
    split_course_section,
)

REQUIRED_COLUMNS = [
    "course_section", "title", "term", "department", "start_time", "end_time", "days",
    "campus", "building", "room", "instructor", "level", "credits", "enrolled", "capacity",
]  # fmt: skip
SECTION_UPDATE_FIELDS = [
    "instructor", "location", "building", "room", "days", "start_time", "end_time",
    "division", "enrolled", "capacity",
]  # fmt: skip


class ExportNotUnderstood(ValueError):
    pass


@dataclass
class ParsedExport:
    rows_read: int = 0
    sections: list[dict] = field(default_factory=list)
    courses: dict[str, dict] = field(default_factory=dict)
    terms: dict[str, str] = field(default_factory=dict)  # code -> name
    credit_conflicts: set[str] = field(default_factory=set)
    extra_meetings: list[str] = field(default_factory=list)
    canceled: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    parsed: ParsedExport
    new_sections: int = 0
    deactivated: int = 0
    new_course_codes: list[str] = field(default_factory=list)
    new_courses_without_description: list[str] = field(default_factory=list)
    sections_total: int = 0


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


RAW_COLUMNS = REQUIRED_COLUMNS + ["concurrent"]
RIGHT_FIELDS = 12  # start_time .. concurrent: never contain commas
TERM_FIELD = re.compile(r"^\d{4}-\d{4} - [A-Za-z ]+$")


def split_raw_row(line: str) -> dict:
    """One row of mySAU's raw export -> named fields. Raises ValueError if it can't.

    The raw export (Course Schedule -> Export -> CSV, checked Nov 17) has no header and
    does not quote fields, but titles and departments can contain commas
    ("Heating, Ventilation, & A/C", "Dept of Accounting, Finance, & Economics"). The term
    ("2026-2027 - Spring") and the last 12 fields are fixed, so the row is split around them.
    """
    parts = line.split(",")
    term_at = next((i for i, part in enumerate(parts[2:], start=2) if TERM_FIELD.match(part.strip())), None)
    if term_at is None or len(parts) < term_at + 1 + 1 + RIGHT_FIELDS:
        raise ValueError("row does not have the export's 16 fields")
    return dict(
        zip(
            RAW_COLUMNS,
            [parts[0], ",".join(parts[1:term_at]), parts[term_at], ",".join(parts[term_at + 1 : -RIGHT_FIELDS]),
             *parts[-RIGHT_FIELDS:]],
            strict=True,
        )
    )


def read_export(data: bytes) -> pd.DataFrame:
    """The export file's bytes -> a table of strings. Read in memory, never saved.

    Two layouts: mySAU's raw export (no header, unquoted commas) and a CSV with a header
    row (data/sections_spring_2027.csv). Each row keeps its file line number in _line;
    a raw row that can't be split carries the reason in _problem.
    """
    if data.lstrip()[:1] == b"<":
        raise ExportNotUnderstood("the export is an HTML table, not a CSV")
    text = data.decode("utf-8-sig", errors="replace")
    first_line = text.lstrip().split("\n", 1)[0]
    if first_line.split(",")[0].strip().lower() == "course_section":
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        frame.columns = [column.strip() for column in frame.columns]
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ExportNotUnderstood(f"the export is missing columns: {missing}")
        frame["_line"] = range(2, len(frame) + 2)  # line 1 is the header
        frame["_problem"] = ""
        return frame

    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = split_raw_row(line)
            row["_problem"] = ""
        except ValueError as error:
            row = {column: "" for column in RAW_COLUMNS} | {"course_section": line[:40], "_problem": str(error)}
        row["_line"] = number
        rows.append(row)
    if rows and all(row["_problem"] for row in rows):
        raise ExportNotUnderstood("no row has the export's 16 fields")
    return pd.DataFrame(rows, columns=RAW_COLUMNS + ["_line", "_problem"], dtype=object)


def parse_export(frame: pd.DataFrame) -> ParsedExport:
    result = ParsedExport(rows_read=len(frame))
    by_section: dict[tuple[str, str, str], list[dict]] = {}
    for row in frame.to_dict("records"):
        line = int(row["_line"])
        try:
            if row["_problem"]:
                raise ValueError(row["_problem"])
            parsed = parse_row(row)
        except ValueError as error:
            message = f"line {line}: {row['course_section']!r} {row['title']!r} - {error}"
            (result.canceled if str(error) == "canceled section" else result.rejected).append(message)
            continue
        parsed["line"] = line
        key = (parsed["term_code"], parsed["course_code"], parsed["section_number"])
        by_section.setdefault(key, []).append(parsed)

    for rows in by_section.values():
        main_row = max(rows, key=lambda parsed: (len(parsed["days"] or ""), -parsed["line"]))
        result.sections.append(main_row)
        for other in rows:
            if other is not main_row:
                result.extra_meetings.append(
                    f"line {other['line']}: {other['course_code']} {other['section_number']} - "
                    f"not loaded: {describe_meeting(other)}  (kept: {describe_meeting(main_row)})"
                )

    for parsed in result.sections:
        course = result.courses.setdefault(
            parsed["course_code"],
            {
                "code": parsed["course_code"],
                "title": parsed["title"],
                "department": parsed["department"],
                "credits": parsed["credits"],
            },
        )
        if course["credits"] != parsed["credits"]:
            result.credit_conflicts.add(parsed["course_code"])
    for code in result.credit_conflicts:
        result.courses[code]["credits"] = None  # sections disagree, so don't pick one

    result.terms = {parsed["term_code"]: parsed["term_name"] for parsed in result.sections}
    return result


def apply_export(parsed: ParsedExport) -> ImportResult:
    """Write a parsed export to the database in one transaction."""
    if not parsed.sections:
        raise ExportNotUnderstood("the export has no usable sections")
    result = ImportResult(parsed)
    with SessionLocal.begin() as session:
        sections_before = session.scalar(select(func.count()).select_from(Section))
        known = dict(session.execute(select(Course.code, Course.description)).all())
        result.new_course_codes = sorted(set(parsed.courses) - set(known))
        result.new_courses_without_description = list(result.new_course_codes)

        term_insert = insert(Term)
        session.execute(
            term_insert.on_conflict_do_update(
                index_elements=[Term.code], set_={"name": term_insert.excluded.name}
            ),
            [{"code": code, "name": name} for code, name in parsed.terms.items()],
        )
        term_ids = dict(session.execute(select(Term.code, Term.id)).all())
        export_term_ids = [term_ids[code] for code in parsed.terms]
        session.execute(
            update(Term).values(is_current_registration=Term.id.in_(export_term_ids))
        )

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
            list(parsed.courses.values()),
        )
        course_ids = dict(session.execute(select(Course.code, Course.id)).all())

        rows = [
            {
                "course_id": course_ids[row["course_code"]],
                "term_id": term_ids[row["term_code"]],
                "section_number": row["section_number"],
                "active": True,
                **{name: row[name] for name in SECTION_UPDATE_FIELDS},
            }
            for row in parsed.sections
        ]
        section_insert = insert(Section)
        loaded_ids = session.scalars(
            section_insert.on_conflict_do_update(
                index_elements=[Section.course_id, Section.term_id, Section.section_number],
                set_={
                    "active": True,
                    **{name: section_insert.excluded[name] for name in SECTION_UPDATE_FIELDS},
                },
            ).returning(Section.id),
            rows,
        ).all()

        # Missing from the export: kept for saved schedules, but no longer offered.
        deactivated = session.execute(
            update(Section)
            .where(
                Section.term_id.in_(export_term_ids),
                Section.active.is_(True),
                Section.id.not_in(loaded_ids),
            )
            .values(active=False)
        )
        result.deactivated = deactivated.rowcount
        result.sections_total = session.scalar(select(func.count()).select_from(Section))
    result.new_sections = result.sections_total - sections_before
    return result


def import_export_bytes(data: bytes) -> ImportResult:
    return apply_export(parse_export(read_export(data)))
