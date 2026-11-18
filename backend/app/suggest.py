"""AI suggest (POST /ai/suggest, the Create Schedule form's Auto-generate), built by code.

Until Nov 18 this ran Flow's whole tool loop (4+ Gemini calls, ~20 s). Now code does the
exact work and Gemini only explains:
1. Courses: the student's can-take list (app/progress.py), required first, then choice, then
   electives, at most one course per choice group or elective line (so three courses never
   fill one "choose 3 hours" group). Form notes ("I like databases") move the courses whose
   description matches them up the list (one RAG search; skipped when there are no notes).
2. The solver (app/solver.py) finds the best section combination: fixed calendar events and
   "can't do" times are hard limits, delivery in-person-only / online-only too; preferred time,
   days, lunch, instructors and flexible events only rank. Credits: the target, else the saved
   range, else 12-15.
3. The checker runs on it, like on every schedule.
4. One Gemini call (no tools) writes a 2-3 sentence explanation. If Gemini isn't set up or
   fails, a plain sentence from code is used, so Auto-generate works without Gemini.

Gemini never picks the sections here; it only explains code's choice.
"""

import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import time

from google.genai import errors, types

from app import checker, solver
from app.advisor import (
    FLOW_INSTRUCTIONS,
    UNKNOWN_NAME,
    AdvisorData,
    build_student_record,
    load_advisor_data,
    personalize,
    section_brief,
    split_quick_replies,
)
from app.config import get_settings
from app.embeddings import get_client
from app.checker import SectionInfo

log = logging.getLogger(__name__)

DEFAULT_CREDITS = (12.0, 15.0)
MAX_CANDIDATES = 18  # courses handed to the solver (it stops once the credits are reached)
KIND_ORDER = {"required": 0, "choice": 1, "elective": 2}
EXPLAIN_THINKING = "LOW"  # the explanation needs no planning; see explain()

EXPLAIN_INSTRUCTIONS = """This request comes from the Create Schedule form. The schedule below was \
already built by Flowsaic's code and checked by the official checker; you don't change it. In 2-3 short \
sentences, tell the student why it fits them (requirements it covers, how it respects their commitments \
and preferences). Mention any conflict or warning briefly. Plain text, no lists, no questions."""


@dataclass
class SuggestRequest:
    """The Create Schedule form, already merged with the saved preferences."""

    target_credits: float | None = None
    min_credits: float | None = None
    max_credits: float | None = None
    unavailable: list[solver.Block] = field(default_factory=list)
    preferred_time: str | None = None  # morning | midday | afternoon | evening
    preferred_days: str = ""
    delivery: list[str] | None = None  # ["in_person"], ["online"] or both / None
    lunch: solver.Block | None = None
    preferred_instructors: list[str] = field(default_factory=list)
    avoid_instructors: list[str] = field(default_factory=list)
    notes: str = ""
    request_text: str = ""  # the form as a sentence, for the explanation


@dataclass
class Suggestion:
    sections: list[SectionInfo]
    conflicts: list[dict]
    warnings: list[dict]
    explanation: str


# --- choosing (pure) ------------------------------------------------------------------------------

def candidate_courses(can_take: list[dict], boosted: list[str] = ()) -> list[str]:
    """Course codes for the solver, best first: required, then choice, then elective; courses
    matching the notes first within each kind; one course per choice group or elective line."""
    rank = {code: i for i, code in enumerate(boosted)}
    ordered = sorted(can_take, key=lambda c: (KIND_ORDER.get(c["kind"], 3), rank.get(c["code"], len(rank)), c["code"]))
    chosen: list[str] = []
    groups: set[str] = set()
    for course in ordered:
        if course["kind"] != "required":
            group = (course["counts_toward"] or [course["code"]])[0]
            if group in groups:
                continue
            groups.add(group)
        chosen.append(course["code"])
    return chosen[:MAX_CANDIDATES]


def constraints_for(request: SuggestRequest, commitments: list) -> solver.Constraints:
    fixed, flexible = solver.commitment_blocks(commitments)
    if request.target_credits:
        low = float(request.target_credits)
        high = max(low, float(request.max_credits or 18))
    else:
        low = float(request.min_credits) if request.min_credits is not None else DEFAULT_CREDITS[0]
        high = float(request.max_credits) if request.max_credits is not None else max(DEFAULT_CREDITS[1], low)
    delivery = set(request.delivery or ["in_person", "online"])
    return solver.Constraints(
        unavailable=list(request.unavailable) + fixed, flexible_blocks=flexible,
        preferred_time=request.preferred_time if request.preferred_time in ("morning", "midday", "afternoon", "evening") else None,
        preferred_days=request.preferred_days or "", lunch=request.lunch,
        preferred_instructors=list(request.preferred_instructors), avoid_instructors=list(request.avoid_instructors),
        allow_online="online" in delivery, online_only=delivery == {"online"},
        min_credits=low, max_credits=high,
    )


