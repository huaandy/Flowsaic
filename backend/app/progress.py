"""Degree progress and "what can I take this term" for one student: the student context
that GET /me/progress returns and that Flow (the AI advisor) will be given.

Two sources (AGENTS.md, Nov 17):
- A student who connected mySAU: their audit (student_requirements) IS their plan.
- Everyone else (the demo students): the public degree map (requirement_groups).

Rules:
- Passed = completed with a grade that earns credit (F and W don't). In progress counts
  for prereqs and shows as "in progress", never as met.
- all: every listed course and child group done. choose_hours: listed courses add up to
  hours_required. A course used by one choose group isn't reused by another (so
  ENGL 2223 can't fill World Literature and Fine Arts/Humanities at once).
- Elective lines in a group's note ("12 hours of upper-level Psychology electives") are
  read by parse_electives. Taken courses not used by any listed requirement fill them,
  most specific elective first. Lines we can't read stay as plain notes.
- A group with nothing we can track (e.g. "Completion of an approved minor") is
  "not_tracked", never "met".
- Can take = offered this term (active sections), not passed or in progress, prereqs met
  (every prereq group has an option passed or in progress), undergraduate level.

The functions below are pure (plain data in, plain data out) so they can be tested
without a database; load_progress() reads the database and calls them.
"""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import (
    CompletedCourse,
    Course,
    CoursePrereq,
    DegreePlan,
    RequirementCourse,
    RequirementGroup,
    Section,
    Student,
    StudentRequirement,
    Term,
)
from app.normalize import COURSE_CODE_RE

NOT_EARNED = {"F", "W"}

# Subject words in elective lines -> course prefixes (SAU's catalog, Nov 2026).
SUBJECT_PREFIXES: dict[str, tuple[str, ...]] = {
    "computer science": ("CSCI",),
    "data science": ("DSCI",),
    "mathematics": ("MATH",),
    "math": ("MATH",),
    "information systems": ("IS",),
    "psychology": ("PSYC",),
    "sociology": ("SOC",),
    "social work": ("SWK",),
    "criminal justice": ("CRJU",),
    "public health": ("PH",),
    "natural science": ("BIOL", "CHEM", "PHYS", "GEOL", "PHSC", "AST"),
    "science": ("BIOL", "CHEM", "PHYS", "GEOL", "PHSC", "AST"),
    "science and engineering": ("BIOL", "CHEM", "PHYS", "GEOL", "PHSC", "AST", "ENGR", "CHEG", "IENG", "MECH", "ETEC"),
    "science & engineering": ("BIOL", "CHEM", "PHYS", "GEOL", "PHSC", "AST", "ENGR", "CHEG", "IENG", "MECH", "ETEC"),
    "engineering": ("ENGR", "CHEG", "IENG", "MECH", "ETEC"),
    "physics": ("PHYS",),
    "chemistry": ("CHEM",),
    "biology": ("BIOL",),
    "business": ("ACCT", "ECON", "FIN", "GBUS", "HCAD", "IS", "MGMT", "MKTG", "SCM", "IB"),
    "accounting": ("ACCT",),
    "finance": ("FIN",),
    "management": ("MGMT",),
    "marketing": ("MKTG",),
    "supply chain management": ("SCM",),
    "history": ("HIST",),
    "u.s. history": ("HIST",),
    "non-u.s. history": ("HIST",),
    "political science": ("PSCI",),
    "geography": ("GEOG",),
    "english": ("ENGL",),
    "literature": ("ENGL",),
    "spanish": ("SPAN",),
    "french": ("FREN",),
    "foreign language": ("SPAN", "FREN", "CHIN", "JAPN", "GERM", "RUSS", "FL"),
    "art": ("ART",),
    "music": ("MUS", "MULI", "MUTH", "MUED", "MUEN"),
    "theatre": ("THEA",),
    "mass media": ("MM",),
    "mass communication": ("MCOM",),
    "education": ("EDUC", "TEDU", "SPED", "MAT"),
    "agriculture": ("AGRI", "AGEC", "AGBS", "AGED", "ANSC", "PLSC"),
}

ELECTIVE_RE = re.compile(
    r"(?:(\d+)(?:\s*[-–]\s*(\d+))?\s+hours?\s+(?:of\s+)?)?"  # "15-17 hours of" (optional)
    r"(upper[- ]level\s+|lower[- ]level\s+)?"
    r"([A-Za-z.&,/' -]*?)\s*electives?\b",
    re.I,
)
NAME_HOURS_RE = re.compile(r"\((\d+)(?:\s*[-–]\s*\d+)?\s*(?:credit\s+)?hours?\)", re.I)


