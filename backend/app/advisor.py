"""Flow, Flowsaic's AI advisor (contract v2, Nov 17). Gemini behind it, with tools.

How Flow knows the student (never their name, email or ID):
- A STUDENT RECORD in the system instructions: program, classification, hours, passed and
  in-progress courses, every requirement's status, what they can take this term and what's
  blocked. Built from SQL by app/progress.py.
- Tools Gemini calls as needed (function calling, run here, scoped to this student):
  get_my_progress, get_course, find_courses (RAG), get_sections, check_schedule,
  find_schedules (the solver) and propose_schedule (a checked schedule card).
- The conversation so far, sent back by the front end (`memory` from earlier replies).

Rules: code does the exact work (eligibility, conflicts, combinations); Flow chooses, explains
and talks. Every proposed schedule goes through the checker. Flow never saves. Flow writes
{first_name} and the backend fills in the name after Gemini replies.
"""

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import time

from google import genai
from google.genai import errors, types
from sqlalchemy import select

from app import checker, progress, solver
from app.checker import SectionInfo, StudentContext
from app.config import get_settings
from app.db import SessionLocal
from app.demo_seed import NEW_STUDENT_EMAIL
from app.embeddings import embed_texts, get_client, query_prompt
from app.models import Course, DocChunk, Student, Term
from app.normalize import COURSE_CODE_RE

MAX_STEPS = 10  # model calls per message (tool rounds + the final answer)
WRAP_UP = ("(Flowsaic: two tool steps left. If you have a good schedule, call propose_schedule now; "
           "then answer the student.)")
ANSWER_NOW = "(Flowsaic: answer the student now in plain text, using what you already found.)"
MAX_PROPOSALS = 3
LABEL_RE = re.compile(r"^\s*([A-Z]+(?: [A-Z]+)* \d{4,5})\s*-\s*(\d{3}[A-Z]?)\s*$")
HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
NAME_TOKEN = "{first_name}"

FLOW_INSTRUCTIONS = """You are Flow, the friendly AI academic advisor inside Flowsaic, a course-planning app \
for Southern Arkansas University (SAU). You help one student plan: explain their degree progress, find \
courses and electives that fit their interests, and build schedules around their life.

How you work:
- The STUDENT RECORD below is accurate and comes from the school's data. Trust it over your own assumptions.
- Use your tools for anything specific: course details and prerequisites (get_course), what a course is \
about or which electives match an interest (find_courses), meeting times and seats (get_sections), \
whether a set of sections works (check_schedule), and building schedules (find_schedules).
- Never invent courses, sections, times, instructors, seats or rules. Only mention sections a tool returned.
- Before saying a course is or isn't offered, or that the student can't take it, look it up (get_course or \
get_sections) in this reply. Describe meeting times exactly as the tools return them; never say two courses \
share a time slot unless their times match.
- You only know Flowsaic's data: this student's record, SAU's catalog and this term's sections. For anything \
else (restaurants, campus life, registration dates, fees, people, policies not in your data) say plainly that \
you don't have that information and point them to SAU or their advisor. Never make up names, places, dates \
or policies, even as a friendly suggestion.
- When the student changes something vaguely ("I have a job", "I'm busy some days"), ask ONE short question \
about the specifics (which days and times) before rebuilding. Don't guess their schedule. Keep every earlier \
constraint unless they change it.
- If you swap out or postpone a required course, say it's still required and will need a later term.
- To show a schedule, ALWAYS call propose_schedule. It runs the official checker and shows the student a \
card with a Save button, right below your message. Build candidates with find_schedules first; it already \
avoids time overlaps. Don't repeat every section in your text; the card lists them.
- If propose_schedule reports conflicts, fix them (different sections or courses) and propose again, \
unless the student asked for that exact schedule. Never hide a conflict or warning; mention them briefly.
- Prefer courses the record marks as required, then choices, then electives, unless the student says otherwise.
- You never save, register or enroll the student. They click Save themselves, and register in mySAU.
- If something important is missing (how many credits, times they can't do), ask ONE short question. \
If they just want a schedule, build one without asking: start from the required and choice courses they can \
take, aim for 12-15 credits, propose it, and invite changes. If the required courses already make a sensible \
load (for example a senior who only needs a few courses), propose that and offer to add an elective rather \
than searching for one.
- Be efficient: usually 2-5 tool calls per reply. Don't repeat a search that already answered the question.
- "Open electives (any course counts)" means any offered course the student can take works; ask what \
interests them, or use find_courses with only_can_take=false once.
- When a requirement is "not tracked" or unclear, say so and suggest confirming with their SAU advisor.

Style: warm, encouraging, concise (usually under 150 words). Plain text with short bullet lists. No tables. \
Refer to courses as code and title, e.g. "CSCI 4203 Database Design". To address the student by name, \
write exactly {first_name} (only in greetings, at most once per reply). Never ask for passwords, ID \
numbers or other personal information."""

