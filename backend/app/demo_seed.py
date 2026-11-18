"""The three fake demo students for the Dec 7 demo. Run by db/scripts/seed_demo.py.

Each one is built around real Spring 2027 sections so the demo shows real results:
- Alex Rivera, Computer Science junior: the main demo. Lots of choices, real time
  overlaps (CSCI 4203 / MATH 3043-002 on MW 14:10), a full section (MATH 3043-001),
  a missing prereq (CSCI 4932 needs CSCI 4922), a prereq met by a course in progress
  (CSCI 3143 needs CSCI 3213).
- Jordan Brooks, General Business freshman in their first semester: almost everything
  "not met" or in progress. MGMT 2003 needs ENGL 1123 (missing prereq even if both are
  on the same schedule); ACCT 2003-001 and ECON 2103-001 overlap on MWF 09:00.
- Sam Okafor, Psychology senior: nearly done. Failed PSYC 3183 (an F row) and is
  retaking it, so anything counting completed courses must look at the grade.
- Returning Student (user 4 on the login page): filled by Connect mySAU and kept, across
  restarts, sign-outs and seed runs (`clear_returning` empties it).
- New Student (user 5): filled by Connect mySAU, emptied at startup, sign-in, sign-out and
  on every seed run, so it is a first-time student every time.

All names and emails are made up. Re-running updates the students in place (matched on
email) and replaces only their source='manual' course rows. Nothing is written unless
every degree plan and every course code is in the database.
"""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import (
    CalendarEvent,
    CompletedCourse,
    Course,
    DegreePlan,
    Schedule,
    Student,
    StudentPreferences,
    StudentRequirement,
    StudentSettings,
)

CATALOG_YEAR = "2026-2027"
DEMO_PASSWORD = "flowsaic-demo"  # plain demo password, fine for semester 1 (AGENTS.md)
CURRENT_TERM = "Fall 2026"  # what "in progress" means while registering for Spring 2027
NOT_EARNED = {"F", "W"}  # grades that do not earn credit


@dataclass(frozen=True)
class DemoCourse:
    code: str
    term: str
    grade: str | None = None  # None = in progress

    @property
    def status(self) -> str:
        return "in_progress" if self.grade is None else "completed"

    @property
    def credits(self) -> int:
        """SAU convention: the last digit of the course number is its credit hours."""
        return int(self.code[-1])


@dataclass(frozen=True)
class DemoStudent:
    name: str
    email: str
    plan_name: str
    classification: str
    courses: tuple[DemoCourse, ...] = field(default=())

    @property
    def earned_hours(self) -> int:
        return sum(c.credits for c in self.courses if c.grade is not None and c.grade not in NOT_EARNED)


def classification_for(earned_hours: int) -> str:
    """SAU classes by earned hours: under 30 freshman, 30-59 sophomore, 60-89 junior, 90+ senior."""
    if earned_hours >= 90:
        return "Senior"
    if earned_hours >= 60:
        return "Junior"
    if earned_hours >= 30:
        return "Sophomore"
    return "Freshman"


def _term(term: str, *rows: tuple[str, str | None] | str) -> list[DemoCourse]:
    """_term("Fall 2024", ("CSCI 2103", "A"), ...) ; a bare code is in progress."""
    return [DemoCourse(row, term) if isinstance(row, str) else DemoCourse(row[0], term, row[1]) for row in rows]


ALEX = DemoStudent(
    name="Alex Rivera",
    email="alex.rivera@demo.flowsaic.test",
    plan_name="Computer Science, BS",
    classification="Junior",
    courses=tuple(
        _term("Spring 2024", ("MATH 1023", "A"))  # high school concurrent credit; MATH 3043 needs it
        + _term("Fall 2024", ("GSTD 1002", "A"), ("ENGL 1113", "A"), ("MATH 1525", "B"), ("CSCI 2103", "A"),
              ("CSCI 2101", "A"), ("HIST 1013", "B"))
        + _term("Spring 2025", ("ENGL 1123", "B"), ("MATH 1545", "C"), ("CSCI 2113", "A"), ("CSCI 2111", "A"),
                ("PSCI 2003", "B"))
        + _term("Fall 2025", ("MATH 2033", "B"), ("CSCI 3103", "B"), ("BIOL 1043", "B"), ("BIOL 1041", "A"),
                ("ENGL 2223", "B"), ("CSCI 2001", "A"))
        + _term("Spring 2026", ("CSCI 3063", "B"), ("ART 2013", "A"), ("PSYC 2003", "A"), ("SPAN 1053", "B"),
                ("GEOG 2003", "A"))
        + _term(CURRENT_TERM, "CSCI 3213", "CSCI 3403", "HUM 2003", "SOC 2003")
    ),
)

JORDAN = DemoStudent(
    name="Jordan Brooks",
    email="jordan.brooks@demo.flowsaic.test",
    plan_name="Business Administration: General Business, BBA",
    classification="Freshman",
    courses=tuple(
        _term("Spring 2026", ("PSCI 2003", "A"))  # high school concurrent credit
        + _term(CURRENT_TERM, "GSTD 1002", "ENGL 1113", "MATH 1023", "ACCT 2113", "HIST 1013")
    ),
)

