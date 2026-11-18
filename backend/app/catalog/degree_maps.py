"""Degree maps: every undergraduate program -> degree_plans, requirement_groups,
requirement_courses.

Run by db/scripts/scrape_degree_maps.py and by the public data refresh.

Source (decided Nov 17): SAU's main site, www.saumag.edu/academics/program/<slug>/.
The catalog's own program pages (catalog.saumag.edu/preview_program.php) sit behind an
AWS WAF bot challenge, and we never try to get past it. The main site's program pages copy
the catalog curriculum, are open, and each links to its catalog program ("Degree Plan
2026-2027" -> catoid/poid). Only pages linking to settings.catalog_catoid are loaded.

- Program pages are listed in www.saumag.edu/academics/sitemap.xml.
- Plan names come from the catalog's own list (data/raw/degree_maps/programs_list.html,
  saved once from a browser) by poid, e.g. "Computer Science, BS". Without it, the page title.
- A page's "Minor Requirements" section is loaded as its own plan ("<Name> Minor").
- The parts of each page we parse are saved to data/raw/degree_maps/<slug>.html, so the
  parse can be rebuilt offline (--offline). The rest of the page (scripts, styles) is dropped.
- Programs that do not parse cleanly are listed in data/degree_maps_needs_review.csv and
  loaded anyway with what parsed.

Parse rules (the curriculum is <h4> headings, each followed by lines):
- A block of course lines -> rule 'all'.
- "Select N hours from the following:" -> rule 'choose_hours', hours_required N, as a child
  of the block above it ("Select 3-5 hours" uses 3 and keeps the range in the note).
- "one of these combinations ... or ..." blocks -> 'choose_hours' with the block's hours,
  the combinations in the note, and flagged for review (pairs are not enforced).
- Text that is not a course list ("15-17 hours of upper-level ... electives",
  "General Education (28 hours)") -> the group's note. Shown, not enforced.
- "Total Hours - 120" -> degree_plans.total_hours.

General education: program pages only say "General Education (28 hours)" plus a note.
The shared core comes from www.saumag.edu/academics/general-education/ (35 hours in
2026-27, saved as data/raw/degree_maps/general-education.html). It is copied under each
program's gen ed block, minus what the program's note says the major covers:
- "3 hours of social science and 4 hours of physical science requirements are included in
  the major": that many hours come out of each area, starting with the named choice
  ("Social Science choice"), then choices whose courses the major already requires.
- "7 hours of mathematics and physical science ...": each named area is dropped whole.
- A note listing its own areas ("English Composition (6 hours) Fine Arts/Humanities
  (6 hours) ..."): only those areas are kept, at those hours.
If what is left does not add up to the program's gen ed hours, the program is flagged.
Lecture + lab choices load as "choose 4 hours" with the pairs in the note (not enforced).
"""

import copy
import csv
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.catalog.http import PoliteClient
from app.config import REPO_DIR, get_settings
from app.db import SessionLocal
from app.models import DegreePlan, RequirementCourse, RequirementGroup
from app.normalize import normalize_course_code

log = logging.getLogger("flowsaic.catalog.degree_maps")

RAW_DIR = REPO_DIR / "data" / "raw" / "degree_maps"
LIST_PAGE = RAW_DIR / "programs_list.html"  # catalog "Degree Programs by Type", for names
SITEMAP_FILE = RAW_DIR / "sitemap.xml"
NEEDS_REVIEW_PATH = REPO_DIR / "data" / "degree_maps_needs_review.csv"
SITEMAP_PATH = "/academics/sitemap.xml"
PROGRAM_PREFIX = "/academics/program/"

