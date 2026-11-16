"""SQLAlchemy models for the AGENTS.md data model, plus doc_chunks for RAG.

Schema changes go through Alembic migrations only (ground rule 1).
IDs are UUIDs. SAU codes (course codes, term codes) are plain text, and course_code
columns are deliberately not foreign keys, so a degree plan can list courses that
are not offered this term.
"""

import uuid
from datetime import datetime, time

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
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


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


class Term(Base):
    __tablename__ = "terms"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)


class Course(Base):
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
    """One row per prereq. Rows sharing an option_group are alternatives (any one counts)."""

    __tablename__ = "course_prereqs"

    course_code: Mapped[str] = mapped_column(Text, primary_key=True)
    option_group: Mapped[int] = mapped_column(Integer, primary_key=True)
    requires_code: Mapped[str] = mapped_column(Text, primary_key=True)


class Section(Base):
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


class DegreePlan(Base):
    __tablename__ = "degree_plans"
    __table_args__ = (UniqueConstraint("name", "catalog_year"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    catalog_year: Mapped[str] = mapped_column(Text)
    total_hours: Mapped[int] = mapped_column(Integer)


class RequirementGroup(Base):
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


class RequirementCourse(Base):
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


class CompletedCourse(Base):
    __tablename__ = "completed_courses"
    __table_args__ = (CheckConstraint("status IN ('completed', 'in_progress')", name="status"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    course_code: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text)


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (CheckConstraint("source IN ('manual', 'ai')", name="source"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"))
    name: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduleSection(Base):
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
