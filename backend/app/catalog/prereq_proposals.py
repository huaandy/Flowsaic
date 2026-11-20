"""A one-time, offline Gemini pass over prereq wording the parser can't read (Nov 20).

Run by db/scripts/propose_prereqs.py. It reads data/course_info.csv, picks the courses a
person should look at (every needs_review row with prereq text, and every row whose prereqs
use alternatives together with AND groups: the lecture/lab pair courses), sends their public
catalog wording to Gemini in batches, and writes data/course_prereq_proposals.csv.

Nothing here changes what Flowsaic enforces. A proposal is only used after a person reads it
and copies the row into data/course_prereq_overrides.csv with their name in reviewed_by
(AGENTS.md ground rule 5: the LLM never decides validity). Code checks every proposal before
it is written: it must parse in the loader's syntax and may only name courses that appear in
the catalog wording; anything else is marked valid=no with the reason.

Only public catalog text is sent (course code, title, prerequisite wording). No student data.
"""

import csv
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.catalog.course_build import codes, expand_slash
from app.normalize import parse_prereq_sets

PROPOSAL_COLUMNS = [
    "code", "title", "prereq_text", "current_prereqs", "current_needs_review",
    "proposed_prereqs", "proposed_other_requirements", "valid", "check_note", "model_note",
    "model", "proposed_at",
]
BATCH_SIZE = 20

SYSTEM = """You turn university catalog prerequisite wording into a strict machine format.

Format for "prereqs":
- ';' separates groups that are ALL required.
- '|' separates alternatives inside one group (any ONE of them is enough).
- '+' joins courses that are needed TOGETHER as one alternative (a lecture and its lab).
- Course codes are written exactly like 'PHYS 2103' (subject, a space, the number).
- Example: "PHYS 2103 and PHYS 2101, or PHYS 2213 and PHYS 2211, and MATH 1023"
  -> "PHYS 2103+PHYS 2101|PHYS 2213+PHYS 2211;MATH 1023"
- "BIOL 2063 /2061" means BIOL 2063 and BIOL 2061 together.

Rules:
- Use only course codes that appear in the wording. Never invent one.
- Conditions that are not courses (instructor or department permission, class standing,
  admission to a program, ACT scores, placement exams, minimum grades, "or equivalent")
  go in "other_requirements" as short plain text, never in "prereqs".
- When a non-course condition is an alternative to the courses ("X or instructor
  permission"), still write the courses in "prereqs" and put "or instructor permission" in
  "other_requirements".
- When a non-course condition can replace the courses entirely (for example "MATH 1023 or an
  ACT math subscore of 26"), leave "prereqs" empty and explain in "note".
- If the wording is ambiguous, give your best reading and say why in "note".

Answer with JSON only: a list with one object per course, in the order given:
[{"code": "...", "prereqs": "...", "other_requirements": "...", "note": "..."}]"""


@dataclass
class Proposal:
    code: str
    prereqs: str
    other_requirements: str
    note: str


def needs_a_look(row: dict[str, str]) -> bool:
    """needs_review rows with wording to read, and rows mixing alternatives with AND groups
    (the lecture/lab pair courses and the other ';' + '|' rows)."""
    if not row["prereq_text"]:
        return False
    prereqs = row["prereqs"]
    return bool(row["needs_review"]) or "+" in prereqs or (";" in prereqs and "|" in prereqs)


def select_rows(course_info: Path, only: set[str] | None = None) -> list[dict[str, str]]:
    with open(course_info, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if only:
        return [row for row in rows if row["code"] in only and row["prereq_text"]]
    return [row for row in rows if needs_a_look(row)]


def batch_prompt(rows: list[dict[str, str]]) -> str:
    lines = ["Convert these courses' prerequisites:"]
    for row in rows:
        lines.append(f"- {row['code']} ({row['title']}): {row['prereq_text']}")
    return "\n".join(lines)


def parse_answer(text: str) -> list[Proposal]:
    """Gemini's JSON answer -> proposals. Tolerates a ```json fence. Bad JSON -> []."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = data.get("courses") or [data]
    proposals = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and item.get("code"):
            proposals.append(Proposal(
                code=" ".join(str(item["code"]).split()),
                prereqs=str(item.get("prereqs") or "").strip(),
                other_requirements=str(item.get("other_requirements") or "").strip(),
                note=str(item.get("note") or "").strip(),
            ))
    return proposals


def check_proposal(row: dict[str, str], proposal: Proposal | None) -> tuple[str, str]:
    """(valid 'yes'/'no', why). Code, not Gemini, decides whether a proposal is even usable."""
    if proposal is None:
        return "no", "no answer for this course"
    try:
        groups = parse_prereq_sets(proposal.prereqs)
    except ValueError:
        return "no", "prereqs don't parse in the loader's syntax"
    named = {code for group in groups for option in group for code in option}
    in_text = set(codes(expand_slash(row["prereq_text"])))
    invented = sorted(named - in_text)
    if invented:
        return "no", f"names courses not in the catalog wording: {', '.join(invented)}"
    if proposal.prereqs == row["prereqs"] and proposal.other_requirements == row["other_requirements"]:
        return "yes", "same as now"
    return "yes", ""


def ask_gemini(client, model: str, rows: list[dict[str, str]]) -> list[Proposal]:
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=batch_prompt(rows))])],
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0,
                                           response_mime_type="application/json"),
    )
    return parse_answer(response.text)


def propose(
    rows: list[dict[str, str]],
    client,
    model: str,
    *,
    batch_size: int = BATCH_SIZE,
    log_line: Callable[[str], None] = print,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[dict[str, str]]:
    """One proposal row per course. A batch whose call fails is written with valid=no."""
    out: list[dict[str, str]] = []
    stamp = now().isoformat(timespec="seconds")
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        try:
            answers = {p.code: p for p in ask_gemini(client, model, batch)}
            failed = ""
        except Exception as error:  # noqa: BLE001 - one failed batch must not lose the rest
            answers, failed = {}, f"Gemini call failed ({type(error).__name__})"
        for row in batch:
            proposal = answers.get(row["code"])
            valid, why = ("no", failed) if failed else check_proposal(row, proposal)
            out.append({
                "code": row["code"], "title": row["title"], "prereq_text": row["prereq_text"],
                "current_prereqs": row["prereqs"], "current_needs_review": row["needs_review"],
                "proposed_prereqs": proposal.prereqs if proposal else "",
                "proposed_other_requirements": proposal.other_requirements if proposal else "",
                "valid": valid, "check_note": why, "model_note": proposal.note if proposal else "",
                "model": model, "proposed_at": stamp,
            })
        log_line(f"{min(start + batch_size, len(rows))} / {len(rows)} courses")
    return out


def write_proposals(rows: list[dict[str, str]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=PROPOSAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