def build_schedule(data: AdvisorData, request: SuggestRequest, boosted: list[str] = ()) -> tuple[list[SectionInfo], str | None]:
    """(the best sections, None) or ([], why nothing fits)."""
    codes = candidate_courses(data.progress["can_take"], boosted)
    if not codes:
        return [], "there's nothing on your plan you can take this term yet"
    constraints = constraints_for(request, data.context.commitments)
    result = solver.search([], codes, data.load_sections(codes), constraints, limit=1)
    # The minimum can't be reached (too few courses fit)? Take the most credits that do fit,
    # lowering the minimum one credit at a time. (With no minimum at all the solver's best
    # answer would be an empty schedule: every course is optional and costs a little score.)
    floor = int(constraints.min_credits or 1)
    while not result["schedules"] and floor > 1:
        floor -= 1
        result = solver.search([], codes, data.load_sections(codes), replace(constraints, min_credits=float(floor)), limit=1)
    if not result["schedules"] or not result["schedules"][0]["sections"]:
        return [], result["message"] or "no combination of sections fits your commitments and preferences"
    return result["schedules"][0]["sections"], None


def credits_of(sections: list[SectionInfo]) -> float:
    return sum(s.credits for s in {s.code: s for s in sections}.values())


def template_explanation(sections: list[SectionInfo], check: dict, data: AdvisorData) -> str:
    """Used when Gemini isn't available."""
    kinds = {c["code"]: c["kind"] for c in data.progress["can_take"]}
    required = sum(1 for code in {s.code for s in sections} if kinds.get(code) == "required")
    parts = [f"{len({s.code for s in sections})} courses, {credits_of(sections):g} credits"]
    if required:
        parts.append(f"{required} of them required for your degree")
    text = ", ".join(parts) + ", built around your fixed commitments."
    if check["conflicts"] or check["warnings"]:
        text += f" The checker found {len(check['conflicts'])} conflicts and {len(check['warnings'])} warnings, listed below."
    return text


# --- Gemini (one call, no tools) ------------------------------------------------------------------

def boosted_by_notes(data: AdvisorData, notes: str) -> list[str]:
    """Can-take courses whose description matches the notes, best first. [] without notes or Gemini."""
    notes = notes.strip()[:300]
    if not notes:
        return []
    try:
        return [r["code"] for r in data.search(notes, [c["code"] for c in data.progress["can_take"]])]
    except Exception as error:  # no key, network, quota: the schedule is still built
        log.warning("suggest: notes search skipped (%s)", type(error).__name__)
        return []


def explain(data: AdvisorData, sections: list[SectionInfo], check: dict, request: SuggestRequest,
            client, model: str | None) -> str | None:
    if client is None or not model:
        return None
    lines = [f"Student's request: {request.request_text or 'build my schedule'}",
             f"Schedule ({credits_of(sections):g} credits):"]
    lines += [f"- {b['label']} {b['title'] or ''}: {b['meets']}, {b['instructor']}" for b in map(section_brief, sections)]
    lines += [f"Conflict: {c['message']}" for c in check["conflicts"]]
    lines += [f"Warning: {w['message']}" for w in check["warnings"]]
    system = FLOW_INSTRUCTIONS + "\n\n" + EXPLAIN_INSTRUCTIONS + "\n\n" + build_student_record(data)
    contents = [types.Content(role="user", parts=[types.Part.from_text(text="\n".join(lines))])]
    # Low thinking: measured Nov 18 on gemini-3.8-flash, 9.1 s -> 2.9 s for the same quality. A
    # model that rejects the setting gets one plain retry.
    fast = types.GenerateContentConfig(system_instruction=system, temperature=0.4,
                                       thinking_config=types.ThinkingConfig(thinking_level=EXPLAIN_THINKING))
    try:
        try:
            response = client.models.generate_content(model=model, contents=contents, config=fast)
        except errors.ClientError as error:
            if "thinking" not in str(error).lower():
                raise
            response = client.models.generate_content(
                model=model, contents=contents, config=types.GenerateContentConfig(system_instruction=system, temperature=0.4))
    except errors.APIError as error:
        log.warning("suggest: explanation skipped (%s)", type(error).__name__)
        return None
    text, _ = split_quick_replies((response.text or "").strip())  # the form has no quick replies
    return personalize(text, data.first_name if data.first_name != UNKNOWN_NAME else "") or None


def suggest(data: AdvisorData, request: SuggestRequest, client, model: str | None) -> Suggestion:
    """The whole Auto-generate: choose, check, explain."""
    boosted = boosted_by_notes(data, request.notes) if client is not None else []
    sections, reason = build_schedule(data, request, boosted)
    if not sections:
        return Suggestion([], [], [], f"I couldn't build a schedule: {reason}. Try fewer limits, or ask Flow.")
    check = checker.check_schedule(sections, data.context)
    text = explain(data, sections, check, request, client, model) or template_explanation(sections, check, data)
    return Suggestion(sections, check["conflicts"], check["warnings"], text)


def suggest_for_student(student_id: uuid.UUID, request: SuggestRequest) -> Suggestion:
    """Load the student (LookupError if they're gone) and suggest. Without a Gemini key or model
    the schedule is still built; only the notes search and the written explanation are skipped."""
    try:
        client = get_client()
    except RuntimeError:
        client = None
    data = load_advisor_data(student_id, client)
    return suggest(data, request, client, get_settings().gemini_model)


def clock(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))
