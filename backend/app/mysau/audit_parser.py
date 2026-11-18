"""Parse a mySAU degree audit ("Unofficial Advising Worksheet") into the data Flowsaic keeps.

Two steps:
1. extract_lines(pdf_bytes) (pdfplumber, in memory) -> AuditLine list with layout hints:
   indent, whether the line sits on a shaded header bar, and the met / not met /
   in progress icon beside it. The PDF text has no icons, so they come from the layout.
2. parse_lines(lines) -> ParsedAudit. Pure, so it is tested with a fake audit.

Privacy (prompt 2; the name since Nov 18): from the header only the student's first and last
name (no middle name or initial), the major, catalog year, classification and a yes/no hold
are read. ID number, address, phones, advisor and GPA are never read into the result, and
GPA lines elsewhere are dropped. A hold's text is never kept. Nothing here logs or prints
audit text.

What is kept:
- students: name ("First Last"), major, catalog_year, classification, has_hold, total hours
  earned / needed.
- completed_courses (source 'audit'): code, grade, credits, term, status, requirement_name
  (None for "Nonapplied Coursework").
- student_requirements: every requirement block, met or not, across all pages. Block
  headers repeat at the top of each page; repeats are merged.
"""

import hashlib
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal

from app.normalize import normalize_course_code

CLASSIFICATIONS = ("Freshman", "Sophomore", "Junior", "Senior", "Graduate", "Post-Baccalaureate")

TOP_HEADER = re.compile(r"^(?P<name>.+?)\s*\((?P<status>MET|NOT MET)\)$")
# "Computer Science:........66.00 Hours Earned". Anything may sit among the dots (one page
# overlays a faint "GPA"), so only the start is matched and the hours are searched for.
SUMMARY = re.compile(r"^(?P<name>[^.:]+):\s*\.{3,}")
SUMMARY_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*Hours Earned\s*$")
HOURS_IN = re.compile(r"\((\d+)(?:\s*-\s*\d+)? hours?\)", re.I)
# "Select 5 hours from the following:", "Select 4 hours (lecture + lab) from ...", not
# "Select 3 hours of World Literature/Philosophy and 6 hours of ..." (a description).
SELECT = re.compile(r"^Select (\d+)(?:\s*-\s*\d+)? hours\b(?:\s*\([^)]*\))?\s+from\b", re.I)
# Page furniture that never belongs to a requirement.
FURNITURE = re.compile(
    r"^(Unofficial Advising Worksheet|Advising Worksheet \(|Code Key:|- (Requirement is|Course |"
    r"Indicates|An (un)?approved|Represents)|(RED|BLUE) - |Advisor: _|Page \d+ of \d+)"
)
GPA_LINE = re.compile(r"\bGPA\b", re.I)
TOTALS = re.compile(r"Total Hours Earned/Needed:\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")
DEGREE_HOURS = re.compile(r"Degree Hours:\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)")
CATALOG_YEAR = re.compile(r"Catalog\s*Year\s*(\d{4}(?:-\d{4})?)")  # the PDF packs this text tightly
MAJOR = re.compile(r"^Major 1:\s*(.+)$")
NAME = re.compile(r"^Name:\s*(.+)$")
CLASSIFICATION = re.compile(rf"Classification:\s*({'|'.join(CLASSIFICATIONS)})\b")

# "CSCI-3103-001 Title B 3.00 2024 1S", "ART -2013-032 Title B 3.00 2023 1S",
# "BIOL-1041-005 -L Title A 1.00 2025 1S",
# "ENGL1013 Composition I (ENGL1113) A 3.00 2022 3T (TR) Other College"
CODE = r"(?P<subject>[A-Z]{2,4}) ?-?(?P<number>\d{4}[A-Z]?)(?:-(?P<section>[0-9A-Z]{3,4}))?(?: -L)?"
COMPLETED = re.compile(
    rf"^{CODE}\s+(?P<title>.+?)\s+(?P<grade>[A-Z][A-Z+-]{{0,2}})\s+(?P<credits>\d+\.\d{{2}})\s+"
    r"(?P<term>\d{4} \d[A-Z])(?P<transfer>\s+\(TR\).*)?$"
)
IN_PROGRESS = re.compile(
    rf"^{CODE}\s+(?P<title>.+?)\s+\((?P<credits>\d+\.\d{{2}}) In Progress (?P<term>[^)]+)\)$"
)
CUMULATIVE_IN_PROGRESS = re.compile(
    rf"^Section {CODE} is currently in progress \((?P<credits>\d+\.\d{{2}}) in (?P<term>[^)]+)\)$"
)
CUMULATIVE_TRACKER = re.compile(r"Earned:\s*\d+(?:\.\d+)? hours\s*/\s*\d+ count")
NEEDED = re.compile(rf"^{CODE}\s+(?P<title>[A-Za-z].*)$")
EQUIVALENT = re.compile(r"\(?\b([A-Z]{2,4}) ?(\d{4}[A-Z]?)\)?$")
OPTION = re.compile(r"^-\s*(?P<rest>.+)$")
OPTION_CODES = re.compile(r"\b([A-Z]{2,4}) ?(\d{4}[A-Z]?)((?:/\d{4}[A-Z]?)*)")


