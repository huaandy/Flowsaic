"""Course descriptions: a slow, rolling crawl of the public course detail pages.

Run by db/scripts/scrape_course_info.py and by the public data refresh.

Why rolling: robots.txt asks for 120 seconds between requests, so all ~1,900 course pages
take about 63 hours. Each run fetches the pages not fetched in the last
PUBLIC_REFRESH_MAX_AGE_DAYS days (never-fetched first, then oldest), and saves progress as
it goes, so a run cut off by a restart picks up where it stopped.

Which pages: the course list page sits behind bot protection, so course IDs (coid) come
from the courses already in the raw file. A course added to the catalog later is not
found by this crawl.

Files (all under data/):
- raw/sau_catalog_2026_27_raw.json: [coid, "CODE NUM - Title", body] per course, the same
  format as the Nov 16 scrape, so data/raw/build_course_info.py still rebuilds offline.
  The file name is from that scrape; it holds the catalog in settings.catalog_catoid.
- raw/course_pages_fetched.json: {coid: ISO time the page was last fetched}.
- course_info.csv and course_info_needs_review.csv: rebuilt from the raw file, with
  course_prereq_overrides.csv (reviewed hand fixes) applied last.

At each checkpoint (every CHECKPOINT_PAGES pages, and at the end) the CSVs are rebuilt;
if any course row changed, the CSV is loaded and only the changed courses are re-embedded.
"""

import csv
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

from app.catalog.course_build import apply_overrides, build_rows, load_overrides, write_csvs
from app.catalog.http import PoliteClient
from app.config import REPO_DIR, get_settings

log = logging.getLogger("flowsaic.catalog.courses")

DATA_DIR = REPO_DIR / "data"
RAW_PATH = DATA_DIR / "raw" / "sau_catalog_2026_27_raw.json"
FETCHED_PATH = DATA_DIR / "raw" / "course_pages_fetched.json"
COURSE_INFO_PATH = DATA_DIR / "course_info.csv"
NEEDS_REVIEW_PATH = DATA_DIR / "course_info_needs_review.csv"
# Reviewed hand fixes, applied after every rebuild so they are never lost (Nov 20).
OVERRIDES_PATH = DATA_DIR / "course_prereq_overrides.csv"
CHECKPOINT_PAGES = 30  # about an hour of crawling at 120 s a page
# The raw file was scraped on Nov 16; treat its pages as fetched then, so the first
# rolling pass starts a week later instead of re-fetching everything at once.
RAW_SCRAPED_AT = "2026-11-16T00:00:00+00:00"


def course_path(coid: str) -> str:
    return f"/preview_course_nopop.php?catoid={get_settings().catalog_catoid}&coid={coid}"


def _text(node) -> str:
    return str(node).replace("\xa0", " ")


def parse_course_page(html: str) -> tuple[str, str] | None:
    """Return (title_line, body) from a course page, or None when the page has no course.

    title_line is "CODE NUM - Title"; body has one block per line, the same as the raw file:
    "Prerequisites: ...", "Corequisites: ...", the description, "ACTS Course Equivalent: ...".
    """
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(id="course_preview_title")
    if heading is None:
        return None  # broken coid: SAU redirects to an unrelated page
    title_line = " ".join(_text(heading.get_text()).split())

    lines: list[str] = []
    current: list[str] = []
    seen_rule = False
    for node in heading.next_siblings:
        if isinstance(node, Tag):
            if node.name == "hr":
                if seen_rule:
                    break  # the rule after the course text
                seen_rule = True
                continue
            if node.name in ("div", "table", "h1", "h2", "h3"):
                break
            if node.name == "br":
                lines.append("".join(current))
                current = []
                continue
            if "display: none" in (node.get("style") or "").replace("display:none", "display: none"):
                continue  # hidden spacer spans after course links
            current.append(_text(node.get_text()))
        elif isinstance(node, NavigableString):
            current.append(_text(node))
    lines.append("".join(current))
    body = "\n".join(" ".join(line.split()) for line in lines if line.strip())
    return title_line, body


def load_raw() -> list[list[str]]:
    return json.loads(RAW_PATH.read_text(encoding="utf-8")) if RAW_PATH.exists() else []


def save_raw(raw: list[list[str]]) -> None:
    RAW_PATH.write_text(json.dumps(raw), encoding="utf-8")  # same layout as the Nov 16 file


def load_fetched(raw: list[list[str]]) -> dict[str, str]:
    if FETCHED_PATH.exists():
        return json.loads(FETCHED_PATH.read_text(encoding="utf-8"))
    return {coid: RAW_SCRAPED_AT for coid, _title, _body in raw}


def save_fetched(fetched: dict[str, str]) -> None:
    FETCHED_PATH.write_text(json.dumps(fetched, indent=0, sort_keys=True) + "\n", encoding="utf-8")


