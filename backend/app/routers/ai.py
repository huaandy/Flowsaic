"""Flow, the AI advisor, and AI suggest (contract v2).

- POST /ai/advisor: one conversation turn. The front end keeps the conversation and sends it
  back as `history`, using each reply's `memory` (not `reply`) as the assistant's text (it also
  lists the schedules shown). Gemini knows the student's first name only (Nov 18).
- POST /ai/suggest: the Create Schedule form's Auto-generate. Code builds and checks the schedule
  (app/suggest.py); one Gemini call only explains it. Same request and response as before.

Gemini never decides validity (the checker does) and never saves (the student's Save button
calls POST /schedules).
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import advisor, solver
from app import suggest as suggest_engine
from app.auth import ApiError, current_student_id
from app.checker import SectionInfo
from app.db import SessionLocal
from app.models import Term
from app.routers import planning
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
    suggestions: list[str] = Field(default_factory=list,
                                   description="Up to 3 quick replies for buttons (send one as the next message)")
    tools_used: list[str]


class Block(BaseModel):
    days: str = Field(pattern=r"^[MTWRFSUmtwrfsu]+$")
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Lunch(BaseModel):
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class Preferences(BaseModel):
    """The Create Schedule form. Fields left out fall back to the student's saved preferences
    (GET /me/preferences); fixed calendar events are always kept free."""

    term_id: uuid.UUID | None = Field(default=None, description="Only the current registration term for now")
    target_credits: int | None = Field(default=None, ge=1, le=21)
    min_credits: int | None = Field(default=None, ge=0, le=21)
    max_credits: int | None = Field(default=None, ge=1, le=21)
    unavailable: list[Block] = Field(default_factory=list, max_length=10)
    preferred_time: Literal["morning", "midday", "afternoon", "evening", "none", ""] | None = None
    preferred_days: str | None = Field(default=None, pattern=r"^[MTWRFmtwrf]{0,5}$",
                                       description="Letters MTWRF; soft")
    delivery: list[Literal["in_person", "online"]] | None = Field(default=None, min_length=1, max_length=2)
    lunch: Lunch | None = None
    preferred_instructors: list[str] = Field(default_factory=list, max_length=10)
    avoid_instructors: list[str] = Field(default_factory=list, max_length=10)
    notes: str = Field(default="", max_length=1000)


SAVED_FIELDS = ("min_credits", "max_credits", "preferred_time", "preferred_days", "delivery")


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


def _run(student_id: uuid.UUID, message: str, history: list[dict]) -> dict:
    try:
        return advisor.advise(student_id, message, history)
    except advisor.AdvisorUnavailable as error:
        raise ApiError(503 if error.code == "gemini_model_not_set" else 502, error.code) from None
    except LookupError:
        raise ApiError(401, "not_authenticated") from None


@router.post("/advisor", response_model=AdvisorReply)
def flow(body: AdvisorRequest, student_id: uuid.UUID = Depends(current_student_id)):
    result = _run(student_id, body.message, [t.model_dump() for t in body.history])
    return {**result, "proposals": [_proposal(p) for p in result["proposals"]]}


def with_saved(body: Preferences, saved: dict) -> tuple[Preferences, str | None]:
    """The form with the saved preferences filling every field it left out, and the saved
    flexibility (None when nothing was ever saved)."""
    if saved.get("updated_at") is None:
        return body, None
    filled = {name: saved[name] for name in SAVED_FIELDS if name not in body.model_fields_set}
    if filled.get("min_credits") == 0:
        filled["min_credits"] = None  # 0 = no minimum saved: keep Auto-generate's usual target (Nov 20)
    merged = body.model_copy(update=filled)
    if merged.min_credits is not None and merged.max_credits is not None and merged.min_credits > merged.max_credits:
        merged = merged.model_copy(update={"min_credits": merged.max_credits})
    return merged, saved.get("flexibility")


def preferences_message(p: Preferences, flexibility: str | None = None) -> str:
    """The form as a plain request to Flow (no personal data)."""
    lines = ["Build my schedule for next term."]
    if p.target_credits:
        lines.append(f"Target: {p.target_credits} credits.")
    elif p.min_credits:
        lines.append(f"I want {p.min_credits}-{p.max_credits or 18} credits.")
    elif p.max_credits is not None:
        lines.append(f"Up to {p.max_credits} credits.")
    for b in p.unavailable:
        lines.append(f"I can't do {b.days.upper()} {b.start}-{b.end}.")
    lines.append("Keep my fixed calendar commitments free.")
    if p.preferred_time and p.preferred_time != "none":
        lines.append(f"I prefer {p.preferred_time} classes.")
    if p.preferred_days:
        lines.append(f"I prefer classes on {p.preferred_days.upper()}.")
    if p.delivery == ["in_person"]:
        lines.append("In-person sections only.")
    elif p.delivery == ["online"]:
        lines.append("Online sections only.")
    if p.lunch:
        lines.append(f"I'd like lunch free {p.lunch.start}-{p.lunch.end}.")
    if p.preferred_instructors:
        lines.append("Instructors I'd like: " + ", ".join(p.preferred_instructors) + ".")
    if p.avoid_instructors:
        lines.append("Instructors to avoid: " + ", ".join(p.avoid_instructors) + ".")
    if flexibility == "strict":
        lines.append("Treat these preferences as firm.")
    elif flexibility == "flexible":
        lines.append("These preferences are light wishes.")
    if p.notes.strip():
        lines.append("Notes: " + p.notes.strip())
    return " ".join(lines)


def load_saved_preferences(student_id: uuid.UUID) -> dict:
    return planning.load_preferences(student_id)


@router.post("/suggest", response_model=SuggestResult)
def suggest(body: Preferences, student_id: uuid.UUID = Depends(current_student_id)):
    if body.term_id is not None:
        with SessionLocal() as session:
            current = session.scalar(select(Term.id).where(Term.is_current_registration.is_(True)))
        if body.term_id != current:
            return JSONResponse(status_code=422, content={"error": "term_not_supported"})
    body, flexibility = with_saved(body, load_saved_preferences(student_id))
    try:
        result = run_suggest(student_id, to_suggest_request(body, flexibility))
    except LookupError:
        raise ApiError(401, "not_authenticated") from None
    return {"section_ids": [s.id for s in result.sections], "sections": [_section(s) for s in result.sections],
            "explanation": result.explanation, "warnings": result.warnings, "conflicts": result.conflicts}


def to_suggest_request(p: Preferences, flexibility: str | None) -> suggest_engine.SuggestRequest:
    clock = suggest_engine.clock
    return suggest_engine.SuggestRequest(
        target_credits=p.target_credits, min_credits=p.min_credits, max_credits=p.max_credits,
        unavailable=[solver.Block(b.days.upper(), clock(b.start), clock(b.end)) for b in p.unavailable],
        preferred_time=p.preferred_time or None, preferred_days=(p.preferred_days or "").upper(),
        delivery=p.delivery, lunch=solver.Block("MTWRF", clock(p.lunch.start), clock(p.lunch.end)) if p.lunch else None,
        preferred_instructors=p.preferred_instructors, avoid_instructors=p.avoid_instructors, notes=p.notes,
        request_text=preferences_message(p, flexibility),
    )


def run_suggest(student_id: uuid.UUID, request: suggest_engine.SuggestRequest) -> suggest_engine.Suggestion:
    """Module function so tests can replace it."""
    return suggest_engine.suggest_for_student(student_id, request)