@dataclass
class AuditLine:
    text: str
    indent: float = 0.0  # x position of the line's left edge
    bar: bool = False  # sits on a shaded requirement header bar
    icon: str | None = None  # "met", "not_met", "in_progress" or None


@dataclass
class AuditCourse:
    course_code: str
    status: str  # completed | in_progress
    grade: str | None
    credits: Decimal | None
    term: str | None
    requirement_name: str | None
    transfer: bool = False


@dataclass
class AuditRequirement:
    name: str
    parent_name: str | None
    status: str  # met | not_met | in_progress
    rule: str = "all"
    hours_earned: Decimal | None = None
    hours_required: Decimal | None = None
    course_options: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    sort_order: int = 0
    indent: float = 0.0

    @property
    def note(self) -> str | None:
        return " ".join(self.notes) or None


@dataclass
class ParsedAudit:
    student_name: str | None = None  # "First Last" only; see first_and_last()
    major: str | None = None
    catalog_year: str | None = None
    classification: str | None = None
    has_hold: bool = False
    total_hours_earned: Decimal | None = None
    total_hours_needed: Decimal | None = None
    courses: list[AuditCourse] = field(default_factory=list)
    requirements: list[AuditRequirement] = field(default_factory=list)
    unparsed_lines: int = 0  # counted, never logged


def _strip_gpa(text: str) -> str:
    """'Primary AIM: Computer Science (NOT MET) GPA:3.2800' -> without the GPA."""
    return re.sub(r"\s*GPA:\s*[\d.]*\s*$", "", text)


def _code(subject: str, number: str) -> str:
    return normalize_course_code(f"{subject} {number}")


def _option_codes(text: str) -> list[str]:
    """'BIOL1043/1041 Intro to Biology/Lab' -> ['BIOL 1043', 'BIOL 1041']."""
    codes: list[str] = []
    for subject, number, more in OPTION_CODES.findall(text):
        codes.append(_code(subject, number))
        codes.extend(_code(subject, extra) for extra in more.split("/") if extra)
    return codes


def first_and_last(raw: str) -> str | None:
    """The audit's 'Last, First Middle' -> 'First Last'. A middle name or initial is dropped,
    a suffix stays with the last name ('Fakerson Jr., Testy Q.' -> 'Testy Fakerson Jr.').
    Without a comma: first and last word. ALL CAPS becomes Title Case. None if unreadable."""
    raw = " ".join(raw.split()).strip(" ,")
    if "," in raw:
        last, given = (part.strip() for part in raw.split(",", 1))
        first = given.split(" ")[0] if given else ""
    else:
        words = raw.split(" ")
        first, last = (words[0], words[-1]) if len(words) >= 2 else ("", "")
    name = f"{first} {last}".strip()
    if not first or not last or len(name) > 80 or not re.fullmatch(r"[A-Za-z][A-Za-z.'\- ]*", name):
        return None
    return name.title() if name.isupper() else name


def parse_header(lines: list[AuditLine]) -> dict:
    """First and last name, major, catalog year, classification and a yes/no hold. Nothing else is read."""
    found: dict = {"student_name": None, "major": None, "catalog_year": None, "classification": None,
                   "has_hold": False}
    for index, line in enumerate(lines):
        text = " ".join(line.text.split())
        if found["student_name"] is None and (match := NAME.match(text)):
            found["student_name"] = first_and_last(match[1])
        if match := CATALOG_YEAR.search(text):
            found["catalog_year"] = match[1]
        if match := MAJOR.match(text):
            found["major"] = match[1].strip()
        elif text == "Major 1:" and index + 1 < len(lines):
            found["major"] = " ".join(lines[index + 1].text.split())  # the value is the next column
        if match := CLASSIFICATION.search(text):
            found["classification"] = match[1]
        elif text in CLASSIFICATIONS:
            found["classification"] = text
        if "hold" in re.sub(r"holds and warnings:?", "", text, flags=re.I).lower():
            found["has_hold"] = True  # the hold's name is never kept
    return found


