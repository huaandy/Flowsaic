"""Turn raw catalog course entries into data/course_info.csv rows.

The one copy of the rules: db/scripts/scrape_course_info.py (live or offline) and
data/raw/build_course_info.py (offline) both call it, and a test checks the committed CSV
against it.
- prereqs: ';' = all required, '|' = any one of these, '+' = these together (one option).
- "A and B or C and D" where every side is one course or a lecture+lab pair (same subject,
  same first three digits: PHYS 2103 / PHYS 2101), and at least one side is a pair, becomes
  alternative sets: 'A+B|C+D' (Nov 20). Any other and/or mix is read as before, so
  "ETEC 3003 or ENGR 3003 and ETEC 3013 or ENGR 3023" stays two OR groups.
- Prereqs too complex to parse are left blank and flagged needs_review, so the schedule
  checker never blocks wrongly.
- data/course_prereq_overrides.csv is applied last (apply_overrides): a person's reviewed fix
  wins over the parser and survives every rebuild. An overridden row's needs_review is
  cleared, because a person has read it. A row without reviewed_by is never applied.

A raw entry is [coid, "CODE NUM - Title", body]. body is the course text with one block
per line ("Prerequisites: ...", "Corequisites: ...", description, "ACTS Course Equivalent: ...")
or "" when SAU's detail page is broken.
"""

import csv
import re
from pathlib import Path

from app.normalize import normalize_course_code, parse_prereq_sets

COLUMNS = [
    "code", "title", "description", "prereqs", "other_requirements",
    "prereq_text", "coreqs", "coreq_text", "needs_review",
]
REVIEW_COLUMNS = ["code", "title", "prereq_text", "prereqs", "needs_review"]
OVERRIDE_COLUMNS = ["code", "prereqs", "other_requirements", "reviewed_by", "note"]

SUBJECT = r"[A-Z]{1,4}(?: [A-Z]{1,3})?"
CODE = re.compile(rf"\b({SUBJECT}) ?(\d{{4,5}}[A-Z]?)\b")
SLASH_PAIR = re.compile(rf"\b({SUBJECT}) ?(\d{{4,5}}[A-Z]?)\s*/\s*(\d{{4,5}}[A-Z]?)\b")
TITLE = re.compile(r"^(.+?)\s+(\d{4,5}[A-Z]?)\s+-\s+(.+)$")
BLANKED = ("and/or mix", "complex wording", "mixed or + lecture/lab pair")

# One side of an alternative: a course, or two joined by 'and' or '/'.
_ONE = rf"\b(?:{SUBJECT}) ?\d{{4,5}}[A-Z]?\b"
_SIDE = rf"{_ONE}(?:\s*(?:\band\b|/)\s*{_ONE})?"
_OR = r"\s*,?\s+or\s+"
PAIR_SEGMENT = re.compile(rf"(?:\beither\s+)?{_SIDE}(?:{_OR}{_SIDE})+")
PLACEHOLDER = re.compile(r"\x00(\d+)\x00")


def codes(text: str) -> list[str]:
    return [f"{subject} {number}" for subject, number in CODE.findall(text)]


def expand_slash(text: str) -> str:
    """'BIOL 2063 /2061' -> 'BIOL 2063 / BIOL 2061'."""
    return SLASH_PAIR.sub(r"\1 \2 / \1 \3", text)


def clean(text: str) -> str:
    return re.sub(r"\s+([.,;])", r"\1", re.sub(r"\s+", " ", text)).strip()


def is_lecture_lab_pair(a: str, b: str) -> bool:
    """PHYS 2103 / PHYS 2101, AGED 2001 / AGED 2002: same subject, same first three digits."""
    subject_a, number_a = a.rsplit(" ", 1)
    subject_b, number_b = b.rsplit(" ", 1)
    return (a != b and subject_a == subject_b and len(number_a) == len(number_b)
            and number_a[:3] == number_b[:3])