POID = re.compile(r"preview_program\.php\?catoid=(\d+)&(?:amp;|#038;)?poid=(\d+)")
# A course line: "CSCI 3103 – Data Structures"; the dash after the code tells it apart
# from numbers inside titles. Pairs ("... and CSCI 2101 – Lab") give two matches.
COURSE = re.compile(r"\b([A-Z]{2,4}) ?(\d{4}[A-Z]?)\s*[–—-]")
ANY_CODE = re.compile(r"\b[A-Z]{2,4} ?\d{4}[A-Z]?\b")
SELECT = re.compile(r"^select (?:any )?(\d+)(?:\s*[-–]\s*(\d+))? (?:credit )?hours?\b", re.I)
HOURS = re.compile(r"\((\d+)(?:\s*[-–]\s*(\d+))? (?:credit )?hours?\)", re.I)
TOTAL = re.compile(r"^total (?:credit )?hours\b\D*(\d+)", re.I)
# Gen ed list items: "CHEM 1013 College Chemistry I and CHEM 1011 Lab", "CHIN 1003 or 1013 ...".
GEN_ED_CODE = re.compile(r"\b([A-Z]{2,4}) (\d{4})(?:\s+or\s+(\d{4}))?")
GEN_ED_PATH = "/academics/general-education/"
GEN_ED_FILE = RAW_DIR / "general-education.html"


@dataclass
class Group:
    name: str
    rule: str = "all"
    hours_required: int | None = None
    courses: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    children: list["Group"] = field(default_factory=list)
    has_or: bool = False
    hours: int | None = None  # the block's hours as shown (lower bound); used for checks only
    pairs: list[str] = field(default_factory=list)  # lecture + lab combinations, gen ed only

    @property
    def note(self) -> str | None:
        return " ".join(self.notes) or None


@dataclass
class GenEd:
    """The shared general education core (35 hours in 2026-27), from the gen ed page."""

    areas: list[Group]
    notes: list[str]


@dataclass
class Program:
    slug: str
    name: str
    catalog_year: str
    total_hours: int | None
    groups: list[Group]
    poid: str | None = None
    problems: list[str] = field(default_factory=list)


@dataclass
class PageResult:
    slug: str
    programs: list[Program] = field(default_factory=list)
    skipped: str | None = None  # why the page was not loaded


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def page_url(slug: str) -> str:
    return get_settings().saumag_base_url.rstrip("/") + f"{PROGRAM_PREFIX}{slug}/"


def raw_page_file(slug: str) -> Path:
    return RAW_DIR / f"{slug}.html"


# --- program list -------------------------------------------------------------------------

def program_slugs(sitemap_xml: str) -> list[str]:
    """Program page slugs from the academics sitemap, in sitemap order."""
    slugs: dict[str, None] = {}
    for loc in re.findall(r"<loc>([^<]+)</loc>", sitemap_xml):
        if PROGRAM_PREFIX in loc:
            slug = loc.split(PROGRAM_PREFIX, 1)[1].strip("/")
            if slug and "/" not in slug:
                slugs[slug] = None
    return list(slugs)


def catalog_names() -> dict[str, str]:
    """{poid: catalog program name} from the saved catalog list page, if present."""
    if not LIST_PAGE.exists():
        return {}
    catoid = str(get_settings().catalog_catoid)
    soup = BeautifulSoup(LIST_PAGE.read_text(encoding="utf-8", errors="replace"), "html.parser")
    names: dict[str, str] = {}
    for link in soup.find_all("a", href=True):
        match = POID.search(link["href"])
        if match and match[1] == catoid:
            names.setdefault(match[2], _clean(link.get_text()))
    return names


# --- parse one page -----------------------------------------------------------------------

def trim_page(html: str) -> str:
    """Keep only what the parser reads: the title, the Degree Plan link, the curriculum."""
    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []
    title = soup.find("meta", property="og:title")
    if title:
        parts.append(str(title))
    plan_link = soup.find("a", class_="prog-facts-plan-link")
    if plan_link:
        parts.append(str(plan_link))
    for section_id in ("prog-curriculum", "prog-minor"):
        section = soup.find(id=section_id)
        if section:
            parts.append(str(section))
    return "<!-- trimmed copy of a www.saumag.edu program page -->\n" + "\n".join(parts) + "\n"


def _lines(node: Tag) -> list[tuple[str, bool]]:
    """Text lines of a <p>/<ul>/<table>, split at <br> and list items. (text, is_bold)."""
    if node.name in ("ul", "ol"):
        return [(_clean(li.get_text(" ")), False) for li in node.find_all("li")]
    if node.name == "table":
        return [(_clean(tr.get_text(" ")), False) for tr in node.find_all("tr")]
    lines: list[tuple[str, bool]] = []
    current: list[str] = []
    bold = False

    def flush():
        text = _clean("".join(current))
        if text:
            lines.append((text, bold))

    for child in node.children:
        if isinstance(child, Tag) and child.name == "br":
            flush()
            current, bold = [], False
            continue
        if isinstance(child, Tag) and child.name in ("strong", "b") and not "".join(current).strip():
            bold = True
        current.append(child.get_text(" ") if isinstance(child, Tag) else str(child))
    flush()
    return lines