SUGGEST_INSTRUCTIONS = """This request comes from the Create Schedule form, not a conversation. Build ONE \
schedule from the student's preferences: call find_schedules (and check or adjust as needed), then call \
propose_schedule exactly once with your best schedule. Your text reply is a 2-4 sentence explanation of \
the choice. Do not ask questions."""

# --- tool declarations (what Gemini sees) ---------------------------------------------------

_SECTIONS_PARAM = {"type": "array", "items": {"type": "string"},
                   "description": "Section labels like 'CSCI 4203-001', from get_sections or find_schedules"}
_CODES_PARAM = {"type": "array", "items": {"type": "string"}, "description": "Course codes like 'CSCI 4203'"}

TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_my_progress",
        description="The student's full requirement tree: every group's status, hours, needed courses, "
                    "options and electives. Use for detailed degree-progress questions.",
        parameters_json_schema={"type": "object", "properties": {
            "group": {"type": "string", "description": "Optional: only the requirement group whose name contains this text"}}},
    ),
    types.FunctionDeclaration(
        name="get_course",
        description="One course: title, credits, description, prerequisites and whether the student meets "
                    "them, whether it's offered this term, and how it counts for the student.",
        parameters_json_schema={"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    ),
    types.FunctionDeclaration(
        name="find_courses",
        description="Search course descriptions by meaning (e.g. 'security', 'working with animals'). "
                    "By default searches only courses the student can take this term.",
        parameters_json_schema={"type": "object", "properties": {
            "query": {"type": "string"},
            "only_can_take": {"type": "boolean", "description": "Default true. False = any course offered this term."}},
            "required": ["query"]},
    ),
    types.FunctionDeclaration(
        name="get_sections",
        description="This term's sections for up to 8 courses: label, days, times, instructor, open seats.",
        parameters_json_schema={"type": "object", "properties": {"codes": _CODES_PARAM}, "required": ["codes"]},
    ),
    types.FunctionDeclaration(
        name="check_schedule",
        description="Run the official checker on a set of sections: conflicts (time overlap, missing prereq, "
                    "duplicate course) and warnings (already passed, full, not on plan, over 18 credits).",
        parameters_json_schema={"type": "object", "properties": {"sections": _SECTIONS_PARAM}, "required": ["sections"]},
    ),
    types.FunctionDeclaration(
        name="find_schedules",
        description="Find section combinations with no time overlaps that meet the constraints. 'must' "
                    "courses are always included; 'optional' courses are added best first until the credits "
                    "reach min_credits. Returns up to 3 options, each already checked.",
        parameters_json_schema={"type": "object", "properties": {
            "must": _CODES_PARAM,
            "optional": _CODES_PARAM,
            "min_credits": {"type": "number"},
            "max_credits": {"type": "number", "description": "Default 18"},
            "unavailable": {"type": "array", "description": "Times the student can't do", "items": {
                "type": "object", "properties": {"days": {"type": "string", "description": "Letters MTWRFSU, R = Thursday"},
                                                 "start": {"type": "string", "description": "HH:MM 24-hour"},
                                                 "end": {"type": "string", "description": "HH:MM 24-hour"}},
                "required": ["days", "start", "end"]}},
            "days_off": {"type": "string", "description": "Days with no classes, letters MTWRFSU"},
            "earliest_start": {"type": "string", "description": "HH:MM"},
            "latest_end": {"type": "string", "description": "HH:MM"},
            "preferred_time": {"type": "string", "enum": ["morning", "afternoon", "evening"]},
            "lunch": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}},
            "avoid_instructors": {"type": "array", "items": {"type": "string"}},
            "preferred_instructors": {"type": "array", "items": {"type": "string"}},
            "open_seats_only": {"type": "boolean"},
            "allow_online": {"type": "boolean", "description": "Default true"}}},
    ),
    types.FunctionDeclaration(
        name="propose_schedule",
        description="Show the student a schedule card (with a Save button) after running the checker. Returns "
                    "the checker's conflicts and warnings. Use for every schedule you recommend.",
        parameters_json_schema={"type": "object", "properties": {
            "name": {"type": "string", "description": "Short name, e.g. 'Spring 2027: afternoons, no Fridays'"},
            "sections": _SECTIONS_PARAM,
            "explanation": {"type": "string", "description": "One or two sentences on why this schedule"}},
            "required": ["name", "sections", "explanation"]},
    ),
]
TOOLS = types.Tool(function_declarations=TOOL_DECLARATIONS)


