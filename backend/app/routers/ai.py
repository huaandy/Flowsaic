"""Flow, the AI advisor, and AI suggest (contract v2).

- POST /ai/advisor: one conversation turn. The front end keeps the conversation and sends it
  back as `history`, using each reply's `memory` (not `reply`) as the assistant's text, so the
  student's name never goes to Gemini.
- POST /ai/suggest: the Create Schedule form. Same engine, one checked schedule.

Gemini never decides validity (the checker does) and never saves (the student's Save button
calls POST /schedules).
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import advisor
from app.auth import ApiError, current_student_id
from app.checker import SectionInfo
from app.db import SessionLocal
from app.models import Term
from app.routers.schedules import CheckItem

router = APIRouter(prefix="/ai", tags=["ai"])


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=6000)


class AdvisorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20,
                                description="Earlier turns. For Flow's turns send `memory`, not `reply`.")


class ProposedSection(BaseModel):
    id: uuid.UUID
    code: str
    section_number: str
    title: str | None
    credits: float
    days: str | None
    start_time: str | None
    end_time: str | None
    instructor: str
    location: str | None
    seats_open: int
    capacity: int


class Proposal(BaseModel):
    name: str
    explanation: str
    term_id: uuid.UUID | None
    section_ids: list[uuid.UUID]
    sections: list[ProposedSection]
    credits: float
    conflicts: list[CheckItem]
    warnings: list[CheckItem]


class AdvisorReply(BaseModel):
    reply: str = Field(description="Show this to the student")
    memory: str = Field(description="Send this back in history as Flow's turn")
    proposals: list[Proposal] = Field(description="Checked schedules, each with a Save button")
    tools_used: list[str]


class Block(BaseModel):
    days: str = Field(pattern=r"^[MTWRFSUmtwrfsu]+$")
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Lunch(BaseModel):
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Preferences(BaseModel):
    term_id: uuid.UUID | None = Field(default=None, description="Only the current registration term for now")
    target_credits: int | None = Field(default=None, ge=1, le=21)
    unavailable: list[Block] = Field(default_factory=list, max_length=10)
    preferred_time: Literal["morning", "afternoon", "evening", ""] | None = None
    lunch: Lunch | None = None
    preferred_instructors: list[str] = Field(default_factory=list, max_length=10)
    avoid_instructors: list[str] = Field(default_factory=list, max_length=10)
    notes: str = Field(default="", max_length=1000)


class SuggestResult(BaseModel):
    section_ids: list[uuid.UUID]
    sections: list[ProposedSection]
    explanation: str
    warnings: list[CheckItem]
    conflicts: list[CheckItem]


def _section(s: SectionInfo) -> dict:
    return {"id": s.id, "code": s.code, "section_number": s.section_number, "title": s.title, "credits": s.credits,
            "days": s.days, "start_time": s.start.strftime("%H:%M") if s.start else None,
            "end_time": s.end.strftime("%H:%M") if s.end else None, "instructor": s.instructor,
            "location": s.location, "seats_open": s.seats_open, "capacity": s.capacity}


def _proposal(p: dict) -> dict:
    sections = p["sections"]
    return {"name": p["name"], "explanation": p["explanation"],
            "term_id": sections[0].term_id if sections else None,
            "section_ids": [s.id for s in sections], "sections": [_section(s) for s in sections],
            "credits": p["credits"], "conflicts": p["conflicts"], "warnings": p["warnings"]}


def _run(student_id: uuid.UUID, message: str, history: list[dict], mode: str) -> dict:
    try:
        return advisor.advise(student_id, message, history, mode)
    except advisor.AdvisorUnavailable as error:
        raise ApiError(503 if error.code == "gemini_model_not_set" else 502, error.code) from None
    except LookupError:
        raise ApiError(401, "not_authenticated") from None


@router.post("/advisor", response_model=AdvisorReply)
def flow(body: AdvisorRequest, student_id: uuid.UUID = Depends(current_student_id)):
    result = _run(student_id, body.message, [t.model_dump() for t in body.history], "chat")
    return {**result, "proposals": [_proposal(p) for p in result["proposals"]]}


def preferences_message(p: Preferences) -> str:
    """The form as a plain request to Flow (no personal data)."""
    lines = ["Build my schedule for next term."]
    if p.target_credits:
        lines.append(f"Target: {p.target_credits} credits.")
    for b in p.unavailable:
        lines.append(f"I can't do {b.days.upper()} {b.start}-{b.end}.")
    if p.preferred_time:
        lines.append(f"I prefer {p.preferred_time} classes.")
    if p.lunch:
        lines.append(f"I'd like lunch free {p.lunch.start}-{p.lunch.end}.")
    if p.preferred_instructors:
        lines.append("Instructors I'd like: " + ", ".join(p.preferred_instructors) + ".")
    if p.avoid_instructors:
        lines.append("Instructors to avoid: " + ", ".join(p.avoid_instructors) + ".")
    if p.notes.strip():
        lines.append("Notes: " + p.notes.strip())
    return " ".join(lines)


@router.post("/suggest", response_model=SuggestResult)
def suggest(body: Preferences, student_id: uuid.UUID = Depends(current_student_id)):
    if body.term_id is not None:
        with SessionLocal() as session:
            current = session.scalar(select(Term.id).where(Term.is_current_registration.is_(True)))
        if body.term_id != current:
            return JSONResponse(status_code=422, content={"error": "term_not_supported"})
    result = _run(student_id, preferences_message(body), [], "suggest")
    if not result["proposals"]:
        return {"section_ids": [], "sections": [], "explanation": result["reply"], "warnings": [], "conflicts": []}
    best = _proposal(result["proposals"][-1])
    return {"section_ids": best["section_ids"], "sections": best["sections"],
            "explanation": best["explanation"] or result["reply"], "warnings": best["warnings"],
            "conflicts": best["conflicts"]}