def parse_curriculum(section: Tag, label: str) -> tuple[list[Group], int | None, list[str]]:
    """One curriculum section -> (top-level groups, total hours, problems)."""
    content = section.find(class_="prog-curriculum-content") or section
    groups: list[Group] = []
    problems: list[str] = []
    total: int | None = None
    current: Group | None = None
    parent: Group | None = None  # the last top-level block, for "Select N hours" children

    for node in content.children:
        if isinstance(node, NavigableString):
            if _clean(node):
                problems.append(f"{label}: loose text {_clean(node)[:60]!r}")
            continue
        if not isinstance(node, Tag):
            continue
        if node.name in ("h2", "h3", "h4", "h5", "h6"):
            heading = _clean(node.get_text(" ")).rstrip(":")
            if not heading:
                continue
            if match := TOTAL.match(heading):
                total = int(match[1])
                current = None
                continue
            if match := SELECT.match(heading):
                current = Group(name=heading, rule="choose_hours", hours_required=int(match[1]))
                if match[2]:
                    current.notes.append(f"{match[1]}-{match[2]} hours.")
                (parent.children if parent else groups).append(current)
                continue
            current = Group(name=heading)
            parent = current
            groups.append(current)
            continue
        if node.name in ("p", "ul", "ol", "table", "div"):
            for text, bold in _lines(node):
                if current is None:
                    problems.append(f"{label}: text before any heading {text[:60]!r}")
                    continue
                codes = [f"{s} {n}" for s, n in COURSE.findall(text)]
                if bold and text.lower().startswith("note"):
                    # "Note: ... AGEC 2073 - Principles of Agricultural Economics is required."
                    current.notes.append(re.sub(r"^note\s*:\s*", "", text, flags=re.I))
                    if codes:
                        current.courses.extend(codes)
                        problems.append(f"{label}: a note in {current.name} names {', '.join(codes)}; check where it counts")
                elif select := SELECT.match(text):
                    # "Select N hours from the following:" as a line inside a block.
                    if not current.courses and current.rule == "all":
                        current.rule, current.hours_required = "choose_hours", int(select[1])
                    else:
                        child = Group(name=text.rstrip(":"), rule="choose_hours", hours_required=int(select[1]))
                        (parent.children if parent else groups).append(child)
                        current = child
                    if select[2]:
                        current.notes.append(f"{select[1]}-{select[2]} hours.")
                elif codes:
                    current.courses.extend(codes)
                elif text.lower() == "or":
                    current.has_or = True
                elif ANY_CODE.search(text):
                    for code in ANY_CODE.findall(text):
                        try:
                            current.courses.append(normalize_course_code(code))
                        except ValueError:
                            pass
                    problems.append(f"{label}: unclear course line {text[:60]!r}")
                else:
                    current.notes.append(text)
            continue
        problems.append(f"{label}: unexpected <{node.name}>")

    for group in _walk(groups):
        if group.has_or:
            # "one of these course combinations: A and B, or C and D" -> pick hours from the list.
            group.rule = "choose_hours"
            hours = HOURS.search(group.name)
            group.hours_required = int(hours[1]) if hours else None
            # The intro line ("Select one of the following course combinations:") is replaced.
            group.notes = [n for n in group.notes if not n.endswith(":")]
            group.notes.append("One of these combinations: " + " or ".join(_pairs(group.courses)) + ".")
            problems.append(f"{label}: {group.name} is a choice of course combinations; loaded as choose hours")
        if group.rule == "choose_hours" and group.hours_required is None:
            problems.append(f"{label}: {group.name} has no hours")
    if not groups:
        problems.append(f"{label}: no requirement blocks")
    if total is None:
        problems.append(f"{label}: no total hours")
    return groups, total, problems