class AdvisorUnavailable(RuntimeError):
    """Gemini isn't configured or can't be reached. .code is the API error code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# --- the data Flow works from ----------------------------------------------------------------

@dataclass
class AdvisorData:
    first_name: str
    classification: str | None
    progress: dict
    context: StudentContext
    term_name: str | None
    load_sections: Callable[[list[str]], dict[str, list[SectionInfo]]]
    course_details: Callable[[str], dict | None]
    search: Callable[[str, list[str] | None], list[dict]]
    offered_codes: set[str] = field(default_factory=set)
    # (code, title) -> [{code, title}]: same subject, title starting the same way
    # ("Senior Project" -> "Senior Project I", "Senior Project II"), so a lookup shows the whole sequence.
    related_courses: Callable[[str, str], list[dict]] = lambda code, title: []


def _hours(value) -> str:
    return "?" if value is None else f"{float(value):g}"


def build_student_record(data: AdvisorData) -> str:
    """Everything Flow should know up front, as plain text. No name, email or ID."""
    p = data.progress
    lines = ["STUDENT RECORD (no personal identifiers)"]
    lines.append(f"Planning term: {data.term_name or 'unknown'}")
    if p["source"] == "audit":
        lines.append("Program: from the student's own mySAU degree audit")
    elif p["source"] == "degree_plan":
        lines.append(f"Program: {p['plan']['name']} ({p['plan']['catalog_year']} catalog, public degree map)")
    else:
        lines.append("Program: unknown. The student hasn't connected mySAU yet; suggest Connect mySAU on their profile.")
    lines.append(f"Classification: {data.classification or 'unknown'}. Hours: {_hours(p['hours']['earned'])} earned, "
                 f"{_hours(p['hours']['in_progress'])} in progress, {_hours(p['hours']['required'])} required.")
    passed = sorted(data.context.passed)
    lines.append("Passed: " + (", ".join(passed) if passed else "none"))
    lines.append("In progress now: " + (", ".join(sorted(data.context.in_progress)) or "none"))

    def walk(node: dict, depth: int) -> None:
        pad = "  " * depth
        hours = f" {_hours(node['hours_done'])}" + (f"+{_hours(node['hours_in_progress'])} in progress" if node["hours_in_progress"] else "")
        hours += f"/{_hours(node['hours_required'])} h" if node["hours_required"] is not None else " h"
        lines.append(f"{pad}- {node['name']}: {node['status']},{hours}")
        if node["status"] == "met":
            return
        needed = [c["code"] for c in node["courses"] if c["status"] == "needed"]
        options = [c["code"] for c in node["courses"] if c["status"] == "option"]
        if needed:
            lines.append(f"{pad}  still needed: {', '.join(needed)}")
        if options and node["rule"] == "choose_hours":
            lines.append(f"{pad}  choose from: {', '.join(options[:25])}" + (" ..." if len(options) > 25 else ""))
        for e in node["electives"]:
            if e["status"] != "met":
                lines.append(f"{pad}  elective: {e['text']} ({_hours(e['hours_done'])} done)")
        if node["status"] == "not_tracked" and node.get("note"):
            lines.append(f"{pad}  note: {node['note'][:200]}")
        for child in node["children"]:
            walk(child, depth + 1)

    lines.append("Requirements:")
    for node in p["requirements"]:
        walk(node, 0)
    lines.append(f"Can take in {data.term_name or 'this term'} (offered, not taken, prereqs met):")
    for c in p["can_take"]:
        lines.append(f"- [{c['kind']}] {c['code']} {c['title'] or ''} ({_hours(c['credits'])} cr, "
                     f"{c['seats_open']} open seats) counts toward: {'; '.join(c['counts_toward'])[:120]}")
    if not p["can_take"]:
        lines.append("- (nothing listed)")
    if p["blocked"]:
        lines.append("Needed but blocked by prerequisites: " + "; ".join(
            f"{b['code']} needs {' and '.join(' or '.join(g) for g in b['missing_prereqs'])}" for b in p["blocked"]))
    if p["open_electives"]:
        lines.append("Open electives (any course counts): " + "; ".join(p["open_electives"]))
    return "\n".join(lines)


# --- tools (run here, never by Gemini) --------------------------------------------------------

def _clock(value: str | None) -> time | None:
    if not value:
        return None
    match = HHMM_RE.match(value.strip())
    if not match:
        raise ValueError(f"time {value!r} must be HH:MM")
    return time(int(match[1]), int(match[2]))


def _code(raw: str) -> str:
    code = " ".join(str(raw).upper().split())
    if not COURSE_CODE_RE.fullmatch(code):
        raise ValueError(f"{raw!r} isn't a course code like 'CSCI 4203'")
    return code


def section_brief(s: SectionInfo) -> dict:
    return {
        "label": s.label, "title": s.title, "credits": s.credits,
        "meets": f"{s.days} {s.start:%H:%M}-{s.end:%H:%M}" if s.meets else "online or TBA",
        "instructor": s.instructor, "open_seats": s.seats_open, "capacity": s.capacity,
    }


def _checked(result: dict) -> dict:
    """The checker's result without section IDs (Gemini works with labels)."""
    return {kind: [{"code": i["code"], "message": i["message"]} for i in result[kind]] for kind in ("conflicts", "warnings")}