def parse_lines(lines: list[AuditLine]) -> ParsedAudit:
    result = ParsedAudit()
    first_block = next(
        (i for i, line in enumerate(lines) if line.bar and TOP_HEADER.match(_strip_gpa(" ".join(line.text.split())))),
        len(lines),
    )
    header = parse_header(lines[:first_block])
    result.student_name = header["student_name"]
    result.major = header["major"]
    result.catalog_year = header["catalog_year"]
    result.classification = header["classification"]
    result.has_hold = header["has_hold"]
    for line in lines[:first_block]:
        if match := DEGREE_HOURS.search(line.text):
            result.total_hours_earned, result.total_hours_needed = Decimal(match[1]), Decimal(match[2])
    # Backstop for the page footer, which repeats the student's name: any later line that
    # contains the header's name is dropped, so the name never ends up in requirement text.
    private = [
        " ".join(line.text.split(":", 1)[1].split())
        for line in lines[:first_block]
        if line.text.strip().startswith(("Name:", "Advisor #"))
    ]
    private = [value for value in private if len(value) >= 3]

    by_name: dict[tuple[str | None, str], AuditRequirement] = {}
    stack: list[AuditRequirement] = []  # open requirements, outermost first
    top: AuditRequirement | None = None
    nonapplied = False
    totals_block = False
    # (requirement, line): drops the description lines repeated at the top of each page,
    # while the same wording under two different requirements is kept for both.
    seen_text: set[tuple[int, str]] = set()
    order = 0

    def current() -> AuditRequirement | None:
        return stack[-1] if stack else None

    def add_course(course: AuditCourse) -> None:
        if course not in result.courses:
            result.courses.append(course)

    for line in lines[first_block:]:
        text = " ".join(line.text.split())
        if not text or FURNITURE.match(text) or any(value in text for value in private):
            continue
        # The totals share a line with the GPA: take the hours, never keep the line.
        if match := TOTALS.search(text):
            result.total_hours_earned, result.total_hours_needed = Decimal(match[1]), Decimal(match[2])
            continue
        text = _strip_gpa(text)  # "Primary AIM: Computer Science (NOT MET) GPA:3.28"
        if GPA_LINE.search(text):
            continue

        if line.bar and (match := TOP_HEADER.match(text)):
            name = match["name"].strip()
            totals_block = name.lower() == "course totals"
            nonapplied = False
            if totals_block:
                stack, top = [], None
                continue
            key = (None, name)
            if key not in by_name:
                order += 1
                by_name[key] = AuditRequirement(
                    name=name, parent_name=None, status=match["status"].lower().replace(" ", "_"),
                    sort_order=order, indent=line.indent,
                )
                result.requirements.append(by_name[key])
            if top is not by_name[key]:
                top = by_name[key]
                stack = [top]
            # else: the same block repeated at the top of a new page; keep where we were.
            continue

        if line.bar and text.lower().startswith("nonapplied coursework"):
            nonapplied, totals_block = True, False
            stack, top = [], None
            continue
        if totals_block:
            continue

        if match := SUMMARY.match(text):
            hours = SUMMARY_HOURS.search(text)
            same_block = top is not None and match["name"].strip().lower() == top.name.split(":")[-1].strip().lower()
            if same_block and hours:
                top.hours_earned = Decimal(hours[1])
            continue
        if not line.bar and top is not None and (id(top), text) in seen_text:
            continue  # the block's description, repeated at the top of a new page: keep nesting

        if line.bar and top is not None:
            # A sub-requirement bar. Its parent is the nearest open requirement to its left.
            while len(stack) > 1 and stack[-1].indent >= line.indent:
                stack.pop()
            parent = stack[-1]
            key = (parent.name, text)
            if key not in by_name:
                order += 1
                status = {"met": "met", "not_met": "not_met"}.get(line.icon or "", "not_met")
                by_name[key] = AuditRequirement(
                    name=text, parent_name=parent.name, status=status, sort_order=order, indent=line.indent
                )
                result.requirements.append(by_name[key])
            stack.append(by_name[key])
            continue

        # A line at or left of an open sub-requirement's bar is back in the outer block.
        while len(stack) > 1 and line.indent <= stack[-1].indent:
            stack.pop()
        requirement = current()
        requirement_name = None if nonapplied else (requirement.name if requirement else None)

        if match := CUMULATIVE_IN_PROGRESS.match(text):
            add_course(AuditCourse(_code(match["subject"], match["number"]), "in_progress", None,
                                   Decimal(match["credits"]), match["term"].strip(), requirement_name))
            continue
        if CUMULATIVE_TRACKER.search(text):
            continue  # the cumulative course's tracker line; its section is recorded above
        if match := IN_PROGRESS.match(text):
            add_course(AuditCourse(_code(match["subject"], match["number"]), "in_progress", None,
                                   Decimal(match["credits"]), match["term"].strip(), requirement_name))
            continue
        if match := COMPLETED.match(text):
            code = _code(match["subject"], match["number"])
            transfer = bool(match["transfer"])
            if transfer and (equivalent := EQUIVALENT.search(match["title"])):
                code = _code(equivalent[1], equivalent[2])  # the SAU course it counts as
            add_course(AuditCourse(code, "completed", match["grade"], Decimal(match["credits"]),
                                   match["term"], requirement_name, transfer))
            continue

        if requirement is None:
            result.unparsed_lines += 1
            continue
        if (id(requirement), text) in seen_text:
            continue
        seen_text.add((id(requirement), text))

        if match := OPTION.match(text):
            codes = _option_codes(match["rest"])
            if codes:
                requirement.course_options.extend(c for c in codes if c not in requirement.course_options)
            else:
                requirement.notes.append(text)
            continue
        if match := SELECT.match(text):
            requirement.rule = "choose_hours"
            requirement.hours_required = Decimal(match[1])
            requirement.notes.append(text)
            continue
        if (match := NEEDED.match(text)) and line.icon == "not_met":
            # "CSCI4932 Senior Project II" under a NOT MET requirement: still needed.
            code = _code(match["subject"], match["number"])
            if code not in requirement.course_options:
                requirement.course_options.append(code)
            continue
        if re.match(r"^[A-Z]{2,4} ?\d{4}[A-Z]?(?:/\d{4}[A-Z]?)+\b", text):
            # "CSCI 2103/2101 Computer Science I/Lab": the courses this block requires.
            requirement.course_options.extend(c for c in _option_codes(text) if c not in requirement.course_options)
            continue
        if line.icon in ("met", "not_met") and re.match(r"^[A-Z0-9+]{4,}\s", text):
            # Rule items like "RESUNIVB University Residency": a requirement of their own.
            name = text.split(" ", 1)[1]
            key = (requirement.name, name)
            if key not in by_name:
                order += 1
                by_name[key] = AuditRequirement(name=name, parent_name=requirement.name,
                                                status=line.icon, sort_order=order, indent=line.indent)
                result.requirements.append(by_name[key])
            stack.append(by_name[key])  # its description lines follow
            continue
        if (match := HOURS_IN.search(text)) and requirement.hours_required is None:
            requirement.hours_required = Decimal(match[1])
        requirement.notes.append(text)

    _finish(result)
    return result