def pair_alternatives(segment: str) -> str | None:
    """'CHEM 1013 and CHEM 1011 or CHEM 1023 and CHEM 1021' -> 'CHEM 1013+CHEM 1011|CHEM 1023+CHEM 1021'.

    Only when every side is one course or a lecture+lab pair and at least one side is a
    pair. Anything else -> None, and the text is read the old way."""
    sides = re.split(_OR, re.sub(r"^either\s+", "", segment.strip(), flags=re.I))
    options: list[str] = []
    for side in sides:
        found = codes(side)
        if len(found) not in (1, 2) or (len(found) == 2 and not is_lecture_lab_pair(*found)):
            return None
        options.append("+".join(found))
    if not any("+" in option for option in options):
        return None
    return "|".join(dict.fromkeys(options))


def mark_pair_alternatives(text: str) -> tuple[str, list[str], list[str]]:
    """Replace each pair-alternatives segment with a placeholder. Returns (text, the prereq
    value of each placeholder, the original wording of each)."""
    values: list[str] = []
    wording: list[str] = []

    def replace(match: re.Match) -> str:
        value = pair_alternatives(match[0])
        if value is None:
            return match[0]
        values.append(value)
        wording.append(match[0].strip())
        return f"\x00{len(values) - 1}\x00"

    return PAIR_SEGMENT.sub(replace, text), values, wording


def parse_prereq_text(text: str) -> tuple[list[str], list[str], list[str]]:
    """Return (groups, other, review). groups are AND items: 'A', 'A|B' (any one) or
    'A+B|C+D' (one of these sets)."""
    t = expand_slash(text)
    t = re.sub(r"\bor (higher|better|above)\b", "", t, flags=re.I)
    t = re.sub(r"\b(conditional|unconditional) or (conditional|unconditional)\b", "\\1", t, flags=re.I)
    t = t.rstrip(".")
    t, pair_values, pair_wording = mark_pair_alternatives(t)
    groups: list[str] = []
    other: list[str] = []
    review: list[str] = []
    clauses = [c.strip() for c in re.split(r";|,|\band\b", t) if c.strip()]
    for clause in clauses:
        marked = PLACEHOLDER.search(clause)
        if marked:
            groups.append(pair_values[int(marked[1])])
            rest = PLACEHOLDER.sub("", clause)
            if codes(rest) or PLACEHOLDER.search(rest):
                review.append("complex wording")
            elif re.search(r"\bor\b", rest) and re.sub(r"\bor\b|[^A-Za-z]", "", rest):
                # "<pairs> or permission of the department chair": keep the non-course part.
                review.append("course OR non-course alternative")
                other.append(clause[marked.end():].strip(" ,"))
            continue
        found = codes(clause)
        has_or = bool(re.search(r"\bor\b", clause))
        if not found:
            other.append(clause)
            continue
        if "/" in clause and has_or:
            review.append("mixed or + lecture/lab pair")
            groups.append("|".join(found))
            continue
        if "/" in clause:
            groups.extend(found)
            continue
        if has_or:
            rest = CODE.sub("", clause)
            rest = re.sub(r"\b(or|in|a|of|grade|minimum|[A-D])\b|[^A-Za-z]", "", rest, flags=re.I)
            if rest:
                review.append("course OR non-course alternative")
                other.append(clause)
            groups.append("|".join(found))
            continue
        if len(found) > 1:
            groups.extend(found)
        else:
            groups.append(found[0])
        rest = re.sub(
            r"\b(grade|of|minimum|in|a|an|with|C|B|D)\b|[^A-Za-z]", "", CODE.sub("", clause), flags=re.I
        )
        if rest:
            other.append(clause)
    # Judge the wording without the pair segments, which are fully understood. With no
    # segments, plain is the same text the pre-Nov 20 rules looked at.
    plain = PLACEHOLDER.sub("", t)
    if re.search(r"\(|\beither\b", plain, re.I):
        review.append("complex wording")
    if re.search(r"\bor\b", plain) and re.search(r"\band\b", plain) and not any("|" in g for g in groups):
        review.append("and/or mix")
    return list(dict.fromkeys(groups)), other, list(dict.fromkeys(review))


