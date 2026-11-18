"""The schedule checker: the ONE function that decides whether a schedule is valid,
whether the student built it or Flow did (AGENTS.md, contract v2). The AI never decides.

Input: a student and a list of sections. Output: { "conflicts": [...], "warnings": [...] }.
Conflicts block saving; warnings don't. Each item: { code, section_ids, message }.

| Check                                                        | Result   | Code              |
| Two sections meet on the same day at overlapping times       | Conflict | time_overlap      |
| A prereq group has no option passed or in progress           | Conflict | missing_prereq    |
| Same course added twice                                      | Conflict | duplicate_course  |
| Course already passed                                        | Warning  | already_completed |
| Section is full                                              | Warning  | section_full      |
| Course isn't on the student's plan                           | Warning  | not_on_plan       |
| Total credits over 18                                        | Warning  | over_credit_limit |
| A section meets during a fixed calendar event                | Conflict | commitment_overlap |
| A section meets during a flexible calendar event             | Warning  | commitment_overlap_flexible |

Overlap: same day and start_a < end_b and start_b < end_a. Online/TBA sections (no days or
times) never overlap. Lecture/lab pairing isn't enforced. F and W never count as passed.
A course in the same schedule doesn't satisfy a prereq (it has to be passed or in progress).
Calendar events have a weekday, not a date, so every event is a weekly block. Commitment
messages name the event's category, never its title (titles are the student's own words,
and checker messages also go to Gemini). Commitment items also carry the event's id.

check_schedule() is pure; load_check_context() reads the database.
"""

import uuid
from dataclasses import dataclass, field
from datetime import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    CalendarEvent,
    CompletedCourse,
    Course,
    CoursePrereq,
    RequirementCourse,
    RequirementGroup,
    Section,
    Student,
    StudentRequirement,
)
from app.normalize import COURSE_CODE_RE, DAY_ORDER
from app.progress import Elective, Taken, credits_from_code, parse_electives, split_taken

CREDIT_LIMIT = 18


@dataclass
class SectionInfo:
    id: uuid.UUID
    code: str
    section_number: str
    title: str | None
    credits: float
    days: str | None
    start: time | None
    end: time | None
    instructor: str
    enrolled: int
    capacity: int
    term_id: uuid.UUID | None = None
    location: str | None = None

    @property
    def label(self) -> str:
        return f"{self.code}-{self.section_number}"

    @property
    def seats_open(self) -> int:
        return max(self.capacity - self.enrolled, 0)

    @property
    def meets(self) -> bool:
        """Online/TBA sections have no meeting time and never overlap."""
        return bool(self.days and self.start and self.end)


@dataclass
class PlanScope:
    """What counts as 'on the plan' for not_on_plan. None = the student has no plan yet."""

    codes: set[str]
    electives: list[Elective] = field(default_factory=list)
    has_open_electives: bool = False

    def covers(self, code: str) -> bool:
        return code in self.codes or any(e.matches(code) for e in self.electives if e.prefixes or e.level)


@dataclass
class Commitment:
    """A calendar event as the checker sees it: a weekly block, fixed or flexible."""

    id: uuid.UUID
    day: str  # one letter of MTWRF
    start: time
    end: time
    category: str
    fixed: bool

    @property
    def what(self) -> str:
        kind = CATEGORY_WORDS.get(self.category, "personal")
        return f"{kind} commitment" if self.fixed else f"flexible {kind} commitment"


CATEGORY_WORDS = {"work": "work", "personal_study": "personal/study", "extracurricular": "extracurricular"}


@dataclass
class StudentContext:
    passed: dict[str, float]
    in_progress: dict[str, float]
    prereqs: dict[str, list[list[str]]]
    plan: PlanScope | None
    commitments: list[Commitment] = field(default_factory=list)


def ordered_days(days: set[str]) -> str:
    return "".join(d for d in DAY_ORDER if d in days)


def overlap(a: SectionInfo, b: SectionInfo) -> str | None:
    """The shared days if a and b meet at the same time, else None."""
    if not (a.meets and b.meets):
        return None
    common = set(a.days) & set(b.days)
    if common and a.start < b.end and b.start < a.end:
        return ordered_days(common)
    return None


def item(code: str, sections: list[SectionInfo], message: str, event_ids: list[uuid.UUID] | None = None) -> dict:
    """One conflict or warning. Commitment items also carry event_ids."""
    result = {"code": code, "section_ids": [s.id for s in sections], "message": message}
    if event_ids:
        result["event_ids"] = event_ids
    return result


def meets_during(section: SectionInfo, commitment: Commitment) -> bool:
    return (section.meets and commitment.day in section.days
            and section.start < commitment.end and commitment.start < section.end)


