"""Load a course schedule export (SAU's Course Schedule CSV) into terms, courses and sections.

Run from backend/:  uv run python ..\\db\\scripts\\import_sections.py [path-to-csv]

The same importer runs when a student connects mySAU (backend/app/mysau/sections_import.py),
so a file loaded by hand and a live export are treated the same way.

Re-running updates rows instead of duplicating them:
- terms are matched on code, courses on code, sections on (course, term, section number).
- courses already in the catalog only get department and credits filled in. A course
  that is not in the catalog gets a minimal row (code, title, department, credits).
- a section of the file's term that is missing from the file is set inactive, never
  deleted (saved schedules point at it). The file's term becomes the current
  registration term.

Rules (decided Nov 16):
- The "concurrent" column is ignored.
- Sections whose title starts with CANCELED are printed and skipped.
- The sections table holds one meeting time per section. When the export lists a section
  on several rows (several meeting times), the row with the most meeting days is loaded
  and the other rows are printed as "extra meeting time, not loaded".
- Bad rows are printed and skipped, never guessed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import REPO_DIR  # noqa: E402
from app.mysau.sections_import import ExportNotUnderstood, import_export_bytes  # noqa: E402

DEFAULT_PATH = REPO_DIR / "data" / "sections_spring_2027.csv"


def print_report(result, source: str) -> None:
    parsed = result.parsed
    loaded = len(parsed.sections)
    no_time = sum(1 for row in parsed.sections if row["start_time"] is None)
    print(f"File: {source}")
    print(f"Rows read:                        {parsed.rows_read}")
    print(f"Terms:                            {', '.join(f'{name} ({code})' for code, name in parsed.terms.items())}")
    print(f"Sections loaded:                  {loaded}  ({result.new_sections} new, {loaded - result.new_sections} updated)")
    print(f"  with a meeting time:            {loaded - no_time}")
    print(f"  online or TBA (no time):        {no_time}")
    print(f"Sections missing from the file, set inactive: {result.deactivated}")
    print(f"Courses offered this term:        {len(parsed.courses)}")
    print(f"  already in the courses table:   {len(parsed.courses) - len(result.new_course_codes)}  (department and credits filled in)")
    print(f"  not in the courses table, minimal row created now (no description): {len(result.new_course_codes)}")
    if result.new_course_codes:
        print(f"    {', '.join(result.new_course_codes)}")
    if parsed.credit_conflicts:
        print(f"Courses whose sections disagree on credits (credits left blank): {sorted(parsed.credit_conflicts)}")
    print(f"Sections in the table now:        {result.sections_total}")
    print(f"Extra meeting rows, not loaded:   {len(parsed.extra_meetings)}")
    for message in parsed.extra_meetings:
        print(f"  {message}")
    print(f"Canceled sections, skipped:       {len(parsed.canceled)}")
    for message in parsed.canceled:
        print(f"  {message}")
    print(f"Rejected rows:                    {len(parsed.rejected)}")
    for message in parsed.rejected:
        print(f"  {message}")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    try:
        result = import_export_bytes(path.read_bytes())
    except ExportNotUnderstood as error:
        sys.exit(f"{path.name}: {error}")
    print_report(result, str(path))


if __name__ == "__main__":
    main()