# --- inputs ----------------------------------------------------------------------------------

@dataclass
class PlanGroup:
    id: str
    parent_id: str | None
    name: str
    rule: str
    hours_required: float | None
    note: str | None
    courses: list[str] = field(default_factory=list)


@dataclass
class Taken:
    code: str
    status: str  # completed | in_progress
    grade: str | None = None
    credits: float | None = None


@dataclass
class Offering:
    sections: int
    seats_open: int


@dataclass
class Elective:
    text: str
    hours_required: float | None
    level: str | None  # "upper" | "lower" | None
    prefixes: tuple[str, ...] | None  # None = any subject
    unrestricted: bool

    def matches(self, code: str) -> bool:
        prefix, number = code.rsplit(" ", 1)
        if self.prefixes is not None and prefix not in self.prefixes:
            return False
        if self.level == "upper" and number[0] not in "34":
            return False
        if self.level == "lower" and number[0] not in "12":
            return False
        return True

    @property
    def specificity(self) -> int:
        """Fill the narrowest electives first."""
        if self.prefixes is not None:
            return 0
        return 1 if self.level else 2


# --- small helpers ---------------------------------------------------------------------------

def split_taken(taken: list[Taken]) -> tuple[dict[str, float], dict[str, float]]:
    """(passed, in_progress): code -> credits. A course both failed and retaken shows once."""
    passed: dict[str, float] = {}
    in_progress: dict[str, float] = {}
    for row in taken:
        credits = float(row.credits) if row.credits is not None else credits_from_code(row.code)
        if row.status == "completed" and (row.grade or "").upper() not in NOT_EARNED:
            passed[row.code] = credits
        elif row.status == "in_progress":
            in_progress[row.code] = credits
    for code in passed:
        in_progress.pop(code, None)
    return passed, in_progress


def credits_from_code(code: str) -> float:
    """SAU convention: the last digit of the course number is its credit hours."""
    return float(code[-1]) if code[-1].isdigit() else 3.0


def course_level(code: str) -> int:
    number = code.rsplit(" ", 1)[-1]
    return int(number[0]) if number[:1].isdigit() else 0


def hours_in_name(name: str) -> float | None:
    match = NAME_HOURS_RE.search(name)
    return float(match[1]) if match else None


def parse_electives(note: str | None) -> list[Elective]:
    """'15-17 hours of upper-level Computer Science, Data Science, or Mathematics electives'
    -> one Elective(15 hours, upper, CSCI/DSCI/MATH). Lines we can't map are left out."""
    if not note:
        return []
    found: list[Elective] = []
    for match in ELECTIVE_RE.finditer(note):
        low, _high, level_word, subject_text = match.groups()
        subject_text = subject_text.strip(" ,")
        inner = re.search(r"\b(upper|lower)[- ]level\s+", subject_text, re.I)
        if inner:
            # "... may count. Upper-level Management or Marketing electives": the elective
            # starts at the level word; hours before it belonged to another sentence.
            if inner.start() > 0:
                low = None
            level_word, subject_text = inner[1], subject_text[inner.end():]
        level = None
        if level_word:
            level = "upper" if level_word.lower().startswith("upper") else "lower"
        subject = subject_text.lower()
        text = match.group(0).strip()
        hours = float(low) if low else None
        if subject in ("unrestricted", "", "approved"):
            if subject == "approved" or (not subject and not level and not hours):
                continue  # "approved electives", or a bare word: advisor's call, not trackable
            found.append(Elective(text, hours, level, None, unrestricted=not level))
            continue
        prefixes: list[str] = []
        names = [n.strip() for n in re.split(r",\s*(?:or\s+)?|\s+or\s+", subject) if n.strip()]
        for name in names:
            name = re.sub(r"^(?:upper|lower)[- ]level\s+", "", name)
            if name not in SUBJECT_PREFIXES:
                prefixes = []
                break
            prefixes.extend(p for p in SUBJECT_PREFIXES[name] if p not in prefixes)
        if prefixes:
            found.append(Elective(text, hours, level, tuple(prefixes), unrestricted=False))
    return found


# --- degree map progress ---------------------------------------------------------------------