def _finish(result: ParsedAudit) -> None:
    """Hours earned per requirement, and in-progress status where courses are under way."""
    earned: dict[str, Decimal] = {}
    under_way: set[str] = set()
    for course in result.courses:
        if course.requirement_name is None:
            continue
        if course.status == "completed" and course.credits is not None:
            earned[course.requirement_name] = earned.get(course.requirement_name, Decimal(0)) + course.credits
        elif course.status == "in_progress":
            under_way.add(course.requirement_name)
    children: dict[str, list[AuditRequirement]] = {}
    for requirement in result.requirements:
        if requirement.parent_name:
            children.setdefault(requirement.parent_name, []).append(requirement)

    def total(requirement: AuditRequirement) -> Decimal:
        own = earned.get(requirement.name, Decimal(0))
        return own + sum((total(child) for child in children.get(requirement.name, [])), Decimal(0))

    def has_under_way(requirement: AuditRequirement) -> bool:
        return requirement.name in under_way or any(has_under_way(c) for c in children.get(requirement.name, []))

    for requirement in result.requirements:
        if requirement.hours_earned is None:
            requirement.hours_earned = total(requirement)
        if requirement.status == "not_met" and has_under_way(requirement):
            requirement.status = "in_progress"


# --- PDF -> lines (in memory only) -------------------------------------------------------

# Layout of the worksheet (checked Nov 17 on a real audit, structure only):
# - Status icons are small images left of the text. Every page ends with a Code Key that
#   shows each icon next to its label, so icons are matched to statuses from the Code Key
#   itself rather than from fixed image fingerprints.
# - Requirement headers sit on filled bars (black or gray, ~14 pt tall, wide). The white
#   boxes around the personal information are not bars.
# - Nesting is the icon's x position (about 27, 40, 51, 63, 74 pt). Lines with no icon are
#   compared as if their icon sat ICON_GAP pt left of the text.
# - Everything from the Code Key down (legend and the footer with the student's name) is cut.
ICON_GAP = 11.0
COLUMN_GAP = 30.0  # header only: a wider gap between words starts a new column
KEY_LABELS = {"requirement is met": "met", "requirement is not met": "not_met", "course is in progress": "in_progress"}