def _pairs(codes: list[str]) -> list[str]:
    """['A','B','C','D'] -> ['A + B', 'C + D'] for lecture/lab combinations."""
    if len(codes) % 2:
        return codes
    return [f"{codes[i]} + {codes[i + 1]}" for i in range(0, len(codes), 2)]


def _walk(groups: list[Group]):
    for group in groups:
        yield group
        yield from _walk(group.children)


# --- general education --------------------------------------------------------------------

def trim_gen_ed(html: str) -> str:
    """Keep only the curriculum part of the gen ed page (from its h2 to the notes)."""
    soup = BeautifulSoup(html, "html.parser")
    start = next((h for h in soup.find_all("h2") if "General Education Curriculum" in h.get_text()), None)
    if start is None:
        return "<!-- trimmed copy of www.saumag.edu/academics/general-education/: no curriculum found -->\n"
    parts = [str(start)] + [str(sibling) for sibling in start.find_next_siblings()]
    return "<!-- trimmed copy of www.saumag.edu/academics/general-education/ -->\n" + "\n".join(parts) + "\n"


def _hours(text: str) -> int | None:
    match = HOURS.search(text)
    return int(match[1]) if match else None


def parse_gen_ed(html: str) -> GenEd:
    """Areas (h3) -> blocks; "X choice (N hours), one of:" -> choose N children."""
    soup = BeautifulSoup(html, "html.parser")
    start = next((h for h in soup.find_all("h2") if "General Education Curriculum" in h.get_text()), None)
    areas: list[Group] = []
    notes: list[str] = []
    if start is None:
        return GenEd(areas, notes)
    area: Group | None = None
    target: Group | None = None
    in_notes = False
    for node in start.find_next_siblings():
        text = _clean(node.get_text(" "))
        if node.name == "h3":
            in_notes = text.lower() == "notes"
            if not in_notes:
                area = Group(name=text, hours=_hours(text))
                areas.append(area)
                target = None
            continue
        if in_notes:
            if node.name in ("ol", "ul"):
                notes.extend(_clean(li.get_text(" ")) for li in node.find_all("li"))
            continue
        if area is None:
            continue  # intro paragraphs
        if node.name == "p":
            choice = re.match(r"(.+?)\s*\((\d+) hours?\)\s*,?\s*(.*)", text)
            if node.find("strong") and choice:
                target = Group(name=choice[1], rule="choose_hours", hours_required=int(choice[2]),
                               hours=int(choice[2]))
                rest = choice[3].rstrip(":").strip()
                if rest and rest.lower() not in ("one of", "one of the following"):
                    target.notes.append(rest[0].upper() + rest[1:] + ".")
                area.children.append(target)
            elif text.lower().startswith("fulfilled by completing one of"):
                area.rule, area.hours_required = "choose_hours", area.hours
                target = area
            elif text.lower().startswith("fulfilled by completing"):
                target = area
        elif node.name in ("ul", "ol") and target is not None:
            for li in node.find_all("li"):
                item = _clean(li.get_text(" "))
                codes = []
                for subject, number, other in GEN_ED_CODE.findall(item):
                    codes.append(f"{subject} {number}")
                    if other:
                        codes.append(f"{subject} {other}")
                target.courses.extend(codes)
                if " and " in item and len(codes) == 2:
                    target.pairs.append(f"{codes[0]} + {codes[1]}")
    for group in _walk(areas):
        if group.pairs:
            intro = next((n for n in group.notes if n.lower().startswith("one lecture and lab")), "")
            see = re.search(r"\(see note \d+\)", intro)
            group.notes = [n for n in group.notes if n != intro]
            group.notes.append(
                "One lecture and lab combination" + (f" {see[0]}" if see else "") + ": "
                + ", ".join(group.pairs) + "."
            )
        if group.children and group.hours is None:
            group.hours = sum(child.hours or 0 for child in group.children)
    return GenEd(areas, notes)


