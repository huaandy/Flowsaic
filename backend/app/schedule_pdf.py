"""A saved schedule as a PDF for an academic advisor to review: GET /schedules/{id}/pdf (Nov 20).

Three steps, each testable on its own:
- load_report(): everything the page shows, read for the signed-in student's own schedule.
- render_html(): plain data -> one HTML page (every value escaped). Pure.
- html_to_pdf(): the HTML -> PDF bytes with the Playwright Chromium setup already installs
  for mySAU connect (headless here; no new dependency).

What goes on it: the student's name, major, catalog year, classification, hours, hold yes/no
and how fresh the data is; each section (code, title, section, days, times, instructor,
location, credits, the requirement it fills); total credits; how each course's prereqs are
met, flagging those met only by a course still in progress; the checker's warnings (and any
conflicts) in its own plain words; requirements still left after this term; the student's
commitments by category, day and time only (never a title or location: those are the
student's own words); whether the student or Flow built it; when the PDF was made.

Not on it: email, student ID, signature lines or any advisor workflow (semester 2).
"""

import html
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app import checker
from app.db import SessionLocal
from app.models import CalendarEvent, RefreshRun, Student
from app.normalize import DAY_ORDER, option_codes, option_done
from app.progress import Taken, build_progress, course_flags, load_progress_inputs, split_taken

DAY_NAMES = {"M": "Mon", "T": "Tue", "W": "Wed", "R": "Thu", "F": "Fri", "S": "Sat", "U": "Sun"}
CATEGORY_NAMES = {"work": "Work", "personal_study": "Personal / study", "extracurricular": "Extracurricular"}


class PdfUnavailable(RuntimeError):
    """Chromium isn't installed (or can't start) on this machine."""


@dataclass
class Report:
    student: dict
    schedule: dict
    sections: list[dict]
    prereqs: list[dict]
    conflicts: list[str]
    warnings: list[str]
    left: list[dict]
    commitments: list[dict]
    freshness: dict
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# --- prereqs and requirements (pure) ---------------------------------------------------------------

def prereq_status(code: str, prereqs: dict[str, list[list[str]]], passed: dict, in_progress: dict) -> dict:
    """How each prereq group of one course is met. Prefers an option fully passed; otherwise
    one that needs a course still in progress (flagged); otherwise not met."""
    groups = []
    for options in prereqs.get(code, []):
        passed_option = next((o for o in options if option_done(o, passed)), None)
        if passed_option:
            groups.append({"options": options, "met_by": passed_option, "state": "passed"})
            continue
        ip_option = next((o for o in options if option_done(o, passed, in_progress)), None)
        if ip_option:
            pending = [c for c in option_codes(ip_option) if c not in passed]
            groups.append({"options": options, "met_by": ip_option, "state": "in_progress", "pending": pending})
        else:
            groups.append({"options": options, "met_by": None, "state": "missing"})
    return {"code": code, "groups": groups,
            "only_in_progress": any(g["state"] == "in_progress" for g in groups)}


GENERIC_NAME = re.compile(r"^(select|choose|take)\b", re.I)


def requirement_label(name: str, parent: str | None) -> str:
    """'Select 3-5 hours:' under 'UL CS/Math Electives' -> 'UL CS/Math Electives: select 3-5 hours'.
    Audit blocks often have a generic name that only makes sense next to their parent's."""
    name = name.strip().rstrip(":").strip()
    if parent and GENERIC_NAME.match(name):
        return f"{parent.strip().rstrip(':')}: {name[0].lower()}{name[1:]}"
    return name


def requirement_labels(tree: list[dict]) -> dict[str, str]:
    """Requirement name -> the label shown in the PDF (generic names get their parent's)."""
    labels: dict[str, str] = {}

    def walk(node: dict, parent: str | None) -> None:
        labels.setdefault(node["name"], requirement_label(node["name"], parent))
        for child in node.get("children") or []:
            walk(child, node["name"])

    for root in tree:
        walk(root, None)
    return labels


