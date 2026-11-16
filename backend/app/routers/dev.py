"""Developer test page and its endpoints. NOT part of the Semester 1 Contract.

This exists so the team can look at the loaded data and try search and Gemini by hand.
It is not the product front end (that is /frontend, Andy's) and these /dev endpoints are
not among the contract's sixteen. Remove or switch this off before any real deployment.

Only the typed question and public course text are sent to Gemini. Never student data.
"""

import uuid
from datetime import datetime, time
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.embeddings import embed_texts, get_client, query_prompt
from app.models import Base, Course, CoursePrereq, DocChunk, Section, Term

router = APIRouter(prefix="/dev", tags=["dev (test page, not in the contract)"])

DEV_PAGE = Path(__file__).resolve().parents[1] / "static" / "dev.html"
TOP_K = 8
BROWSE_LIMIT = 30
MAX_SECTIONS_IN_PROMPT = 6  # keeps the prompt small for courses with dozens of sections
TABLE_PAGE_SIZE = 50
HIDDEN_COLUMNS = {"password"}  # never shown by the table viewer, even for demo accounts

CHAT_INSTRUCTIONS = """You are a test assistant for Flowsaic, a course planning app for \
Southern Arkansas University (SAU).
Answer the student's question using ONLY the course list given in the latest message.
- Refer to courses by code and title, for example "CSCI 2103 Computer Science I".
- If the list does not contain what is needed to answer, say so plainly. Never invent \
courses, sections, times, instructors or requirements.
- You cannot check schedules for conflicts or confirm degree requirements. Say that an \
advisor or the schedule checker decides those.
- Keep answers short and in plain text. No markdown."""


def error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


def get_genai_client() -> genai.Client:
    return get_client()


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


def find_similar_courses(session: Session, client: genai.Client, query: str) -> list[dict]:
    """The TOP_K courses whose descriptions are closest in meaning to the query."""
    vector = embed_texts(client, [query_prompt(query)])[0]
    distance = DocChunk.embedding.cosine_distance(vector).label("distance")
    rows = session.execute(
        select(Course, distance)
        .join(Course, Course.code == DocChunk.source_code)
        .where(DocChunk.source_type == "course")
        .order_by(distance)
        .limit(TOP_K)
    ).all()
    details = course_details(session, [course for course, _ in rows])
    return [
        {**detail, "distance": round(float(row_distance), 4)}
        for detail, (_, row_distance) in zip(details, rows, strict=True)
    ]


def course_details(session: Session, courses: list[Course]) -> list[dict]:
    """Courses with their prereq groups and sections, in the order given."""
    if not courses:
        return []
    prereqs: dict[str, dict[int, list[str]]] = {}
    for row in session.execute(
        select(CoursePrereq)
        .where(CoursePrereq.course_code.in_([course.code for course in courses]))
        .order_by(CoursePrereq.option_group, CoursePrereq.requires_code)
    ).scalars():
        prereqs.setdefault(row.course_code, {}).setdefault(row.option_group, []).append(
            row.requires_code
        )

    sections: dict = {}
    for section, term_name in session.execute(
        select(Section, Term.name)
        .join(Term, Term.id == Section.term_id)
        .where(Section.course_id.in_([course.id for course in courses]))
        .order_by(Section.section_number)
    ).all():
        sections.setdefault(section.course_id, []).append(
            {
                "section_number": section.section_number,
                "term": term_name,
                "instructor": section.instructor,
                "days": section.days,
                "start_time": section.start_time.strftime("%H:%M") if section.start_time else None,
                "end_time": section.end_time.strftime("%H:%M") if section.end_time else None,
                "location": section.location,
                "building": section.building,
                "room": section.room,
                "enrolled": section.enrolled,
                "capacity": section.capacity,
                "seats_open": max(section.capacity - section.enrolled, 0),
            }
        )

    return [
        {
            "code": course.code,
            "title": course.title,
            "department": course.department,
            "credits": course.credits,
            "description": course.description,
            "other_requirements": course.other_requirements,
            # Each inner list is one group: any one course in it satisfies that group.
            "prereq_groups": list(prereqs.get(course.code, {}).values()),
            "sections": sections.get(course.id, []),
        }
        for course in courses
    ]


def course_as_prompt_text(course: dict) -> str:
    """One course as plain text for Gemini: catalog facts only."""
    prereqs = " AND ".join("(" + " OR ".join(group) + ")" for group in course["prereq_groups"])
    offered = (
        f"offered in {course['sections'][0]['term']} ({len(course['sections'])} sections)"
        if course["sections"]
        else "not offered this term"
    )
    credits = f"{course['credits']} credits" if course["credits"] is not None else "credits unknown"
    lines = [
        f"{course['code']} {course['title']} | {credits} | {offered} | "
        f"prerequisites: {prereqs or 'none listed'}",
        course["description"] or "No description.",
    ]
    for section in course["sections"][:MAX_SECTIONS_IN_PROMPT]:
        when = (
            f"{section['days'] or 'days TBA'} {section['start_time']}-{section['end_time']}"
            if section["start_time"]
            else "online or time TBA"
        )
        lines.append(
            f"  Section {section['section_number']}: {when}, {section['instructor']}, "
            f"{section['seats_open']} of {section['capacity']} seats open"
        )
    if len(course["sections"]) > MAX_SECTIONS_IN_PROMPT:
        lines.append(f"  (and {len(course['sections']) - MAX_SECTIONS_IN_PROMPT} more sections)")
    return "\n".join(lines)