def plan_progress(
    groups: list[PlanGroup],
    passed: dict[str, float],
    in_progress: dict[str, float],
    titles: dict[str, str],
) -> tuple[list[dict], list[dict]]:
    """Returns (tree, needs): the requirement tree with statuses, and what's still needed:
    [{code, group, kind}] for listed courses and [{elective, group}] for electives."""
    children: dict[str | None, list[PlanGroup]] = {}
    for group in groups:
        children.setdefault(group.parent_id, []).append(group)

    used_by_choice: set[str] = set()
    consumed: set[str] = set()  # taken courses a listed requirement uses (not free for electives)
    needs: list[dict] = []
    electives: list[tuple[Elective, dict]] = []  # filled after the tree, then statuses fixed up

    def course_status(code: str) -> str:
        if code in passed:
            return "passed"
        return "in_progress" if code in in_progress else "needed"

    def build(group: PlanGroup) -> dict:
        node = {
            "name": group.name,
            "rule": group.rule,
            "status": "met",
            "hours_done": 0.0,
            "hours_in_progress": 0.0,
            "hours_required": group.hours_required if group.rule == "choose_hours" else hours_in_name(group.name),
            "courses": [],
            "note": group.note,
            "electives": [],
            "children": [],
        }
        own_met, own_with_ip, tracked = True, True, False

        if group.rule == "choose_hours":
            tracked = True
            required = group.hours_required or 0.0
            done = ip = 0.0
            chosen: list[str] = []
            for code in group.courses:  # passed first, then in progress, never reused
                if done >= required:
                    break
                if code in passed and code not in used_by_choice:
                    chosen.append(code)
                    done += passed[code]
            for code in group.courses:
                if done + ip >= required:
                    break
                if code in in_progress and code not in used_by_choice:
                    chosen.append(code)
                    ip += in_progress[code]
            used_by_choice.update(chosen)
            consumed.update(chosen)
            node["hours_done"], node["hours_in_progress"] = done, ip
            own_met, own_with_ip = done >= required, done + ip >= required
            for code in group.courses:
                status = course_status(code) if code in chosen else ("option" if code not in passed and code not in in_progress else "counted_elsewhere")
                node["courses"].append({"code": code, "title": titles.get(code), "status": status})
            if not own_with_ip:
                needs.extend({"code": c, "group": group.name, "kind": "choice"} for c in group.courses
                             if c not in passed and c not in in_progress)
        else:
            for code in group.courses:
                tracked = True
                status = course_status(code)
                node["courses"].append({"code": code, "title": titles.get(code), "status": status})
                if status == "passed":
                    node["hours_done"] += passed[code]
                    consumed.add(code)
                elif status == "in_progress":
                    node["hours_in_progress"] += in_progress[code]
                    consumed.add(code)
                    own_met = False
                else:
                    own_met = own_with_ip = False
                    needs.append({"code": code, "group": group.name, "kind": "required"})

        for elective in parse_electives(group.note):
            tracked = True
            entry = {"text": elective.text, "hours_required": elective.hours_required, "hours_done": 0.0,
                     "hours_in_progress": 0.0, "status": "not_met", "courses": []}
            node["electives"].append(entry)
            electives.append((elective, entry))

        for child in children.get(group.id, []):
            child_node = build(child)
            node["children"].append(child_node)
            tracked = True

        node["_own"] = (own_met, own_with_ip, tracked)
        return node

    tree = [build(group) for group in children.get(None, [])]

    # Electives: taken courses no listed requirement used, narrowest elective first.
    pool_passed = {c: h for c, h in passed.items() if c not in consumed}
    pool_ip = {c: h for c, h in in_progress.items() if c not in consumed}
    for elective, entry in sorted(electives, key=lambda pair: pair[0].specificity):
        # "Upper-level English electives" gives no hours: at least one course then.
        need = elective.hours_required or 1.0
        for pool, key in ((pool_passed, "hours_done"), (pool_ip, "hours_in_progress")):
            for code in [c for c in pool if elective.matches(c)]:
                if entry["hours_done"] + entry["hours_in_progress"] >= need:
                    break
                entry[key] += pool.pop(code)
                entry["courses"].append({"code": code, "title": titles.get(code),
                                         "status": "passed" if key == "hours_done" else "in_progress"})
        if entry["hours_done"] >= need:
            entry["status"] = "met"
        elif entry["hours_done"] + entry["hours_in_progress"] >= need:
            entry["status"] = "in_progress"
        else:
            needs.append({"elective": elective, "group": entry["text"]})

    def settle(node: dict) -> str:
        own_met, own_with_ip, tracked = node.pop("_own")
        statuses = [settle(child) for child in node["children"]]
        statuses += [entry["status"] for entry in node["electives"]]
        statuses = [s for s in statuses if s != "not_tracked"]
        node["hours_done"] += sum(c["hours_done"] for c in node["children"]) + sum(e["hours_done"] for e in node["electives"])
        node["hours_in_progress"] += (sum(c["hours_in_progress"] for c in node["children"])
                                      + sum(e["hours_in_progress"] for e in node["electives"]))
        if not tracked or (not node["courses"] and not statuses and node["rule"] != "choose_hours"):
            node["status"] = "not_tracked"
        elif own_met and all(s == "met" for s in statuses):
            node["status"] = "met"
        elif own_with_ip and all(s in ("met", "in_progress") for s in statuses):
            node["status"] = "in_progress"
        else:
            node["status"] = "not_met"
        return node["status"]

    for node in tree:
        settle(node)
    return tree, needs


