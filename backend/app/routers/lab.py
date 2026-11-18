"""Schedule lab: test-page endpoints for trying the checker and the solver by hand.
NOT part of the contract (like /dev). Flow will call the same solver as a tool.

- GET /dev/lab/sections?codes=CSCI 4203,MATH 3043: this term's sections for those courses.
- POST /dev/lab/solve: find_schedules for the signed-in student, each result run through
  the checker, exactly what Flow will see.
"""

import re
import uuid
from datetime import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import checker, solver
from app.auth import ApiError, current_student_id
from app.db import SessionLocal
from app.models import Term
from app.normalize import COURSE_CODE_RE

router = APIRouter(prefix="/dev/lab", tags=["dev (test page, not in the contract)"])

HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def current_term_id() -> uuid.UUID:
    with SessionLocal() as session:
        term_id = session.scalar(select(Term.id).where(Term.is_current_registration.is_(True)))
    if term_id is None:
        raise ApiError(404, "no_current_term")
    return term_id


def section_out(section: checker.SectionInfo) -> dict:
    return {
        "id": section.id, "code": section.code, "section_number": section.section_number,
        "title": section.title, "credits": section.credits, "days": section.days,
        "start_time": section.start.strftime("%H:%M") if section.start else None,
        "end_time": section.end.strftime("%H:%M") if section.end else None,
        "instructor": section.instructor, "location": section.location,
        "enrolled": section.enrolled, "capacity": section.capacity, "seats_open": section.seats_open,
    }


def normalize_code(raw: str) -> str:
    code = " ".join(raw.upper().split())
    if not COURSE_CODE_RE.fullmatch(code):
        raise ApiError(422, "invalid_course_code")
    return code


@router.get("/sections")
def sections(codes: str = Query(max_length=600), _: uuid.UUID = Depends(current_student_id)) -> dict:
    wanted = [normalize_code(c) for c in codes.split(",") if c.strip()][:20]
    term_id = current_term_id()
    found = solver.load_term_sections(wanted, term_id)
    return {"term_id": term_id, "courses": [
        {"code": code, "sections": [section_out(s) for s in found.get(code, [])]} for code in wanted
    ]}


class BlockIn(BaseModel):
    days: str = Field(pattern=r"^[MTWRFSUmtwrfsu]+$")
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def hhmm(cls, value: str) -> str:
        if not HHMM.match(value):
            raise ValueError("time must be HH:MM")
        return value


def to_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


class SolveRequest(BaseModel):
    must: list[str] = Field(default_factory=list, max_length=10)
    optional: list[str] = Field(default_factory=list, max_length=25)
    unavailable: list[BlockIn] = Field(default_factory=list, max_length=10)
    earliest_start: str | None = Field(default=None, pattern=HHMM.pattern)
    latest_end: str | None = Field(default=None, pattern=HHMM.pattern)
    days_off: str = Field(default="", pattern=r"^[MTWRFSUmtwrfsu]*$")
    avoid_instructors: list[str] = Field(default_factory=list, max_length=10)
    preferred_instructors: list[str] = Field(default_factory=list, max_length=10)
    preferred_time: str | None = Field(default=None, pattern=r"^(morning|afternoon|evening)$")
    open_seats_only: bool = False
    allow_online: bool = True
    min_credits: float | None = Field(default=None, ge=0, le=24)
    max_credits: float = Field(default=18, ge=1, le=24)
    limit: int = Field(default=5, ge=1, le=10)


@router.post("/solve")
def solve(body: SolveRequest, student_id: uuid.UUID = Depends(current_student_id)) -> dict:
    must = [normalize_code(c) for c in body.must]
    optional = [normalize_code(c) for c in body.optional]
    if not must and not optional:
        raise ApiError(422, "no_courses")
    constraints = solver.Constraints(
        unavailable=[solver.Block(b.days.upper(), to_time(b.start), to_time(b.end)) for b in body.unavailable],
        earliest_start=to_time(body.earliest_start), latest_end=to_time(body.latest_end),
        days_off=body.days_off.upper(), avoid_instructors=body.avoid_instructors,
        preferred_instructors=body.preferred_instructors, preferred_time=body.preferred_time,
        open_seats_only=body.open_seats_only, allow_online=body.allow_online,
        min_credits=body.min_credits, max_credits=body.max_credits,
    )
    term_id = current_term_id()
    result = solver.find_schedules(must, optional, constraints, term_id, body.limit)
    with SessionLocal() as session:
        context = checker.load_student_context(session, student_id)
    return {
        "term_id": term_id,
        "unschedulable": result["unschedulable"],
        "message": result["message"],
        "complete": result["complete"],
        "schedules": [
            {"credits": s["credits"], "score": s["score"], "sections": [section_out(x) for x in s["sections"]],
             **checker.check_schedule(s["sections"], context)}
            for s in result["schedules"]
        ],
    }