# "3 hours of fine arts/humanities, 3 hours of mathematics, and 4 hours of physical science
# requirements are included in the major."
COVERED = re.compile(
    r"(\d+ hours? of .+?)\s+(?:general education\s+)?(?:requirements?\s+)?(?:are|is) included in the major",
    re.I,
)
COVERED_PART = re.compile(r"(\d+) hours? of (.+?)(?=,?\s*(?:and\s+)?\d+ hours? of|$)", re.I)
# Engineering pages list their own reduced areas: "English Composition (6 hours) Fine Arts/Humanities (6 hours)".
LISTED_AREA = re.compile(r"([A-Z][\w./]*(?: [A-Z][\w./]*)*) \((\d+) hours?\)")
AREA_ALIASES = {"english composition": "english", "natural science": "science", "math": "mathematics"}


def _area_key(name: str) -> str:
    key = re.sub(r"\s*\(.*", "", name).strip().lower()
    key = re.sub(r"\s+choice$", "", key)
    return AREA_ALIASES.get(key, key)


def _find_area(areas: list[Group], phrase: str) -> tuple[Group, Group | None] | None:
    """'physical science' -> (Science, Physical Science choice); 'mathematics' -> (Mathematics, None)."""
    key = _area_key(phrase)
    for area in areas:
        for child in area.children:
            if _area_key(child.name) == key:
                return area, child
    for area in areas:
        if _area_key(area.name) == key:
            return area, None
    return None


def _set_hours(group: Group, hours: int) -> None:
    """A choose group needs fewer hours for this program ("Fine Arts/Humanities choice" 6 -> 3)."""
    if group.rule == "choose_hours" and group.hours_required is not None:
        group.hours_required = max(group.hours_required - ((group.hours or 0) - hours), 0)
    group.hours = hours
    group.name = HOURS.sub(f"({hours} hours)", group.name)
    group.notes.append(f"{hours} hours for this program; the rest is covered by the major.")


def _reduce_area(area: Group, hours: int, prefer: Group | None, major_codes: set[str]) -> int:
    """Take `hours` out of an area the major partly covers. Children named in the note go
    first, then children whose courses the major already requires, then the last ones.
    Returns the hours that could not be taken out."""
    if not area.children:
        if hours >= (area.hours or 0):
            left = hours - (area.hours or 0)
            area.hours = 0
            return left
        _set_hours(area, (area.hours or 0) - hours)
        return 0
    order = [prefer] if prefer is not None else []
    order += [c for c in area.children if c not in order and set(c.courses) & major_codes]
    order += [c for c in reversed(area.children) if c not in order]
    left = hours
    for child in order:
        if left <= 0:
            break
        child_hours = child.hours or 0
        if child_hours <= left:
            area.children.remove(child)
            left -= child_hours
        else:
            _set_hours(child, child_hours - left)
            left = 0
    area.hours = sum(child.hours or 0 for child in area.children)
    area.name = HOURS.sub(f"({area.hours} hours)", area.name)
    return left


def _trim_gen_ed(areas: list[Group], note: str, major_codes: set[str]) -> list[str]:
    """Apply the program's gen ed note to a copy of the core. Returns problems."""
    note = note.replace("​", "")
    problems: list[str] = []
    listed = LISTED_AREA.findall(note)
    if len(listed) >= 2:
        # The page spells out its own areas: keep only those, at the listed hours.
        keep: dict[int, set[int] | None] = {}  # id(area) -> ids of kept children (None = whole area)
        wanted: list[tuple[Group, int]] = []
        for phrase, hours in listed:
            found = _find_area(areas, phrase)
            if found is None:
                problems.append(f"gen ed area {phrase!r} not matched to the gen ed core")
                continue
            area, child = found
            target = child or area
            if child is None:
                keep[id(area)] = None
            elif keep.get(id(area), set()) is not None:
                keep.setdefault(id(area), set()).add(id(child))
            wanted.append((target, int(hours)))
        kept_areas = []
        for area in areas:
            if id(area) not in keep:
                continue
            children = keep[id(area)]
            if children is not None:
                area.children = [c for c in area.children if id(c) in children]
                area.hours = sum(c.hours or 0 for c in area.children)
                area.name = HOURS.sub(f"({area.hours} hours)", area.name)
            kept_areas.append(area)
        for target, hours in wanted:
            if (target.hours or 0) > hours:
                if target.children:
                    _reduce_area(target, target.hours - hours, None, major_codes)
                else:
                    _set_hours(target, hours)
        for area in kept_areas:
            area.hours = sum(c.hours or 0 for c in area.children) if area.children else area.hours
            area.name = HOURS.sub(f"({area.hours} hours)", area.name)
        areas[:] = kept_areas
        return problems

    covered = COVERED.search(note)
    if covered is None:
        return problems
    core = copy.deepcopy(areas)  # to tell "already dropped" from "unknown"
    for hours, phrase in COVERED_PART.findall(covered[1]):
        names = [n for n in re.split(r",\s*(?:and\s+)?|\s+and\s+", phrase.strip()) if n]
        for name in names:
            found = _find_area(areas, name)
            if found is None:
                # "natural science and physical science": science is already gone.
                if _find_area(core, name) is None:
                    problems.append(f"gen ed note mentions {name!r}; not matched to the gen ed core")
                continue
            area, child = found
            if len(names) > 1:
                # "7 hours of mathematics and physical science": each one is covered whole.
                if child is None:
                    areas.remove(area)
                else:
                    _reduce_area(area, child.hours or 0, child, major_codes)
            else:
                _reduce_area(area, int(hours), child, major_codes)
            if area in areas and not area.children and not area.hours:
                areas.remove(area)
    return problems