class AdvisorTools:
    def __init__(self, data: AdvisorData):
        self.data = data
        self.proposals: list[dict] = []
        self.used: list[str] = []

    def call(self, name: str, args: dict) -> dict:
        self.used.append(name)
        handler = getattr(self, f"tool_{name}", None)
        if handler is None:
            return {"error": f"unknown tool {name}"}
        try:
            return handler(**args)
        except (ValueError, TypeError, KeyError) as error:
            return {"error": str(error)}

    # get_my_progress
    def tool_get_my_progress(self, group: str | None = None) -> dict:
        def compact(node: dict) -> dict:
            return {
                "name": node["name"], "status": node["status"], "rule": node["rule"],
                "hours_done": node["hours_done"], "hours_in_progress": node["hours_in_progress"],
                "hours_required": node["hours_required"],
                "courses": {c["code"]: c["status"] for c in node["courses"]},
                "electives": [{"text": e["text"], "status": e["status"], "hours_done": e["hours_done"],
                               "counted": [c["code"] for c in e["courses"]]} for e in node["electives"]],
                "note": (node.get("note") or "")[:300] or None,
                "children": [compact(child) for child in node["children"]],
            }

        tree = [compact(node) for node in self.data.progress["requirements"]]
        if group:
            found: list[dict] = []

            def find(nodes: list[dict]) -> None:
                for node in nodes:
                    if group.lower() in node["name"].lower():
                        found.append(node)
                    else:
                        find(node["children"])

            find(tree)
            return {"requirements": found or f"no group named like {group!r}"}
        return {"requirements": tree}

    # get_course
    def tool_get_course(self, code: str) -> dict:
        code = _code(code)
        details = self.data.course_details(code)
        if details is None:
            return {"error": f"{code} isn't in the SAU catalog"}
        ctx = self.data.context
        prereqs = ctx.prereqs.get(code, [])
        missing = [g for g in prereqs if not any(o in ctx.passed or o in ctx.in_progress for o in g)]
        can = next((c for c in self.data.progress["can_take"] if c["code"] == code), None)
        status = self._status(code)
        related = [
            {"code": r["code"], "title": r["title"], "offered_this_term": r["code"] in self.data.offered_codes,
             "status_for_student": self._status(r["code"])}
            for r in self.data.related_courses(code, details["title"] or "") if r["code"] != code
        ]
        return {
            "code": code, "title": details["title"], "credits": details["credits"],
            "description": (details["description"] or "")[:900] or None,
            "other_requirements": details.get("other_requirements"),
            "prerequisites": " and ".join("(" + " or ".join(g) + ")" for g in prereqs) or "none listed",
            "missing_prerequisites": [" or ".join(g) for g in missing],
            "status_for_student": status,
            "counts_toward": can["counts_toward"] if can else None,
            "offered_this_term": code in self.data.offered_codes,
            "related_courses": related or None,
        }

    def _status(self, code: str) -> str:
        ctx = self.data.context
        missing = [g for g in ctx.prereqs.get(code, []) if not any(o in ctx.passed or o in ctx.in_progress for o in g)]
        offered = code in self.data.offered_codes
        if code in ctx.passed:
            return "passed"
        if code in ctx.in_progress:
            return "in progress now"
        if any(c["code"] == code for c in self.data.progress["can_take"]):
            return "can take this term"
        if not offered:
            return "not offered this term"
        if missing:
            return "offered this term, but blocked: needs " + " and ".join(" or ".join(g) for g in missing)
        return "offered, not on the student's remaining plan"

    # find_courses (RAG)
    def tool_find_courses(self, query: str, only_can_take: bool = True) -> dict:
        query = str(query).strip()[:300]
        if not query:
            raise ValueError("query is empty")
        codes = [c["code"] for c in self.data.progress["can_take"]] if only_can_take else sorted(self.data.offered_codes)
        if not codes:
            return {"results": [], "note": "nothing to search: the student has no courses they can take listed"}
        try:
            results = self.data.search(query, codes)
        except (errors.APIError, RuntimeError):
            return {"error": "course search is unavailable right now; use get_course or the record instead"}
        can = {c["code"]: c for c in self.data.progress["can_take"]}
        for r in results:
            r["can_take"] = r["code"] in can
            r["counts_toward"] = can[r["code"]]["counts_toward"] if r["code"] in can else None
        return {"results": results}

    # get_sections
    def tool_get_sections(self, codes: list[str]) -> dict:
        wanted = [_code(c) for c in list(codes)[:8]]
        found = self.data.load_sections(wanted)
        return {"courses": [{"code": code, "sections": [section_brief(s) for s in found.get(code, [])]
                             or "not offered this term"} for code in wanted]}

    def _resolve(self, labels: list[str]) -> list[SectionInfo]:
        parsed = []
        for label in labels:
            match = LABEL_RE.match(str(label).upper())
            if not match:
                raise ValueError(f"{label!r} isn't a section label like 'CSCI 4203-001'")
            parsed.append((" ".join(match[1].split()), match[2]))
        found = self.data.load_sections(sorted({code for code, _ in parsed}))
        sections = []
        for code, number in parsed:
            section = next((s for s in found.get(code, []) if s.section_number == number), None)
            if section is None:
                raise ValueError(f"{code}-{number} isn't offered this term")
            sections.append(section)
        return sections

    # check_schedule
    def tool_check_schedule(self, sections: list[str]) -> dict:
        resolved = self._resolve(list(sections)[:12])
        return {"credits": sum(s.credits for s in {s.code: s for s in resolved}.values()),
                **_checked(checker.check_schedule(resolved, self.data.context))}

    # find_schedules (the solver)
    def tool_find_schedules(self, must=None, optional=None, min_credits=None, max_credits=None, unavailable=None,
                            days_off="", earliest_start=None, latest_end=None, preferred_time=None, lunch=None,
                            avoid_instructors=None, preferred_instructors=None, open_seats_only=False,
                            allow_online=True) -> dict:
        must_codes = [_code(c) for c in (must or [])][:8]
        optional_codes = [_code(c) for c in (optional or [])][:20]
        if not must_codes and not optional_codes:
            raise ValueError("give at least one course in must or optional")
        blocks = [solver.Block(str(b["days"]).upper(), _clock(b["start"]), _clock(b["end"])) for b in (unavailable or [])]
        constraints = solver.Constraints(
            unavailable=blocks, earliest_start=_clock(earliest_start), latest_end=_clock(latest_end),
            days_off=re.sub(r"[^MTWRFSU]", "", str(days_off or "").upper()),
            avoid_instructors=list(avoid_instructors or []), preferred_instructors=list(preferred_instructors or []),
            preferred_time=preferred_time if preferred_time in ("morning", "afternoon", "evening") else None,
            lunch=solver.Block("MTWRF", _clock(lunch["start"]), _clock(lunch["end"])) if lunch and lunch.get("start") and lunch.get("end") else None,
            open_seats_only=bool(open_seats_only), allow_online=allow_online is not False,
            min_credits=float(min_credits) if min_credits is not None else None,
            max_credits=float(max_credits) if max_credits is not None else 18.0,
        )
        result = solver.search(must_codes, optional_codes, self.data.load_sections(must_codes + optional_codes),
                               constraints, limit=3)
        return {
            "options": [{"option": i + 1, "credits": s["credits"], "sections": [section_brief(x) for x in s["sections"]],
                         **_checked(checker.check_schedule(s["sections"], self.data.context))}
                        for i, s in enumerate(result["schedules"])],
            "unschedulable": result["unschedulable"],
            "message": result["message"],
        }

    # propose_schedule
    def tool_propose_schedule(self, name: str, sections: list[str], explanation: str = "") -> dict:
        if len(self.proposals) >= MAX_PROPOSALS:
            return {"error": f"at most {MAX_PROPOSALS} schedules per reply"}
        resolved = self._resolve(list(sections)[:12])
        if not resolved:
            raise ValueError("a schedule needs at least one section")
        result = checker.check_schedule(resolved, self.data.context)
        self.proposals.append({
            "name": str(name)[:120] or "Suggested schedule",
            "explanation": str(explanation)[:600],
            "sections": resolved,
            "credits": sum(s.credits for s in {s.code: s for s in resolved}.values()),
            "conflicts": result["conflicts"],
            "warnings": result["warnings"],
        })
        return {"shown_to_student": True, **_checked(result)}