def _image_key(image: dict) -> str:
    stream = image.get("stream")
    data = stream.get_data() if stream is not None and hasattr(stream, "get_data") else b""
    return hashlib.sha1(data).hexdigest()


def _is_bar(rect: dict) -> bool:
    fill = rect.get("non_stroking_color")
    white = isinstance(fill, tuple | list) and len(fill) >= 3 and min(fill[:3]) > 0.99
    return rect["width"] > 200 and 10 < rect["height"] < 20 and fill is not None and not white


def _code_key_icons(page, key_top: float) -> dict[str, str]:
    """{image fingerprint: status} from the Code Key at the bottom of a page."""
    words = [w for w in page.extract_words() if w["top"] >= key_top]
    icons = sorted((im for im in page.images if im["top"] >= key_top - 2), key=lambda im: (round(im["top"]), im["x0"]))
    found: dict[str, str] = {}
    for icon in icons:
        middle = (icon["top"] + icon["bottom"]) / 2
        row = [w for w in words if abs((w["top"] + w["bottom"]) / 2 - middle) < 5 and w["x0"] >= icon["x1"] - 1]
        next_icon = min((im["x0"] for im in icons if im is not icon and im["x0"] > icon["x0"]
                         and abs((im["top"] + im["bottom"]) / 2 - middle) < 5), default=10_000)
        label = " ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"]) if w["x0"] < next_icon)
        label = label.strip(" -").lower()
        for text, status in KEY_LABELS.items():
            if label.startswith(text):
                found[_image_key(icon)] = status
    return found


def _split_columns(line: dict) -> list[dict]:
    """Header lines hold two columns side by side; split them where the words are far apart."""
    chars = sorted(line.get("chars") or [], key=lambda c: c["x0"])
    if not chars:
        return [line]
    parts, current = [], [chars[0]]
    for char in chars[1:]:
        if char["x0"] - current[-1]["x1"] > COLUMN_GAP:
            parts.append(current)
            current = []
        current.append(char)
    parts.append(current)

    def join(part: list[dict]) -> str:
        text = part[0]["text"]
        for before, char in zip(part, part[1:]):
            text += (" " if char["x0"] - before["x1"] > 1.5 else "") + char["text"]
        return " ".join(text.split())

    return [{"text": join(part), "x0": part[0]["x0"]} for part in parts]


def extract_lines(pdf_bytes: bytes) -> list[AuditLine]:
    """The audit PDF (bytes in memory, never a file) -> lines with layout hints."""
    import pdfplumber

    raw: list[tuple[str, float, bool, str | None]] = []
    icon_status: dict[str, str] = {}
    in_header = True
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            key_top = next(
                (w["top"] for i, w in enumerate(words)
                 if w["text"] == "Code" and i + 1 < len(words) and words[i + 1]["text"].startswith("Key")),
                page.height,
            )
            icon_status.update(_code_key_icons(page, key_top))
            images = [im for im in page.images if im["bottom"] <= key_top]
            bars = [r for r in page.rects if r["bottom"] <= key_top and _is_bar(r)]
            for line in page.extract_text_lines(return_chars=True):
                if line["top"] >= key_top:
                    continue
                on_bar = any(r["top"] - 2 <= line["top"] and r["bottom"] + 2 >= line["bottom"] for r in bars)
                if in_header and on_bar and TOP_HEADER.match(_strip_gpa(" ".join(line["text"].split()))):
                    in_header = False
                middle = (line["top"] + line["bottom"]) / 2
                icon = max(
                    (im for im in images
                     if abs((im["top"] + im["bottom"]) / 2 - middle) < 5
                     and im["x1"] <= line["x0"] + 2 and line["x0"] - im["x1"] < 15),
                    key=lambda im: im["x1"], default=None,
                )
                pieces = _split_columns(line) if in_header else [line]
                for piece in pieces:
                    indent = icon["x0"] if icon is not None else piece["x0"] - ICON_GAP
                    raw.append((piece["text"], indent, on_bar, _image_key(icon) if icon is not None else None))
    return [AuditLine(text, indent, bar, icon_status.get(key) if key else None) for text, indent, bar, key in raw]


def parse_audit_pdf(pdf_bytes: bytes) -> ParsedAudit:
    return parse_lines(extract_lines(pdf_bytes))