def attach_gen_ed(groups: list[Group], gen_ed: GenEd | None) -> list[str]:
    """Copy the shared gen ed core under the program's "General Education (N hours)" block,
    minus what its note says the major already covers. Returns problems."""
    block = next((g for g in groups if g.name.lower().startswith("general education")), None)
    if block is None or gen_ed is None or not gen_ed.areas:
        return []
    major_codes = {code for g in _walk([g for g in groups if g is not block]) for code in g.courses}
    areas = copy.deepcopy(gen_ed.areas)
    problems = _trim_gen_ed(areas, block.note or "", major_codes)
    block.children = areas + block.children
    if gen_ed.notes:
        block.notes.append("Gen ed notes: " + " ".join(f"({i}) {n}" for i, n in enumerate(gen_ed.notes, 1)))

    expected = _hours(block.name)
    shown = sum(area.hours or 0 for area in areas)
    if expected is not None and shown != expected:
        problems.append(f"gen ed adds up to {shown} hours but the program says {expected}")
    return problems


def _loose(name: str) -> str:
    """'Communications Design Minor' and 'Communication Design Minor' compare equal."""
    return re.sub(r"s\b", "", name.lower())


def _minor_name(minor: Tag, program_name: str, names: dict[str, str]) -> tuple[str, str | None]:
    """The catalog name of a page's minor, tried in this order:
    - the section's own heading: "Finance Minor for Business Majors (15 hours)", "Minor in Music"
    - "Computer Science, BS" -> "Computer Science Minor"
    - after the colon: "Agricultural Science: Poultry Science" -> "Poultry Science Minor",
      "Performing Arts: Theatre - Acting Concentration" -> "Theatre Minor"
    - before the colon: "Chemistry: Science" -> "Chemistry Minor"
    The first one on the catalog list wins; otherwise the first candidate, unmatched."""
    candidates: list[str] = []
    headings = [HOURS.sub("", _clean(h.get_text(" "))).strip() for h in minor.find_all(["h2", "h3", "h4"])]
    text = next((t for t in headings if t.lower() != "minor requirements"), None)
    if text is not None:
        music = re.fullmatch(r"Minor in (.+)", text, re.I)
        if music:
            candidates.append(f"{music[1]} Minor")
        elif "minor" in text.lower() and text.lower() != "minor requirements":
            candidates.append(text)
    base = re.sub(r",\s*[A-Z][A-Za-z+]*$", "", program_name)
    base = re.sub(r"\s+Certificate$", "", base)
    tail = base.split(":")[-1].strip()
    candidates += [
        f"{base} Minor",
        f"{tail} Minor",
        f"{tail.split(' - ')[0].strip()} Minor",
        f"{base.split(':')[0].strip()} Minor",
    ]
    by_name = {_loose(n): (n, p) for p, n in names.items()}
    for candidate in candidates:
        if _loose(candidate) in by_name:
            return by_name[_loose(candidate)]
    return candidates[0], None


