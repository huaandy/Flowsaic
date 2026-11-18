"""Save a parsed degree audit to an EXISTING Flowsaic student.

- Never creates a student and never changes the student's name, email or password.
- students: major, catalog_year, classification, has_hold, total hours, audit_refreshed_at.
- completed_courses: the student's source='audit' rows are replaced; self_reported and
  manual rows are left alone.
- student_requirements: replaced with the audit's blocks. For this student they ARE the
  degree plan (their own catalog year).
All in one transaction: a failed save leaves the old audit data in place.
"""

import uuid

from sqlalchemy import delete, func, update

from app.db import SessionLocal
from app.models import CompletedCourse, Student, StudentRequirement
from app.mysau.audit_parser import ParsedAudit


class StudentNotFound(LookupError):
    pass


def student_exists(student_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.get(Student, student_id) is not None


def save_audit(student_id: uuid.UUID, parsed: ParsedAudit) -> int:
    """Returns the number of course and requirement rows written."""
    with SessionLocal.begin() as session:
        if session.get(Student, student_id) is None:
            raise StudentNotFound
        session.execute(
            update(Student)
            .where(Student.id == student_id)
            .values(
                major=parsed.major,
                catalog_year=parsed.catalog_year,
                classification=parsed.classification,
                has_hold=parsed.has_hold,
                total_hours_earned=parsed.total_hours_earned,
                total_hours_needed=parsed.total_hours_needed,
                audit_refreshed_at=func.now(),
            )
        )
        session.execute(
            delete(CompletedCourse).where(
                CompletedCourse.student_id == student_id, CompletedCourse.source == "audit"
            )
        )
        session.add_all(
            CompletedCourse(
                student_id=student_id,
                course_code=course.course_code,
                status=course.status,
                grade=course.grade,
                credits=course.credits,
                term=course.term,
                source="audit",
                requirement_name=course.requirement_name,
            )
            for course in parsed.courses
        )
        session.execute(delete(StudentRequirement).where(StudentRequirement.student_id == student_id))
        session.add_all(
            StudentRequirement(
                student_id=student_id,
                name=requirement.name,
                parent_name=requirement.parent_name,
                status=requirement.status,
                rule=requirement.rule,
                hours_earned=requirement.hours_earned,
                hours_required=requirement.hours_required,
                course_options=requirement.course_options,
                note=requirement.note,
                sort_order=requirement.sort_order,
            )
            for requirement in parsed.requirements
        )
    return len(parsed.courses) + len(parsed.requirements)