def stale_coids(coids: list[str], fetched: dict[str, str], now: datetime, max_age: timedelta) -> list[str]:
    """Never-fetched first, then oldest first."""
    cutoff = now - max_age
    stale = [c for c in coids if c not in fetched or datetime.fromisoformat(fetched[c]) < cutoff]
    return sorted(stale, key=lambda c: (c in fetched, fetched.get(c, "")))


def built_rows(raw: list[list[str]], log_line: Callable[[str], None] = log.info) -> list[dict]:
    """The rows of course_info.csv: the parser's, then the reviewed overrides on top."""
    overrides, problems = load_overrides(OVERRIDES_PATH)
    rows, unknown = apply_overrides(build_rows(raw), overrides)
    for problem in problems + unknown:
        log_line(f"override not applied: {problem}")
    return rows


def _rows_by_code(raw: list[list[str]], log_line: Callable[[str], None] = log.info) -> dict[str, dict]:
    return {row["code"]: row for row in built_rows(raw, log_line)}


def _csv_rows() -> dict[str, dict]:
    """What course_info.csv says now. Comparing against it (not the raw file) means pages
    fetched by a run that stopped early still get loaded by the next run."""
    if not COURSE_INFO_PATH.exists():
        return {}
    with open(COURSE_INFO_PATH, newline="", encoding="utf-8") as file:
        return {row["code"]: row for row in csv.DictReader(file)}


def _apply_changes(raw, previous_rows, log_line, load_and_embed: bool, always_load: bool = False) -> tuple[int, dict]:
    """Rebuild the CSVs. If course rows changed (or always_load), load them and embed what
    isn't embedded yet. always_load is for the end of a run: a fresh database (a teammate's
    first setup) has an up-to-date CSV but no courses, so "nothing changed" isn't enough
    (fixed Nov 18). Loading is an upsert and embedding skips unchanged text, so it's cheap."""
    rows = _rows_by_code(raw, log_line)
    changed = sum(1 for code, row in rows.items() if previous_rows.get(code) != row)
    if not changed and not always_load:
        return 0, rows
    if changed:
        write_csvs(list(rows.values()), COURSE_INFO_PATH, NEEDS_REVIEW_PATH)
    if load_and_embed:
        from app.course_embed import embed_changed_courses
        from app.course_load import load_course_info_csv

        loaded = load_course_info_csv(COURSE_INFO_PATH)
        log_line(f"loaded {loaded.courses} courses ({changed} changed rows)")
        if get_settings().gemini_api_key:
            embedded = embed_changed_courses()
            log_line(f"re-embedded {embedded.embedded} courses" + (f"; {embedded.stopped}" if embedded.stopped else ""))
        else:
            log_line("GEMINI_API_KEY not set: changed courses not re-embedded")
    return changed, rows


def refresh_course_info(
    *,
    limit: int | None = None,
    client: PoliteClient | None = None,
    load_and_embed: bool = True,
    log_line: Callable[[str], None] = log.info,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Fetch stale course pages. Returns how many course_info.csv rows changed.

    With course_info_crawl off (the default) and no explicit limit, nothing is fetched:
    the CSVs are rebuilt from the saved raw file, loaded, and changed text re-embedded.
    """
    if limit is None and not get_settings().course_info_crawl:
        limit = 0
    raw = load_raw()
    by_coid = {entry[0]: entry for entry in raw}
    fetched = load_fetched(raw)
    coids = list(by_coid)
    max_age = timedelta(days=get_settings().public_refresh_max_age_days)
    todo = stale_coids(coids, fetched, now(), max_age)
    if limit is not None:
        todo = todo[:limit]
    log_line(f"{len(coids)} course pages known, {len(todo)} to fetch this run")

    rows = _csv_rows()
    changed = 0
    own_client = client is None
    client = client or PoliteClient()
    try:
        for count, coid in enumerate(todo, start=1):
            parsed = parse_course_page(client.get(course_path(coid)))
            if parsed is not None:
                title_line, body = parsed
                if coid in by_coid:
                    by_coid[coid][1:] = [title_line, body]
                else:
                    by_coid[coid] = [coid, title_line, body]
                    raw.append(by_coid[coid])
            fetched[coid] = now().isoformat(timespec="seconds")
            if count % CHECKPOINT_PAGES == 0:
                save_raw(raw)
                save_fetched(fetched)
                step, rows = _apply_changes(raw, rows, log_line, load_and_embed)
                changed += step
                log_line(f"checkpoint: {count} / {len(todo)} pages")
    finally:
        # Save whatever was fetched, even when the run stops early.
        save_raw(raw)
        save_fetched(fetched)
        if own_client:
            client.close()
    step, rows = _apply_changes(raw, rows, log_line, load_and_embed, always_load=True)
    return changed + step