def parse_program_page(
    html: str, slug: str, names: dict[str, str] | None = None, gen_ed: GenEd | None = None
) -> PageResult:
    names = names or {}
    settings = get_settings()
    soup = BeautifulSoup(html, "html.parser")
    result = PageResult(slug)

    plan_link = soup.find("a", class_="prog-facts-plan-link")
    match = POID.search(plan_link.get("href", "")) if plan_link else None
    if not match:
        result.skipped = "no catalog Degree Plan link"
        return result
    if match[1] != str(settings.catalog_catoid):
        result.skipped = f"links to another catalog (catoid {match[1]})"
        return result
    poid = match[2]
    year = re.search(r"\d{4}-\d{4}", plan_link.get_text())
    catalog_year = year[0] if year else ""

    title_tag = soup.find("meta", property="og:title")
    page_title = _clean(title_tag["content"].split("|")[0]) if title_tag else slug
    name = names.get(poid, page_title)

    curriculum = soup.find(id="prog-curriculum")
    if curriculum is None:
        result.skipped = "no Curriculum section"
        return result
    groups, total, problems = parse_curriculum(curriculum, "curriculum")
    problems.extend(attach_gen_ed(groups, gen_ed))
    if not catalog_year:
        problems.append("no catalog year on the Degree Plan link")
    if poid not in names:
        problems.append(f"poid {poid} not on the saved catalog list; named from the page title")
    result.programs.append(Program(slug, name, catalog_year, total, groups, poid, problems))

    minor = soup.find(id="prog-minor")
    if minor is not None:
        minor_name, minor_poid = _minor_name(minor, name, names)
        minor_groups, minor_total, minor_problems = parse_curriculum(minor, "minor")
        if minor_poid is None:
            minor_problems.append(f"minor name {minor_name!r} not on the saved catalog list")
        result.programs.append(
            Program(slug, minor_name, catalog_year, minor_total, minor_groups, minor_poid, minor_problems)
        )
    return result


# --- load ---------------------------------------------------------------------------------

def _insert_groups(session, plan_id, groups: list[Group], parent_id=None) -> None:
    for order, group in enumerate(groups):
        row = RequirementGroup(
            degree_plan_id=plan_id,
            parent_id=parent_id,
            name=group.name,
            rule=group.rule,
            hours_required=group.hours_required,
            sort_order=order,
            note=group.note,
        )
        session.add(row)
        session.flush()
        for code in dict.fromkeys(group.courses):  # a course once per group
            session.add(RequirementCourse(group_id=row.id, course_code=code))
        _insert_groups(session, plan_id, group.children, row.id)


def load_program(program: Program, source_url: str, scraped_at: datetime) -> None:
    """Upsert the plan by (name, catalog_year) and replace its requirement tree.

    The plan row keeps its id, so students pointing at it are not affected.
    """
    with SessionLocal.begin() as session:
        statement = insert(DegreePlan).values(
            name=program.name,
            catalog_year=program.catalog_year,
            total_hours=program.total_hours or 0,
            source_url=source_url,
            scraped_at=scraped_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[DegreePlan.name, DegreePlan.catalog_year],
            set_={
                "total_hours": statement.excluded.total_hours,
                "source_url": statement.excluded.source_url,
                "scraped_at": statement.excluded.scraped_at,
            },
        ).returning(DegreePlan.id)
        plan_id = session.scalar(statement)
        session.execute(delete(RequirementGroup).where(RequirementGroup.degree_plan_id == plan_id))
        _insert_groups(session, plan_id, program.groups)


def write_needs_review(results: list[PageResult]) -> int:
    rows = []
    for result in results:
        if result.skipped:
            rows.append([result.slug, "", f"skipped: {result.skipped}"])
        for program in result.programs:
            if program.problems:
                rows.append([result.slug, program.name, "; ".join(program.problems)])
    with open(NEEDS_REVIEW_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["slug", "name", "problems"])
        writer.writerows(rows)
    return sum(1 for r in results for p in r.programs if p.problems)


# --- run ----------------------------------------------------------------------------------