SAM = DemoStudent(
    name="Sam Okafor",
    email="sam.okafor@demo.flowsaic.test",
    plan_name="Psychology, BS",
    classification="Senior",
    courses=tuple(
        _term("Fall 2023", ("GSTD 1002", "A"), ("ENGL 1113", "B"), ("MATH 1023", "B"), ("PSYC 2003", "A"),
              ("HIST 1003", "B"))
        + _term("Spring 2024", ("ENGL 1123", "B"), ("BIOL 1043", "B"), ("BIOL 1041", "A"), ("SOC 2003", "A"),
                ("SPCH 1113", "B"), ("MUS 2013", "A"))
        + _term("Fall 2024", ("ENGL 2213", "B"), ("CHEM 1133", "C"), ("CHEM 1131", "B"), ("HIST 2013", "B"),
                ("PSYC 3223", "A"), ("SOC 1003", "A"))
        + _term("Spring 2025", ("THEA 2003", "A"), ("PSYC 3093", "B"), ("PSYC 3003", "A"), ("GEOL 1003", "B"),
                ("GEOL 1001", "A"), ("SPAN 1053", "B"))
        + _term("Fall 2025", ("PSYC 4033", "B"), ("PSYC 4073", "A"), ("PSYC 3123", "A"), ("SWK 2043", "A"),
                ("PHSC 2023", "B"), ("SPAN 1063", "B"))
        + _term("Spring 2026", ("PSYC 4093", "A"), ("PSYC 4063", "B"), ("PSYC 4163", "A"), ("ECON 2103", "B"),
                ("CRJU 2003", "A"), ("PSYC 3183", "F"))
        + _term(CURRENT_TERM, "PSYC 3183", "SPAN 2033", "HS 1403", "GEOG 2003")  # PSYC 3183 is the retake
    ),
)

DEMO_STUDENTS: tuple[DemoStudent, ...] = (ALEX, JORDAN, SAM)

# Two placeholder accounts for "Connect mySAU" (course schedule + the person's own degree
# audit). Neither has a public plan or fake courses; whatever they show came from mySAU.
#
# User 4, Returning Student: keeps what Connect mySAU saved, across restarts, sign-outs and
# seed runs, like a student coming back. `seed_demo.py --clear-returning` empties it (do
# that before a database dump is shared: it holds a real audit).
RETURNING_STUDENT_NAME = "Returning Student"
RETURNING_STUDENT_EMAIL = "returning.student@demo.flowsaic.test"
# User 4's email before Nov 17. The seed renames that row to the returning student, so an
# audit already connected on it is kept.
OLD_NEW_STUDENT_EMAIL = "new.student@demo.flowsaic.test"

# User 5, New Student: a first-time student every time. Emptied (audit, courses, saved
# schedules) when the backend starts, when they sign in and when they sign out.
NEW_STUDENT_NAME = "New Student"
NEW_STUDENT_EMAIL = "new.user@demo.flowsaic.test"

# Accounts that start with a placeholder name. Connect mySAU replaces it with the student's
# first and last name from their audit; emptying the account puts the placeholder back.
PLACEHOLDER_EMAILS = frozenset({RETURNING_STUDENT_EMAIL, NEW_STUDENT_EMAIL})
PLACEHOLDER_NAMES = frozenset({RETURNING_STUDENT_NAME, NEW_STUDENT_NAME})

# The student fields Connect mySAU fills in, emptied.
EMPTY_AUDIT_FIELDS = {
    "degree_plan_id": None,
    "classification": None,
    "major": None,
    "catalog_year": None,
    "has_hold": False,
    "total_hours_earned": None,
    "total_hours_needed": None,
    "audit_refreshed_at": None,
}


class SeedError(Exception):
    """Something the seed needs is not in the database. Nothing was written."""


@dataclass
class SeededStudent:
    name: str
    email: str
    plan_name: str
    classification: str
    completed: int
    in_progress: int
    earned_hours: int


def _clear_student(session, student_id, placeholder_name: str | None = None) -> None:
    """Empty one student's record: courses, audit requirements, saved schedules (their
    sections go with them), calendar events, scheduling preferences, settings (photo included)
    and the audit fields. With placeholder_name, the name (from their audit) goes back to it.
    Email and password stay."""
    for model in (CompletedCourse, StudentRequirement, Schedule, CalendarEvent, StudentPreferences, StudentSettings):
        session.execute(delete(model).where(model.student_id == student_id))
    name = {"name": placeholder_name} if placeholder_name else {}
    session.execute(update(Student).where(Student.id == student_id).values(**EMPTY_AUDIT_FIELDS, **name))


def clear_new_student(only_if: uuid.UUID | None = None) -> bool:
    """Empty user 5 (New Student). Called at startup, sign-in and sign-out.

    With only_if, do it only when that student is user 5 (sign-out passes whoever it was).
    True if user 5 was emptied.
    """
    with SessionLocal() as session, session.begin():
        student_id = session.scalar(select(Student.id).where(Student.email == NEW_STUDENT_EMAIL))
        if student_id is None or (only_if is not None and student_id != only_if):
            return False
        _clear_student(session, student_id, NEW_STUDENT_NAME)
        return True


