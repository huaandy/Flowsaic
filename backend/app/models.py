"""SQLAlchemy models for the AGENTS.md data model, plus doc_chunks for RAG.

Schema changes go through Alembic migrations only (ground rule 1).
IDs are UUIDs. SAU codes (course codes, term codes) are plain text, and course_code
columns are deliberately not foreign keys, so a degree plan can list courses that
are not offered this term.
"""

import uuid
from datetime import datetime, time
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# gemini-embedding-2 requested at 768 dimensions. Changing this needs a migration
# and a full re-run of embed_course_info.py.
EMBEDDING_DIM = 768

# Fixed constraint names, so migrations are predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Credits and hours from the degree audit can be fractional (e.g. 3.00, 0.50).
HOURS = Numeric(5, 2)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class Term(Base):
    """A semester, e.g. Spring 2027."""

    __tablename__ = "terms"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    # The term the latest mySAU Course Schedule export covers (open for registration).
    is_current_registration: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class Course(Base):
    """A catalog course, e.g. CSCI 3103. Exists whether or not it is offered this term."""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    title: Mapped[str] = mapped_column(Text)
    # Department and credits come from the sections export, so they are null for
    # catalog courses that are not offered this term.
    department: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    # Instructor permission, standing, admission. Stored, not enforced in semester 1.
    other_requirements: Mapped[str | None] = mapped_column(Text)


class CoursePrereq(Base):
    """One row per prereq course. Every option_group must be met. Inside a group, each
    alt_set is one alternative (any one counts); the rows of one alt_set are all needed
    together (a lecture+lab pair, say). Migration 0004 (Nov 20) added alt_set; before it
    every row was its own alternative, which is what a CSV without '+' still loads as."""

    __tablename__ = "course_prereqs"

    course_code: Mapped[str] = mapped_column(Text, primary_key=True)
    option_group: Mapped[int] = mapped_column(Integer, primary_key=True)
    alt_set: Mapped[int] = mapped_column(Integer, primary_key=True)
    requires_code: Mapped[str] = mapped_column(Text, primary_key=True)