def left_after_term(tree: list[dict], schedule_codes: set[str]) -> list[dict]:
    """The most specific requirements not met yet, with the schedule's courses counted as in
    progress. Each: label, hours text, the courses in this schedule that count toward it, and
    covered = this schedule (once passed) brings it to its required hours.

    covered matters for a connected student: the audit's own statuses are used as is, so a
    schedule never turns an audit block "in progress"; its hours still show it is covered."""
    out: list[dict] = []
    labels = requirement_labels(tree)

    def walk(node: dict) -> None:
        children = node.get("children") or []
        open_children = [c for c in children if c["status"] == "not_met"]
        for child in children:
            walk(child)
        if node["status"] != "not_met" or open_children:
            return
        listed = {c["code"] for c in node.get("courses") or []}
        listed |= {c["code"] for e in node.get("electives") or [] for c in e.get("courses") or []}
        in_schedule = sorted(listed & schedule_codes)
        required = node.get("hours_required")
        done = (node.get("hours_done") or 0) + (node.get("hours_in_progress") or 0)
        hours = f"{_num(done)} of {_num(required)} hours" if required else ""
        covered = bool(in_schedule and required and done >= required)
        out.append({"name": labels[node["name"]], "hours": hours, "this_schedule": in_schedule, "covered": covered})

    for root in tree:
        walk(root)
    return out


def _num(value) -> str:
    value = float(value or 0)
    return str(int(value)) if value == int(value) else f"{value:g}"


def commitment_rows(events: list) -> list[dict]:
    """Category, day, time and fixed/flexible only. Titles and locations never leave here."""
    rows = [{"category": CATEGORY_NAMES.get(e.category, "Personal"), "day": e.day,
             "time": f"{e.start_time:%H:%M}-{e.end_time:%H:%M}", "fixed": bool(e.fixed)} for e in events]
    return sorted(rows, key=lambda r: (DAY_ORDER.find(r["day"]), r["time"]))


# --- database --------------------------------------------------------------------------------------

def _freshness(session, student: Student, term_name: str) -> dict:
    export = session.scalar(
        select(RefreshRun.finished_at).where(RefreshRun.kind == "sections", RefreshRun.status == "ok")
        .order_by(RefreshRun.finished_at.desc()).limit(1)
    )
    return {"audit_refreshed_at": student.audit_refreshed_at, "schedule_term": term_name,
            "schedule_export_at": export}


def load_report(student_id: uuid.UUID, schedule_id: uuid.UUID) -> Report:
    """The student's own schedule only. Raises ApiError 404 schedule_not_found otherwise."""
    from app.routers.schedules import get_schedule

    detail = get_schedule(student_id, schedule_id)  # 404 for someone else's schedule
    inputs = load_progress_inputs(student_id)
    flags = course_flags(inputs)
    passed, in_progress = split_taken(inputs["taken"])
    codes = list(dict.fromkeys(s["code"] for s in detail["sections"]))
    credits = {s["code"]: s["credits"] for s in detail["sections"]}
    progress_now = build_progress(**inputs)
    after = build_progress(**{**inputs, "taken": inputs["taken"] + [
        Taken(code, "in_progress", None, credits[code]) for code in codes
        if code not in passed and code not in in_progress]})

    with SessionLocal() as session:
        student = session.get(Student, student_id)
        events = session.scalars(select(CalendarEvent).where(CalendarEvent.student_id == student_id)).all()
        freshness = _freshness(session, student, detail["term"]["name"])
        hours = progress_now["hours"]
        student_info = {
            "name": student.name, "major": student.major or (progress_now["plan"] or {}).get("name"),
            "catalog_year": student.catalog_year or (progress_now["plan"] or {}).get("catalog_year"),
            "classification": student.classification,
            "hours_earned": float(student.total_hours_earned) if student.total_hours_earned is not None else hours["earned"],
            "hours_needed": float(student.total_hours_needed) if student.total_hours_needed is not None else hours["required"],
            "has_hold": bool(student.has_hold), "plan_source": progress_now["source"],
        }
        commitments = commitment_rows(events)

    labels = requirement_labels(progress_now["requirements"])
    sections = [{**s, "requirements": [labels.get(n, n) for n in flags.requirement_names(s["code"])]}
                for s in detail["sections"]]
    return Report(
        student=student_info,
        schedule={"name": detail["name"], "term": detail["term"]["name"], "source": detail["source"],
                  "created_at": detail["created_at"], "credits": detail["credits"]},
        sections=sections,
        prereqs=[prereq_status(code, inputs["prereqs"], passed, in_progress) for code in codes],
        conflicts=[c["message"] for c in detail["conflicts"]],
        warnings=[w["message"] for w in detail["warnings"]],
        left=left_after_term(after["requirements"], set(codes)),
        commitments=commitments,
        freshness=freshness,
    )