def hours_text(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


def check_schedule(sections: list[SectionInfo], student: StudentContext, credit_limit: int = CREDIT_LIMIT) -> dict:
    conflicts: list[dict] = []
    warnings: list[dict] = []

    # time_overlap: every pair once.
    for i, a in enumerate(sections):
        for b in sections[i + 1:]:
            if a.code == b.code:
                continue  # reported as duplicate_course instead
            days = overlap(a, b)
            if days:
                start = max(a.start, b.start)
                conflicts.append(item("time_overlap", [a, b],
                                      f"{a.code} and {b.code} overlap on {days} {start:%H:%M}"))

    # duplicate_course: the same course in more than one section.
    by_code: dict[str, list[SectionInfo]] = {}
    for section in sections:
        by_code.setdefault(section.code, []).append(section)
    for code, group in by_code.items():
        if len(group) > 1:
            numbers = " and ".join(s.section_number for s in group)
            conflicts.append(item("duplicate_course", group, f"{code} is in this schedule more than once (sections {numbers})"))

    for code, group in by_code.items():
        # missing_prereq
        missing = [options for options in student.prereqs.get(code, [])
                   if not any(o in student.passed or o in student.in_progress for o in options)]
        if missing:
            needs = " and ".join(" or ".join(options) for options in missing)
            conflicts.append(item("missing_prereq", group, f"{code} needs {needs} (passed or in progress)"))
        # already_completed
        if code in student.passed:
            warnings.append(item("already_completed", group, f"You already passed {code}"))
        # not_on_plan
        if student.plan is not None and not student.plan.covers(code):
            extra = " (it would count as a general elective)" if student.plan.has_open_electives else ""
            warnings.append(item("not_on_plan", group, f"{code} isn't on your degree plan{extra}"))
        for section in group:
            # section_full
            if section.capacity and section.enrolled >= section.capacity:
                warnings.append(item("section_full", [section],
                                     f"{section.label} is full ({section.enrolled}/{section.capacity} enrolled)"))

    # commitment_overlap (fixed events) / commitment_overlap_flexible (the rest).
    for section in sections:
        for c in student.commitments:
            if meets_during(section, c):
                when = f"{c.day} {c.start:%H:%M}-{c.end:%H:%M}"
                if c.fixed:
                    conflicts.append(item("commitment_overlap", [section],
                                          f"{section.label} meets during your {c.what} ({when})", [c.id]))
                else:
                    warnings.append(item("commitment_overlap_flexible", [section],
                                         f"{section.label} overlaps your {c.what} ({when})", [c.id]))

    # over_credit_limit: each course once.
    total = sum(group[0].credits for group in by_code.values())
    if total > credit_limit:
        warnings.append(item("over_credit_limit", sections,
                             f"{hours_text(total)} credits is over the {credit_limit}-credit limit"))
    return {"conflicts": conflicts, "warnings": warnings}


# --- database --------------------------------------------------------------------------------

class SectionNotFound(LookupError):
    pass


class SectionNotInTerm(ValueError):
    pass


def section_info(section: Section, course: Course) -> SectionInfo:
    return SectionInfo(
        id=section.id,
        code=course.code,
        section_number=section.section_number,
        title=course.title,
        credits=float(course.credits) if course.credits is not None else credits_from_code(course.code),
        days=section.days,
        start=section.start_time,
        end=section.end_time,
        instructor=section.instructor or "Staff",
        enrolled=section.enrolled or 0,
        capacity=section.capacity or 0,
        term_id=section.term_id,
        location=section.location,
    )


def load_sections(session, section_ids: list[uuid.UUID], term_id: uuid.UUID | None = None) -> list[SectionInfo]:
    """The sections in the order given. Unknown or inactive -> SectionNotFound."""
    rows = {
        section.id: section_info(section, course)
        for section, course in session.execute(
            select(Section, Course).join(Course, Course.id == Section.course_id)
            .where(Section.id.in_(section_ids), Section.active.is_(True))
        )
    }
    missing = [sid for sid in section_ids if sid not in rows]
    if missing:
        raise SectionNotFound(missing)
    if term_id is not None and any(rows[sid].term_id != term_id for sid in section_ids):
        raise SectionNotInTerm
    return [rows[sid] for sid in section_ids]


def load_student_context(session, student_id: uuid.UUID) -> StudentContext:
    student = session.get(Student, student_id)
    if student is None:
        raise LookupError("student not found")
    taken = [Taken(r.course_code, r.status, r.grade, float(r.credits) if r.credits is not None else None)
             for r in session.scalars(select(CompletedCourse).where(CompletedCourse.student_id == student_id))]
    passed, in_progress = split_taken(taken)

    prereqs: dict[str, dict[int, list[str]]] = {}
    for code, group, requires in session.execute(
        select(CoursePrereq.course_code, CoursePrereq.option_group, CoursePrereq.requires_code)
    ):
        prereqs.setdefault(code, {}).setdefault(group, []).append(requires)

    audit = session.scalars(select(StudentRequirement).where(StudentRequirement.student_id == student_id)).all()
    plan: PlanScope | None = None
    if audit:
        codes = {c for r in audit for c in (r.course_options or []) if COURSE_CODE_RE.fullmatch(c)}
        plan = PlanScope(codes, [], has_open_electives=any("elective" in r.name.lower() for r in audit))
    elif student.degree_plan_id is not None:
        groups = session.scalars(select(RequirementGroup).where(RequirementGroup.degree_plan_id == student.degree_plan_id)).all()
        codes = set(session.scalars(
            select(RequirementCourse.course_code).join(RequirementGroup, RequirementGroup.id == RequirementCourse.group_id)
            .where(RequirementGroup.degree_plan_id == student.degree_plan_id)
        ))
        electives = [e for g in groups for e in parse_electives(g.note)]
        plan = PlanScope(codes, electives, has_open_electives=any(e.unrestricted for e in electives))
    commitments = [
        Commitment(e.id, e.day, e.start_time, e.end_time, e.category, e.fixed)
        for e in session.scalars(select(CalendarEvent).where(CalendarEvent.student_id == student_id))
    ]
    return StudentContext(passed, in_progress,
                          {code: [groups_[k] for k in sorted(groups_)] for code, groups_ in prereqs.items()}, plan,
                          commitments)


def check_for_student(student_id: uuid.UUID, section_ids: list[uuid.UUID], term_id: uuid.UUID | None = None) -> dict:
    with SessionLocal() as session:
        sections = load_sections(session, section_ids, term_id)
        context = load_student_context(session, student_id)
    return check_schedule(sections, context)