# --- mySAU audit progress --------------------------------------------------------------------

def audit_progress(requirements: list[dict], passed: dict[str, float], in_progress: dict[str, float],
                   titles: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """The audit already says what's met. Build the tree by parent_name and list the course
    options of requirements that aren't met."""
    nodes = []
    for req in requirements:
        options = [code for code in req.get("course_options") or [] if COURSE_CODE_RE.fullmatch(code)]
        nodes.append({
            "name": req["name"],
            "parent_name": req.get("parent_name"),
            "rule": req.get("rule") or "all",
            "status": req["status"],
            "hours_done": float(req["hours_earned"]) if req.get("hours_earned") is not None else 0.0,
            "hours_in_progress": 0.0,
            "hours_required": float(req["hours_required"]) if req.get("hours_required") is not None else None,
            "courses": [{"code": c, "title": titles.get(c),
                         "status": "passed" if c in passed else "in_progress" if c in in_progress else "option"}
                        for c in options],
            "note": req.get("note"),
            "electives": [],
            "children": [],
        })
    by_name: dict[str, dict] = {}
    roots: list[dict] = []
    for node in nodes:
        parent = by_name.get(node["parent_name"]) if node["parent_name"] else None
        (parent["children"] if parent is not None else roots).append(node)
        by_name.setdefault(node["name"], node)
    for node in nodes:
        node.pop("parent_name")
    needs = [
        {"code": course["code"], "group": node["name"], "kind": "choice" if node["rule"] == "choose_hours" else "required"}
        for node in nodes if node["status"] == "not_met"
        for course in node["courses"] if course["status"] == "option"
    ]
    return roots, needs


# --- what can I take this term ---------------------------------------------------------------

def missing_prereqs(code: str, prereqs: dict[str, list[list[str]]], passed: dict, in_progress: dict) -> list[list[str]]:
    """Prereq groups with no option passed or in progress."""
    return [options for options in prereqs.get(code, [])
            if not any(o in passed or o in in_progress for o in options)]


def can_take(
    needs: list[dict],
    offered: dict[str, Offering],
    prereqs: dict[str, list[list[str]]],
    passed: dict[str, float],
    in_progress: dict[str, float],
    titles: dict[str, str],
    credits: dict[str, float],
) -> tuple[list[dict], list[dict]]:
    """(eligible, blocked) for the current term. Elective candidates are listed for
    subject electives; unrestricted electives aren't enumerated (anything eligible counts)."""
    kind_order = {"required": 0, "choice": 1, "elective": 2}
    eligible: dict[str, dict] = {}
    blocked: dict[str, dict] = {}

    def consider(code: str, kind: str, reason: str) -> None:
        if code in passed or code in in_progress or code not in offered or course_level(code) >= 5:
            return
        missing = missing_prereqs(code, prereqs, passed, in_progress)
        if missing:
            if kind != "elective":
                blocked.setdefault(code, {"code": code, "title": titles.get(code), "missing_prereqs": missing,
                                          "counts_toward": []})["counts_toward"].append(reason)
            return
        entry = eligible.setdefault(code, {
            "code": code, "title": titles.get(code), "credits": credits.get(code, credits_from_code(code)),
            "kind": kind, "counts_toward": [], "sections": offered[code].sections,
            "seats_open": offered[code].seats_open,
        })
        if kind_order[kind] < kind_order[entry["kind"]]:
            entry["kind"] = kind
        if reason not in entry["counts_toward"]:
            entry["counts_toward"].append(reason)

    for need in needs:
        if "code" in need:
            consider(need["code"], need["kind"], need["group"])
    # A course the plan lists by name isn't also an elective (SAU: no double counting).
    listed = {need["code"] for need in needs if "code" in need}
    for need in needs:
        elective = need.get("elective")
        if elective is not None and not elective.unrestricted:
            for code in sorted(offered):
                if code not in listed and elective.matches(code):
                    consider(code, "elective", elective.text)
    ordered = sorted(eligible.values(), key=lambda e: (kind_order[e["kind"]], e["code"]))
    return ordered, sorted(blocked.values(), key=lambda b: b["code"])


def build_progress(
    *,
    source: str,
    plan: dict | None,
    term: dict | None,
    groups: list[PlanGroup],
    audit_requirements: list[dict],
    taken: list[Taken],
    titles: dict[str, str],
    credits: dict[str, float],
    offered: dict[str, Offering],
    prereqs: dict[str, list[list[str]]],
    total_hours: float | None,
) -> dict:
    passed, in_progress = split_taken(taken)
    if source == "audit":
        tree, needs = audit_progress(audit_requirements, passed, in_progress, titles)
    elif source == "degree_plan":
        tree, needs = plan_progress(groups, passed, in_progress, titles)
    else:
        tree, needs = [], []
    eligible, blocked = can_take(needs, offered, prereqs, passed, in_progress, titles, credits)
    unrestricted = [n["elective"].text for n in needs if n.get("elective") is not None and n["elective"].unrestricted]
    return {
        "source": source,
        "plan": plan,
        "term": term,
        "hours": {
            "earned": sum(passed.values()),
            "in_progress": sum(in_progress.values()),
            "required": total_hours,
        },
        "requirements": tree,
        "can_take": eligible,
        "blocked": blocked,
        "open_electives": unrestricted,
    }


# --- per-course flags for the catalog ------------------------------------------------------

@dataclass
class CourseFlags:
    """What one student's record says about any course: built from build_progress's own tree,
    so the catalog and /me/progress always agree."""

    passed: dict[str, float]
    in_progress: dict[str, float]
    prereqs: dict[str, list[list[str]]]
    listed: dict[str, list[str]]  # course code -> requirement names that list it
    electives: list[Elective] = field(default_factory=list)  # subject/level electives of the plan
    has_plan: bool = False

    def missing_prereqs(self, code: str) -> list[list[str]]:
        return missing_prereqs(code, self.prereqs, self.passed, self.in_progress)

    def eligibility(self, code: str) -> str:
        """completed | in_progress | missing_prereq | eligible. F and W aren't completed."""
        if code in self.passed:
            return "completed"
        if code in self.in_progress:
            return "in_progress"
        return "missing_prereq" if self.missing_prereqs(code) else "eligible"

    def requirement_names(self, code: str) -> list[str]:
        """Requirements that list the course by name; otherwise the electives it would fill.
        A course the plan lists by name is never also an elective (as in can_take)."""
        names = self.listed.get(code)
        if names:
            return list(names)
        return [e.text for e in self.electives if e.matches(code)]

    def for_course(self, code: str) -> dict:
        names = self.requirement_names(code)
        return {"eligibility": self.eligibility(code), "missing_prereqs": self.missing_prereqs(code),
                "on_my_plan": bool(names), "requirement_names": names}


def requirement_index(tree: list[dict]) -> dict[str, list[str]]:
    """Course code -> names of the requirement nodes (or elective lines) that list or count it."""
    index: dict[str, list[str]] = {}

    def add(code: str, name: str) -> None:
        names = index.setdefault(code, [])
        if name not in names:
            names.append(name)

    def walk(node: dict) -> None:
        for course in node["courses"]:
            add(course["code"], node["name"])
        for elective in node["electives"]:
            for course in elective["courses"]:
                add(course["code"], elective["text"])
        for child in node["children"]:
            walk(child)

    for node in tree:
        walk(node)
    return index


def course_flags(inputs: dict) -> CourseFlags:
    """Pure: load_progress_inputs(...) -> CourseFlags."""
    result = build_progress(**inputs)
    passed, in_progress = split_taken(inputs["taken"])
    electives = ([e for g in inputs["groups"] for e in parse_electives(g.note) if e.prefixes or e.level]
                 if result["source"] == "degree_plan" else [])
    return CourseFlags(passed, in_progress, inputs["prereqs"], requirement_index(result["requirements"]),
                       electives, has_plan=result["source"] != "none")


# --- database --------------------------------------------------------------------------------

def load_progress(student_id: uuid.UUID) -> dict:
    """GET /me/progress for one student."""
    return build_progress(**load_progress_inputs(student_id))


def load_course_flags(student_id: uuid.UUID) -> "CourseFlags":
    """Per-course flags for the catalog, from the same inputs and tree as load_progress."""
    return course_flags(load_progress_inputs(student_id))


def load_progress_inputs(student_id: uuid.UUID) -> dict:
    """Everything build_progress needs, read for one student (its keyword arguments)."""
    with SessionLocal() as session:
        student = session.get(Student, student_id)
        if student is None:
            raise LookupError("student not found")
        taken = [
            Taken(row.course_code, row.status, row.grade, float(row.credits) if row.credits is not None else None)
            for row in session.scalars(select(CompletedCourse).where(CompletedCourse.student_id == student_id))
        ]
        audit_rows = session.scalars(
            select(StudentRequirement).where(StudentRequirement.student_id == student_id)
            .order_by(StudentRequirement.sort_order)
        ).all()
        audit_requirements = [
            {"name": r.name, "parent_name": r.parent_name, "status": r.status, "rule": r.rule,
             "hours_earned": r.hours_earned, "hours_required": r.hours_required,
             "course_options": list(r.course_options or []), "note": r.note}
            for r in audit_rows
        ]
        plan_row = session.get(DegreePlan, student.degree_plan_id) if student.degree_plan_id else None
        groups: list[PlanGroup] = []
        if audit_requirements:
            source = "audit"
        elif plan_row is not None:
            source = "degree_plan"
            group_rows = session.scalars(
                select(RequirementGroup).where(RequirementGroup.degree_plan_id == plan_row.id)
                .order_by(RequirementGroup.sort_order)
            ).all()
            courses_by_group: dict = {}
            for group_id, code in session.execute(
                select(RequirementCourse.group_id, RequirementCourse.course_code)
                .join(RequirementGroup, RequirementGroup.id == RequirementCourse.group_id)
                .where(RequirementGroup.degree_plan_id == plan_row.id)
                .order_by(RequirementCourse.course_code)
            ):
                courses_by_group.setdefault(group_id, []).append(code)
            groups = [
                PlanGroup(str(g.id), str(g.parent_id) if g.parent_id else None, g.name, g.rule,
                          float(g.hours_required) if g.hours_required is not None else None, g.note,
                          courses_by_group.get(g.id, []))
                for g in group_rows
            ]
        else:
            source = "none"

        term_row = session.scalar(select(Term).where(Term.is_current_registration.is_(True)))
        offered: dict[str, Offering] = {}
        if term_row is not None:
            seats = func.sum(func.greatest(Section.capacity - Section.enrolled, 0))
            for code, count, open_seats in session.execute(
                select(Course.code, func.count(Section.id), seats)
                .join(Section, Section.course_id == Course.id)
                .where(Section.term_id == term_row.id, Section.active.is_(True))
                .group_by(Course.code)
            ):
                offered[code] = Offering(int(count), int(open_seats or 0))

        prereqs: dict[str, dict[int, list[str]]] = {}
        for code, group, requires in session.execute(
            select(CoursePrereq.course_code, CoursePrereq.option_group, CoursePrereq.requires_code)
        ):
            prereqs.setdefault(code, {}).setdefault(group, []).append(requires)
        titles: dict[str, str] = {}
        credits: dict[str, float] = {}
        for code, title, course_credits in session.execute(select(Course.code, Course.title, Course.credits)):
            titles[code] = title
            if course_credits is not None:
                credits[code] = float(course_credits)

    return dict(
        source=source,
        plan={"name": plan_row.name, "catalog_year": plan_row.catalog_year} if plan_row and source == "degree_plan" else None,
        term={"id": term_row.id, "name": term_row.name} if term_row else None,
        groups=groups,
        audit_requirements=audit_requirements,
        taken=taken,
        titles=titles,
        credits=credits,
        offered=offered,
        prereqs={code: [groups_[k] for k in sorted(groups_)] for code, groups_ in prereqs.items()},
        total_hours=(float(student.total_hours_needed) if student.total_hours_needed is not None
                     else float(plan_row.total_hours) if plan_row and plan_row.total_hours else None),
    )