@router.get("", include_in_schema=False)
def dev_page() -> FileResponse:
    return FileResponse(DEV_PAGE, media_type="text/html")


@router.get("/stats")
def stats(session: Session = Depends(get_db)) -> dict:
    """Row counts, so the page can show what is loaded."""

    def count(model) -> int:
        return session.scalar(select(func.count()).select_from(model))

    return {
        "terms": [name for (name,) in session.execute(select(Term.name).order_by(Term.name))],
        "courses": count(Course),
        "sections": count(Section),
        "prereq_rows": count(CoursePrereq),
        "embedded_chunks": count(DocChunk),
    }


def display_value(column_name: str, value):
    """Turn one database value into something safe and short to show on the page."""
    if value is None:
        return None
    if column_name in HIDDEN_COLUMNS:
        return "(hidden)"
    if isinstance(value, bool | int):
        return value
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, str | uuid.UUID):
        return str(value)
    # An embedding: 768 numbers. Show the first few and the count.
    numbers = [float(number) for number in value]
    preview = ", ".join(f"{number:.4f}" for number in numbers[:4])
    return f"[{preview}, …]  ({len(numbers)} numbers)"


@router.get("/tables")
def tables(session: Session = Depends(get_db)) -> dict:
    """Every table with its columns and row count. Read-only."""
    return {
        "tables": [
            {
                "name": table.name,
                "columns": [column.name for column in table.columns],
                "rows": session.scalar(select(func.count()).select_from(table)),
            }
            for table in Base.metadata.sorted_tables
        ]
    }


@router.get("/tables/{name}")
def table_rows(
    name: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=TABLE_PAGE_SIZE, ge=1, le=200),
    session: Session = Depends(get_db),
):
    """One page of rows from a table. Read-only. Only tables defined in app/models.py."""
    table = Base.metadata.tables.get(name)  # a lookup, so the name never reaches SQL as text
    if table is None:
        return error(404, "table_not_found")

    total = session.scalar(select(func.count()).select_from(table))
    rows = session.execute(
        select(table).order_by(*table.primary_key.columns).offset(offset).limit(limit)
    ).mappings()
    return {
        "name": name,
        "columns": [column.name for column in table.columns],
        "total": total,
        "offset": offset,
        "limit": limit,
        "rows": [
            [display_value(column.name, row[column.name]) for column in table.columns]
            for row in rows
        ],
    }


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=300),
    session: Session = Depends(get_db),
    client: genai.Client = Depends(get_genai_client),
):
    """Search course descriptions by meaning. Uses one Gemini embedding request."""
    try:
        return {"query": q, "results": find_similar_courses(session, client, q)}
    except errors.APIError:
        return error(502, "ai_unavailable")


@router.get("/courses")
def browse(
    search: str = Query(default="", max_length=100),
    offered_only: bool = True,
    session: Session = Depends(get_db),
) -> dict:
    """Look up courses by code or title (plain text match, no AI)."""
    statement = select(Course).order_by(Course.code).limit(BROWSE_LIMIT)
    text = search.strip()
    if text:
        pattern = f"%{text}%"
        statement = statement.where(or_(Course.code.ilike(pattern), Course.title.ilike(pattern)))
    if offered_only:
        statement = statement.where(
            select(Section.id).where(Section.course_id == Course.id).exists()
        )
    courses = list(session.execute(statement).scalars())
    return {"limit": BROWSE_LIMIT, "results": course_details(session, courses)}


@router.post("/chat")
def chat(
    body: ChatRequest,
    session: Session = Depends(get_db),
    client: genai.Client = Depends(get_genai_client),
):
    """Ask Gemini a question. It is given the 8 most relevant courses and nothing else."""
    model = get_settings().gemini_model
    if not model:
        return error(503, "gemini_model_not_set")

    try:
        # Search with the last two questions as well, so a follow-up like "which of those
        # has a prerequisite?" still finds the courses the conversation is about.
        earlier = [turn.text for turn in body.history if turn.role == "user"][-2:]
        courses = find_similar_courses(session, client, " ".join([*earlier, body.message]))
        course_text = "\n\n".join(course_as_prompt_text(course) for course in courses)
        contents = [
            types.Content(
                role="user" if turn.role == "user" else "model",
                parts=[types.Part.from_text(text=turn.text)],
            )
            for turn in body.history
        ]
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"Course list:\n\n{course_text}\n\nStudent's question: {body.message}"
                    )
                ],
            )
        )
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CHAT_INSTRUCTIONS, temperature=0.3
            ),
        )
    except errors.APIError:
        return error(502, "ai_unavailable")

    answer = (response.text or "").strip()
    if not answer:
        return error(502, "ai_empty_answer")
    return {"answer": answer, "model": model, "courses_given_to_ai": courses}