class Section(Base):
    """One offering of a course in a term: who teaches it, when, where, and seats."""

    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id", ondelete="CASCADE"))
    section_number: Mapped[str] = mapped_column(Text)
    instructor: Mapped[str] = mapped_column(Text, server_default="Staff")
    location: Mapped[str | None] = mapped_column(Text)
    building: Mapped[str | None] = mapped_column(Text)
    room: Mapped[str | None] = mapped_column(Text)
    # Null days/times = online or TBA. Days are letters from MTWRFSU.
    days: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    division: Mapped[str | None] = mapped_column(Text)
    enrolled: Mapped[int] = mapped_column(Integer, server_default="0")
    capacity: Mapped[int] = mapped_column(Integer, server_default="0")
    # A section missing from a newer export is set inactive, never deleted, because
    # saved schedules point at it.
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class DegreePlan(Base):
    """A degree, e.g. BS Computer Science 2023. Its requirements are a tree of groups."""

    __tablename__ = "degree_plans"
    __table_args__ = (UniqueConstraint("name", "catalog_year"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    catalog_year: Mapped[str] = mapped_column(Text)
    total_hours: Mapped[int] = mapped_column(Integer)
    # Set by scrape_degree_maps.py; null for plans entered by hand.
    source_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequirementGroup(Base):
    """One node in a degree plan's tree. rule: 'all' courses, or 'choose_hours' worth."""

    __tablename__ = "requirement_groups"
    __table_args__ = (CheckConstraint("rule IN ('all', 'choose_hours')", name="rule"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    degree_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("degree_plans.id", ondelete="CASCADE")
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirement_groups.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(Text)
    hours_required: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    # Rules that are not a course list, e.g. "may only include one course in Art".
    # Shown as text, not enforced.
    note: Mapped[str | None] = mapped_column(Text)


class RequirementCourse(Base):
    """A course that counts toward a requirement group."""

    __tablename__ = "requirement_courses"

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_groups.id", ondelete="CASCADE"), primary_key=True
    )
    course_code: Mapped[str] = mapped_column(Text, primary_key=True)


class Student(Base):
    """Demo accounts only. A plain demo password is fine for semester 1."""

    __tablename__ = "students"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password: Mapped[str] = mapped_column(Text)
    degree_plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("degree_plans.id"))
    classification: Mapped[str | None] = mapped_column(Text)
    # Filled from the mySAU degree audit. The audit header (name, ID, address, phones,
    # advisor, GPA) is never stored, and holds are only a yes/no: a hold's name can
    # reveal a balance owed.
    major: Mapped[str | None] = mapped_column(Text)
    catalog_year: Mapped[str | None] = mapped_column(Text)
    has_hold: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    total_hours_earned: Mapped[Decimal | None] = mapped_column(HOURS)
    total_hours_needed: Mapped[Decimal | None] = mapped_column(HOURS)
    audit_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CompletedCourse(Base):
    """A course a student has finished or is taking now.

    One row per course line. The same course can appear more than once (it counts toward
    two requirements, it was retaken, or it is both self-reported and on the audit), so
    the key is a plain id. A mySAU refresh replaces only the student's source='audit' rows.
    """

    __tablename__ = "completed_courses"
    __table_args__ = (
        CheckConstraint("status IN ('completed', 'in_progress')", name="status"),
        CheckConstraint("source IN ('audit', 'self_reported', 'manual')", name="source"),
        Index("ix_completed_courses_student_id", "student_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    course_code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    grade: Mapped[str | None] = mapped_column(Text)
    credits: Mapped[Decimal | None] = mapped_column(HOURS)
    term: Mapped[str | None] = mapped_column(Text)  # as the audit prints it, e.g. "2024 1S"
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    # The audit requirement this line counts toward. Null for "Nonapplied Coursework"
    # and for rows not from the audit.
    requirement_name: Mapped[str | None] = mapped_column(Text)


class StudentRequirement(Base):
    """One requirement block from a student's mySAU degree audit.

    For a student who has connected mySAU, these rows ARE their degree plan (for their
    own catalog year). Public degree_plans are the fallback for everyone else.
    """

    __tablename__ = "student_requirements"
    __table_args__ = (
        CheckConstraint("status IN ('met', 'not_met', 'in_progress')", name="status"),
        CheckConstraint("rule IN ('all', 'choose_hours')", name="rule"),
        Index("ix_student_requirements_student_id", "student_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    parent_name: Mapped[str | None] = mapped_column(Text)  # null for a top-level block
    status: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(Text, server_default="all")
    hours_earned: Mapped[Decimal | None] = mapped_column(HOURS)
    hours_required: Mapped[Decimal | None] = mapped_column(HOURS)
    # The "Select N hours from..." list, or the required courses. Course codes as text.
    course_options: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")


class Schedule(Base):
    """A saved schedule for one student and term, built by hand or suggested by the AI."""

    __tablename__ = "schedules"
    __table_args__ = (CheckConstraint("source IN ('manual', 'ai')", name="source"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"))
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleSection(Base):
    """A section that is part of a saved schedule."""

    __tablename__ = "schedule_sections"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), primary_key=True
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), primary_key=True
    )


class DocChunk(Base):
    """RAG text chunks. For courses: source_type='course', source_code=course code, chunk_index=0."""

    __tablename__ = "doc_chunks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_code", "chunk_index"),
        Index(
            "ix_doc_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source_type: Mapped[str] = mapped_column(Text)
    source_code: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer, server_default="0")
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    # sha256 hex of content. The embed script re-embeds a chunk only when this changes.
    content_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshRun(Base):
    """One data refresh: a public scrape, or a student's mySAU connect.

    error is a short message only, never page content.
    """

    __tablename__ = "refresh_runs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('course_info', 'degree_maps', 'sections', 'audit')", name="kind"
        ),
        CheckConstraint("status IN ('running', 'ok', 'failed')", name="status"),
        Index("ix_refresh_runs_kind", "kind", "started_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_changed: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    # Null for public runs.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE")
    )


# --- student planning (migration 0003) -------------------------------------------------------

EVENT_CATEGORIES = ("work", "personal_study", "extracurricular")
EVENT_RECURRENCES = ("none", "weekly")
EVENT_PRIORITIES = ("low", "normal", "high")
PREFERRED_TIMES = ("morning", "midday", "afternoon", "evening", "none")
DELIVERIES = ("in_person", "online")
FLEXIBILITIES = ("flexible", "balanced", "strict")
APPEARANCES = ("light", "dark", "system")
VISIBILITIES = ("private", "advisors", "community")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


class CalendarEvent(Base):
    """A student's own commitment on the weekly calendar (work, study, a club).

    Fixed events block courses (checker conflict commitment_overlap); flexible ones only warn
    (commitment_overlap_flexible). Events have a weekday, not a date: the checker treats every
    event as a weekly block, whatever its recurrence says.
    """

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("day IN ('M', 'T', 'W', 'R', 'F')", name="day"),
        CheckConstraint("start_time < end_time", name="times"),
        CheckConstraint(_one_of("category", EVENT_CATEGORIES), name="category"),
        CheckConstraint(_one_of("recurrence", EVENT_RECURRENCES), name="recurrence"),
        CheckConstraint(_one_of("priority", EVENT_PRIORITIES), name="priority"),
        Index("ix_calendar_events_student_id", "student_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    day: Mapped[str] = mapped_column(Text)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, server_default="personal_study")
    recurrence: Mapped[str] = mapped_column(Text, server_default="weekly")
    priority: Mapped[str] = mapped_column(Text, server_default="normal")
    fixed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentPreferences(Base):
    """Scheduling preferences, one row per student. Defaults for Create Schedule, AI suggest and Flow.
    A missing row means the defaults below."""

    __tablename__ = "student_preferences"
    __table_args__ = (
        CheckConstraint(_one_of("preferred_time", PREFERRED_TIMES), name="preferred_time"),
        CheckConstraint(_one_of("flexibility", FLEXIBILITIES), name="flexibility"),
        CheckConstraint("min_credits <= max_credits", name="credits"),
        CheckConstraint("delivery <@ ARRAY['in_person', 'online']::text[]", name="delivery"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_time: Mapped[str] = mapped_column(Text, server_default="none")
    # Letters from MTWRF, in that order. Empty = no preference.
    preferred_days: Mapped[str] = mapped_column(Text, server_default="")
    min_credits: Mapped[int] = mapped_column(Integer, server_default="12")
    max_credits: Mapped[int] = mapped_column(Integer, server_default="18")
    delivery: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{in_person,online}'::text[]")
    )
    flexibility: Mapped[str] = mapped_column(Text, server_default="balanced")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentSettings(Base):
    """App settings, one row per student. A missing row means the defaults below."""

    __tablename__ = "student_settings"
    __table_args__ = (
        CheckConstraint(_one_of("appearance", APPEARANCES), name="appearance"),
        CheckConstraint(_one_of("profile_visibility", VISIBILITIES), name="profile_visibility"),
        CheckConstraint("photo IS NULL OR photo LIKE 'data:image/%'", name="photo"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    email_notifications: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    push_notifications: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    advisor_updates: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    schedule_alerts: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    appearance: Mapped[str] = mapped_column(Text, server_default="light")
    high_contrast: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    larger_text: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    reduce_motion: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    profile_visibility: Mapped[str] = mapped_column(Text, server_default="advisors")
    # A profile photo as an image data URL (data:image/png;base64,...), at most ~1 MB.
    photo: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