# --- HTML ------------------------------------------------------------------------------------------

def _e(value) -> str:
    return html.escape("" if value is None else str(value))


def _date(value) -> str:
    return value.strftime("%b %d, %Y") if value else ""


def _days(days: str | None) -> str:
    return " ".join(DAY_NAMES.get(d, d) for d in days) if days else "Online / TBA"


def _option(option: str) -> str:
    return " and ".join(option_codes(option))


def _prereq_lines(item: dict) -> str:
    if not item["groups"]:
        return "No prerequisites listed"
    parts = []
    for group in item["groups"]:
        wanted = " or ".join(f"({_option(o)})" if "+" in o else o for o in group["options"])
        if group["state"] == "passed":
            parts.append(f"{_e(wanted)}: met by {_e(_option(group['met_by']))} (passed)")
        elif group["state"] == "in_progress":
            parts.append(f"{_e(wanted)}: <b>met only by a course in progress</b> "
                         f"({_e(', '.join(group['pending']))}, must be passed)")
        else:
            parts.append(f"{_e(wanted)}: <b>not met</b>")
    return "<br>".join(parts)


CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; color: #1d2530; font-size: 10.5pt; margin: 0; }
h1 { font-size: 17pt; margin: 0 0 2px; }
h2 { font-size: 11.5pt; margin: 18px 0 6px; border-bottom: 1px solid #c9d1db; padding-bottom: 3px; }
.sub { color: #556070; margin: 0 0 12px; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 4px 6px; border-bottom: 1px solid #e3e8ee; }
th { background: #f1f4f8; font-weight: 600; font-size: 9.5pt; }
.facts td:first-child { color: #556070; width: 30%; }
.num { text-align: right; white-space: nowrap; }
.flag { color: #9b4a00; }
ul { margin: 4px 0; padding-left: 18px; }
.foot { color: #6a7482; font-size: 8.5pt; margin-top: 18px; }
h2, .subhead { break-after: avoid; page-break-after: avoid; }
tr, li { break-inside: avoid; page-break-inside: avoid; }
"""


def render_html(report: Report) -> str:
    s, sch, f = report.student, report.schedule, report.freshness
    hours = _num(s["hours_earned"]) + (f" of {_num(s['hours_needed'])}" if s["hours_needed"] else "")
    audit = (f"mySAU degree audit, refreshed {_date(f['audit_refreshed_at'])}" if f["audit_refreshed_at"]
             else "public degree map (no mySAU audit connected)" if s["plan_source"] == "degree_plan"
             else "no degree plan on file")
    export = (f"{_e(f['schedule_term'])} course schedule, exported {_date(f['schedule_export_at'])}"
              if f["schedule_export_at"] else f"{_e(f['schedule_term'])} course schedule (loaded from a saved file)")
    source = "Built with Flow, Flowsaic's AI advisor, and checked by the schedule checker" if sch["source"] == "ai" \
        else "Built by the student in Create Schedule"

    facts = [("Student", s["name"]), ("Major", s["major"]), ("Catalog year", s["catalog_year"]),
             ("Classification", s["classification"]), ("Hours earned", hours),
             ("Registration hold", "Yes" if s["has_hold"] else "No")]
    rows = "".join(f"<tr><td>{_e(k)}</td><td>{_e(v) if v not in (None, '') else '-'}</td></tr>" for k, v in facts)

    section_rows = "".join(
        f"<tr><td>{_e(x['code'])}</td><td>{_e(x['title'])}</td><td>{_e(x['section_number'])}</td>"
        f"<td>{_e(_days(x['days']))}</td>"
        f"<td>{_e(x['start_time'] + '-' + x['end_time']) if x['start_time'] else ''}</td>"
        f"<td>{_e(x['instructor'])}</td><td>{_e(x['location'])}</td><td class='num'>{_e(_num(x['credits']))}</td>"
        f"<td>{_e('; '.join(x['requirements'])) or 'Not on the degree plan'}"
        f"{'' if x['active'] else ' <b>(no longer in the latest export)</b>'}</td></tr>"
        for x in report.sections)

    prereq_rows = "".join(
        f"<tr><td>{_e(p['code'])}{' <span class=flag>(in progress)</span>' if p['only_in_progress'] else ''}</td>"
        f"<td>{_prereq_lines(p)}</td></tr>" for p in report.prereqs)

    def bullet(items: list[str], empty: str) -> str:
        return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>" if items else f"<p>{_e(empty)}</p>"

    def requirement_items(rows: list[dict]) -> str:
        return "<ul>" + "".join(
            f"<li>{_e(r['name'])}{' (' + _e(r['hours']) + ')' if r['hours'] else ''}"
            f"{' - this schedule counts toward it: ' + _e(', '.join(r['this_schedule'])) if r['this_schedule'] else ''}</li>"
            for r in rows) + "</ul>"

    still_left = [r for r in report.left if not r.get("covered")]
    covered = [r for r in report.left if r.get("covered")]
    left = (requirement_items(still_left) if still_left
            else f"<p>Nothing {'else ' if covered else ''}left that Flowsaic can track.</p>")
    if covered:
        left += ('<p class="subhead"><b>Covered by this schedule once its courses are passed:</b></p>'
                 + requirement_items(covered))

    commitments = "".join(
        f"<tr><td>{_e(DAY_NAMES.get(c['day'], c['day']))}</td><td>{_e(c['time'])}</td><td>{_e(c['category'])}</td>"
        f"<td>{'Fixed (classes may not overlap)' if c['fixed'] else 'Flexible'}</td></tr>" for c in report.commitments)

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Schedule for review</title><style>{CSS}</style></head><body>
<h1>{_e(sch['term'])} schedule for review</h1>
<p class="sub">{_e(sch['name'])} &middot; {_e(source)} &middot; saved {_date(sch['created_at'])}</p>
<table class="facts">{rows}</table>
<h2>Data freshness</h2>
<p>Degree requirements: {_e(audit)}.<br>Sections: {export}.</p>
<h2>Sections ({_e(_num(sch['credits']))} credits)</h2>
<table><tr><th>Course</th><th>Title</th><th>Sec.</th><th>Days</th><th>Time</th><th>Instructor</th>
<th>Location</th><th class="num">Cr.</th><th>Requirement it fills</th></tr>{section_rows}
<tr><td colspan="7"><b>Total credits</b></td><td class="num"><b>{_e(_num(sch['credits']))}</b></td><td></td></tr></table>
<h2>Prerequisites</h2>
<table><tr><th>Course</th><th>How it is met</th></tr>{prereq_rows}</table>
<h2>Checker results</h2>
{bullet(report.conflicts, '') if report.conflicts else ''}
{bullet(report.warnings, 'No warnings: no time overlaps, missing prerequisites, full sections or credit-limit issues.')}
<h2>Requirements still left after this term</h2>
{left}
<h2>Weekly commitments</h2>
{"<table><tr><th>Day</th><th>Time</th><th>Category</th><th>Kind</th></tr>" + commitments + "</table>"
 if report.commitments else "<p>None entered.</p>"}
<p class="foot">Generated by Flowsaic on {report.generated_at:%b %d, %Y at %H:%M} UTC. Prerequisites and requirements
come from SAU's catalog and the student's record in Flowsaic; the official degree audit in mySAU decides.</p>
</body></html>"""


# --- PDF -------------------------------------------------------------------------------------------

def html_to_pdf(page_html: str) -> bytes:
    """Headless Chromium. No network, no files written. Raises PdfUnavailable."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as error:  # pragma: no cover - playwright is a dependency
        raise PdfUnavailable("playwright not installed") from error
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(java_script_enabled=False, offline=True)
                page = context.new_page()
                page.set_content(page_html, wait_until="load")
                return page.pdf(format="Letter", print_background=True,
                                margin={"top": "0.6in", "bottom": "0.6in", "left": "0.6in", "right": "0.6in"})
            finally:
                browser.close()
    except Error as error:
        raise PdfUnavailable(type(error).__name__) from error


def pdf_filename(schedule_name: str, term: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", f"{term} {schedule_name}").strip("-").lower()[:60]
    return f"flowsaic-{slug or 'schedule'}.pdf"