# --- the conversation loop -----------------------------------------------------------------------

def personalize(text: str, first_name: str) -> str:
    return text.replace(NAME_TOKEN, first_name)


def _proposal_memory(proposals: list[dict]) -> str:
    if not proposals:
        return ""
    return "\n[Schedules shown: " + "; ".join(
        f"{p['name']}: {', '.join(s.label for s in p['sections'])}" for p in proposals) + "]"


def run_flow(data: AdvisorData, message: str, history: list[dict], *, client, model: str,
             mode: str = "chat") -> dict:
    """One student message -> Flow's reply, the schedules it proposed, and memory for the next turn."""
    tools = AdvisorTools(data)
    system = FLOW_INSTRUCTIONS + ("\n\n" + SUGGEST_INSTRUCTIONS if mode == "suggest" else "") + "\n\n" + build_student_record(data)
    config = types.GenerateContentConfig(
        system_instruction=system, tools=[TOOLS], temperature=0.4,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    final_config = types.GenerateContentConfig(system_instruction=system, temperature=0.4)
    contents = [
        types.Content(role="user" if turn["role"] == "user" else "model", parts=[types.Part.from_text(text=turn["text"])])
        for turn in history[-20:]
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    text = ""
    try:
        for step in range(MAX_STEPS):
            last = step == MAX_STEPS - 1
            response = client.models.generate_content(model=model, contents=contents,
                                                      config=final_config if last else config)
            calls = [] if last else (response.function_calls or [])
            if not calls:
                text = (response.text or "").strip()
                break
            contents.append(response.candidates[0].content)
            # Results go back as role "user" (the API rejects "tool"), each tied to its call's id.
            parts = [
                types.Part(function_response=types.FunctionResponse(
                    id=call.id, name=call.name,
                    response={"result": json.loads(json.dumps(tools.call(call.name, dict(call.args or {})), default=str))}))
                for call in calls
            ]
            if step == MAX_STEPS - 3:
                parts.append(types.Part.from_text(text=WRAP_UP))
            contents.append(types.Content(role="user", parts=parts))
        if not text:
            # One more try, plainly asking for an answer (the model sometimes stops without text).
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=ANSWER_NOW)]))
            text = (client.models.generate_content(model=model, contents=contents, config=final_config).text or "").strip()
    except errors.APIError:
        raise AdvisorUnavailable("ai_unavailable") from None

    if not text:
        text = ("I put together the schedule below." if tools.proposals
                else "Sorry, I couldn't come up with an answer for that. Could you rephrase it?")
    return {
        "reply": personalize(text, data.first_name),
        "memory": text + _proposal_memory(tools.proposals),  # keeps {first_name}: the name never goes to Gemini
        "proposals": tools.proposals,
        "tools_used": tools.used,
    }