def build_row(title_line: str, body: str | None) -> dict[str, str]:
    """One raw entry -> one course_info.csv row. Raises ValueError on an unreadable title."""
    match = TITLE.match(title_line.strip())
    if not match:
        raise ValueError(f"unreadable course title {title_line!r}")
    code = f"{re.sub(r'\s+', ' ', match[1])} {match[2]}"
    title = match[3].strip()
    prereq = coreq = ""
    description: list[str] = []
    for line in (body or "").split("\n"):
        line = line.strip()
        if line.startswith("Prerequisites:"):
            prereq = line[14:]
        elif line.startswith("Corequisites:"):
            coreq = line[13:]
        elif line.startswith("ACTS Course Equivalent:") or not line:
            continue
        else:
            description.append(line)
    prereq, coreq, desc = clean(prereq), clean(coreq), clean(" ".join(description))
    groups, other, review = parse_prereq_text(prereq) if prereq else ([], [], [])
    if any(reason in review for reason in BLANKED):
        groups = []
        review.append("prereqs left blank so the checker does not block wrongly; enter by hand")
    if not body:
        review.insert(0, "SAU detail page is broken, no description")
    coreq_groups = parse_prereq_text(coreq)[0] if coreq else []
    return {
        "code": code,
        "title": title,
        "description": desc,
        "prereqs": ";".join(groups),
        "other_requirements": "; ".join(other),
        "prereq_text": prereq,
        "coreqs": ";".join(coreq_groups),
        "coreq_text": coreq,
        "needs_review": "; ".join(review),
    }


# --- hand fixes ------------------------------------------------------------------------------

def load_overrides(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """data/course_prereq_overrides.csv -> ({code: row}, problems). A row is skipped (and
    named in problems) when it has no reviewed_by, a bad code or prereqs the loader can't read,
    or repeats a code. A missing file means no overrides."""
    if not path.exists():
        return {}, []
    overrides: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        missing = [c for c in OVERRIDE_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return {}, [f"{path.name} is missing columns: {', '.join(missing)}"]
        for line, row in enumerate(reader, start=2):
            row = {key: (row.get(key) or "").strip() for key in OVERRIDE_COLUMNS}
            try:
                code = normalize_course_code(row["code"])
                if not row["reviewed_by"]:
                    raise ValueError("no reviewed_by (only reviewed rows are applied)")
                parse_prereq_sets(row["prereqs"])
                if code in overrides:
                    raise ValueError("code listed twice")
            except ValueError as error:
                problems.append(f"line {line}: {row['code'] or '(blank)'} - {error}")
                continue
            overrides[code] = {**row, "code": code}
    return overrides, problems


def apply_overrides(rows: list[dict[str, str]], overrides: dict[str, dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    """Replace prereqs and other_requirements of the overridden courses (as written, blank
    included) and clear their needs_review. Returns (rows, codes not in the catalog)."""
    known = {row["code"] for row in rows}
    problems = [f"{code} - not in the catalog" for code in overrides if code not in known]
    result = []
    for row in rows:
        fix = overrides.get(row["code"])
        if fix is not None:
            row = {**row, "prereqs": fix["prereqs"], "other_requirements": fix["other_requirements"],
                   "needs_review": ""}
        result.append(row)
    return result, problems


def build_rows(raw: list[list[str]], overrides: dict[str, dict[str, str]] | None = None) -> list[dict[str, str]]:
    rows = [build_row(title_line, body) for _coid, title_line, body in raw]
    return apply_overrides(rows, overrides)[0] if overrides else rows


def write_csvs(rows: list[dict[str, str]], course_info: Path, needs_review: Path) -> None:
    """Write both files exactly as build_course_info.py does (UTF-8, CRLF, same columns)."""
    with open(course_info, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(needs_review, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for row in rows:
            if row["needs_review"]:
                writer.writerow({key: row[key] for key in REVIEW_COLUMNS})