def _upsert_placeholder(session, name: str, email: str) -> uuid.UUID:
    """Create the account, or reset its password only: never its data, and never the name
    Connect mySAU gave it (clearing the account puts the placeholder name back)."""
    values = {"name": name, "email": email, "password": DEMO_PASSWORD}
    return session.scalar(
        insert(Student)
        .values(**values, **EMPTY_AUDIT_FIELDS)
        .on_conflict_do_update(index_elements=[Student.email], set_={"password": DEMO_PASSWORD})
        .returning(Student.id)
    )


def _seed_returning_student(session, clear: bool) -> SeededStudent:
    """User 4. Keeps its mySAU data unless clear=True."""
    if session.scalar(select(Student.id).where(Student.email == RETURNING_STUDENT_EMAIL)) is None:
        # The old user 4 becomes the returning student, with whatever it connected.
        session.execute(
            update(Student).where(Student.email == OLD_NEW_STUDENT_EMAIL)
            .values(email=RETURNING_STUDENT_EMAIL, name=RETURNING_STUDENT_NAME)
        )
    student_id = _upsert_placeholder(session, RETURNING_STUDENT_NAME, RETURNING_STUDENT_EMAIL)
    if clear:
        _clear_student(session, student_id, RETURNING_STUDENT_NAME)
    student = session.get(Student, student_id)
    session.refresh(student)
    statuses = list(session.scalars(
        select(CompletedCourse.status).where(CompletedCourse.student_id == student_id)
    ))
    return SeededStudent(
        RETURNING_STUDENT_NAME, RETURNING_STUDENT_EMAIL,  # the label, never a real name from an audit
        f"{student.major} (from their mySAU audit)" if student.audit_refreshed_at else "(none until Connect mySAU)",
        student.classification or "-",
        statuses.count("completed"), statuses.count("in_progress"),
        int(student.total_hours_earned or 0),
    )


def _reset_new_student(session) -> SeededStudent:
    """User 5: create it, or empty it."""
    _clear_student(session, _upsert_placeholder(session, NEW_STUDENT_NAME, NEW_STUDENT_EMAIL), NEW_STUDENT_NAME)
    return SeededStudent(NEW_STUDENT_NAME, NEW_STUDENT_EMAIL, "(none until Connect mySAU)", "-", 0, 0, 0)


def seed_demo_students(
    students: tuple[DemoStudent, ...] = DEMO_STUDENTS, *, clear_returning: bool = False
) -> list[SeededStudent]:
    """Upsert the demo students and replace their manual course rows, create or keep the
    returning student (user 4; emptied only with clear_returning) and reset the new student
    (user 5), in one transaction."""
    results: list[SeededStudent] = []
    with SessionLocal() as session, session.begin():
        plans = dict(
            session.execute(
                select(DegreePlan.name, DegreePlan.id).where(
                    DegreePlan.catalog_year == CATALOG_YEAR,
                    DegreePlan.name.in_({s.plan_name for s in students}),
                )
            ).all()
        )
        missing_plans = sorted({s.plan_name for s in students} - set(plans))
        if missing_plans:
            raise SeedError(
                f"degree plans not loaded for {CATALOG_YEAR}: {', '.join(missing_plans)}. "
                "Run scrape_degree_maps.py first."
            )
        codes = {c.code for s in students for c in s.courses}
        known = set(session.scalars(select(Course.code).where(Course.code.in_(codes))))
        if codes - known:
            raise SeedError(
                f"courses not in the courses table: {', '.join(sorted(codes - known))}. "
                "Run load_course_info.py and import_sections.py first."
            )

        for student in students:
            values = {
                "name": student.name,
                "email": student.email,
                "password": DEMO_PASSWORD,
                "degree_plan_id": plans[student.plan_name],
                "classification": student.classification,
                "major": student.plan_name,
                "catalog_year": CATALOG_YEAR,
                "has_hold": False,
            }
            student_id = session.scalar(
                insert(Student)
                .values(**values)
                .on_conflict_do_update(index_elements=[Student.email], set_=values)
                .returning(Student.id)
            )
            session.execute(
                delete(CompletedCourse).where(
                    CompletedCourse.student_id == student_id, CompletedCourse.source == "manual"
                )
            )
            session.add_all(
                CompletedCourse(
                    student_id=student_id,
                    course_code=course.code,
                    status=course.status,
                    grade=course.grade,
                    credits=course.credits,
                    term=course.term,
                    source="manual",
                )
                for course in student.courses
            )
            results.append(
                SeededStudent(
                    name=student.name,
                    email=student.email,
                    plan_name=student.plan_name,
                    classification=student.classification,
                    completed=sum(c.status == "completed" for c in student.courses),
                    in_progress=sum(c.status == "in_progress" for c in student.courses),
                    earned_hours=student.earned_hours,
                )
            )
        results.append(_seed_returning_student(session, clear_returning))
        results.append(_reset_new_student(session))
    return results
