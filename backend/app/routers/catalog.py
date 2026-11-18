"""The course catalog for the signed-in student (contract): terms, courses, one course, and
the header search.

- GET /terms: every term, the current registration term first.
- GET /courses: courses offered in a term (an active section), with their active sections and
  this student's flags. Filters: search (code, title or description), department, on_my_plan,
  eligible_only, level, delivery, open_only, credits, days. Paged with limit/offset; `total`
  counts every match. `departments` lists every department offered that term (for a dropdown).
- GET /courses/{id}: one course with its prereq option groups and every section in the term
  (inactive ones too, marked active=false). The term defaults to the current registration term.
- GET /search?q=: code/title matches first, then courses whose description is closest in
  meaning (RAG, the same search Flow uses). Without a Gemini key it returns the text matches only.

Per-student flags come from app/progress.py (the same tree as /me/progress):
eligibility = completed | in_progress | missing_prereq | eligible, plus on_my_plan and
requirement_names. level comes from the course number (CSCI 3103 -> 3000). A section's
delivery is "online" when it has no days/times or its campus says online, else "in_person"
(the export has no hybrid flag).
"""

import logging
import uuid
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app import course_search, progress
from app.auth import ApiError, current_student_id
from app.db import SessionLocal
from app.embeddings import get_client
from app.models import Course, Section, Term
from app.normalize import DAY_ORDER

router = APIRouter(tags=["catalog"])
log = logging.getLogger(__name__)

HHMM = "%H:%M"


# --- response models ----------------------------------------------------------------------------

class TermOut(BaseModel):
    id: uuid.UUID
    code: str = Field(description="SAU's export text, e.g. '2026-2027 - Spring'")
    name: str = Field(description="e.g. 'Spring 2027'")
    is_current_registration: bool


class CatalogSection(BaseModel):
    id: uuid.UUID
    section_number: str
    instructor: str
    location: str | None = Field(description="The export's campus, e.g. 'Main Campus' or 'Online'")
    building: str | None
    room: str | None
    days: str | None = Field(description="Letters from MTWRFSU (R = Thursday); null = online or TBA")
    start_time: str | None = Field(description="HH:MM, null = online or TBA")
    end_time: str | None
    division: str | None = Field(description="UG or GR")
    enrolled: int
    capacity: int
    seats_open: int
    active: bool = Field(description="false = no longer in the latest export")
    delivery: Literal["in_person", "online"]


