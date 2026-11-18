"""Turn raw catalog course entries into data/course_info.csv rows.

A port of data/raw/build_course_info.py with the same rules, so a live scrape and the
offline rebuild give the same file (a test checks this against the committed CSV):
- prereqs: ';' = all required, '|' = any one of these.
- Prereqs too complex to parse are left blank and flagged needs_review, so the schedule
  checker never blocks wrongly.

A raw entry is [coid, "CODE NUM - Title", body]. body is the course text with one block
per line ("Prerequisites: ...", "Corequisites: ...", description, "ACTS Course Equivalent: ...")
or "" when SAU's detail page is broken.
"""

import csv
import re
from pathlib import Path

COLUMNS = [
    "code", "title", "description", "prereqs", "other_requirements",
    "prereq_text", "coreqs", "coreq_text", "needs_review",
]
REVIEW_COLUMNS = ["code", "title", "prereq_text", "prereqs", "needs_review"]

SUBJECT = r"[A-Z]{1,4}(?: [A-Z]{1,3})?"
CODE = re.compile(rf"\b({SUBJECT}) ?(\d{{4,5}}[A-Z]?)\b")
SLASH_PAIR = re.compile(rf"\b({SUBJECT}) ?(\d{{4,5}}[A-Z]?)\s*/\s*(\d{{4,5}}[A-Z]?)\b")
TITLE = re.compile(r"^(.+?)\s+(\d{4,5}[A-Z]?)\s+-\s+(.+)$")
BLANKED = ("and/or mix", "complex wording", "mixed or + lecture/lab pair")


def codes(text: str) -> list[str]:
    return [f"{subject} {number}" for subject, number in CODE.findall(text)]


def expand_slash(text: str) -> str:
    """'BIOL 2063 /2061' -> 'BIOL 2063 / BIOL 2061'."""
    return SLASH_PAIR.sub(r"\1 \2 / \1 \3", text)


def clean(text: str) -> str:
    return re.sub(r"\s+([.,;])", r"\1", re.sub(r"\s+", " ", text)).strip()


def parse_prereq_text(text: str) -> tuple[list[str], list[str], list[str]]:
    """Return (groups, other, review). groups are AND items, each 'A' or 'A|B' (any one)."""
    t = expand_slash(text)
    t = re.sub(r"\bor (higher|better|above)\b", "", t, flags=re.I)
    t = re.sub(r"\b(conditional|unconditional) or (conditional|unconditional)\b", "\\1", t, flags=re.I)
    t = t.rstrip(".")
    groups: list[str] = []
    other: list[str] = []
    review: list[str] = []
    clauses = [c.strip() for c in re.split(r";|,|\band\b", t) if c.strip()]
    for clause in clauses:
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
    if re.search(r"\(|\beither\b", text, re.I):
        review.append("complex wording")
    if re.search(r"\bor\b", t) and re.search(r"\band\b", t) and not any("|" in g for g in groups):
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


def build_rows(raw: list[list[str]]) -> list[dict[str, str]]:
    return [build_row(title_line, body) for _coid, title_line, body in raw]


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
