"""Schedules for the signed-in student (contract): check, save, list, view, replace, delete.

- POST /schedules/check runs the checker without saving.
- POST and PUT /schedules run the checker first. Conflicts block saving:
  422 { "error": "schedule_has_conflicts", "conflicts": [...] }. Warnings don't.
- Flow (the AI) never saves; the student's Save button calls POST /schedules with source "ai".
- A saved section that later disappears from the export stays (sections are never deleted)
  and comes back with active = false.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app import checker
from app.auth import ApiError, current_student_id
from app.db import SessionLocal
from app.models import Course, Schedule, ScheduleSection, Section, Term

router = APIRouter(prefix="/schedules", tags=["schedules"])


class CheckRequest(BaseModel):
    term_id: uuid.UUID
    section_ids: list[uuid.UUID] = Field(max_length=40)


class CheckItem(BaseModel):
    code: str = Field(description="time_overlap, missing_prereq, duplicate_course, already_completed, "
                                  "section_full, not_on_plan or over_credit_limit")
    section_ids: list[uuid.UUID]
    message: str = Field(description="Shown to the student as is")


class CheckResult(BaseModel):
    conflicts: list[CheckItem] = Field(description="Block saving")
    warnings: list[CheckItem] = Field(description="Don't block saving")


class SaveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    term_id: uuid.UUID
    section_ids: list[uuid.UUID] = Field(min_length=1, max_length=15)
    source: Literal["manual", "ai"] = "manual"


class TermOut(BaseModel):
    id: uuid.UUID
    name: str


class ScheduleSectionOut(BaseModel):
    id: uuid.UUID
    code: str
    section_number: str
    title: str | None
    credits: float
    days: str | None
    start_time: str | None = Field(description="HH:MM, null = online or TBA")
    end_time: str | None
    instructor: str
    location: str | None
    enrolled: int
    capacity: int
    seats_open: int
    active: bool = Field(description="false = no longer in the latest export")


class ScheduleSummary(BaseModel):
    id: uuid.UUID
    name: str
    term: TermOut
    source: str
    created_at: datetime
    credits: float
    section_count: int


class ScheduleDetail(ScheduleSummary):
    sections: list[ScheduleSectionOut]
    conflicts: list[CheckItem]
    warnings: list[CheckItem]


# --- checker ---------------------------------------------------------------------------------

def run_check(student_id: uuid.UUID, section_ids: list[uuid.UUID], term_id: uuid.UUID) -> dict:
    try:
        return checker.check_for_student(student_id, section_ids, term_id)
    except checker.SectionNotFound:
        raise ApiError(404, "section_not_found") from None
    except checker.SectionNotInTerm:
        raise ApiError(422, "section_not_in_term") from None
    except LookupError:
        raise ApiError(401, "not_authenticated") from None


# --- storage (module functions so tests can replace them) -------------------------------------

def _section_out(section: Section, course: Course) -> dict:
    info = checker.section_info(section, course)
    return {
        "id": section.id, "code": course.code, "section_number": section.section_number, "title": course.title,
        "credits": info.credits, "days": section.days,
        "start_time": section.start_time.strftime("%H:%M") if section.start_time else None,
        "end_time": section.end_time.strftime("%H:%M") if section.end_time else None,
        "instructor": info.instructor, "location": section.location, "enrolled": info.enrolled,
        "capacity": info.capacity, "seats_open": info.seats_open, "active": section.active,
    }


def _summary(schedule: Schedule, term: Term, sections: list[dict]) -> dict:
    by_code = {s["code"]: s["credits"] for s in sections}
    return {"id": schedule.id, "name": schedule.name, "term": {"id": term.id, "name": term.name},
            "source": schedule.source, "created_at": schedule.created_at,
            "credits": sum(by_code.values()), "section_count": len(sections)}


def _load_sections(session, schedule_id: uuid.UUID) -> list[dict]:
    rows = session.execute(
        select(Section, Course).join(ScheduleSection, ScheduleSection.section_id == Section.id)
        .join(Course, Course.id == Section.course_id).where(ScheduleSection.schedule_id == schedule_id)
    ).all()
    sections = [_section_out(section, course) for section, course in rows]
    return sorted(sections, key=lambda s: (s["code"], s["section_number"]))


def list_schedules(student_id: uuid.UUID) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Schedule, Term).join(Term, Term.id == Schedule.term_id)
            .where(Schedule.student_id == student_id).order_by(Schedule.created_at.desc())
        ).all()
        return [_summary(schedule, term, _load_sections(session, schedule.id)) for schedule, term in rows]


def get_schedule(student_id: uuid.UUID, schedule_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        row = session.execute(
            select(Schedule, Term).join(Term, Term.id == Schedule.term_id)
            .where(Schedule.id == schedule_id, Schedule.student_id == student_id)
        ).first()
        if row is None:
            raise ApiError(404, "schedule_not_found")
        schedule, term = row
        sections = _load_sections(session, schedule.id)
        active_ids = [s["id"] for s in sections if s["active"]]
        result = (checker.check_schedule(checker.load_sections(session, active_ids),
                                         checker.load_student_context(session, student_id))
                  if active_ids else {"conflicts": [], "warnings": []})
        return {**_summary(schedule, term, sections), "sections": sections, **result}


def save_schedule(student_id: uuid.UUID, body: SaveRequest, schedule_id: uuid.UUID | None = None) -> uuid.UUID:
    """Insert (schedule_id None) or replace. The caller has already run the checker."""
    with SessionLocal.begin() as session:
        if schedule_id is None:
            schedule = Schedule(student_id=student_id, term_id=body.term_id, name=body.name, source=body.source)
            session.add(schedule)
            session.flush()
        else:
            schedule = session.scalar(select(Schedule).where(Schedule.id == schedule_id, Schedule.student_id == student_id))
            if schedule is None:
                raise ApiError(404, "schedule_not_found")
            schedule.name, schedule.term_id, schedule.source = body.name, body.term_id, body.source
            session.execute(delete(ScheduleSection).where(ScheduleSection.schedule_id == schedule.id))
        session.add_all(ScheduleSection(schedule_id=schedule.id, section_id=sid) for sid in dict.fromkeys(body.section_ids))
        return schedule.id


def delete_schedule(student_id: uuid.UUID, schedule_id: uuid.UUID) -> None:
    with SessionLocal.begin() as session:
        result = session.execute(delete(Schedule).where(Schedule.id == schedule_id, Schedule.student_id == student_id))
        if result.rowcount == 0:
            raise ApiError(404, "schedule_not_found")


def owns_schedule(student_id: uuid.UUID, schedule_id: uuid.UUID) -> bool:
    with SessionLocal() as session:
        return session.scalar(select(Schedule.id).where(Schedule.id == schedule_id, Schedule.student_id == student_id)) is not None


# --- endpoints -------------------------------------------------------------------------------

@router.post("/check", response_model=CheckResult)
def check(body: CheckRequest, student_id: uuid.UUID = Depends(current_student_id)):
    if not body.section_ids:
        return JSONResponse({"conflicts": [], "warnings": []})
    return run_check(student_id, list(dict.fromkeys(body.section_ids)), body.term_id)


def _checked_save(student_id: uuid.UUID, body: SaveRequest, schedule_id: uuid.UUID | None):
    result = run_check(student_id, list(dict.fromkeys(body.section_ids)), body.term_id)
    if result["conflicts"]:
        conflicts = [{**c, "section_ids": [str(i) for i in c["section_ids"]]} for c in result["conflicts"]]
        return JSONResponse(status_code=422, content={"error": "schedule_has_conflicts", "conflicts": conflicts})
    new_id = save_schedule(student_id, body, schedule_id)
    return get_schedule(student_id, new_id)


@router.get("", response_model=list[ScheduleSummary])
def my_schedules(student_id: uuid.UUID = Depends(current_student_id)):
    return list_schedules(student_id)


@router.post("", status_code=201, response_model=ScheduleDetail,
             responses={422: {"description": '{ "error": "schedule_has_conflicts", "conflicts": [...] }'}})
def create(body: SaveRequest, student_id: uuid.UUID = Depends(current_student_id)):
    return _checked_save(student_id, body, None)


@router.get("/{schedule_id}", response_model=ScheduleDetail)
def view(schedule_id: uuid.UUID, student_id: uuid.UUID = Depends(current_student_id)):
    return get_schedule(student_id, schedule_id)


@router.put("/{schedule_id}", response_model=ScheduleDetail)
def replace(schedule_id: uuid.UUID, body: SaveRequest, student_id: uuid.UUID = Depends(current_student_id)):
    if not owns_schedule(student_id, schedule_id):
        raise ApiError(404, "schedule_not_found")
    return _checked_save(student_id, body, schedule_id)


@router.delete("/{schedule_id}", status_code=204)
def remove(schedule_id: uuid.UUID, student_id: uuid.UUID = Depends(current_student_id)) -> Response:
    delete_schedule(student_id, schedule_id)
    return Response(status_code=204)