def refresh_degree_maps(
    *,
    offline: bool = False,
    only: list[str] | None = None,
    limit: int | None = None,
    client: PoliteClient | None = None,
    log_line: Callable[[str], None] = log.info,
) -> int:
    """Fetch (or, offline, re-read) program pages, parse and load them.

    Returns the number of plans loaded. A full run writes the needs-review file.
    """
    settings = get_settings()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    own_client = client is None and not offline
    if not offline:
        client = client or PoliteClient(
            base_url=settings.saumag_base_url, min_delay=settings.degree_maps_delay_seconds
        )
    try:
        if offline:
            sitemap = SITEMAP_FILE.read_text(encoding="utf-8") if SITEMAP_FILE.exists() else ""
            slugs = program_slugs(sitemap) or sorted(
                p.stem for p in RAW_DIR.glob("*.html") if p.name not in (LIST_PAGE.name, GEN_ED_FILE.name)
            )
            gen_ed_html = GEN_ED_FILE.read_text(encoding="utf-8") if GEN_ED_FILE.exists() else ""
        else:
            sitemap = client.get(SITEMAP_PATH)
            SITEMAP_FILE.write_text(sitemap, encoding="utf-8")
            slugs = program_slugs(sitemap)
            gen_ed_html = trim_gen_ed(client.get(GEN_ED_PATH))
            GEN_ED_FILE.write_text(gen_ed_html, encoding="utf-8")
        gen_ed = parse_gen_ed(gen_ed_html)
        log_line(
            f"general education core: {len(gen_ed.areas)} areas, "
            f"{sum(a.hours or 0 for a in gen_ed.areas)} hours"
            if gen_ed.areas else "general education page not parsed; plans keep a gen ed note only"
        )
        if only:
            slugs = [slug for slug in slugs if slug in only] or list(only)
        if limit is not None:
            slugs = slugs[:limit]
        names = catalog_names()
        if not names:
            log_line("note: data/raw/degree_maps/programs_list.html missing; names come from page titles")
        log_line(f"{len(slugs)} program pages to {'re-parse' if offline else 'fetch'}")

        results: list[PageResult] = []
        loaded = 0
        for count, slug in enumerate(slugs, start=1):
            path = raw_page_file(slug)
            if offline:
                if not path.exists():
                    log_line(f"  {count}/{len(slugs)} {slug}: no saved page, skipped")
                    continue
                html = path.read_text(encoding="utf-8")
                scraped_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            else:
                html = trim_page(client.get(f"{PROGRAM_PREFIX}{slug}/"))
                path.write_text(html, encoding="utf-8")
                scraped_at = datetime.now(UTC)
            result = parse_program_page(html, slug, names, gen_ed)
            results.append(result)
            if result.skipped:
                log_line(f"  {count}/{len(slugs)} {slug}: skipped ({result.skipped})")
                continue
            for program in result.programs:
                load_program(program, page_url(slug), scraped_at)
                loaded += 1
                flag = f"  [review: {len(program.problems)}]" if program.problems else ""
                log_line(f"  {count}/{len(slugs)} {program.name}{flag}")
    finally:
        if own_client:
            client.close()

    if not only and limit is None:
        flagged = write_needs_review(results)
        skipped = sum(1 for r in results if r.skipped)
        log_line(f"{loaded} plans loaded, {flagged} need review, {skipped} pages skipped")
    return loaded


def plan_tree(name: str, catalog_year: str) -> list[dict]:
    """A loaded plan's requirement tree, for printing and checks."""
    with SessionLocal() as session:
        plan_id = session.scalar(
            select(DegreePlan.id).where(DegreePlan.name == name, DegreePlan.catalog_year == catalog_year)
        )
        if plan_id is None:
            return []
        groups = session.scalars(
            select(RequirementGroup)
            .where(RequirementGroup.degree_plan_id == plan_id)
            .order_by(RequirementGroup.sort_order)
        ).all()
        courses: dict = {}
        for group_id, code in session.execute(
            select(RequirementCourse.group_id, RequirementCourse.course_code).where(
                RequirementCourse.group_id.in_([g.id for g in groups])
            )
        ):
            courses.setdefault(group_id, []).append(code)

    def build(parent_id):
        return [
            {
                "name": g.name, "rule": g.rule, "hours_required": g.hours_required, "note": g.note,
                "courses": sorted(courses.get(g.id, [])), "children": build(g.id),
            }
            for g in groups
            if g.parent_id == parent_id
        ]

    return build(None)