# --- database -------------------------------------------------------------------------------------

def first_name_for(student: Student) -> str:
    if student.email == NEW_STUDENT_EMAIL or not student.name.strip():
        return "there"
    return student.name.split()[0]


def search_courses(client: genai.Client, query: str, codes: list[str] | None, k: int = 8) -> list[dict]:
    """RAG: the k course descriptions closest in meaning to the query, among `codes`."""
    vector = embed_texts(client, [query_prompt(query)])[0]
    distance = DocChunk.embedding.cosine_distance(vector).label("distance")
    statement = (
        select(Course.code, Course.title, Course.credits, Course.description, distance)
        .join(Course, Course.code == DocChunk.source_code)
        .where(DocChunk.source_type == "course")
        .order_by(distance).limit(k)
    )
    if codes is not None:
        statement = statement.where(DocChunk.source_code.in_(codes))
    with SessionLocal() as session:
        rows = session.execute(statement).all()
    return [{"code": code, "title": title, "credits": float(credits) if credits is not None else None,
             "description": (description or "")[:400], "distance": round(float(dist), 3)}
            for code, title, credits, description, dist in rows]


def load_advisor_data(student_id: uuid.UUID, client: genai.Client) -> AdvisorData:
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if student is None:
            raise LookupError("student not found")
        context = checker.load_student_context(session, student_id)
        term = session.scalar(select(Term).where(Term.is_current_registration.is_(True)))
        first_name, classification = first_name_for(student), student.classification
    student_progress = progress.load_progress(student_id)
    term_id = term.id if term else None
    offered = set(solver.load_offered_codes(term_id)) if term_id else set()

    def load_sections(codes: list[str]) -> dict[str, list[SectionInfo]]:
        return solver.load_term_sections(codes, term_id) if term_id else {}

    def course_details(code: str) -> dict | None:
        with SessionLocal() as session:
            course = session.scalar(select(Course).where(Course.code == code))
            if course is None:
                return None
            return {"title": course.title, "credits": float(course.credits) if course.credits is not None else None,
                    "description": course.description, "other_requirements": course.other_requirements}

    def related_courses(code: str, title: str) -> list[dict]:
        stem = " ".join(re.findall(r"[A-Za-z]+", title)[:2])
        if not stem:
            return []
        prefix = code.rsplit(" ", 1)[0]
        with SessionLocal() as session:
            rows = session.execute(
                select(Course.code, Course.title)
                .where(Course.code.like(prefix + " %"), Course.title.ilike(stem + "%"))
                .order_by(Course.code).limit(6)
            ).all()
        return [{"code": c, "title": t} for c, t in rows]

    return AdvisorData(
        first_name=first_name, classification=classification, progress=student_progress, context=context,
        term_name=term.name if term else None, load_sections=load_sections, course_details=course_details,
        search=lambda query, codes: search_courses(client, query, codes), offered_codes=offered,
        related_courses=related_courses,
    )


def advise(student_id: uuid.UUID, message: str, history: list[dict], mode: str = "chat") -> dict:
    """The endpoint's entry point: load everything for this student and run one turn."""
    settings = get_settings()
    if not settings.gemini_model:
        raise AdvisorUnavailable("gemini_model_not_set")
    try:
        client = get_client()
    except RuntimeError:
        raise AdvisorUnavailable("ai_unavailable") from None
    try:
        data = load_advisor_data(student_id, client)
        return run_flow(data, message, history, client=client, model=settings.gemini_model, mode=mode)
    except errors.APIError:
        raise AdvisorUnavailable("ai_unavailable") from None

