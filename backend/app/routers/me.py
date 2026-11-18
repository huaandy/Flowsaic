"""The signed-in student: GET /me, GET /me/progress, GET /me/completed-courses, plus two
endpoints added in contract v2 (Nov 17):

- GET /me/audit: the student's mySAU degree audit blocks (student_requirements). For a
  student who has connected mySAU, these are their degree plan (AGENTS.md, Nov 17).
- POST /me/connect-mysau: start a mySAU connect for the signed-in student (same code as
  POST /connect/mysau). Poll GET /data/refresh/{id} for each returned run.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import progress
from app.auth import ApiError, current_student_id
from app.db import SessionLocal
from app.models import CompletedCourse, Course, DegreePlan, Student, StudentRequirement
from app.mysau import run as mysau_run
from app.routers.data import RunStarted

router = APIRouter(prefix="/me", tags=["me"])


class PlanOut(BaseModel):
    id: uuid.UUID
    name: str
    catalog_year: str


class StudentOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    classification: str | None
    major: str | None
    catalog_year: str | None
    degree_plan: PlanOut | None
    has_hold: bool
    total_hours_earned: float | None
    total_hours_needed: float | None
    audit_refreshed_at: datetime | None
    connected_mysau: bool


class CompletedCourseOut(BaseModel):
    course_code: str
    title: str | None
    status: str
    grade: str | None
    credits: float | None
    term: str | None
    source: str
    requirement_name: str | None


class RequirementOut(BaseModel):
    name: str
    parent_name: str | None
    status: str
    rule: str
    hours_earned: float | None
    hours_required: float | None
    course_options: list[str]
    note: str | None


class AuditOut(BaseModel):
    refreshed_at: datetime | None
    requirements: list[RequirementOut]


class ProgressCourse(BaseModel):
    code: str
    title: str | None
    status: str = Field(description="passed, in_progress, needed, option, or counted_elsewhere")


class ProgressElective(BaseModel):
    text: str
    hours_required: float | None
    hours_done: float
    hours_in_progress: float
    status: str
    courses: list[ProgressCourse]


class RequirementNode(BaseModel):
    name: str
    rule: str
    status: str = Field(description="met, in_progress, not_met, or not_tracked")
    hours_done: float
    hours_in_progress: float
    hours_required: float | None
    courses: list[ProgressCourse]
    note: str | None
    electives: list[ProgressElective]
    children: list["RequirementNode"]


class EligibleCourse(BaseModel):
    code: str
    title: str | None
    credits: float
    kind: str = Field(description="required, choice, or elective")
    counts_toward: list[str]
    sections: int
    seats_open: int


class BlockedCourse(BaseModel):
    code: str
    title: str | None
    missing_prereqs: list[list[str]] = Field(description="Prereq groups with no option done; any one option per group")
    counts_toward: list[str]


class PlanRef(BaseModel):
    name: str
    catalog_year: str


class TermRef(BaseModel):
    id: uuid.UUID
    name: str


class HoursOut(BaseModel):
    earned: float
    in_progress: float
    required: float | None


class ProgressOut(BaseModel):
    source: Literal["audit", "degree_plan", "none"]
    plan: PlanRef | None
    term: TermRef | None
    hours: HoursOut
    requirements: list[RequirementNode]
    can_take: list[EligibleCourse]
    blocked: list[BlockedCourse]
    open_electives: list[str]


class ConnectRequest(BaseModel):
    fetch: list[Literal["sections", "audit"]] = Field(default=["sections", "audit"], min_length=1)


class ConnectStarted(BaseModel):
    runs: list[RunStarted]


def _number(value) -> float | None:
    return None if value is None else float(value)


# --- reads (module functions so tests can replace them) ----------------------------------

def load_profile(student_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if student is None:
            raise ApiError(401, "not_authenticated")  # the account is gone; sign in again
        plan = session.get(DegreePlan, student.degree_plan_id) if student.degree_plan_id else None
        return {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "classification": student.classification,
            "major": student.major,
            "catalog_year": student.catalog_year,
            "degree_plan": (
                {"id": plan.id, "name": plan.name, "catalog_year": plan.catalog_year} if plan else None
            ),
            "has_hold": student.has_hold,
            "total_hours_earned": _number(student.total_hours_earned),
            "total_hours_needed": _number(student.total_hours_needed),
            "audit_refreshed_at": student.audit_refreshed_at,
            "connected_mysau": student.audit_refreshed_at is not None,
        }


def load_completed_courses(student_id: uuid.UUID) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(CompletedCourse, Course.title)
            .outerjoin(Course, Course.code == CompletedCourse.course_code)
            .where(CompletedCourse.student_id == student_id)
            .order_by(CompletedCourse.status, CompletedCourse.term, CompletedCourse.course_code)
        ).all()
    return [
        {
            "course_code": row.course_code,
            "title": title,
            "status": row.status,
            "grade": row.grade,
            "credits": _number(row.credits),
            "term": row.term,
            "source": row.source,
            "requirement_name": row.requirement_name,
        }
        for row, title in rows
    ]


def load_audit(student_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        refreshed_at = session.scalar(select(Student.audit_refreshed_at).where(Student.id == student_id))
        rows = session.scalars(
            select(StudentRequirement)
            .where(StudentRequirement.student_id == student_id)
            .order_by(StudentRequirement.sort_order)
        ).all()
    return {
        "refreshed_at": refreshed_at,
        "requirements": [
            {
                "name": row.name,
                "parent_name": row.parent_name,
                "status": row.status,
                "rule": row.rule,
                "hours_earned": _number(row.hours_earned),
                "hours_required": _number(row.hours_required),
                "course_options": list(row.course_options or []),
                "note": row.note,
            }
            for row in rows
        ],
    }


def load_student_progress(student_id: uuid.UUID) -> dict:
    try:
        return progress.load_progress(student_id)
    except LookupError:
        raise ApiError(401, "not_authenticated") from None


# --- endpoints ----------------------------------------------------------------------------

@router.get("", response_model=StudentOut)
def me(student_id: uuid.UUID = Depends(current_student_id)):
    return load_profile(student_id)


@router.get("/progress", response_model=ProgressOut)
def my_progress(student_id: uuid.UUID = Depends(current_student_id)):
    """Degree progress (from the mySAU audit if connected, else the public degree map) and
    the courses the student can take in the current registration term."""
    return load_student_progress(student_id)


@router.get("/completed-courses", response_model=list[CompletedCourseOut])
def completed_courses(student_id: uuid.UUID = Depends(current_student_id)):
    return load_completed_courses(student_id)


@router.get("/audit", response_model=AuditOut)
def audit(student_id: uuid.UUID = Depends(current_student_id)):
    return load_audit(student_id)


@router.post("/connect-mysau", status_code=202, response_model=ConnectStarted)
def connect_mysau(body: ConnectRequest | None = None, student_id: uuid.UUID = Depends(current_student_id)):
    fetch = list(dict.fromkeys((body or ConnectRequest()).fetch))
    try:
        run_ids = mysau_run.start_connect(student_id, fetch)
    except mysau_run.StudentNotFound:
        return JSONResponse(status_code=401, content={"error": "not_authenticated"})
    except mysau_run.ConnectAlreadyRunning:
        return JSONResponse(status_code=409, content={"error": "connect_already_running"})
    return {"runs": [{"id": run_id, "kind": kind} for kind, run_id in run_ids.items()]}