class CatalogCourse(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    department: str | None
    credits: float
    description: str | None
    other_requirements: str | None = Field(description="Shown, not enforced (instructor permission, standing...)")
    level: int = Field(description="From the course number: 1000, 2000, 3000, 4000 (5000+ = graduate)")
    prereqs: list[list[str]] = Field(description="Option groups: every group needs one of its codes")
    eligibility: Literal["eligible", "missing_prereq", "completed", "in_progress"]
    missing_prereqs: list[list[str]] = Field(description="The prereq groups the student hasn't met")
    on_my_plan: bool
    requirement_names: list[str] = Field(description="Requirements (or elective lines) the course counts toward")
    offered: bool = Field(description="Has an active section in the term")
    seats_open: int = Field(description="Open seats across the term's active sections")
    sections: list[CatalogSection]


class CourseList(BaseModel):
    total: int = Field(description="Every course matching the filters, before limit/offset")
    courses: list[CatalogCourse]
    departments: list[str] = Field(description="Every department offered in the term")


class CourseDetail(CatalogCourse):
    term: TermOut | None


class SearchResult(BaseModel):
    course_id: uuid.UUID
    code: str
    title: str
    snippet: str | None = Field(description="A short piece of the description")
    match_type: Literal["code", "title", "description"]
    offered: bool = Field(description="Offered in the current registration term")


class SearchOut(BaseModel):
    query: str
    results: list[SearchResult]


# --- pure helpers --------------------------------------------------------------------------------

def delivery_for(days: str | None, start, end, location: str | None) -> str:
    if not (days and start and end) or "online" in (location or "").lower():
        return "online"
    return "in_person"


def section_out(section: Section) -> dict:
    enrolled, capacity = section.enrolled or 0, section.capacity or 0
    return {
        "id": section.id, "section_number": section.section_number, "instructor": section.instructor or "Staff",
        "location": section.location, "building": section.building, "room": section.room, "days": section.days,
        "start_time": section.start_time.strftime(HHMM) if section.start_time else None,
        "end_time": section.end_time.strftime(HHMM) if section.end_time else None,
        "division": section.division, "enrolled": enrolled, "capacity": capacity,
        "seats_open": max(capacity - enrolled, 0), "active": section.active,
        "delivery": delivery_for(section.days, section.start_time, section.end_time, section.location),
    }


def course_out(course: dict, sections: list[dict], flags: progress.CourseFlags) -> dict:
    code = course["code"]
    active = [s for s in sections if s["active"]]
    return {
        **course,
        "credits": float(course["credits"]) if course["credits"] is not None else progress.credits_from_code(code),
        "level": progress.course_level(code) * 1000,
        "prereqs": flags.prereqs.get(code, []),
        **flags.for_course(code),
        "offered": bool(active),
        "seats_open": sum(s["seats_open"] for s in active),
        "sections": sections,
    }


def ordered_days(text: str) -> str:
    letters = set(text.upper())
    return "".join(d for d in DAY_ORDER if d in letters)


def keep(course: dict, *, on_my_plan: bool, eligible_only: bool, level: int | None, delivery: str | None,
         open_only: bool, credits: float | None, days: str | None) -> bool:
    """The filters that need the student's flags or the sections (applied after the SQL query)."""
    sections = course["sections"]
    if on_my_plan and not course["on_my_plan"]:
        return False
    if eligible_only and course["eligibility"] != "eligible":
        return False
    if level is not None and course["level"] != level:
        return False
    if credits is not None and course["credits"] != credits:
        return False
    if delivery and not any(s["delivery"] == delivery for s in sections):
        return False
    if open_only and not any(s["seats_open"] > 0 for s in sections):
        return False
    if days and not any(s["days"] and ordered_days(s["days"]) == days for s in sections):
        return False
    return True


# --- storage (module functions so tests can replace them) -----------------------------------------

def _term_out(term: Term) -> dict:
    return {"id": term.id, "code": term.code, "name": term.name, "is_current_registration": term.is_current_registration}


def _course_row(course: Course) -> dict:
    return {"id": course.id, "code": course.code, "title": course.title, "department": course.department,
            "credits": course.credits, "description": course.description,
            "other_requirements": course.other_requirements}


def list_terms() -> list[dict]:
    with SessionLocal() as session:
        terms = session.scalars(select(Term).order_by(Term.is_current_registration.desc(), Term.name)).all()
        return [_term_out(t) for t in terms]


def find_term(term_id: uuid.UUID | None) -> dict | None:
    """The term, or the current registration term when term_id is None."""
    with SessionLocal() as session:
        statement = select(Term).where(Term.id == term_id if term_id else Term.is_current_registration.is_(True))
        term = session.scalar(statement)
        return _term_out(term) if term else None


def load_term_catalog(term_id: uuid.UUID, search: str | None, department: str | None) -> tuple[list[dict], list[str]]:
    """(courses offered in the term matching search/department, each with its active sections in
    'sections'; every department offered in the term)."""
    with SessionLocal() as session:
        statement = (select(Course, Section).join(Section, Section.course_id == Course.id)
                     .where(Section.term_id == term_id, Section.active.is_(True)))
        departments = sorted(set(session.scalars(
            select(Course.department).join(Section, Section.course_id == Course.id)
            .where(Section.term_id == term_id, Section.active.is_(True), Course.department.is_not(None)))))
        if search:
            statement = statement.where(or_(course_search.text_match_filter(search),
                                            Course.description.icontains(search, autoescape=True)))
        if department:
            statement = statement.where(Course.department == department)
        courses: dict[uuid.UUID, dict] = {}
        for course, section in session.execute(statement.order_by(Course.code, Section.section_number)):
            entry = courses.setdefault(course.id, {**_course_row(course), "sections": []})
            entry["sections"].append(section_out(section))
    return list(courses.values()), departments


def load_course(course_id: uuid.UUID, term_id: uuid.UUID | None) -> tuple[dict, list[dict]] | None:
    """(course, every section in the term, inactive ones too), or None if there's no such course."""
    with SessionLocal() as session:
        course = session.get(Course, course_id)
        if course is None:
            return None
        sections = [] if term_id is None else [section_out(s) for s in session.scalars(
            select(Section).where(Section.course_id == course_id, Section.term_id == term_id)
            .order_by(Section.section_number))]
        return _course_row(course), sections


def load_flags(student_id: uuid.UUID) -> progress.CourseFlags:
    try:
        return progress.load_course_flags(student_id)
    except LookupError:
        raise ApiError(401, "not_authenticated") from None


# --- endpoints ------------------------------------------------------------------------------------

@router.get("/terms", response_model=list[TermOut])
def terms(_: uuid.UUID = Depends(current_student_id)):
    return list_terms()


@router.get("/courses", response_model=CourseList)
def courses(
    term_id: uuid.UUID,
    search: str | None = Query(default=None, max_length=100, description="Code, title or description"),
    department: str | None = Query(default=None, max_length=120),
    on_my_plan: bool = False,
    eligible_only: bool = Query(default=False, description="Only courses with eligibility = eligible"),
    level: int | None = Query(default=None, ge=1000, le=7000, description="1000, 2000, 3000, 4000..."),
    delivery: Literal["in_person", "online"] | None = Query(default=None, description="Has a section with it"),
    open_only: bool = Query(default=False, description="Has a section with open seats"),
    credits: float | None = Query(default=None, ge=0, le=12),
    days: str | None = Query(default=None, pattern=r"^[MTWRFSUmtwrfsu]{1,7}$",
                             description="Has a section meeting exactly these days, e.g. MWF"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    student_id: uuid.UUID = Depends(current_student_id),
):
    if find_term(term_id) is None:
        raise ApiError(404, "term_not_found")
    search = (search or "").strip() or None
    rows, departments = load_term_catalog(term_id, search, department)
    flags = load_flags(student_id)
    built = [course_out({k: v for k, v in row.items() if k != "sections"}, row["sections"], flags) for row in rows]
    matched = [c for c in built if keep(c, on_my_plan=on_my_plan, eligible_only=eligible_only, level=level,
                                        delivery=delivery, open_only=open_only, credits=credits,
                                        days=ordered_days(days) if days else None)]
    matched.sort(key=lambda c: c["code"])
    return {"total": len(matched), "courses": matched[offset:offset + limit], "departments": departments}


@router.get("/courses/{course_id}", response_model=CourseDetail)
def course(course_id: uuid.UUID, term_id: uuid.UUID | None = None,
           student_id: uuid.UUID = Depends(current_student_id)):
    term = find_term(term_id)
    if term_id is not None and term is None:
        raise ApiError(404, "term_not_found")
    found = load_course(course_id, term["id"] if term else None)
    if found is None:
        raise ApiError(404, "course_not_found")
    row, sections = found
    return {**course_out(row, sections, load_flags(student_id)), "term": term}


@lru_cache(maxsize=256)
def _described_like(query: str, k: int) -> tuple[tuple[str, str, str], ...]:
    """RAG hits for a query, cached: the same text costs one embedding request per server run."""
    hits = course_search.search_courses(get_client(), query, None, k=k)
    return tuple((h["code"], h["title"], h["description"]) for h in hits)


def described_like(query: str, k: int) -> list[tuple[str, str, str]]:
    """(code, title, description) of the closest descriptions; [] when Gemini isn't available."""
    try:
        return list(_described_like(query.lower(), k))
    except Exception as error:  # no key, network, quota: the text matches still answer
        log.warning("description search skipped (%s)", type(error).__name__)
        return []


@router.get("/search", response_model=SearchOut)
def search(q: str = Query(min_length=2, max_length=100), limit: int = Query(default=10, ge=1, le=20),
           _: uuid.UUID = Depends(current_student_id)):
    query = " ".join(q.split())
    if len(query) < 2:
        raise ApiError(422, "invalid_request")
    term = find_term(None)
    offered = course_search.offered_codes(term["id"] if term else None)
    results = [
        {"course_id": m["course_id"], "code": m["code"], "title": m["title"],
         "snippet": course_search.snippet(m["description"], query), "match_type": m["match_type"],
         "offered": m["code"] in offered}
        for m in course_search.text_matches(query, limit)
    ]
    if len(results) < limit:
        seen = {r["code"] for r in results}
        hits = [h for h in described_like(query, limit) if h[0] not in seen][: limit - len(results)]
        ids = course_search.course_ids([code for code, _, _ in hits])
        results += [
            {"course_id": ids[code][0], "code": code, "title": title,
             "snippet": course_search.snippet(description, query), "match_type": "description",
             "offered": code in offered}
            for code, title, description in hits if code in ids
        ]
    return {"query": query, "results": results}
